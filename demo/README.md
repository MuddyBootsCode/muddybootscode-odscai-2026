# Demo: ontology-driven development on an existing codebase

Run of show for the talk. The codebase is `land-title/`, a small Neo4j graph of
operators, leases, tracts, wells and mineral owners with the county title chain
as `TitleEvent` nodes. It ships with no ontology and no hooks. The talk adds
them live, then breaks things.

| File | What it is for |
|---|---|
| `reset.sh` | Materialize `land-title/` as a fresh git repo at `~/Projects/land-title`. Run before every rehearsal and before the talk. |
| `selftest.sh` | Replay every step that does not need Claude, in a scratch copy with its own Neo4j on ports 7484/7697. Run the night before. |
| `INTERVIEW.md` | Your answers to the skill's five interview questions. |
| `PROMPTS.md` | The prompts to paste, with what should happen after each. |
| `OFFLINE.md` | The terminal-only TDD piece, for when the network is gone. |
| `reference/land-title.md` | The ontology a good interview produces. The safety net. |

## Before the talk

```bash
docker pull neo4j:5-enterprise          # needs network; do it at the hotel
bash demo/selftest.sh                   # every step, no Claude, ~1 minute, cleans up after itself
bash demo/reset.sh                      # fresh ~/Projects/land-title
```

Check the observer mod is installed at user scope (`/ontology` in any repo
shows a pane, empty is fine). The install line is in the top-level README.

## On stage

1. **Existing codebase.** In a terminal:

   ```bash
   cd ~/Projects/land-title
   docker compose up -d --wait
   uv run pytest -q
   ```

   Fifteen tests pass. Show `cypher/constraints.cypher`, `landtitle/queries.py`
   and the `OWNED_BY` edge in `cypher/seed.cypher`. Point out that nothing says
   what the system is for, what "lease" means here, or what is out of scope.

2. **Run the skill.** Open `~/Projects/land-title` in the desktop app and paste
   P1 from `PROMPTS.md`. It reads the schema and code, drafts the ontology, and
   asks the five questions. Answer from `INTERVIEW.md`. It installs the hooks.
   Open the pane with `/ontology`.

3. **Break it.** P2: put the owner on the Well. Watch the per-edit check, the
   card, and the Stop block. Then P3 (do it right) or P4 (out of scope),
   whichever the room wants.

4. **Offline.** Back in the terminal, `OFFLINE.md`: a new rule, test first, a
   planted data fault found, a commit the gate refuses until the rule is
   written down.

## Reset between runs

```bash
bash demo/reset.sh
```

It stops the Neo4j container, replaces the copy, and leaves one commit. The
next `docker compose up -d --wait` is step 1 again.

## If the interview went sideways

The prompts assume the gates and `declarations:` in `reference/land-title.md`.
If the live ontology drifted (a gate that names a different file, no
`declarations:` block), copy the reference in and validate:

```bash
cp <plugin-repo>/demo/reference/land-title.md ontology/land-title.md
python3 .claude/skills/ontology-driven-dev/scripts/ontology_check.py --validate
```

## Known edges

- `docker compose up -d --wait` blocks on the healthcheck in the compose file, so
  the first `pytest` never races a cold Neo4j. Plain `up -d` returns too early.
- `reset.sh` refuses to delete a directory it did not create, so a real
  `~/Projects/land-title` of your own is safe. Set `DEMO_DIR` to put the copy
  elsewhere.
- The checker writes `.claude/ontology-state.jsonl` on every check, and the
  skill's installer does not gitignore it, so `land-title/.gitignore` does.
- The function-level naming on gate-file cards needs TypeScript; this codebase
  is Python, so cards name the file and lines (match `unmapped`), which is what
  the per-edit messages show too.
