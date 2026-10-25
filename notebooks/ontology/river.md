---
domain: workshop-river
version: 1
governs:
  - "notebooks/lessons/river_reading.py"
---

# River: what does this reading mean?

## Intent

Compare one synthetic gage-height observation with a classroom threshold.
Return **at_or_above**, **below**, or **unavailable**, with a reason.
The result describes only this comparison. It is not a flood forecast or warning.

## Entities and relationships

- **Gauge**: a measurement location, identified by `gauge_id`.
- **Observation**: a quantity and value at a gauge and an offset-aware instant;
  carries a unit and datum. This lesson handles one observation at a time.
- **Threshold**: a demonstration comparison value for one gauge, quantity and
  datum. The threshold contract uses feet.
- `(Observation)-[OBSERVED_AT]->(Gauge)`: exactly one gauge per observation.
- `(Threshold)-[APPLIES_TO]->(Gauge)`: exactly one gauge per threshold.
- Each observation and threshold names the reference datum for its height.

## Vocabulary and rationale

**Gage height / stage** is water-surface height relative to a reference datum;
it is not necessarily water depth. Different sites can use different datums.
**Discharge** is a volume per unit time, a different quantity.
**Unavailable** means this contract cannot make a comparison; it does not mean
below threshold, safe, zero, or that no observation exists elsewhere.

## Invariants

- **RIV-01 — Comparable units:** Convert supported lengths to feet before comparing;
  equality is at_or_above. A number without its unit has no usable comparison meaning.
  [gate: `RiverTests.test_riv_01_units_change_the_answer`; code: `compare_reading`]
- **RIV-02 — Shared context:** Gauge, gage-height quantity and datum must match.
  Converting units cannot fix a different physical reference.
  [gate: `RiverTests.test_riv_02_wrong_context_is_unavailable`; code: `compare_reading`]
- **RIV-03 — Explicit time policy:** Both times must have offsets. Age must be
  between zero and 15 minutes inclusive. Future or older observations are unavailable.
  The 15-minute limit is a classroom policy, not a hydrological standard.
  [gate: `RiverTests.test_riv_03_time_boundary_and_timezone`; code: `compare_reading`]
- **RIV-04 — Absence stays explicit:** Missing/nonfinite values, missing context,
  unsupported units or unparseable observation times yield unavailable. Never
  substitute zero or below. A negative stage can be meaningful relative to a datum.
  [gate: `RiverTests.test_riv_04_missing_and_nonfinite_are_unavailable`; code: `compare_reading`]

## Function and test links

Implementation: `notebooks/lessons/river_reading.py`, `compare_reading`.
Behavioral checks: `notebooks/tests/test_lessons.py`, `RiverTests`.
Notebook counterexamples: `check_river_rules(candidate)` runs the candidate against
named rules. Run repository checks with `python3 -m unittest discover -s notebooks/tests -v`.
This is an explicit human-authored mapping; it does not prove complete coverage.
No required CI or branch protection is established by this notebook.

## Scope and sources

Synthetic gauge, datum, readings and threshold; fixed demonstration clock.
Only `ft` and `m` input units are supported; 1 foot = 0.3048 meters.
Malformed threshold configuration or a naive evaluation clock raises `ValueError`.
No datum conversion, upstream propagation, sensor-quality assessment, rating curve,
forecasting, missing-reading interpolation, operational freshness policy or safety decision.
Passing these checks does not establish that a sensor reading is physically accurate.

Domain references: [USGS: Why we use gage height](https://waterdata.usgs.gov/blog/gage_height/),
[USGS: Why gage height is not measured from the stream bottom](https://www.usgs.gov/faqs/why-doesnt-usgs-measure-gage-height-bottom-stream).

## Changelog

- 2026-10-25 — Initial workshop contract with explicit comparison outcomes.
