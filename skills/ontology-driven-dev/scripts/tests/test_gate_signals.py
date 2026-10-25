"""MUD-782: a gate-file signal says exactly which rule, where the change is and what it was."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import ontology_signals as S  # noqa: E402

LONG = "A plug is in a bore only where their depths overlap; touching an end is not inside the bore at all."
OLD = "export function alpha() {\n  return 1;\n}\n\nexport function beta() {\n  return 2;\n}\n"
NEW = "export function alpha() {\n  console.log('x');\n  return 1;\n}\n\nexport function beta() {\n  return 2;\n}\n"


def onts(*invariants: tuple[str, str]) -> list[dict]:
    return [{"domain": "demo", "invariants": [{"text": t, "gate": g} for t, g in invariants], "declarations": {}}]


def fired(signals: list[dict]) -> list[str]:
    return [s["invariant"] for s in signals if s["kind"] == "gate-file"]


class GateFileSignal(unittest.TestCase):
    def test_records_the_whole_rule_and_its_gate(self):
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, onts((LONG, "`fit.ts:alpha` (strict overlap)")), lambda rel, text, r: {"alpha"})
        self.assertEqual(fired(sigs), [LONG])
        self.assertEqual(sigs[0]["gate"], "`fit.ts:alpha` (strict overlap)")

    def test_a_rule_gated_by_another_function_in_the_file_still_fires_after_the_direct_hit(self):
        # its gate may call the changed function (a shared helper), so it is never dropped
        o = onts(("Beta rule.", "`fit.ts:beta`"), ("Alpha rule.", "`fit.ts:alpha`"))
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, o, lambda rel, text, r: {"alpha"})
        self.assertEqual(fired(sigs), ["Alpha rule.", "Beta rule."])
        self.assertEqual([s["match"] for s in sigs], ["function", "same-file"])
        self.assertEqual(sigs[1]["gate_functions"], ["beta"])

    def test_deleting_the_gate_function_is_a_direct_hit(self):
        old = OLD
        new = "export function beta() {\n  return 2;\n}\n"
        mapper = lambda rel, text, r: {"alpha"} if text == old else {"beta"}
        o = onts(("Alpha rule.", "`fit.ts:alpha`"), ("Beta rule.", "`fit.ts:beta`"))
        sigs = S.gate_file_signals("src/fit.ts", old, new, o, mapper)
        self.assertEqual(sigs[0]["invariant"], "Alpha rule.")
        self.assertEqual(sigs[0]["match"], "function")
        self.assertIn("alpha", sigs[0]["functions"])

    def test_renaming_the_gate_function_is_a_direct_hit(self):
        new = OLD.replace("function alpha", "function alphaRenamed")
        mapper = lambda rel, text, r: {"alpha"} if text == OLD else {"alphaRenamed"}
        sigs = S.gate_file_signals("src/fit.ts", OLD, new, onts(("Alpha rule.", "`fit.ts:alpha`")), mapper)
        self.assertEqual([s["match"] for s in sigs], ["function"])
        self.assertEqual(sigs[0]["functions"], ["alpha", "alphaRenamed"])

    def test_a_rule_gated_by_the_bare_file_fires_on_any_change(self):
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, onts(("File rule.", "`fit.ts`")), lambda rel, text, r: {"alpha"})
        self.assertEqual(fired(sigs), ["File rule."])
        self.assertEqual(sigs[0]["match"], "file")

    def test_a_change_outside_any_function_fires_every_rule_naming_the_file(self):
        o = onts(("Alpha rule.", "`fit.ts:alpha`"), ("Beta rule.", "`fit.ts:beta`"))
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, o, lambda rel, text, r: {"<module>"})
        self.assertEqual(fired(sigs), ["Alpha rule.", "Beta rule."])
        self.assertEqual({s["match"] for s in sigs}, {"module"})

    def test_an_unmappable_file_fires_every_rule_naming_it(self):
        o = onts(("Alpha rule.", "`fit.ts:alpha`"), ("Beta rule.", "`fit.ts:beta`"))
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, o, lambda rel, text, r: None)
        self.assertEqual(fired(sigs), ["Alpha rule.", "Beta rule."])
        self.assertEqual({s["match"] for s in sigs}, {"unmapped"})

    def test_the_signal_says_where_and_what(self):
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, onts(("Alpha rule.", "`fit.ts:alpha`")), lambda rel, text, r: {"alpha"})
        s = sigs[0]
        self.assertEqual(s["functions"], ["alpha"])
        self.assertEqual(s["lines"], [[2, 2]])
        self.assertIn("+  console.log('x');", s["diff"])

    def test_a_rule_whose_gate_does_not_name_the_file_is_not_touched(self):
        sigs = S.gate_file_signals("src/fit.ts", OLD, NEW, onts(("Other rule.", "`other.ts:alpha`")), lambda rel, text, r: {"alpha"})
        self.assertEqual(fired(sigs), [])


ONTOLOGY = """---
domain: demo
governs:
  - "src/**"
---

# Demo

## Intent

Keep the demo honest.

## Entities

- **Thing** — a thing. Key: `id`.

## Relationships

- `(Thing)-[HAS]->(Thing)`

## Invariants

- Alpha rule. [gate: `fit.ts:alpha`]
- Beta rule. [gate: `fit.ts:beta`]

## Vocabulary

- **Thing** — a thing.

## Out of scope

- Nothing.

## Changelog

- 2026-10-25 — Initial.
"""


@unittest.skipUnless(os.environ.get("ONTOLOGY_TYPESCRIPT_DIR"), "set ONTOLOGY_TYPESCRIPT_DIR to a typescript package to run")
class EndToEnd(unittest.TestCase):
    """The real check maps the changed lines with the TypeScript compiler."""

    def test_only_the_rule_of_the_changed_function_fires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True)
            run("init", "-q", "-b", "main"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
            (root / "ontology").mkdir(); (root / "ontology/demo.md").write_text(ONTOLOGY)
            (root / "src").mkdir(); (root / "src/fit.ts").write_text(OLD)
            run("add", "-A"); run("commit", "-q", "-m", "init")
            (root / "src/fit.ts").write_text(NEW)
            r = subprocess.run([sys.executable, str(SCRIPTS / "ontology_check.py"), "--changed"], cwd=root,
                               capture_output=True, text=True, env=os.environ.copy())
            self.assertEqual(r.returncode, 2, r.stderr)
            rec = [json.loads(l) for l in (root / ".claude/ontology-state.jsonl").read_text().splitlines()][-1]
            sigs = [s for f in rec["files"] for s in f["signals"] if s["kind"] == "gate-file"]
            self.assertEqual([(s["invariant"], s["match"]) for s in sigs], [("Alpha rule.", "function"), ("Beta rule.", "same-file")])
            self.assertEqual(sigs[0]["functions"], ["alpha"])
            self.assertIn("gate file for invariant: Alpha rule. (fit.ts › alpha, line 2)", r.stderr)
            self.assertIn("gate file for invariant: Beta rule. (fit.ts › alpha, line 2; its gate is beta)", r.stderr)

    def test_deleting_a_gate_function_flags_its_rule_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True)
            run("init", "-q", "-b", "main"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
            (root / "ontology").mkdir(); (root / "ontology/demo.md").write_text(ONTOLOGY)
            (root / "src").mkdir(); (root / "src/fit.ts").write_text(OLD)
            run("add", "-A"); run("commit", "-q", "-m", "init")
            (root / "src/fit.ts").write_text("export function beta() {\n  return 2;\n}\n")
            subprocess.run([sys.executable, str(SCRIPTS / "ontology_check.py"), "--changed"], cwd=root,
                           capture_output=True, text=True, env=os.environ.copy())
            rec = [json.loads(l) for l in (root / ".claude/ontology-state.jsonl").read_text().splitlines()][-1]
            sigs = {s["invariant"]: s for f in rec["files"] for s in f["signals"] if s["kind"] == "gate-file"}
            self.assertEqual(sigs["Alpha rule."]["match"], "function")
            self.assertIn("alpha", sigs["Alpha rule."]["functions"])


if __name__ == "__main__":
    unittest.main()
