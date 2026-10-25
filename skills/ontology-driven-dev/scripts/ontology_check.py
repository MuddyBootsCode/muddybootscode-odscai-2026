#!/usr/bin/env python3
"""The enforcer. Three modes, all stdlib, all exit non-zero on a problem.

  --validate   Structure check: required sections present, relationships
               reference known entities, every invariant has a gate (warn),
               `declarations:` name known entities. Run in CI and pre-commit.

  --touched    PostToolUse hook. Takes the edited file from --file <path> or
               from the Claude Code hook JSON on stdin (tool_input.file_path).
               Ungoverned: silent. Governed, tier *touched*: silent, recorded.
               Governed, tier *affecting*: the signal on stderr, exit 2.

  --changed    Stop hook, git commit-msg hook, CI. Finds changed files (staged
               with --staged; against the merge base with --base <ref>; else
               working tree + untracked vs HEAD), classifies each governed one
               (see ontology_signals), and blocks when an affecting change has
               no matching ontology edit, or a parity pair moved on one side.
               Honors `ontology-skip: <reason>` (--msg-file) or ONTOLOGY_SKIP.
               With --stop it blocks once per turn (stop_hook_active).

Every run appends one JSON line to .claude/ontology-state.jsonl (or
$ONTOLOGY_STATE): ts, mode, exit, tier, files[{path, tier, signals}], and more.

Exit codes: 0 ok · 1 usage/error · 2 block (Claude Code feeds stderr back to
the model).
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ontology_lib import (  # noqa: E402
    REQUIRED_SECTIONS,
    eprint,
    find_repo_root,
    invariant_counts,
    invariants_naming,
    named_list_counts,
    section_items,
    load_all,
    ontology_dir,
    path_governed_by,
)
from ontology_signals import (  # noqa: E402
    file_signals,
    git,
    git_text,
    parity_signals,
    record_state,
    tier_of,
    worktree_text,
)

QUERY = Path(__file__).resolve().parent / "ontology_query.py"


# ---------- --validate ----------

def validate(onts) -> int:
    root = find_repo_root()
    if not onts:
        eprint(f"no ontology directory or no *.md files in {ontology_dir()}")
        record_state(root, {"mode": "validate", "exit": 2, "domains": [], "message": "no ontology"})
        return 2
    errors, warnings = [], []
    for o in onts:
        name = o["path"].name
        for s in REQUIRED_SECTIONS:
            if s not in o["sections"] or not o["sections"][s].strip():
                errors.append(f"{name}: missing or empty section '## {s}'")
        if not o["entities"]:
            errors.append(f"{name}: no entities parsed — use '- **Name** — description' lines")
        known = {e.lower() for e in o["entities"]}
        for r in o["relationships"]:
            for end in (r["from"], r["to"]):
                if end.lower() not in known:
                    errors.append(f"{name}: relationship references unknown entity '{end}': {r['raw']}")
        if not o["invariants"]:
            errors.append(f"{name}: no invariants — the model has nothing to be held to")
        for i in o["invariants"]:
            if not i["gate"]:
                warnings.append(f"{name}: invariant without a gate: {i['text']}")
        if not o["governs"]:
            warnings.append(f"{name}: no `governs:` list in front matter — the change hook can't protect anything")
        for code_name, entity in o["declarations"].items():
            if entity.lower() not in known:
                errors.append(f"{name}: declarations maps `{code_name}` to unknown entity '{entity}'")
        for a, b in o["parity"]:
            for p in (a, b):
                if not path_governed_by(p, [o]):
                    warnings.append(f"{name}: parity path `{p}` is not in this domain's governs list")
        # D8: a disagreement is a decision nobody has been asked for; an old question is a stall.
        lists = named_list_counts(o)
        if lists["disagreements"] and not lists["open_questions"]:
            warnings.append(f"{name}: {lists['disagreements']} disagreement(s) listed but no open question asks anyone to pick")
        for q in section_items(o, "Open questions"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", q)
            if m and (date.today() - date.fromisoformat(m.group(1))).days > 30:
                warnings.append(f"{name}: open question from {m.group(1)} is older than 30 days: {q[:80]}")
    for w in warnings:
        eprint("warn: " + w)
    for e in errors:
        eprint("error: " + e)
    code = 2 if errors else 0
    counts = invariant_counts(onts)
    if not errors:
        print(f"ontology ok: {len(onts)} domain(s), " + ", ".join(o["domain"] for o in onts))
    print("invariants: " + "  ".join(f"{k.replace('_', '+')} {v}" for k, v in counts.items()))
    record_state(root, {"mode": "validate", "exit": code, "domains": [o["domain"] for o in onts],
                        "errors": len(errors), "warnings": len(warnings), "invariants": counts,
                        "sections": {k: sum(named_list_counts(o)[k] for o in onts) for k in named_list_counts(onts[0])},
                        "problems": [f"warn: {w}" for w in warnings] + [f"error: {e}" for e in errors]})
    return code


# ---------- shared ----------

def rel_to_root(root: Path, fp: str) -> str | None:
    try:
        return str(Path(fp).resolve().relative_to(root)).replace(os.sep, "/")
    except ValueError:
        return None


def is_ontology_file(rel: str) -> bool:
    return rel.startswith("ontology/") and rel.endswith(".md")


TS_EXT = (".ts", ".tsx", ".mts", ".cts")


def typescript_dir(root: Path) -> str | None:
    """The `typescript` package the function mapper loads: ONTOLOGY_TYPESCRIPT_DIR, else the
    repo's own node_modules (top level or one package down). None when there is none."""
    if os.environ.get("ONTOLOGY_TYPESCRIPT_DIR"):
        return os.environ["ONTOLOGY_TYPESCRIPT_DIR"]
    for nm in [root / "node_modules", *sorted(root.glob("*/node_modules"))]:
        if (nm / "typescript").is_dir():
            return str(nm / "typescript")
    return None


def function_mapper(root: Path):
    """mapper(rel, text, ranges) -> names of the functions around those lines of `text`, or
    None when that cannot be told: not TypeScript, no node or typescript, or the mapper
    failed. The text is mapped from a temporary copy, since a staged, committed or old
    version need not be on disk. Without a mapper every rule naming a gate file still fires."""
    script = Path(__file__).resolve().parent / "changed_functions.mjs"
    ts = typescript_dir(root)

    def mapper(rel: str, text: str, ranges: list[list[int]]) -> set[str] | None:
        if not ranges or not rel.endswith(TS_EXT) or ts is None or not script.is_file():
            return None
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / Path(rel).name
            copy.write_text(text, encoding="utf-8")
            payload = {"files": [{"path": str(copy), "lines": ranges}], "typescript": ts}
            try:
                r = subprocess.run(["node", str(script)], input=json.dumps(payload), capture_output=True, text=True, cwd=root)
                names = json.loads(r.stdout or "{}") if r.returncode == 0 else None
            except (OSError, json.JSONDecodeError):
                names = None
        if names is None:
            eprint(f"ontology: could not map {rel} to functions; every rule naming it is flagged")
            return None
        found = next(iter(names.values()), None)
        return set(found) if found else None
    return mapper


def classify(root: Path, rel: str, onts, old_rev: str | None, new_rev: str | None) -> dict:
    """One governed file: {path, tier, signals, domains}. new_rev None = working tree."""
    old = git_text(root, old_rev, rel) if old_rev is not None else None
    new = git_text(root, new_rev, rel) if new_rev is not None else worktree_text(root, rel)
    signals = file_signals(rel, old, new, onts, function_mapper(root))
    doms = sorted({o["domain"] for o, _ in path_governed_by(rel, onts)})
    return {"path": rel, "tier": tier_of(signals), "signals": signals, "domains": doms}


def gate_place(sig: dict) -> str:
    """ " (fit.ts › alpha, line 2)": where in the gate file the change is, when known."""
    fns = [f for f in sig.get("functions", []) if f != "<module>"]
    lines = sig.get("lines") or []
    where = [sig["name"] + (f" › {', '.join(fns)}" if fns else "")]
    if lines:
        first, last = lines[0][0], lines[-1][1]
        where.append(f"line {first}" if first == last else f"lines {first}–{last}")
    if sig.get("match") == "same-file" and sig.get("gate_functions"):
        where[-1] += f"; its gate is {', '.join(sig['gate_functions'])}"
    return f" ({', '.join(where)})" if fns or lines else ""


def describe(sig: dict) -> str:
    k = sig["kind"]
    if k == "declaration":
        return f"`{sig['name']}` ({sig['change']}) → entity {sig['entity']}"
    if k == "parity":
        return f"parity: changed without its partner `{sig['partner']}`"
    if k == "gate-file":
        return f"gate file for invariant: {sig['invariant']}{gate_place(sig)}"
    if k == "deleted":
        return "deleted"
    return k


# ---------- --touched ----------

def touched(onts, file_arg: str | None) -> int:
    fp = file_arg
    if not fp:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            return 0  # not called as a hook; nothing to do
        ti = payload.get("tool_input") or {}
        fp = ti.get("file_path") or ti.get("path")
    if not fp:
        return 0
    root = find_repo_root()
    rel = rel_to_root(root, fp if os.path.isabs(fp) else str(root / fp))
    if not rel or is_ontology_file(rel) or not path_governed_by(rel, onts):
        return 0
    info = classify(root, rel, onts, "HEAD", None)
    code = 2 if info["tier"] == "affecting" else 0
    msg = ""
    if code == 2:
        dom = info["domains"][0] if info["domains"] else "?"
        msg = (f"ontology: `{rel}` changes what ontology/{dom}.md describes: "
               + "; ".join(describe(s) for s in info["signals"])
               + f". Update the ontology in this change (Entities / Relationships / Invariants + a Changelog line). "
               f"Query first: python3 {QUERY} --domain {dom} summary")
        eprint(msg)
    record_state(root, {"mode": "touched", "exit": code, "tier": info["tier"], "files": [info],
                        "domains": info["domains"], "message": msg})
    return code


# ---------- --changed ----------

def changed_files(root: Path, staged: bool, base: str | None) -> tuple[list[str], str]:
    """(files, old_rev). old_rev is what each file is compared against."""
    if staged:
        out = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRD") or ""
        return sorted({l.strip() for l in out.splitlines() if l.strip()}), "HEAD"
    old_rev = "HEAD"
    if base:
        mb = (git(root, "merge-base", base, "HEAD") or "").strip()
        if not mb:
            eprint(f"ontology: cannot find merge base with {base}")
            return [], "HEAD"
        old_rev = mb
    files: set[str] = set()
    for out in (git(root, "diff", "--name-only", "--diff-filter=ACMRD", old_rev),
                git(root, "ls-files", "--others", "--exclude-standard")):
        files.update(l.strip() for l in (out or "").splitlines() if l.strip())
    return sorted(files), old_rev


def skip_reason(msg_file: str | None) -> str | None:
    env = os.environ.get("ONTOLOGY_SKIP")
    if env:
        return env
    if msg_file and Path(msg_file).exists():
        for line in Path(msg_file).read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lower().startswith("ontology-skip:"):
                return line.partition(":")[2].strip() or "(no reason given)"
    return None


def stop_hook_active() -> bool:
    try:
        return bool(json.load(sys.stdin).get("stop_hook_active"))
    except Exception:
        return False


def ontology_diff_text(root: Path, files: list[str], old_rev: str, staged: bool) -> str:
    """Added and removed lines across the changed ontology files."""
    out = []
    for f in files:
        old = git_text(root, old_rev, f) or ""
        new = (git_text(root, "", f) if staged else worktree_text(root, f)) or ""
        a, b = set(old.splitlines()), set(new.splitlines())
        out += sorted(a ^ b)
    return "\n".join(out)


def changed(onts, staged: bool, msg_file: str | None = None, stop: bool = False, base: str | None = None) -> int:
    if not onts:
        return 0  # no ontology yet; nothing to enforce
    already_blocked = stop and stop_hook_active()
    root = find_repo_root()
    files, old_rev = changed_files(root, staged, base)
    onto_files = [f for f in files if is_ontology_file(f)]
    governed = [f for f in files if not is_ontology_file(f) and path_governed_by(f, onts)]
    if not governed:
        # Nothing to enforce, but the run still happened: the observer reads this as a clean check.
        record_state(root, {"mode": "changed", "exit": 0, "tier": "none", "files": [],
                            "ontology_changed": bool(onto_files), "skip": None, "domains": [],
                            "base": base, "staged": staged, "message": ""})
        return 0
    new_rev = "" if staged else None
    infos = [classify(root, f, onts, old_rev, new_rev) for f in governed]
    affecting_paths = {i["path"] for i in infos if i["tier"] == "affecting"}
    for f, sigs in parity_signals(affecting_paths, set(files), onts).items():
        for info in infos:
            if info["path"] == f:
                info["signals"] = info["signals"] + sigs
    affecting = [i for i in infos if i["tier"] == "affecting"]
    tier = "affecting" if affecting else "touched"
    domains = sorted({d for i in infos for d in i["domains"]})

    touched_entities = sorted({s["entity"] for i in infos for s in i["signals"] if s.get("entity")})
    reopen = {e: invariants_naming(onts, e) for e in touched_entities}
    reopen = {e: v for e, v in reopen.items() if v}

    def finish(code: int, message: str, skip: str | None = None) -> int:
        record_state(root, {"mode": "changed", "exit": code, "tier": tier, "files": infos,
                            "ontology_changed": bool(onto_files), "skip": skip, "domains": domains,
                            "base": base, "staged": staged, "message": message, "reopen": reopen})
        return code

    if not affecting:
        return finish(0, "")
    reason = skip_reason(msg_file)
    if reason:
        eprint(f"ontology: skip honored — {reason}")
        return finish(0, f"skip: {reason}", reason)

    problems: list[str] = []
    parity = [(i["path"], s) for i in affecting for s in i["signals"] if s["kind"] == "parity"]
    for path, s in parity:
        problems.append(f"  {path}   parity: changed without its partner `{s['partner']}`")
    needs_onto = [i for i in affecting if any(s["kind"] != "parity" for s in i["signals"])]
    if needs_onto:
        if not onto_files:
            for i in needs_onto:
                for s in i["signals"]:
                    if s["kind"] != "parity":
                        problems.append(f"  {i['path']}   {describe(s)}")
        else:
            diff = ontology_diff_text(root, onto_files, old_rev, staged)
            entities = sorted({s["entity"] for i in needs_onto for s in i["signals"] if s.get("entity")})
            missing = [e for e in entities if not re.search(rf"\b{re.escape(e)}\b", diff, re.I)]
            for e in missing:
                problems.append(f"  ontology/ changed but does not mention {e}")
    if not problems:
        return finish(0, "")

    if already_blocked:
        eprint("ontology: affecting changes still lack an ontology update after one block. "
               "Tell the user which files and why, then stop. The commit-msg hook will still "
               "require an update or `ontology-skip: <reason>`.")
        return finish(0, "blocked once; passing through")
    head = "Governed paths changed in ways the ontology describes, and ontology/ did not follow:"
    eprint(head)
    for p in problems:
        eprint(p)
    for e, rules in reopen.items():
        eprint(f"Reopen the rules that name {e} (confirm, reword, or add the one this change breaks):")
        for r in rules:
            eprint(f"  - {r}")
    eprint("Update the ontology (Entities / Relationships / Invariants + a Changelog line that names the entity), "
           "bring a parity partner along, or mark the change rule-neutral with `ontology-skip: <reason>` "
           "in the commit message (or ONTOLOGY_SKIP=<reason>). Say so to the user either way.")
    return finish(2, head + "\n" + "\n".join(problems))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--validate", action="store_true")
    g.add_argument("--touched", action="store_true")
    g.add_argument("--changed", action="store_true")
    ap.add_argument("--file", help="with --touched: the edited file (instead of hook JSON on stdin)")
    ap.add_argument("--staged", action="store_true", help="with --changed: look at the git index (commit hook)")
    ap.add_argument("--base", help="with --changed: compare against the merge base with this ref (CI)")
    ap.add_argument("--msg-file", help="with --changed: commit message file to scan for `ontology-skip:`")
    ap.add_argument("--stop", action="store_true", help="with --changed: run as the Claude Code Stop hook (block once per turn)")
    a = ap.parse_args()

    onts = load_all()
    if a.validate:
        sys.exit(validate(onts))
    if a.touched:
        sys.exit(touched(onts, a.file))
    if a.changed:
        sys.exit(changed(onts, a.staged, a.msg_file, a.stop, a.base))


if __name__ == "__main__":
    main()
