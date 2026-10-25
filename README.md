# Ontology-driven development for Claude Code and Codex

Choose your agent: [Claude Code](#claude-code-install) or
[Codex](codex/README.md). Both use the same ontology checker. Claude includes
the observer pane; Codex returns findings in the conversation through native
lifecycle hooks.

## ODSC AI West 2026 workshop

The [workshop notebooks](notebooks/README.md) demonstrate how explicit domain
definitions guide implementation and counterexamples:

- [A river reading](notebooks/01_river_reading.ipynb): gauge, units, datum and time.
- [One person isn't one row](notebooks/02_one_person_one_count.ipynb): identity,
  relationships and reporting grain.

Both use synthetic data and run without API keys. Each includes a versioned
ontology, an agent prompt, deliberate counterexamples and an authored reference
repair. Setup, saved outputs and facilitator guidance are included.

## Skill and observer plugin

One plugin, two parts:

- **The `ontology-driven-dev` skill** (`skills/ontology-driven-dev/`). It gives a repo a written ontology in `ontology/<domain>.md`: entities, relationships, invariants with the gate that enforces each, vocabulary, intent and scope. Its scripts query the ontology, validate it, and run as hooks that stop a change to governed code when the ontology was not updated with it.
- **The `ontology-observer` mod** (`hooks/`). A pane beside the chat that shows what those checks saw: each rule by group, the files the last edit touched, and an issue card for each open problem, with Fix it, Explore issue and Leave it.

## Claude Code install

At the prompt of a terminal session:

```
/plugin install ontology-observer --marketplace MuddyBootsCode/muddybootscode-odscai-2026
```

Answer `y` to add the marketplace, then pick a scope.

From a shell:

```
claude plugin install ontology-observer --marketplace MuddyBootsCode/muddybootscode-odscai-2026
```

In the desktop app, where `/plugin` does not run: click + next to the prompt box, then Plugins, Add marketplace with `MuddyBootsCode/muddybootscode-odscai-2026`, then Add plugin.

## Use

1. In your repo, ask Claude to set up the ontology. The skill reads the schema, interviews you for intent, vocabulary and scope, writes `ontology/<domain>.md`, and installs the hooks with `scripts/install.sh`.
2. Open the pane with `/ontology`.

The pane reads `.claude/ontology-state.jsonl`, which the checker scripts write on every check. Without that file the pane is empty.

## What raises an issue card

- A change to a type the ontology maps to an entity.
- A change to the file that enforces a rule (its gate).
- A problem in the ontology file: malformed, or a rule with no gate.
- A rule's test that failed or did not run after the change.

A gate-file card names the file, the function and lines that changed, the diff, and why the rule was flagged. Every rule whose gate names the file is flagged. A rule whose gate names a different function of that file is listed after the direct hits, because its gate may call the changed code. Naming the function needs `node` and a `typescript` package in the repo's `node_modules`, or `ONTOLOGY_TYPESCRIPT_DIR` pointing at one. Without them the card names the file and lines only.

The per-edit check runs on Claude's own edits. An edit saved in your editor is seen by the end-of-turn and commit checks.
