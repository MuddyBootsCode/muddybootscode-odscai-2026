"""Behavior tests for ontology_check.py tiers and the state record.

Each test builds a throwaway git repo with a small ontology, edits governed
files the way a developer would, and runs the real CLI. Stdlib only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
CHECK = SCRIPTS / "ontology_check.py"

ONTOLOGY = """---
domain: demo
version: 1
governs:
  - "src/**"
  - "mcp/**"
  - "tests/**"
declarations:
  - "Item: ItemRecord, ItemKind, Item"
  - "Order: OrderRecord"
parity:
  - "src/types.ts <-> mcp/schema.py"
---

# Demo

## Intent

Keep the well document honest.

## Entities

- **Item** — a product line. Key: `id`.
- **Order** — a customer purchase. Key: `id`.

## Relationships

- `(Order)-[CONTAINS]->(Item)`  0..*

## Invariants

- An Order is larger than any Item in it. [gate: `itemPlacement.test.ts`]

## Vocabulary

- **Item** — any product line. Not only physical goods.

## Out of scope

- Billing.

## Changelog

- 2026-10-24 — Initial.
"""

TYPES_TS = """export interface ItemRecord {
  id: string; // the id
  price: number;
}

export enum ItemKind {
  STANDARD = "Standard",
}

export interface ModalState {
  open: boolean;
}
"""

SCHEMA_PY = '''from pydantic import BaseModel, Field


class Item(BaseModel):
    """One item."""

    price: float | None = Field(default=None, description="Unit price.")
'''

TEST_TS = "test('placement', () => {});\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def check(root: Path, *args: str, stdin: str = "", env: dict | None = None) -> subprocess.CompletedProcess:
    e = {**os.environ, **(env or {})}
    return subprocess.run([sys.executable, str(CHECK), *args], cwd=root, input=stdin,
                          capture_output=True, text=True, env=e)


def state(root: Path) -> list[dict]:
    p = root / ".claude" / "ontology-state.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        self.write("ontology/orders.md", ONTOLOGY)
        self.write("src/types.ts", TYPES_TS)
        self.write("mcp/schema.py", SCHEMA_PY)
        self.write("tests/itemPlacement.test.ts", TEST_TS)
        self.write("README.md", "hi\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def edit(self, rel: str, old: str, new: str):
        p = self.root / rel
        t = p.read_text()
        assert old in t, (rel, old)
        p.write_text(t.replace(old, new))


class ChangedTiers(Repo):
    def test_comment_only_edit_in_named_declaration_is_touched_not_blocked(self):
        self.edit("src/types.ts", "// the id", "// the identifier")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["mode"], "changed")
        self.assertEqual(rec["tier"], "touched")
        self.assertEqual(rec["files"][0]["path"], "src/types.ts")

    def test_member_added_to_named_declaration_blocks_without_ontology_change(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("ItemRecord", r.stderr)
        self.assertIn("Item", r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["tier"], "affecting")
        ts = next(f for f in rec["files"] if f["path"] == "src/types.ts")
        self.assertEqual(ts["signals"][0]["kind"], "declaration")
        self.assertEqual(ts["signals"][0]["name"], "ItemRecord")
        self.assertEqual(ts["signals"][0]["entity"], "Item")
        self.assertIn("+  weight: number;", ts["signals"][0]["diff"])
        self.assertIn(" price: number;", ts["signals"][0]["diff"])  # context line, unchanged

    def test_added_declaration_signal_carries_its_whole_body_as_diff(self):
        self.edit("src/types.ts", "export interface ModalState", "export interface Item {\n  sections: ItemRecord[];\n}\n\nexport interface ModalState")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        rec = state(self.root)[-1]
        ts = next(f for f in rec["files"] if f["path"] == "src/types.ts")
        sig = next(s for s in ts["signals"] if s["name"] == "Item")
        self.assertEqual(sig["change"], "added")
        self.assertIn("+export interface Item {", sig["diff"])
        self.assertIn("+  sections: ItemRecord[];", sig["diff"])
        self.assertNotIn("ModalState", sig["diff"])

    def test_member_added_passes_when_ontology_names_the_entity(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        self.edit("ontology/orders.md", "- 2026-10-24 — Initial.", "- 2026-10-25 — Item gains weight.\n- 2026-10-24 — Initial.")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_member_added_blocks_when_ontology_changed_but_does_not_name_the_entity(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        self.edit("ontology/orders.md", "- 2026-10-24 — Initial.", "- 2026-10-25 — Tidied wording.\n- 2026-10-24 — Initial.")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not mention Item", r.stderr)

    def test_member_added_to_unnamed_declaration_is_only_touched(self):
        self.edit("src/types.ts", "  open: boolean;\n", "  open: boolean;\n  busy: boolean;\n")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(self.root)[-1]["tier"], "touched")

    def test_enum_value_added_is_affecting(self):
        self.edit("src/types.ts", '  STANDARD = "Standard",\n', '  STANDARD = "Standard",\n  BUNDLE = "Bundle",\n')
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("ItemKind", r.stderr)

    def test_python_field_added_is_affecting(self):
        self.edit("mcp/schema.py", "    price: float | None = Field(default=None, description=\"Unit price.\")\n",
                  "    price: float | None = Field(default=None, description=\"Unit price.\")\n    weight: float | None = None\n")
        self.edit("src/types.ts", "// the id", "// id")  # keep parity satisfied
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Item", r.stderr)

    def test_python_description_only_change_is_only_touched(self):
        self.edit("mcp/schema.py", 'description="Unit price."', 'description="Unit price, dollars."')
        self.edit("src/types.ts", "// the id", "// id")  # keep parity satisfied
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(self.root)[-1]["tier"], "touched")

    def test_affecting_change_on_one_parity_side_blocks_even_with_ontology_change(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("ontology/orders.md", "- 2026-10-24 — Initial.", "- 2026-10-25 — Item gains weight.\n- 2026-10-24 — Initial.")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("parity", r.stderr)
        self.assertIn("mcp/schema.py", r.stderr)
        kinds = {s["kind"] for s in state(self.root)[-1]["files"][0]["signals"]}
        self.assertIn("parity", kinds)

    def test_comment_only_change_on_one_parity_side_does_not_ask_for_the_partner(self):
        self.edit("src/types.ts", "// the id", "// id")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_parity_satisfied_when_the_partner_changes_too(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')
        self.edit("ontology/orders.md", "- 2026-10-24 — Initial.", "- 2026-10-25 — Item gains weight.\n- 2026-10-24 — Initial.")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_gate_referenced_test_file_change_is_affecting(self):
        self.edit("tests/itemPlacement.test.ts", "test('placement'", "test('placement strict'")
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("gate", r.stderr)
        self.assertEqual(state(self.root)[-1]["files"][0]["signals"][0]["kind"], "gate-file")

    def test_deleted_governed_file_is_affecting(self):
        (self.root / "src/types.ts").unlink()
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(state(self.root)[-1]["files"][0]["signals"][0]["kind"], "deleted")

    def test_skip_marker_still_passes_an_affecting_change(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        r = check(self.root, "--changed", env={"ONTOLOGY_SKIP": "rename only"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(self.root)[-1]["skip"], "rename only")

    def test_base_ref_compares_committed_branch_against_merge_base(self):
        git(self.root, "switch", "-q", "-c", "feature")
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')
        git(self.root, "commit", "-q", "-am", "add weight")
        self.assertEqual(check(self.root, "--changed").returncode, 0)  # working tree clean
        r = check(self.root, "--changed", "--base", "main")
        self.assertEqual(r.returncode, 2)
        self.assertIn("ItemRecord", r.stderr)


class TouchedTiers(Repo):
    def test_touched_tier_a_is_silent_and_recorded(self):
        self.edit("src/types.ts", "// the id", "// id")
        r = check(self.root, "--touched", "--file", "src/types.ts")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["mode"], "touched")
        self.assertEqual(rec["tier"], "touched")

    def test_touched_tier_b_exits_2_with_the_signal(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        payload = json.dumps({"tool_input": {"file_path": str(self.root / "src/types.ts")}})
        r = check(self.root, "--touched", stdin=payload)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ItemRecord", r.stderr)
        self.assertEqual(state(self.root)[-1]["tier"], "affecting")

    def test_touched_ungoverned_file_records_nothing(self):
        r = check(self.root, "--touched", "--file", "README.md")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(state(self.root), [])


class StateRecord(Repo):
    def test_validate_appends_a_record(self):
        r = check(self.root, "--validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["mode"], "validate")
        self.assertEqual(rec["exit"], 0)
        self.assertEqual(rec["domains"], ["demo"])
        self.assertIn("ts", rec)

    def test_validate_records_its_warning_and_error_lines(self):
        self.edit("ontology/orders.md", "## Vocabulary", "- Every Item has a price.\n\n## Vocabulary")
        r = check(self.root, "--validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["warnings"], 1)
        self.assertEqual(rec["problems"], ["warn: orders.md: invariant without a gate: Every Item has a price."])

    def test_clean_stop_check_still_records(self):
        r = check(self.root, "--changed", "--stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["mode"], "changed")
        self.assertEqual(rec["exit"], 0)
        self.assertEqual(rec["files"], [])
        self.assertFalse(rec["staged"])

    def test_ungoverned_change_still_records(self):
        self.write("README.md", "changed\n")
        r = check(self.root, "--changed", "--staged")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["mode"], "changed")
        self.assertEqual(rec["files"], [])
        self.assertTrue(rec["staged"])

    def test_state_path_override(self):
        p = self.root / "elsewhere.jsonl"
        r = check(self.root, "--validate", env={"ONTOLOGY_STATE": str(p)})
        self.assertEqual(r.returncode, 0)
        self.assertTrue(p.exists())


STATUS_ONTOLOGY = ONTOLOGY.replace(
    "- An Order is larger than any Item in it. [gate: `itemPlacement.test.ts`]",
    "- An Order is larger than any Item in it. [confirmed: reviewer 2026-10-24] [gate: `itemPlacement.test.ts`]\n"
    "- Orders shrink: no order is larger than the order before it. (inferred) [gate: `validate.ts:clampSizeEdit`]\n"
    "- Every Item has a price. (inferred)\n"
    "- An Item is placed in an Order.",
)


class InvariantStatus(Repo):
    """D7: domain agreement and enforcement coverage are two statuses, counted apart."""

    def test_status_markers_are_parsed(self):
        sys.path.insert(0, str(CHECK.parent))
        from ontology_lib import parse_ontology
        self.write("ontology/orders.md", STATUS_ONTOLOGY)
        inv = parse_ontology(self.root / "ontology" / "orders.md")["invariants"]
        by = {i["text"].split(".")[0]: i for i in inv}
        order = by["An Order is larger than any Item in it"]
        self.assertEqual(order["status"], "confirmed")
        self.assertEqual(order["confirmed_by"], "reviewer 2026-10-24")
        self.assertEqual(order["gate"], "`itemPlacement.test.ts`")
        self.assertNotIn("[confirmed", order["text"])
        shrink = by["Orders shrink: no order is larger than the order before it"]
        self.assertEqual(shrink["status"], "inferred")
        self.assertNotIn("(inferred)", shrink["text"])
        self.assertEqual(by["Every Item has a price"]["status"], "inferred")
        self.assertEqual(by["An Item is placed in an Order"]["status"], "unmarked")

    def test_validate_reports_the_four_counts(self):
        self.write("ontology/orders.md", STATUS_ONTOLOGY)
        r = check(self.root, "--validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["invariants"], {
            "confirmed_gated": 1, "confirmed_ungated": 0,
            "unconfirmed_gated": 1, "unconfirmed_ungated": 2,
        })
        self.assertIn("confirmed+gated 1", r.stdout)
        self.assertIn("unconfirmed+ungated 2", r.stdout)

    def test_query_shows_status_beside_each_invariant(self):
        self.write("ontology/orders.md", STATUS_ONTOLOGY)
        r = subprocess.run([sys.executable, str(CHECK.parent / "ontology_query.py"), "invariants"],
                           cwd=self.root, capture_output=True, text=True)
        self.assertIn("[confirmed: reviewer 2026-10-24]", r.stdout)
        self.assertIn("(inferred)", r.stdout)
        self.assertIn("[UNCONFIRMED]", r.stdout)
        self.assertIn("[MISSING GATE]", r.stdout)


class NamedSections(Repo):
    """D8: Gate backlog, Disagreements and Open questions are sections the validator reads."""

    def test_disagreements_without_open_questions_warns(self):
        self.write("ontology/orders.md", ONTOLOGY.replace(
            "## Vocabulary",
            "## Disagreements\n\n- The margin is 0.1 in `validate.ts` and 2 in `Canvas.tsx`.\n\n## Vocabulary"))
        r = check(self.root, "--validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 disagreement(s) listed but no open question", r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["sections"], {"gate_backlog": 0, "disagreements": 1, "open_questions": 0})

    def test_open_question_older_than_30_days_warns(self):
        self.write("ontology/orders.md", ONTOLOGY.replace(
            "## Vocabulary",
            "## Open questions\n\n- 2026-01-05 — Does a bundle have to fit inside its parent order? (asked: reviewer)\n"
            "- 2026-10-24 — Is 0.1 the right margin? (asked: reviewer)\n\n## Vocabulary"))
        r = check(self.root, "--validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("open question from 2026-01-05 is older than 30 days", r.stderr)
        self.assertNotIn("2026-10-24 is older", r.stderr)
        self.assertEqual(state(self.root)[-1]["sections"]["open_questions"], 2)

    def test_summary_counts_the_three_sections(self):
        self.write("ontology/orders.md", ONTOLOGY.replace(
            "## Vocabulary",
            "## Gate backlog\n\n- An item lies inside some order on write.\n- Start is before end on write.\n\n## Vocabulary"))
        r = subprocess.run([sys.executable, str(CHECK.parent / "ontology_query.py"), "summary"],
                           cwd=self.root, capture_output=True, text=True)
        self.assertIn("Gate backlog: 2", r.stdout)


class Reopen(Repo):
    """D9: an affecting change reopens the invariants that name its entity, not the whole interview."""

    def test_block_message_lists_the_invariants_to_reopen(self):
        self.edit("src/types.ts", "  price: number;\n", "  price: number;\n  weight: number;\n")
        self.edit("mcp/schema.py", '"""One item."""', '"""One item line."""')  # satisfy parity
        r = check(self.root, "--changed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Reopen the rules that name Item", r.stderr)
        self.assertIn("An Order is larger than any Item in it.", r.stderr)
        rec = state(self.root)[-1]
        self.assertEqual(rec["reopen"], {"Item": ["An Order is larger than any Item in it."]})


COMMENTED_ONTOLOGY = ONTOLOGY.replace(
    '  - "mcp/**"\n',
    '  # enforcement found by the 2026-10-24 pass: the code that refuses or repairs\n  - "mcp/**"\n',
)


class FrontMatterComments(Repo):
    """A `#` comment inside a front-matter list is skipped, colon or not; the list goes on after it."""

    def test_a_comment_with_a_colon_does_not_end_the_governs_list(self):
        sys.path.insert(0, str(CHECK.parent))
        from ontology_lib import parse_ontology
        self.write("ontology/orders.md", COMMENTED_ONTOLOGY)
        o = parse_ontology(self.root / "ontology" / "orders.md")
        self.assertEqual(o["governs"], ["src/**", "mcp/**", "tests/**"])
        self.assertEqual(sorted(o["declarations"].values()), ["Item", "Item", "Item", "Order"])
        self.assertNotIn("# enforcement found by the 2026-10-24 pass", o["meta"])


if __name__ == "__main__":
    unittest.main()
