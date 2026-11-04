# Ontology-driven development for Codex

This plugin reads a project's domain ontology, reports governed changes, and
asks Codex to review unresolved findings before finishing a turn. It uses the
same Python checker as the Claude plugin. The original skill and observer pane
remain unchanged.

## Install

Requires Git, Python 3.10+ available as `python3`, and a Codex release with
plugins and lifecycle hooks. The CLI commands below were checked against
Codex CLI 0.159.2. macOS/Linux are the initial target; Windows is unverified.

From a shell, for the published release:

```bash
codex plugin marketplace add MuddyBootsCode/muddybootscode-odscai-2026
codex plugin add ontology-driven-dev@muddybootscode-odscai-2026
```

To try the development branch before merge:

```bash
codex plugin marketplace add MuddyBootsCode/muddybootscode-odscai-2026 --ref codex/ontology-review-evidence
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
| After patch or shell tools | Validate and recheck the working-tree diff; surface findings as direct warnings and context. |
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
It is not loaded in Codex. The browser observer below provides a separate local dashboard; it is not an
embedded Codex pane.

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

## Review and executable evidence

The change checker now records `review` independently from per-rule `verification`.
A relevant ontology acknowledgment does not mark a test passed. Record an explicit
acceptance command with the shared `ontology_verify.py --rule 'unique rule text' --
COMMAND ARGS...` runner. In Codex set `ONTOLOGY_STATE` to the absolute target
`.codex/ontology-state.jsonl`; ignore it and `.codex/ontology-state.evidence/`.
Evidence includes the command, exit status, output and source fingerprint. Changed
source or tests invalidate it. CI must run its own acceptance tests; the review
check's exit status alone does not enforce verification. See the shared
[workflow reference](../skills/ontology-driven-dev/references/review-and-verification.md).

Unavailable Git comparisons fail explicitly in the shared checker, including
missing HEAD, invalid merge bases and failed enumeration. No clean verdict is
available until the comparison works.

## Live browser observer

Start the observer from your plugin checkout (Python standard library only):

```bash
python3 codex/scripts/ontology_observer.py --root /absolute/path/to/project --open
```

It opens a token-bearing loopback launch link and refreshes every three seconds.
Keep the process running. Use `--state /absolute/path/to/ontology-state.jsonl` when
hooks or manual checks use a custom state path. The default is the target project's
`.codex/ontology-state.jsonl`. Ignore the state file and its `.evidence/` sibling.

Cards distinguish **Passed**, **Failed**, **Stale**, **Not run**, and **Unable to
check** (including interrupted runs). Each card shows the rule, its confirmation
status, governed files, command, output and last output time. Source edits invalidate
old results. Lost connections visibly mark the display outdated. **Copy fix request**
places the rule and output on your clipboard for pasting into the appropriate chat;
it does not send a message automatically. Hook failures also emit `systemMessage`
warnings without depending on the agent's narration; host rendering can vary.

To enable **Run check**, add an explicit, reviewed argv list for each selected rule
to the project's `ontology/checks.json`. Domain and rule text must match exactly:

```json
{
  "checks": [
    {
      "domain": "orders",
      "rule": "An Order must have at least one Item.",
      "command": ["python3", "-m", "pytest", "tests/test_orders.py", "-q"]
    }
  ]
}
```

Commands execute from the target repository root, without shell expansion, only
when clicked. Review **Command and evidence** before running a newly added command.
The browser cannot supply arbitrary commands; the server validates the current
configuration and allows one check at a time. A missing or invalid configuration
disables running. Gate annotations are never executed. Keep the launch link private;
the service binds only to `127.0.0.1` and checks its token, Host and Origin.

This observes configured acceptance checks, not every possible test in your project.
Ignored dependency changes, external systems and environment changes are outside
the source fingerprint: rerun checks when those change. A local command has your
normal filesystem/network permissions; use only trusted repositories and commands.

Rendered disposable fixture: [failed check with output](observer/screenshots/failed.png)
and [repaired check after reload](observer/screenshots/repaired.png).
