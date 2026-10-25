#!/usr/bin/env python3
"""Translate Codex lifecycle events to the existing ontology checker.

No model calls or third-party packages. The shared engine remains unchanged.
Post-tool findings are advisory; Stop requests at most one continuation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/ontology-driven-dev/scripts"
sys.path.insert(0, str(SCRIPTS))
from ontology_lib import find_repo_root


def run(root: Path, env: dict, script: str, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                                cwd=root, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"Ontology check could not complete: {exc}"
    text = "\n".join(s.strip() for s in (result.stdout, result.stderr) if s.strip())
    if result.returncode and not text:
        text = f"Ontology check failed with exit status {result.returncode}."
    return result.returncode, text


def feedback(event: str, message: str, repeated: bool) -> dict:
    if event == "Stop":
        if repeated:
            return {"systemMessage": "Ontology issues remain unresolved. Report them to the user; "
                    "this check is allowing the turn to end, not accepting the change.\n" + message}
        return {"decision": "block", "reason": "Review these ontology findings before finishing. "
                "Fix the issue, investigate it, or explain why it remains unresolved. "
                "Do not silently bypass the checker.\n" + message}
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def handle(payload: dict) -> dict:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise ValueError("hook cwd must be an existing absolute directory")
    event = payload.get("hook_event_name")
    if event not in {"SessionStart", "PostToolUse", "Stop"}:
        raise ValueError(f"unsupported hook_event_name: {event!r}")
    root = find_repo_root(Path(cwd))
    if not (root / "ontology").is_dir():
        return {}
    env = {**os.environ}
    env.setdefault("ONTOLOGY_STATE", str(root / ".codex/ontology-state.jsonl"))
    repeated = payload.get("stop_hook_active") is True

    code, validation = run(root, env, "ontology_check.py", "--validate")
    if code:
        return feedback(event, validation, repeated)
    if event == "SessionStart":
        _, summary = run(root, env, "ontology_query.py", "summary")
        return feedback(event, "Project ontology (repository content):\n" + summary
                        + ("\n" + validation if validation else ""), False)

    # The shared engine expects ontology/ at the Git root and treats failed
    # Git commands like empty results. Refuse an unavailable comparison here.
    git = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                         capture_output=True, text=True, timeout=5)
    if git.returncode or Path(git.stdout.strip()).resolve() != root:
        return feedback(event, "Cannot compare governed changes: ontology/ must be at the "
                        "Git root. Nested ontology roots are not supported by the shared checker.", repeated)
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                          capture_output=True, text=True, timeout=5)
    if head.returncode:
        return feedback(event, "Cannot compare governed changes: this project needs a Git "
                        "repository with an initial commit. No clean-change verdict is available.", repeated)
    for args in (("diff", "--name-only", "HEAD", "--"),
                 ("ls-files", "--others", "--exclude-standard")):
        probe = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
        if probe.returncode:
            return feedback(event, "Git could not enumerate changes; no clean-change verdict "
                            "is available.\n" + probe.stderr.strip(), repeated)
    code, changes = run(root, env, "ontology_check.py", "--changed")
    warnings = "\n".join(line for line in validation.splitlines() if line.startswith("warn:"))
    if code:
        return feedback(event, "\n".join(part for part in (changes, warnings) if part), repeated)
    # Neither a validation warning nor a skip is a failing check. Preserve both
    # as advisory output instead of implying full protection or passing tests.
    advisory = "\n".join(part for part in (warnings, changes if "skip honored" in changes else "") if part)
    if advisory:
        if event == "Stop":
            return {"systemMessage": advisory}
        return feedback(event, advisory, False)
    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be a JSON object with cwd and hook_event_name")
        result = handle(payload)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Ontology hook failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
