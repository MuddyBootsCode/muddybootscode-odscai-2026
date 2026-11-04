# Ontology Evidence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** Separate review from verification and make unavailable checks explicit.
**Architecture:** Shared stdlib checker plus explicit evidence runner, used by Codex hooks.
**Tech Stack:** Python 3.10+, Git, Markdown, Codex CLI.
**Spec:** ../specs/2026-11-03-ontology-evidence-design.md

## Global Constraints
- Preserve existing runtime records with additive fields.
- Never execute gate annotation text automatically.
- Preserve user edits; isolate intentional regressions.
- Hook trust is a separate acceptance gate.

## Review Focus
- Invalid merge bases, missing HEAD and corrupt indexes must not pass.
- Passing evidence must become stale after a source or test edit.
- Failed or interrupted commands must not leave old passing evidence current.
- Ontology acknowledgment must never manufacture passing evidence.
- Provisional domain claims and open questions must remain visible.

### Task 1: Shared Git failures
- [x] Add real-repository failure tests in scripts/tests/test_ontology_check.py.
- [x] Observe failures, add strict Git comparison handling in ontology_check.py.
- [x] Run shared suite.

### Task 2: Review and evidence
- [x] Add tests for acknowledged-but-unverified, command failure, passing command,
  stale evidence, unknown/ambiguous rule, and changes during execution.
- [x] Add ontology_evidence.py for snapshot/storage/status and ontology_verify.py
  for explicit command execution; report per-rule evidence in checker records.
- [x] Preserve evidence warnings through Codex Stop/PostToolUse.
- [x] Run shared and Codex suites.

### Task 3: Discovery and integration
- [x] Update both skills, template and README for authority, open questions,
  provisional projects, explicit verification and CI limitations.
- [x] Add narrow GradGraph ontology with cited rules and provisional authority.
- [x] Run real acceptance tests and checker in GradGraph; run failing counterexample
  in an isolated copy and retain output.
- [x] Install local package and exercise fresh native lifecycle where available.
- [x] Independent review and final verification; record observed/unobserved gates.

## Execution record

All three tasks implemented inline. Independent reviewer found type-change, symlink
and missing-output issues; each received a failing regression and fix. The follow-up
unmerged-index test also failed before the fix. Full results: codex/VERIFICATION.md.

Implementation choices: explicit acceptance runner instead of automatically executing
gate annotations; reject symlinks/submodules rather than overclaim their snapshot;
staged checks never inherit worktree passing status. These narrow the verification
claim; projects relying on those layouts need separate acceptance setup.
