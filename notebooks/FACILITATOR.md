# Facilitator notes

Use the two notebooks after the workshop's introduction to unwritten domain rules.
They are designed as short live demonstrations; the agent exercise can be take-home
work. Rehearse timing before incorporating them into the deck. The existing casing
break/fix exercise remains separate.

## River walkthrough

Use the 13-cell annotated notebook one cell at a time. Read, predict, then run
the next code cell with **Shift + Enter**. Repeat: **meaning → code → check**.

1. **Cells 1–2:** start with recognizing forecast flooding before the water arrives.
   Distinguish observed stage, forecast crest and the local flood-stage threshold.
   Read FLOOD-01 and its rationale before showing the implementation. The rule is
   written context; Python does not translate the paragraph into a test.
2. **Cells 3–4:** ask for a prediction using **12 ft observed**, **18 ft forecast**
   and **13 ft flood stage**. Point out how the variable names preserve measurement,
   prediction, threshold and feet. Printing the values does not make a decision.
3. **Cells 5–6:** show the answer key: `forecast_flooding`, required by FLOOD-01.
   The four tests check forecast exceedance, equality, observed flooding and no
   threshold exceedance. Separate those expectations from `unittest` and `StringIO`,
   which run the checks and collect the report. This cell defines `run_gate`; it
   does not run the checks yet.
4. **Cells 7–8:** connect each branch of `assess_flood_risk` to its domain meaning,
   then run the gate. The baseline passes all four checks.
5. **Cells 9–10:** add the deliberate early return for an observed stage below
   flood stage. Ask which checks will fail. That exit skips the forecast, so the
   unchanged forecast-exceedance and equality checks fail. `assert not broken_passed`
   confirms the demonstration caught the bug; it does not approve the broken code.
6. **Cells 11–13:** remove the early exit and rerun the same gate. Show
   **PASS → FAIL → PASS**. The rule and expected answers stayed fixed; the code was
   repaired. Point from the failed test's FLOOD-01 label back to the written rule.

The observation and forecast are synthetic classroom values. The fixture assumes
the same point, datum and units, finite values, and an accepted forecast for the
relevant near-term window. This function does not validate those preconditions,
produce a hydrologic forecast or issue an official warning. Do not interpret
`no_threshold_exceedance` as safe. Discharge and rating curves provide vocabulary
context; this lesson does not calculate them.

The test cases are independent of the displayed inputs in Cell 4. Changing those
inputs does not change the acceptance criteria. The notebook captures the expected
test failures so a clean **Restart Kernel and Run All Cells** replay reaches the
repair. Ask what additional rules would be needed for stale or missing forecasts,
the wrong forecast point, or mismatched height references.

## Higher-education walkthrough

1. Ask the reporting question, then have the audience count the two qualifying people.
2. Draw Person → Completion → Institution and Person → Employment. State cardinalities.
3. Show why two degrees times two jobs produce four rows for Ava; Ben adds one row.
4. Ask the agent to identify the reporting unit and membership rules before coding.
5. Run checks with another degree, no jobs and repeated jobs. Tie each result to EDU-01..03.
6. Change the question to completed degrees. EDU-04 gives the separate answer of three.
   This changes the report definition; it does not justify weakening the graduate tests.

## Optional controlled agent comparison

This is an experiment protocol, not a claim that an experiment has already run.
No observations have been supplied with these reference notebooks.

Use the same model/version/settings, initial task, fixtures, tool access and time
budget in two fresh sessions. Provide the canonical ontology only to the context
arm. Hold the acceptance tests fixed and keep them hidden from both candidates
until their first implementations are saved. Neither candidate should see the
reference repair. If you reveal failed tests for a repair round, do so equally.

Suggested initial tasks:

- River: "Assess the supplied observed stage and forecast crest against this
  location's flood stage. Implement
  `assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft)` returning
  `observed_flooding`, `forecast_flooding`, or `no_threshold_exceedance`.
  Inputs are prevalidated for the same point, datum and units, with an accepted
  near-term forecast. Explain your interpretation. Use only the Python standard
  library; do not calculate a forecast or issue an official warning."
- Higher education: "Count people with a completed degree at North in the supplied
  snapshot. Implement `count_graduates(completions, institution_id)` and explain
  your interpretation. Use only the Python standard library."

The ontology arm receives the same task plus the complete domain file. The difference
is supplied domain information, not merely the word 'ontology'. To compare ontology
structure with ordinary prose, add a third arm containing the same facts in prose;
otherwise this experiment cannot isolate the effect of ontology formatting.

Save this record for every attempt:

| Field | Observed value |
|---|---|
| Date, model/version, settings, tool access | |
| Initial prompt and exact ontology revision/hash | |
| Candidate code and explanation | |
| Rule IDs passed/failed on first implementation | |
| Assumptions or questions raised | |
| Repair prompts, code changes and rerun results | |

Record every outcome, including success without ontology context. One paired run
describes that run; repeated controlled runs would be needed for broader claims.
Neither an agent explanation nor a rule-to-file link proves that a test executed.
Observed test results provide the execution evidence.

## From checks to enforcement

The included unittest command runs the behavioral checks and exits nonzero when
one fails. A local notebook displays feedback. A required CI check and an actual
release dependency would enforce workflow acceptance; these notebooks do not
configure those policies. Review changes to definitions and expected outcomes as
carefully as changes to implementation.
