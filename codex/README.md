# Ontology-driven development for Codex

This plugin reads a project's domain ontology, reports governed changes, and
asks Codex to review unresolved findings before finishing a turn. It uses the
same Python checker as the Claude plugin. The original skill and observer pane
remain unchanged.

## Install

Requires Git, Python 3.10+ available as `python3`, and a Codex release with
plugins and lifecycle hooks. The CLI commands below were checked against
Codex CLI 0.159.2. macOS/Linux are the initial target; Windows is unverified.

From a shell, after this change is merged:

```bash
codex plugin marketplace add MuddyBootsCode/muddybootscode-odscai-2026
codex plugin add ontology-driven-dev@muddybootscode-odscai-2026
```

To try the development branch before merge:

```bash
codex plugin marketplace add MuddyBootsCode/muddybootscode-odscai-2026 --ref codex/ontology-plugin
codex plugin add ontology-driven-dev@muddybootscode-odscai-2026
```

For a local checkout, replace the first command with
`codex plugin marketplace add /absolute/path/to/muddybootscode-odscai-2026`.

Restart Codex after installation, open a project, and use `/hooks` in the CLI to
review and trust the plugin's three hooks. Installing a plugin does not grant
hook trust. In the desktop app, a trusted repository marketplace can also appear
in the Plugins Directory after restart; choose **Muddy Boots Code — ODSC AI 2026**
and install **Ontology-driven development**. Availability varies by surface.

This is a repository-distributed plugin. OpenAI currently excludes plugins
containing lifecycle hooks from the universal public directory.

## Use

Ask Codex: **“Use ontology-driven-dev to set up an ontology for this project.”**
For an existing ontology: **“Check my changes against the project ontology.”**

| Event | Behavior |
| --- | --- |
| Session start/resume/compaction | Validate and load the target project's ontology summary. |
| After patch or shell tools | Validate and recheck the working-tree diff; send findings as context. |
| End of turn | Request one corrective continuation for a failing check. If still unresolved on the repeated Stop, show a warning and let the turn end. |

Projects without an `ontology/` directory are left alone. Change comparison
requires a Git repository with an initial commit. The adapter uses the session's
working directory, never the installed plugin directory, to locate the project.
Place `ontology/` at the Git root and write `governs` globs relative to that root.
Nested ontology roots produce an explicit unsupported-layout finding; the shared
checker cannot safely compare their relative paths. Failed Git enumeration is
also reported instead of treated as a clean diff. Validation warnings remain
visible even when the validator returns success.

The checker records results in `.codex/ontology-state.jsonl`; an explicit
`ONTOLOGY_STATE` environment variable can override that path. Treat this as local
runtime output and exclude it from commits in the target repository.

Findings name the affected domain entity or rule and the evidence. Ask Codex to
fix a finding, investigate it, or leave it with an explicit reason. A recorded
skip is not a passing test.

## What is and is not checked

The shared engine validates ontology structure and detects changes to governed
entities, paired paths and annotated gate files. It compares the entire working
tree against HEAD, so findings may include changes made before this Codex turn.
It does **not** automatically execute the tests named in gate annotations.
Run the corresponding tests separately and retain their actual outcomes.

Post-tool feedback does not undo an edit. The Stop hook is bounded local feedback,
not a mandatory acceptance gate; hooks can be disabled, and runtime errors can
prevent them from checking. Required CI or release policy is a separate setup.
Use tracked copies of the shared checker scripts for CI, not the plugin cache.

The `/ontology` pane in `hooks/register.tsx` imports the Claude Code UI runtime.
It is not loaded in Codex. A persistent Codex visual dashboard would need its own
UI integration. This version reports findings in the conversation.

## Development checks

From the repository root:

```bash
python3 -m unittest discover -s codex/tests -v
python3 -m unittest discover -s skills/ontology-driven-dev/scripts/tests -v
python3 -m unittest discover -s notebooks/tests -v
```

`codex/tests` exercises the real adapter and checker in temporary repositories,
including rule-changing edits, repairs, malformed ontology and repeated Stop.
These tests do not replace a fresh-session test after installing and trusting
the plugin in Codex.

The Codex manifest explicitly selects `codex/hooks.json` and `codex/skills/`,
so Codex does not discover the Claude module at `hooks/hooks.json`. Shared scripts
and resources stay at `skills/ontology-driven-dev/` and ship in the same bundle.

Sources checked October 25, 2026:
[plugin packaging](https://developers.openai.com/plugins/build/plugins) and
[Codex hooks](https://learn.chatgpt.com/docs/hooks).
