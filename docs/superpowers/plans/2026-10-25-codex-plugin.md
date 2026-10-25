# Codex ontology plugin implementation plan

Goal: let workshop attendees use the existing ontology checker from Codex.

Design: add a Codex manifest and marketplace entry at the repository root.
Use a separate Codex skill and lifecycle adapter; import the existing Python
checker by path without changing the Claude plugin or duplicating its engine.
Codex receives findings in the conversation. The Claude pane is not portable.

Alternatives: a skill alone loses automatic lifecycle feedback; rewriting the
Claude pane as an MCP app would be a separate UI project. A thin hook adapter
provides the useful workflow with the smallest shared-code surface.

- [x] Exercise real checker behavior in temporary Git repositories: session
  context, governed changes, repairs, malformed ontology, repeat-stop handling,
  directories with spaces, missing ontology and relocated plugin bundles.
- [x] Add `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`,
  `codex/hooks.json`, `codex/scripts/ontology_hook.py`, and the Codex skill.
- [x] Document installation, hook trust, available behavior and limitations.
- [x] Run adapter tests, existing Python tests, skill validation and Codex
  marketplace discovery; inspect the final diff for unrelated changes.

Constraints: Python 3.10+, Git, no additional dependencies. Do not change the
original skill implementation, Claude pane, notebooks, participant kit or deck.
Do not claim automatic hooks are mandatory CI or that static gate references
prove tests ran. Hook failures must be visible; Stop must not loop indefinitely.
Publishing and installing into the user's active environment are separate gates.

Verification: 16 adapter tests passed; the existing engine suite ran 43 tests
with two skips; all 19 notebook tests passed. Skill validation passed using the
existing notebook virtual environment (system Python lacks PyYAML). Codex
0.159.2 `plugin/read` parsed the repository marketplace, skill and three hooks,
with availability AVAILABLE and installed=false. Hook execution in a fresh
installed and trusted Codex session remains a separate acceptance check.

Sources checked October 25, 2026:
- https://developers.openai.com/plugins/build/plugins
- https://learn.chatgpt.com/docs/hooks
- Installed Codex CLI 0.159.2 help.
