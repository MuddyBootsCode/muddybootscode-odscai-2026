"""Change signals: does an edit to a governed file touch what the ontology
describes, or only pass through it?

Two tiers. *Touched*: a governed glob matched, nothing more; advisory only.
*Affecting*: a signal fired, so the ontology has to move with the change:

- declaration — a non-comment line inside a code declaration the ontology
  names (front matter `declarations:`) was added, removed or changed. A
  comment-only or whitespace edit inside the block, or any edit outside a
  named block, is not a signal.
- parity — one file of a `parity:` pair changed and the other did not.
- gate-file — the changed file is named by an invariant's `[gate: ...]`.
- deleted — a governed file was deleted.

Stdlib only, like the rest of the checker.
"""
from __future__ import annotations

import difflib

import json
import os
import re
import subprocess
import time
from pathlib import Path

LANG_BY_EXT = {".ts": "ts", ".tsx": "ts", ".js": "ts", ".mjs": "ts", ".py": "py"}

TS_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:abstract\s+)?(?:const\s+)?(interface|enum|class|type)\s+([A-Za-z_$][\w$]*)"
)
PY_DECL = re.compile(r"^(\s*)class\s+([A-Za-z_]\w*)")


def lang_of(rel: str) -> str | None:
    return LANG_BY_EXT.get(Path(rel).suffix.lower())


# ---------- code lines: the text with comments (and, for Python, strings) blanked ----------

def code_lines(text: str, lang: str) -> list[str]:
    """One entry per source line, comments removed, whitespace collapsed.
    Line count is preserved so indexes line up with `declarations`."""
    if lang == "ts":
        text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
        lines = [re.sub(r"//.*$", "", l) for l in text.splitlines()]
    else:
        text = re.sub(r'("""|\'\'\')(.*?)\1', lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
        lines = []
        for l in text.splitlines():
            l = re.sub(r'"[^"\n]*"', '""', l)
            l = re.sub(r"'[^'\n]*'", "''", l)
            lines.append(re.sub(r"#.*$", "", l))
    return [" ".join(l.split()) for l in lines]


def declarations(text: str, lang: str) -> list[tuple[str, int, int]]:
    """(name, start, end) line ranges, 0-based, end exclusive."""
    raw = text.splitlines()
    code = code_lines(text, lang)
    out: list[tuple[str, int, int]] = []
    if lang == "ts":
        i = 0
        while i < len(raw):
            m = TS_DECL.match(raw[i])
            if not m:
                i += 1
                continue
            depth, seen, j = 0, False, i
            while j < len(raw):
                l = code[j]
                depth += l.count("{") - l.count("}")
                seen = seen or "{" in l
                if seen and depth <= 0:
                    break
                if not seen and l.endswith(";"):
                    break
                j += 1
            out.append((m.group(2), i, min(j + 1, len(raw))))
            i = j + 1
    else:
        for i, line in enumerate(raw):
            m = PY_DECL.match(line)
            if not m:
                continue
            indent = len(m.group(1))
            j = i + 1
            while j < len(raw):
                l = raw[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= indent and not l.lstrip().startswith("#"):
                    break
                j += 1
            out.append((m.group(2), i, j))
    return out


def declaration_bodies(text: str | None, lang: str) -> dict[str, list[str]]:
    """name -> sorted non-blank code lines inside the declaration."""
    if text is None:
        return {}
    code = code_lines(text, lang)
    bodies: dict[str, list[str]] = {}
    for name, s, e in declarations(text, lang):
        bodies.setdefault(name, []).extend(l for l in code[s:e] if l)
    return {k: sorted(v) for k, v in bodies.items()}


def declaration_sources(text: str | None, lang: str) -> dict[str, list[str]]:
    """name -> the declaration's raw source lines, comments kept, for showing a diff."""
    if text is None:
        return {}
    raw = text.splitlines()
    out: dict[str, list[str]] = {}
    for name, s, e in declarations(text, lang):
        out.setdefault(name, []).extend(raw[s:e])
    return out


def declaration_diff(old: list[str] | None, new: list[str] | None, name: str) -> str:
    return "\n".join(difflib.unified_diff(old or [], new or [], fromfile=name, tofile=name, lineterm="", n=2))


def declaration_signals(old: str | None, new: str | None, lang: str, named: dict[str, str]) -> list[dict]:
    a, b = declaration_bodies(old, lang), declaration_bodies(new, lang)
    src_a, src_b = declaration_sources(old, lang), declaration_sources(new, lang)
    out = []
    for name, entity in named.items():
        x, y = a.get(name), b.get(name)
        if x is None and y is None:
            continue
        change = "added" if x is None else "removed" if y is None else "changed" if x != y else None
        if change:
            out.append({"kind": "declaration", "name": name, "entity": entity, "change": change,
                        "diff": declaration_diff(src_a.get(name), src_b.get(name), name)})
    return out


# ---------- git ----------

def git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    return r.stdout if r.returncode == 0 else None


def git_text(root: Path, rev: str, rel: str) -> str | None:
    """File content at `rev` (HEAD, a merge base, or '' for the index). None if absent."""
    return git(root, "show", f"{rev}:{rel}")


def worktree_text(root: Path, rel: str) -> str | None:
    p = root / rel
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    except OSError:
        return None


# ---------- per-file classification ----------

def gate_file_signals(rel: str, onts: list[dict]) -> list[dict]:
    base = Path(rel).name
    out = []
    for o in onts:
        for inv in o["invariants"]:
            if inv["gate"] and base in inv["gate"]:
                out.append({"kind": "gate-file", "name": base, "invariant": inv["text"][:80]})
    return out


def file_signals(rel: str, old: str | None, new: str | None, onts: list[dict]) -> list[dict]:
    """Signals for one governed file given its old and new text."""
    if old is not None and new is None:
        return [{"kind": "deleted", "name": rel}]
    signals: list[dict] = []
    lang = lang_of(rel)
    if lang:
        named: dict[str, str] = {}
        for o in onts:
            named.update(o.get("declarations", {}))
        signals += declaration_signals(old, new, lang, named)
    signals += gate_file_signals(rel, onts)
    return signals


def parity_signals(affecting: set[str], changed: set[str], onts: list[dict]) -> dict[str, list[dict]]:
    """path -> parity signals: one side of a pair had an affecting change and
    the partner did not change at all. A comment-only edit never asks for the
    partner; any edit to the partner satisfies the pair."""
    out: dict[str, list[dict]] = {}
    for o in onts:
        for a, b in o.get("parity", []):
            for moved, partner in ((a, b), (b, a)):
                if moved in affecting and partner not in changed:
                    out.setdefault(moved, []).append({"kind": "parity", "name": moved, "partner": partner})
    return out


def tier_of(signals: list[dict]) -> str:
    return "affecting" if signals else "touched"


# ---------- state record ----------

def state_path(root: Path) -> Path:
    env = os.environ.get("ONTOLOGY_STATE")
    return Path(env) if env else root / ".claude" / "ontology-state.jsonl"


def record_state(root: Path, entry: dict) -> None:
    """Append one JSON line. Never fails the check."""
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}
    try:
        p = state_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
