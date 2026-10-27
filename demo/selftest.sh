#!/usr/bin/env bash
# Pre-talk check. Replays every step of the demo that does not need Claude, in a
# scratch copy, and stops at the first one that misbehaves:
#
#   reset -> compose up -> tests green -> install skill -> reference ontology
#   validates -> E1 edits block the per-edit and Stop checks -> OFFLINE.md:
#   red test, reconciliation query, seed fix, commit blocked, ontology
#   updated, commit passes.
#
# Needs Docker running and the neo4j:5-enterprise image present. Leaves the
# container running for the real demo. The real copy (~/Projects/land-title)
# is not touched: this runs in $SELFTEST_DIR (default /tmp/land-title-selftest).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$(cd "$HERE/.." && pwd)"
export DEMO_DIR="${SELFTEST_DIR:-/tmp/land-title-selftest}"
CHECK=.claude/skills/ontology-driven-dev/scripts/ontology_check.py
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
expect_block() { # run a checker command, require exit 2
  set +e; "$@" >/dev/null 2>/tmp/selftest-err; local rc=$?; set -e
  if [ "$rc" -ne 2 ]; then echo "expected exit 2, got $rc:"; cat /tmp/selftest-err; exit 1; fi
  echo "blocked (exit 2), as expected"
}

step "reset into $DEMO_DIR"
bash "$HERE/reset.sh" >/dev/null
cd "$DEMO_DIR"

step "neo4j up"
docker compose up -d >/dev/null 2>&1
for _ in $(seq 1 45); do
  docker exec land-title-neo4j wget -qO- http://localhost:7474 >/dev/null 2>&1 && break
  sleep 2
done

step "tests green before the ontology"
uv run pytest -q 2>&1 | tail -1

step "install the skill, drop in the reference ontology, validate"
bash "$PLUGIN/skills/ontology-driven-dev/scripts/install.sh" >/dev/null
rm ontology/EXAMPLE.md
cp "$HERE/reference/land-title.md" ontology/land-title.md
sed -i '' 's#| (example) | EXAMPLE.md | see front matter |#| Land and title | land-title.md | cypher/**, landtitle/**, tests/** |#' ontology/README.md
python3 $CHECK --validate
git add -A && git commit -q -m "Add the land-title ontology and its hooks"

step "E1: current_owner on Well blocks the per-edit check"
python3 - <<'PY'
import pathlib
m = pathlib.Path("landtitle/model.py"); m.write_text(m.read_text().replace("    spud: date\n", "    spud: date\n    current_owner: str | None = None\n", 1))
PY
expect_block sh -c "echo '{\"tool_input\":{\"file_path\":\"$PWD/landtitle/model.py\"}}' | python3 $CHECK --touched"

step "E1: the Stop check blocks once, then passes through"
expect_block sh -c "echo '{}' | python3 $CHECK --changed --stop"
echo '{"stop_hook_active": true}' | python3 $CHECK --changed --stop >/dev/null 2>&1 && echo "passed through on the second stop"
git checkout -q -- .

step "OFFLINE 1: the new test is red on T-104"
cat > tests/test_interests.py <<'EOF'
from landtitle import queries


def test_current_interests_on_every_tract_sum_to_one(graph):
    assert queries.unbalanced_tracts(graph) == []
EOF
cat >> landtitle/queries.py <<'EOF'


def unbalanced_tracts(driver: Driver, tolerance: float = 1e-9) -> list[tuple[str, float]]:
    """Tracts whose current OWNED_BY interests do not sum to 1.0. Expected: none."""
    records, _, _ = driver.execute_query(
        """
        MATCH (t:Tract)-[r:OWNED_BY]->(:MineralOwner)
        WITH t.tract_id AS tract_id, round(sum(r.interest), 6) AS total
        WHERE abs(total - 1.0) > $tolerance
        RETURN tract_id, total ORDER BY tract_id
        """,
        tolerance=tolerance,
    )
    return [(r["tract_id"], r["total"]) for r in records]
EOF
if uv run pytest tests/test_interests.py -q >/tmp/selftest-red 2>&1; then echo "expected red"; exit 1; fi
grep -E "T-104" /tmp/selftest-red | head -1

step "OFFLINE 2: seed fixed, green"
sed -i '' "s/{interest: 0.3,  since: 'TE-007'}/{interest: 0.4,  since: 'TE-007'}/" cypher/seed.cypher
uv run pytest -q 2>&1 | tail -1

step "OFFLINE 3: commit blocked until the ontology gains the rule"
git add -A
if git commit -q -m "Reconcile fractional interests per tract" >/dev/null 2>&1; then echo "expected the commit-msg hook to block"; exit 1; fi
echo "blocked, as expected"

step "OFFLINE 4: invariant added, commit passes"
python3 - <<'PY'
import pathlib
p = pathlib.Path("ontology/land-title.md"); t = p.read_text()
t = t.replace("- Every Well sits under at least one Lease.\n",
  "- Every Well sits under at least one Lease.\n- The current OWNED_BY interests on a Tract sum to exactly 1.0. [gate: `landtitle/queries.py:unbalanced_tracts`; `test_current_interests_on_every_tract_sum_to_one`]\n")
t = t.replace("## Changelog\n\n", "## Changelog\n\n- 2026-10-27 — Added the interest-sum invariant after T-104 was found at 0.9.\n")
p.write_text(t)
PY
git add -A && git commit -q -m "Reconcile fractional interests per tract" 2>/dev/null
git log --oneline | head -1

step "all steps behaved; neo4j left running"
