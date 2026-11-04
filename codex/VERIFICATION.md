# Ontology plugin 0.2.0 acceptance — 2026-11-03

Base: muddybootscode-odscai-2026 main 968bc11222b833384b7592545b0cd899b9511ae4.
Test surface: macOS, Codex CLI 0.159.2. Desktop lifecycle was not separately tested.

## Automated checks

- `ONTOLOGY_TYPESCRIPT_DIR=<GradGraph>/node_modules/typescript python3 -m unittest discover -s skills/ontology-driven-dev/scripts/tests`: 63 passed, no skips.
  Initial run without the TypeScript prerequisite passed 61 with 2 skips.
- `python3 -m unittest discover -s codex/tests`: 16 passed.
- `python3 -m unittest discover -s notebooks/tests`: 16 passed.

Regression tests first reproduced false success for missing merge base, corrupt index,
unborn HEAD and non-repository comparison. Independent review reproduced omitted type
changes, unresolved index entries, symlink-dependent evidence and missing/tampered
output. Corresponding regressions fail before fixes and pass afterward.

## GradGraph integration

Added a narrowly scoped provisional skills authorization ontology. Existing policies
are inferred from repository documentation/code and tests, not newly domain-confirmed.
An open question preserves the single-org MCP versus multi-membership UI uncertainty.
No production authorization source was edited.

Using the installed evidence runner in gradgraph-auth-platform:
- `.venv/bin/python -m pytest tests/test_gra724_entitlement_contract.py -q`: 25 passed.
- `.venv/bin/python -m pytest tests/test_gra833_service_principal.py -k 'service_principal_writes_nothing or service_principal_refuses_non_global_skills or service_principal_reads_global_skills' -q`:
  34 passed, 67 deselected, 1 existing httpx deprecation warning.

Actual command/exit/output/snapshot records were retained under the ignored
`.local/ontology/ontology-state.evidence/`, using the supported ONTOLOGY_STATE override
because the parent agent sandbox protects `.codex/` writes.

A disposable copy of the real entitlement module changed denial of an unauthenticated
caller into acceptance. Its negative test failed. A relevant ontology acknowledgment
then produced `review=acknowledged` with `verification=failed`. Restoring the original
implementation made the negative test pass. The source checkout was never regressed.

## Native lifecycle

Installed from a separate local marketplace checkout as version 0.2.0. Compared installed
hook/engine/runner files against the reviewed source. Reviewed and trusted each of the
three ontology hooks in the normal CLI `/hooks` interface; no trust bypass flags.
A broad trust-all action was rejected by automatic review; individual plugin-hook
review succeeded without changing unrelated hook trust.

Fresh session 01a1a2bb-6a11-7d53-a45d-016a4606fada in gradgraph-auth-platform:
- SessionStart injected the Skills authorization ontology, three unconfirmed rules
  and one open question into the actual session transcript.
- Agent ran only `pwd`. State records show PostToolUse and Stop checks at 12:45:58
  and 12:46:00 America/Chicago. No extra context was needed for the clean diff.

Fresh session 01a1a2bb-cc04-7491-b755-2ef21061f8f1 in the disposable counterexample:
- PostToolUse delivered the actual governed-change findings.
- Stop injected one corrective hook prompt into the session transcript.
- Agent reported the intentionally unresolved finding; repeated Stop allowed completion.
  The adapter's separate repeated-Stop warning payload is unit-tested; the CLI JSON
  stream does not expose that systemMessage separately.

Other installed components emitted existing warnings about Linear OAuth, icon paths,
and a clamped user SessionEnd timeout. They did not prevent ontology acceptance.

## Limits

Review exit 0 is not an executable verification gate. CI must explicitly run meaningful
acceptance tests. Evidence records are editable local audit data, not signed attestations.
Ignored dependencies, external services and environment changes require a rerun.
Symlink-backed sources and submodules are rejected for verification. Passing worktree
evidence is labeled worktree_only for staged comparisons. No production deploy, merge,
remote publication or claim of complete GradGraph ontology coverage was made.


# Ontology plugin 0.3.0 observer acceptance — 2026-11-04

- Shared suite: 64 passed with the TypeScript prerequisite enabled, no skips.
- Codex suite: 26 passed, including real loopback HTTP and command execution.
- Notebook suite: 16 passed (existing Python deprecation warning).
- Negative tests reproduced and then prevented completion/result races, lost
  multiline open-question context, and timeout descendants continuing to write.
- Independent review covered observer status correctness and token/Host/Origin/
  command allowlist boundaries; both reported findings were fixed with regressions.

In the rendered local browser observer, selected Run check for all three GradGraph
rules. The entitlement suite passed 25 tests for each of its two rule records; the
service-principal selection passed 34 tests (67 deselected, existing httpx warning).
The observer displayed the resulting rule status and retained output. These are
local checks of the narrow provisional ontology, not production acceptance.

A disposable UI fixture then displayed Not run → Running → Failed, including a
real AssertionError and exit 1. Editing its input displayed Stale; rerunning displayed
Passed, retained after browser reload. Copy fix request displayed its completion
message. Stopping the server displayed Disconnected, an outdated-results warning,
and disabled actions. This fixture exercises the display, not an Order domain acceptance test.
The existing shared evidence tests separately exercise fail/repair/source freshness.

Version 0.3 direct `systemMessage` warnings are verified at the hook protocol boundary.
Version 0.2 native CLI lifecycle acceptance above remains the native-host evidence;
0.3 has not been reinstalled or independently verified in a fresh desktop lifecycle.
The observer is a separate local browser page, not an embedded Codex mod.
