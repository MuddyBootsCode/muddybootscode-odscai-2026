# Facilitator notes

Use the two notebooks after the workshop's introduction to unwritten domain rules.
They are designed as short live demonstrations; the agent exercise can be take-home
work. Rehearse timing before incorporating them into the deck. The existing casing
break/fix exercise remains separate.

## River walkthrough

1. Show `2.4` and ask what it measures. Reveal the gauge, unit, datum and timestamp.
2. Read the domain statements before the function. Explain why those relationships
   determine whether comparison is meaningful.
3. Ask the audience to predict the raw-number comparison and then the unit-aware answer.
4. Run the named counterexamples. Ask why a different datum returns unavailable.
5. Show the reference repair and point from each rule to the code that implements it.
6. Ask what a passed test does not establish: it does not validate a flood forecast,
   sensor accuracy, every possible input or a release policy.

The 7-foot threshold and 15-minute freshness policy are invented classroom choices.
The hydrological distinction between gage height and water depth follows the USGS
references in the ontology. Do not interpret a below-threshold result as safe.

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

- River: "Compare the supplied observation with the threshold. Implement
  `compare_reading(reading, threshold, now)` returning `status`, `reason`, and
  `value_ft`. Explain your interpretation. Use only the Python standard library."
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
