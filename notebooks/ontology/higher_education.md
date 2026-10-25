---
domain: workshop-higher-education
version: 1
governs:
  - "notebooks/lessons/one_person_one_count.py"
---

# Higher education: one person is not one row

## Intent

Answer: **How many distinct people have a completed degree record at the selected
institution in the supplied snapshot?** Define the report before writing its query.
This classroom definition is specific to this report, not all higher-ed reporting.

## Entities and relationships

- **Person**: one resolved individual, keyed by `person_id`.
- **Institution**: one institution, keyed by `institution_id`.
- **Completion**: one degree record, keyed by `completion_id`, with `status` equal
  to `completed`, `in_progress` or `withdrawn`.
- **Employment**: one job record, keyed by `job_id`, linked to a person.
- `(Person)-[HAS]->(Completion)`: zero or more completions per person;
  each completion belongs to exactly one person.
- `(Completion)-[AT]->(Institution)`: exactly one institution per completion.
- `(Person)-[HAS]->(Employment)`: zero or more jobs per person;
  each employment record belongs to exactly one person.

## Vocabulary and rationale

**Graduate**, in this report, is a person with at least one completed degree
record at the selected institution. **Reporting unit** is what contributes one
to the answer. Here it is a person, not a degree, job or joined profile row.
Two degrees and two jobs may produce four joined rows for the same person.
The relationships explain the multiplication; the reporting definition explains
why those rows still contribute one.

## Invariants

- **EDU-01 — One person, one contribution:** Each qualifying `person_id` contributes
  exactly one, regardless of repeated rows, degrees or jobs.
  [gate: `HigherEducationTests.test_edu_01_people_are_not_profile_rows`; code: `count_graduates`]
- **EDU-02 — Membership is explicit:** Only `status == "completed"` records at the
  selected `institution_id` qualify. Identity fields must be nonempty strings.
  Identical copies of a completion count once; contradictory records sharing a
  `completion_id` raise `ValueError` rather than silently picking one.
  [gate: `HigherEducationTests.test_edu_02_institution_and_completion_define_membership`; code: `qualifying_completions`]
- **EDU-03 — Employment is not membership:** Adding, removing or duplicating job
  records cannot change this graduate count. No recorded job means unknown
  employment in this snapshot, not no graduate or proven unemployment.
  [gate: `HigherEducationTests.test_edu_03_missing_jobs_do_not_remove_people`; code: `graduate_report`]
- **EDU-04 — Another question, another unit:** A completion report counts distinct
  qualifying `completion_id` values. It can legitimately exceed the people count.
  Preserve the graduate definition when adding this separate report.
  [gate: `HigherEducationTests.test_edu_04_changed_report_has_changed_unit`; code: `count_completions`]

## Function and test links

Implementation: `notebooks/lessons/one_person_one_count.py`.
Behavioral checks: `notebooks/tests/test_lessons.py`, `HigherEducationTests`.
Notebook counterexamples: `check_education_rules(candidate)` links observed failures
to rule IDs. Run `python3 -m unittest discover -s notebooks/tests -v`.
The mapping is authored and reviewable; it is not automatic evidence of complete
coverage. Required CI and branch protection are separate workflow decisions.

## Scope

All records and institutions are synthetic. IDs are already resolved and compared
exactly. Counts describe only this supplied snapshot, with no reporting-period or
as-of-date filter. No universal alumni definition, identity resolution, inferential
employment rate, causal claim, institution ranking or real GradGraph data.

## Changelog

- 2026-10-25 — Initial person and completion reporting contracts.
