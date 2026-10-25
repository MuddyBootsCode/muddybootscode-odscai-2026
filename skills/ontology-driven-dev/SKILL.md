---
name: ontology-driven-dev
description: Build, query, and enforce a domain ontology so an LLM works inside the rules of a codebase instead of guessing them. Use this whenever a repo has (or needs) an `ontology/` directory, when the user asks to "write the ontology", "define the domain", "set up the ontology workflow", "add gates", "install the ontology hooks", or when you are about to change a schema, data model, migration, or ETL step in a repo that has an ontology — read it first. Also use it when the user describes a graph-shaped domain (chains of ownership, reporting hierarchies, sensor pipelines) and wants the model to stop inventing joins, properties, or aggregation grains.
compatibility: Claude Code (hooks), any agent that can run Python 3 scripts. Git repo required for the change-detection hook.
---

# Ontology-driven development

The model doesn't need to remember the past. It needs to know where it is.

This skill gives a repo a written ontology — entities, relationships, invariants, vocabulary, intent, scope — that the model reads before it writes code, can query mid-task, and cannot drift away from without a hook stopping it. It is the method behind "give the model an ontology of the problem, not a memory of the past."

## Layout this skill expects

```
<repo>/
├── ontology/
│   ├── README.md                 # index: which domain file covers what
│   └── <domain>.md               # one per domain (see assets/ONTOLOGY.template.md)
├── .claude/
│   ├── settings.json             # hooks (see assets/hooks.settings.json)
│   └── skills/ontology-driven-dev/   # this skill, copied into the repo
└── .git/hooks/pre-commit         # optional git-side gate
```

If the repo gitignores `.claude/` (common; often only `.claude/hooks/` is tracked), put the three Python scripts under a tracked path such as `ontology/scripts/` and point `settings.json` and the git hooks there. The scripts depend only on each other and on the working directory, so they run from any folder. Git hooks and CI need the checker in a clean checkout; without it they print "checker not on this branch, skipped" and fail open.

Scripts in `scripts/`:

- `ontology_query.py` — the model's query surface. `summary`, `entity <Name>`, `term <word>`, `invariants`, `scope`, `section <Heading>`.
- `ontology_check.py` — the enforcer. `--validate` (structure), `--touched` (PostToolUse: did this edit hit a governed path?), `--changed` (Stop / pre-commit: governed files changed but ontology didn't → block).
- `install.sh` — copies hooks into `.claude/settings.json` and installs the git pre-commit hook.

## Phase 0 — Figure out where the repo is

Run `python3 scripts/ontology_check.py --validate` from the repo root.

- Exit 0 → ontology exists and is well-formed. Skip to Phase 3 (working inside it).
- "no ontology directory" → Phase 1.
- Validation errors → fix them first (the error names the section and file); then Phase 3.

Don't skip this. The whole point is that the model never starts from a blank page in a repo that already has rules.

## Phase 1 — Build the ontology

An ontology is a graph schema with intent attached. Graph people already write the first three parts as a schema with constraints; the last three are what nobody hands the model.

### 1a. Read the repo before asking anything

Look at, in this order: schema files (migrations, ORM models, Cypher constraints, `.sql`, `.prisma`, `schema.graphql`), the README, existing docs, and the test names. Pull out every noun that has a table, label, type, or class. That's the first draft of **Entities**. Every foreign key, relationship type, or join is the first draft of **Relationships**. Every `NOT NULL`, `UNIQUE`, constraint, or assertion in a test is a candidate **Invariant**.

### 1a-ii. Read the enforcement, not just the schema

A schema says what fields exist. The rules of the domain live in the code that consumes them and refuses, repairs or arranges what it is given. Before the interview, open every normalizer, validator, importer, layout builder, and renderer under the paths you intend to govern, and harvest four kinds of line. Each one is an invariant that already has a gate: the code you found.

1. **Refusals.** A thrown error, a failed validation, an early `return null`, a rejected import row. The condition is the rule. Write it as the positive statement the code protects ("an invoice total equals the sum of its lines"), not as the error text.
2. **Repairs.** A clamp, a `min`/`max` against a neighbour, a sort by date or position, a value snapped to a parent's range, a missing value filled from a sibling. These enforce a rule without ever stating it, and they are the ones the user assumes everyone knows. "The code moves a booking's start to the end of the booking before it" means "bookings for one room never overlap".
3. **Ordering and containment.** Any loop that walks entities by time, position or size and compares each to the previous one. The comparison is the rule, and the loop's key is the grain.
4. **Projection.** In a renderer or exporter, what is drawn or written relative to what: the container a box is drawn inside, the parent a label is attached to, the range a bar fills. Each is a relationship with a constraint, even when the stored document never names it.

For every entity, answer four questions from the code: what is it inside, what comes before it, what is it smaller or shorter than, and what does the code do when that is violated. One sentence per answer goes under **Invariants** with `[gate: <file>:<function>]` pointing at the enforcing code, marked `(inferred)` until the user confirms the wording. Write the sentence the way the domain says it, not the way the code does: no field names, no tolerances, under about twenty words; the code's detail goes in the gate note (see `references/writing-invariants.md`, "One sentence, the way the domain says it"). A field or list named after one kind of thing is not that kind of thing: say the kind in the domain's word and put the code's name in the gate note (see "A code name is not a domain word"). A rule the code enforces in two places gets both gates. A rule you expected and did not find goes in the interview as a question, not in the file as a fact.

Write the draft to `ontology/<domain>.md` using `assets/ONTOLOGY.template.md` as the shape. Mark every line you inferred rather than read with `(inferred)` so the user can see what to confirm.

### 1b. Interview for what the code can't tell you

The code shows what exists; it doesn't show what the system is *for* or what a word *means here*. Ask the user, briefly, for each of these and nothing else:

1. **Intent** — Who uses this and what question are they answering? ("A landman answers who owns what, under which lease, and is title clear.")
2. **The load-bearing level** — Is there one grain, chain, or ordering that everything else depends on? (A reporting grain. An ownership chain. A time order per sensor.) This becomes the first invariant.
   Then read back the rules harvested in 1a-ii, one line each, and ask only two things: which of these is wrong as worded, and which rule you know that the code does not enforce. The second list is the gate backlog.
3. **Vocabulary collisions** — Which ordinary words mean something specific here? ("Lease" is a mineral lease, never a rental. "Unit" is pooled tracts, not a measurement.) Also what a word does *not* mean — those are the lines the model needs most.
4. **Out of scope** — What does this system deliberately not do? This section does more work than any other; it is where scope creep dies.
5. **Silence and absence** — Does a missing row, gap, or null mean something? (A missed sensor interval is itself a reading.) The model's default is to interpolate or ignore; if the domain says otherwise, write it down.

Keep each answer to a line or two in the file. An ontology the model can read in thirty seconds is worth more than a complete one it skims.

### 1c. Governed paths

In the file's front matter, list the globs the ontology governs — the paths whose change should also change the ontology:

```yaml
governs:
  - "migrations/**"
  - "src/models/**"
  - "etl/**/*.py"
  - "cypher/constraints.cypher"
```

The `--changed` hook uses this list. Be specific; governing `src/**` makes the hook fire on every edit and the user will turn it off.

### 1d. Validate and install

```bash
python3 scripts/ontology_check.py --validate
bash scripts/install.sh
```

`install.sh` merges the hooks into `.claude/settings.json` (it won't clobber existing hooks) and appends to `.git/hooks/pre-commit` (validate) and `.git/hooks/commit-msg` (change gate). Tell the user what was installed and that the hooks can be removed by deleting those entries.

## Phase 2 — Derive the gates

Every invariant should have a mechanical check. The model is persuasive; the gate is not, and that asymmetry is the safety story. For each invariant in the ontology:

- **Schema gate** — can the database enforce it? (`NOT NULL`, unique constraint, Neo4j existence/uniqueness constraint.) If yes, write the migration and note the constraint name next to the invariant.
- **Data-quality gate** — can a query assert it after load? (Uniqueness at the grain, referential closure, time ordering.) Write it as a test or a dbt/Great Expectations-style assertion and reference it next to the invariant.
- **Reconciliation gate** — do counts in equal counts out? Add it for any pipeline step, independent of the pipeline that produced the data.
- **Test gate** — one test per invariant, written before the feature that touches it.

Record each gate in the ontology under the invariant it protects:

```
- Every Well has at least one Lease. [gate: migration 0042 `well_leases` PK (api_number, lease_id) + FKs; test_well_has_lease]
```

An invariant with no gate is a wish. Say so to the user and offer to write the gate.

## Phase 3 — Working inside the ontology (the daily loop)

This is the part that runs on every task once the ontology exists.

1. **Read first.** Before touching any file, run `python3 scripts/ontology_query.py summary`. If the task names an entity or a term, run `entity <Name>` or `term <word>` as well. The SessionStart hook prints the summary automatically, but query again for the specific thing you're about to change.
2. **Check scope.** If the task touches anything in **Out of scope**, stop and say so. Don't widen the system without the user saying it's in scope now — and if they do, the ontology changes first, then the code.
3. **Work from a ticket, not a conversation.** If the task doesn't already name an invariant it protects, an acceptance check, and an out-of-scope line, write those three lines before starting. "Done" means the acceptance check passes, not that the diff looks right.
4. **Change the ontology in the same commit as the schema.** If you add an entity, relationship, or rule to the code, add it to `ontology/<domain>.md` in the same change. The `--changed` hook will block a Stop or a commit where governed paths changed and the ontology didn't. That's deliberate: a stale ontology is worse than none, because the model trusts it.
5. **When a gate misses, the ontology is thin.** If a bug gets through every gate, the fix is not "more tests." Find the relationship or invariant the ontology didn't have, add it, and derive the gate from it. The ontology grows by its failures; it's the record of every mistake you've survived.

## When the hook blocks you

`ontology_check.py --changed` exits non-zero with a message like:

```
Governed paths changed but ontology/ did not:
  migrations/0043_add_tract_owner.py   (governed by ontology/oil-gas.md: migrations/**)
Update the ontology (entities / relationships / invariants) or add
`ontology-skip: <reason>` to the commit message (or ONTOLOGY_SKIP=<reason> in the environment) if this change is truly rule-neutral.
```

Three valid responses, in order of preference:
1. Update the ontology — usually a one-line addition under Entities, Relationships, or Invariants, plus a Changelog line.
2. The change is rule-neutral (a rename, a refactor that preserves every invariant) — say so to the user and use the skip marker. Don't use it silently.
3. The governed glob is too broad — narrow it in the front matter and tell the user.

Never edit the hook to make it pass.

## Querying the ontology (reference)

```bash
python3 scripts/ontology_query.py summary                 # intent + entity list + invariant count, all domains
python3 scripts/ontology_query.py --domain oil-gas entity Lease
python3 scripts/ontology_query.py term unit                # vocabulary lookup, case-insensitive
python3 scripts/ontology_query.py invariants              # every invariant with its gate (or MISSING GATE)
python3 scripts/ontology_query.py scope                    # the Out of scope section
python3 scripts/ontology_query.py section "Relationships"
```

Output is plain text sized to drop into context. If the repo has several domains, omit `--domain` to search all of them.

## What not to do

- Don't write the ontology as documentation. Documentation describes what was built; an ontology constrains what may be built. Every line should be something the model could violate.
- Don't let it grow past what the model can read in one go. Split by domain before it does.
- Don't put implementation detail in it (function names, file paths other than the `governs` list). Those change; the rules don't.
- Don't let a code name stand in for a domain word. A rule has to be true with its backticks removed; the code's name for a field or list goes in the gate note, and a collision between the two goes in Vocabulary.
- Don't bypass the hook. If it's firing wrongly, the `governs` list is wrong — fix that.

## Reference

- `assets/ONTOLOGY.template.md` — the file shape with every section and an example line in each.
- `assets/hooks.settings.json` — the hook entries `install.sh` merges in.
- `references/writing-invariants.md` — patterns for turning domain rules into checkable invariants (grain, chain, ordering, absence), with examples from monitoring, education, and land/title.
