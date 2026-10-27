# Offline: test-driven development against the ontology

No Claude, no network. One terminal in `~/Projects/land-title` with Neo4j up.
This assumes the ontology from the interview is in place (if not, see "If the
interview went sideways" in `README.md`).

The rule being added: **the current OWNED_BY interests on a Tract sum to 1.0.**
Nothing enforces it yet, and the seed has a tract that breaks it.

## 1. Write the test first

```bash
cat > tests/test_interests.py <<'EOF'
from landtitle import queries


def test_current_interests_on_every_tract_sum_to_one(graph):
    assert queries.unbalanced_tracts(graph) == []
EOF
uv run pytest tests/test_interests.py -q
```

Red, for the right reason: `AttributeError: module 'landtitle.queries' has no
attribute 'unbalanced_tracts'`. The function does not exist yet.

## 2. Write the query

```bash
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
uv run pytest tests/test_interests.py -q
```

Still red, now because the data is wrong:

```
AssertionError: assert [('T-104', 0.9)] == []
```

Say it out loud: the test caught a real fault in the seed that the three
existing tests never would have. T-104 shows 0.6 to Permian Minerals and 0.3
to Llano Royalty. Someone fat-fingered the 2022 assignment.

## 3. Fix the data, go green

```bash
sed -i '' "s/{interest: 0.3,  since: 'TE-007'}/{interest: 0.4,  since: 'TE-007'}/" cypher/seed.cypher
uv run pytest -q
```

`8 passed`.

## 4. Commit. The gate says no.

```bash
git add -A && git commit -m "Reconcile fractional interests per tract"
```

The commit-msg hook blocks it:

```
Governed paths changed in ways the ontology describes, and ontology/ did not follow:
  cypher/seed.cypher     gate file for invariant: Ownership of a Tract is the traversal ...
  landtitle/queries.py   gate file for invariant: Ownership of a Tract is the traversal ...
  landtitle/queries.py   gate file for invariant: The title chain of a Tract is ordered ...
Update the ontology (Entities / Relationships / Invariants + a Changelog line
that names the entity), bring a parity partner along, or mark the change
rule-neutral with `ontology-skip: <reason>` in the commit message ...
```

Both files it names are gate files for rules that already exist. The change is
not rule-neutral: it adds a rule. So the ontology moves in the same commit.

## 5. Add the rule and its gate to the ontology

Open `ontology/land-title.md`. Under `## Invariants` add:

```
- The current OWNED_BY interests on a Tract sum to exactly 1.0. [gate: `landtitle/queries.py:unbalanced_tracts`; `test_current_interests_on_every_tract_sum_to_one`]
```

Under `## Changelog` add, at the top:

```
- 2026-10-27 — Added the interest-sum invariant after T-104 was found at 0.9.
```

Then:

```bash
git add -A && git commit -m "Reconcile fractional interests per tract"
python3 .claude/skills/ontology-driven-dev/scripts/ontology_query.py invariants
```

The commit passes. The new rule is listed with its gate. The one rule still
marked `MISSING GATE` ("Every Well sits under at least one Lease") is the
closing line: an invariant with no gate is a wish, and that one is the
audience's homework.

## What this showed

- The test came before the code, and failed twice for two different reasons.
- The fix was data, not code. The test still stands as the gate.
- The commit could not land without the rule being written down where the
  model reads it. The next session of Claude Code starts knowing that rule.
