# Domain authority, review, and verification

These are independent facts:
- Domain status: inferred, confirmed, or disputed. Existing code describes behavior,
  not authority. Use `(inferred)` until an attributable domain source confirms a rule.
  Record `[source: document section or code path]` and `[confirmed: name YYYY-MM-DD]`.
  A disputed rule stays provisional; record competing claims in Disagreements.
- Review: a relevant ontology edit acknowledges a change. It is not proof of correctness.
  A changelog acknowledgment should name the entity or gate file and explain the decision.
- Verification: an explicitly selected executable acceptance check ran on this snapshot.
  A gate annotation, review note, skip reason, or assertion that tests passed is not evidence.

## Discovery and focused reassessment

The interview serves the developer and is informed by domain expertise. Ask what
sources they can supply and who can resolve ambiguity. Never assume the developer
lacks expertise; do not invent confirmation or require another person unnecessarily.
For new projects, draft intent, vocabulary, entities, candidate rules and acceptance
cases before code. Empty governs and missing gates are explicit coverage warnings.
When evidence changes, revisit affected rules and preserve superseded decisions in
the Changelog rather than restarting the entire interview.

## Open questions

Use this optional section only for unresolved decisions affecting behavior. Each
bullet names the rule, the specific question, its source/trigger, who can answer,
and whether implementation is blocked or what provisional behavior is allowed.
Example (illustrative, not confirmed domain truth):

- YYYY-MM-DD — Person identity: does a shared email establish the same person?
  Source: importer merges by email. Answerer: developer or identity-domain owner.
  Impact: blocks automatic merging; provisionally retain separate records for review.

Confirmation of a principle does not resolve every implementation question. Do not
silently resolve questions during coding. When answered, update the rule and source,
move the resolution to Changelog, and remove it from the active question list.
`ontology_query.py section "Open questions"` retrieves these decisions. Summary lists
how many are open. No question is required when the decision is already established.

## Execute an acceptance check

Resolve the scripts from the installed skill; run from the target repository root.
Set ONTOLOGY_STATE to the absolute `.codex/ontology-state.jsonl` path in Codex.

```bash
python3 <scripts>/ontology_verify.py --rule 'unique invariant text' -- python3 -m pytest tests/test_identity.py -q
python3 <scripts>/ontology_check.py --changed
```

`--domain` disambiguates matching rule text. The runner never interprets Markdown
as shell commands: select and review the command yourself. It records command,
exit code, combined output, rule definition and a content fingerprint. It does not
prove test quality or that every annotated gate ran. Run a meaningful counterexample
that fails, repair it, and rerun the acceptance check. Do not use `true` or an unrelated
passing test to claim a rule is verified. One run records evidence for one selected
rule; repeat for other rules when relevant.

Evidence states: not_run, passed, failed, stale, interrupted, unavailable.
Verification requires regular-file sources: symlinks and submodules are rejected
until a reliable snapshot boundary can be established. Missing or altered output
logs make passing evidence unavailable.
A later source/test/ontology edit invalidates prior evidence. Ignored dependencies,
external services and environment changes are not fingerprinted; rerun after changes
to them. Staged comparisons label a passing worktree run worktree_only because the
index is not what the command executed. Evidence is local, editable audit material,
not signed attestation. CI must execute checks in its own clean environment.

Evidence and output live beside ONTOLOGY_STATE in `ontology-state.evidence/`.
Ignore that directory and ontology-state.jsonl in the target repo. Logs can contain
command output; do not commit them by default. Verification never establishes domain
authority, and changing the ontology never manufactures passing evidence.
