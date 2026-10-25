# Workshop Notebooks Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check in two executable lessons that trace ontology definitions to code and counterexamples.

**Architecture:** Percent-cell Python sources generate standalone notebooks. The builder embeds canonical ontology Markdown. Standard-library tests exercise the same lesson functions; Jupyter executes the complete generated notebooks.

**Tech Stack:** Python 3.10+, unittest, Jupyter/nbformat/nbclient for authoring verification.

**Spec:** `docs/superpowers/specs/2026-10-25-workshop-notebooks-design.md`

## Global Constraints

- No API keys or network calls in notebook code. Synthetic data and fixed clocks.
- Named rule, rationale, function and test links must be visible.
- Reference examples are authored; actual agent outcomes are recorded separately.
- Keep existing skill, hooks, presentation and participant kit unchanged.

## Review Focus

- Unavailable comparison must not silently become below threshold.
- Exact freshness boundary, future/naive timestamps and nonfinite values.
- Missing employment must not exclude a graduate.
- Repeated identity and conflicting completion IDs.
- Generated notebooks must include the current ontology and run without local files.

## Task 1: Domain rules and executable lessons

Files: `notebooks/ontology/*.md`, `notebooks/lessons/*.py`, `notebooks/tests/test_lessons.py`.

Interfaces: `compare_reading(reading, threshold, now)` returns status/reason/value;
`count_graduates(completions, institution_id)` and `count_completions(...)` return integers.

- [x] Write behavioral tests for conversions, context mismatch, freshness, invalid inputs, cohort membership and repeated relationships; observe failures before lesson implementation.
- [x] Implement ontology documents and minimal reference functions with deliberate faulty candidates.
- [x] Run `python3 -m unittest discover -s notebooks/tests -v`; 19 tests pass after review fixes.

## Task 2: Reproducible participant notebooks and repository delivery

Files: `notebooks/build.py`, two `.ipynb` files, `notebooks/README.md`, `notebooks/requirements.txt`, `notebooks/FACILITATOR.md`, root README workshop links.

- [x] Build notebook JSON from sources and embed the canonical ontology documents.
- [x] Execute both notebooks in fresh Jupyter kernels and validate notebook schemas.
- [x] Check expected mistakes and repairs, inspect rendered HTML structure/outputs, and verify source synchronization. Local browser visual inspection was unavailable.
- [x] Run existing Python tests and notebook tests; review scope and public content. See `notebooks/VERIFICATION.md` for the unavailable observer runtime.
- [x] Commit and push the workshop branch, create a reviewable PR, and reread published files. PR #1 is open; both published notebook blob hashes match local files and retain executed outputs. Review/merge remains pending.
