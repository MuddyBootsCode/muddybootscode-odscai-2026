# Prompts

Copy each block into Claude Code with `~/Projects/land-title` open. Each one
says what should happen so you know when to move on.

## P1. Run the skill on the existing codebase

```
Set up the ontology for this repo with the ontology-driven-dev skill. Read the
schema and code first, then interview me, asking your questions one at a time.
```

Expect: Phase 0 reports no ontology directory. Phase 1a drafts
`ontology/land-title.md` from `cypher/constraints.cypher` (six entities with
their keys), `cypher/seed.cypher` and `landtitle/queries.py` (five
relationships), `landtitle/model.py` (the `declarations:` mapping of `Well`,
`Ownership` and `TitleEvent` to entities), and the test names (candidate
invariants), with `(inferred)` on every line it guessed. Then it asks the five
questions in `INTERVIEW.md`.

When the interview is done it validates and runs `install.sh`. Confirm the
governed paths from `INTERVIEW.md` if it asks, and check the front matter has
the `declarations:` and `parity:` blocks from `INTERVIEW.md`: the skill's own
docs do not mention them, and the `Well → entity Well` card depends on them. One invariant should come out
with no gate: "Every Well sits under at least one Lease." Leave it that way;
it is the closing line of the offline piece. Then:

```
/ontology
```

The pane opens with the rules grouped. Nothing touched yet.

`demo/reference/land-title.md` is what a good interview produces. If the live
one drifts far from it, copy the reference in and move on; the prompts below
assume its gates and `declarations:`.

## P2. Break it: E1, put the owner on the Well

```
Add a current_owner property to Well so the drilling page doesn't have to walk
the title chain every time. Set it from the seed and return it from wells_under.
```

Expect, in order:

1. Claude queries the ontology first (the skill's Phase 3 says read before
   writing) and may already refuse, quoting the rule "never stored as a property
   on a Well". If so, that is the demo: ask it to do it anyway, "just for the
   drilling page", and continue.
2. The edit to `landtitle/model.py` goes through (PostToolUse runs after the
   write), and the per-edit check immediately feeds back:
   `Well (changed) → entity Well; gate file for invariant: Ownership of a Tract
   is the traversal ...`. The pane raises an issue card on `Well` naming the
   file and line, with Fix it, Explore issue and Leave it.
3. Edits to `cypher/seed.cypher` and `landtitle/queries.py` are flagged the same
   way, as gate files of the ownership rule.
4. When Claude tries to stop, the Stop hook blocks once more with the full list,
   a parity warning (`model.py` changed without `constraints.cypher`), and
   "Reopen the rules that name Well". It passes through on the second stop so
   Claude can report instead of looping.

Claude's honest answers, any of which is a good ending:

- Revert and do it the way the ontology says (P3).
- Keep it and update the ontology, which means changing the rule. Make the
  audience watch it try to write "ownership is a property on Well" into the
  Invariants section, then say why that is the wrong fix.
- `ontology-skip:` is not available here because the change is not rule-neutral,
  and Claude should say so rather than reach for it.

## P3. Do it the way the rule says

```
Revert that. Give the drilling page the owners of the tracts under each well by
traversal, as the ontology says, and keep the tests green.
```

Expect: `wells_under` or a new query joins `Lease -[COVERS]-> Tract` to
`owner_of`, no new property anywhere, a test, and a Changelog line in the
ontology because `queries.py` is a gate file. The per-edit checks still flag
(they always do on a gate file), but this time the ontology moves in the same
change and the Stop check passes.

## P4. Out of scope, no hook needed

```
Add monthly production volumes to each Well so we can compute royalty payments.
```

Expect: nothing edited. Claude reads `Out of scope`, says production and
revenue are out of scope, and asks whether that is changing. If you say yes,
the ontology changes first, then the code. This one needs no hook: it shows
the model reading where it is before it moves.
