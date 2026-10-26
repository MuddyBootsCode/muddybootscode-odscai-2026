# Verification record — October 26, 2026

## River replacement

- Replaced `01_river_reading.ipynb` in place with the 13-cell forecast-flooding
  walkthrough. The existing notebook path and Colab links are retained.
- Executed all 5 code cells in a fresh Jupyter kernel launched from an empty
  temporary directory. Saved execution counts and outputs; no unhandled error
  outputs. Baseline: 4 passing checks. Deliberate early return: 2 failures, both
  named FLOOD-01 checks. Repair: the same 4 checks pass.
- The notebook captures deliberate failures so the teaching sequence can finish.
  Separately verified the documented blocking-runner pattern in subprocesses:
  baseline exits 0, broken candidate exits 1, repaired candidate exits 0.
- `python3 -m unittest discover -s notebooks/tests -v`: 16 tests passed (7 river,
  9 higher education), including rejection of both the early-return mutation and
  a mutation that excludes forecast equality at flood stage.
- `python3 notebooks/build.py --check`: both notebooks match their canonical
  lesson sources and embedded ontology documents.
- `nbformat.validate`: the replacement notebook is valid before and after execution.
- Higher-education notebook, lesson, ontology and test class are unchanged.
  Skill and plugin implementation files are unchanged.
- `git diff --check`: passed.

The synthetic case is 12 ft observed, 18 ft forecast crest and 13 ft flood stage.
The expected assessment is `forecast_flooding`. Location, datum, units, finite
values and valid forecast window are stated preconditions, not validation supplied
by this small function. No forecast calculation, official warning issuance,
installed hook, required CI check or controlled model comparison is claimed.

Execution environment: Python 3.15.0, nbformat 5.11.1, nbclient 0.11.0,
ipykernel 7.4.0. Python 3.10 remains the intended language floor; no claim of
testing every supported runtime is made. Review used the saved cell sources and
execution outputs; no new browser or Colab runtime execution is claimed.

## Prior notebook release — October 25, 2026

Historical verification below applies to the original comparison lesson, which
the forecast-flooding lesson above replaces.

- Both notebooks executed to completion in separate fresh Jupyter kernels, each
  launched in an empty temporary directory. All 5 code cells in each notebook
  have saved execution counts and outputs; no error outputs are present.
- `python3 -m unittest discover -s notebooks/tests -q`: 19 tests passed.
- `python3 notebooks/build.py --check`: both notebooks match their canonical
  lesson sources and embedded ontology documents.
- Existing skill suite: `python3 -m unittest discover -s skills/ontology-driven-dev/scripts/tests -q`
  ran 43 tests successfully, with 2 skips.
- Existing observer UI suite: `bun test hooks/register.test.tsx` could not load
  `claude-code/testing`. This checkout does not supply that test runtime. The
  observer and skill source files were not changed.
- HTML exports were generated with nbconvert; section structure and saved
  outputs were inspected. Browser visual inspection of local HTML was blocked
  by the browser's file-URL policy and is not claimed.
- Fresh review found a converted-equality defect: 2.1336 meters was classified
  below 7 feet by floating-point division. A new test reproduced the failure;
  decimal comparison fixed it while retaining a below result for 2.133599999 m.
  Standalone checker gaps for output context, the 15-minute boundary and conflicting
  completion identities were also reproduced with failing tests and corrected.

Observed reference results: river 2.4 m becomes 7.874015748031496 ft and is
at_or_above the invented 7-foot threshold; higher education produces 5 joined
rows, 2 qualifying people and 3 completed degrees.

Verification environment: Python 3.15.0, nbformat 5.11.1, nbclient 0.11.0,
ipykernel 7.4.0, JupyterLab 4.6.4. Python 3.10 is the intended language floor;
this record does not claim a runtime test on every supported Python version.

No controlled model comparison, required CI configuration, branch-protection
change, deployment, operational river validation or PowerPoint edit is claimed.
