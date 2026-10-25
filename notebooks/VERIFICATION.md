# Verification record — October 25, 2026

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
