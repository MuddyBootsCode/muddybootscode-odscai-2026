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

def changed_line_ranges(old: str | None, new: str | None) -> list[list[int]]:
    """1-based [first, last] line ranges of the new text that changed. A pure deletion is
    reported at the line it happened before, so it still has a place in the new file."""
    a, b = (old or "").splitlines(), (new or "").splitlines()
    out: list[list[int]] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        first = j1 + 1
        out.append([first, max(first, j2)])
    return out


def removed_line_ranges(old: str | None, new: str | None) -> list[list[int]]:
    """1-based [first, last] ranges of the old text that were removed or replaced: where a
    deleted or renamed function was, which the new text can no longer show."""
    a, b = (old or "").splitlines(), (new or "").splitlines()
    return [[i1 + 1, i2] for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
            if tag in ("replace", "delete") and i2 > i1]


def change_diff(rel: str, old: str | None, new: str | None, limit: int = 40) -> str:
    """The change as a unified diff with one line of context, cut at `limit` lines."""
    lines = list(difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(),
                                      fromfile=rel, tofile=rel, n=1, lineterm=""))[2:]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... {len(lines) - limit} more lines"]
    return "\n".join(lines)


def gate_functions(gate: str, base: str) -> set[str] | None:
    """The functions a gate names in this file, or None when it names the bare file (or is a
    file the gate only mentions in passing): then any change to the file is a change to it."""
    names: set[str] = set()
    for m in re.finditer(re.escape(base) + r"(?::([A-Za-z_$][\w$.]*))?", gate):
        if not m.group(1):
            return None
        names.add(m.group(1))
    return names


def gate_file_signals(rel: str, old: str | None, new: str | None, onts: list[dict],
                      mapper=None) -> list[dict]:
    """One signal per rule whose gate names this file and whose enforcing code the change
    reached. `mapper(rel, text, ranges)` returns the names of the functions around those
    lines of `text` ("<module>" for code outside any function), or None when it cannot tell.
    The changed lines are mapped in the new text and the removed ones in the old, so a
    deleted or renamed function is named too.

    Every rule naming the file fires: a direct hit when the change is in a function its
    gate names (`match` "function"), the whole file or outside any function ("file",
    "module"), untraceable ("unmapped"), or another function of the file ("same-file"),
    since its gate may call the changed one. The direct hits come first."""
    base = Path(rel).name
    rules = [inv for o in onts for inv in o["invariants"] if inv["gate"] and base in inv["gate"]]
    if not rules:
        return []
    ranges = changed_line_ranges(old, new)
    changed = changed_names(rel, old, new, ranges, mapper)
    diff = change_diff(rel, old, new)
    out = []
    for inv in rules:
        named = gate_functions(inv["gate"], base)
        if changed is None:
            match = "unmapped"
        elif named is None:
            match = "file"
        elif "<module>" in changed:
            match = "module"
        elif named & changed:
            match = "function"
        else:
            match = "same-file"
        out.append({"kind": "gate-file", "name": base, "invariant": inv["text"], "gate": inv["gate"],
                    "match": match, "gate_functions": sorted(named or []), "functions": sorted(changed or []),
                    "lines": ranges, "diff": diff})
    return sorted(out, key=lambda s: s["match"] == "same-file")


def non_blank(text: str | None, ranges: list[list[int]]) -> list[list[int]]:
    """The ranges with blank lines dropped: a blank line between two functions belongs to
    neither, and would otherwise make an edit look like a change outside any function."""
    lines = (text or "").splitlines()
    out: list[list[int]] = []
    for first, last in ranges:
        for n in range(first, last + 1):
            if 0 < n <= len(lines) and lines[n - 1].strip():
                if out and out[-1][1] == n - 1:
                    out[-1][1] = n
                else:
                    out.append([n, n])
    return out


def changed_names(rel: str, old: str | None, new: str | None, ranges: list[list[int]], mapper) -> set[str] | None:
    """The functions the change reached, from the new text's changed lines and the old text's
    removed ones. None when the mapper is missing or cannot tell for either side."""
    if not mapper:
        return None
    removed = removed_line_ranges(old, new)
    sides = [(new, ranges), (old, removed)]
    names: set[str] = set()
    for text, side in sides:
        side = non_blank(text, side)
        if not side or text is None:
            continue
        found = mapper(rel, text, side)
        if found is None:
            return None
        names |= found
    return names or None


def file_signals(rel: str, old: str | None, new: str | None, onts: list[dict], mapper=None) -> list[dict]:
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
    signals += gate_file_signals(rel, old, new, onts, mapper)
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
