---
domain: workshop-river
version: 2
governs:
  - "notebooks/lessons/river_reading.py"
---

## Cell 2 · Give the pieces names and explain how they connect

**Crayons and glue:** label the things before drawing arrows between them.
Here the labels distinguish a measurement, a prediction and a threshold.
Calling all three simply “water level” would hide why they behave differently.

| Term | Meaning |
|---|---|
| **Stage** | Water-surface height relative to a gauge's reference datum. |
| **Discharge** | Volume passing a location per unit time, commonly cubic feet per second. |
| **Rating curve** | A site-specific relationship between stage and discharge. |
| **Observed stage** | A measured stage with a location and observation time. |
| **Forecast crest** | The highest stage predicted for an event, with its expected time. |
| **Flood stage** | A flood threshold belonging to a particular forecast point. |

**Relationships:** an observation is measured at a gauge; a forecast is for a
forecast point; a threshold applies to that point. This example uses the
Wimberley gauge / forecast-point mapping, the same height reference, and feet.

> **FLOOD-01 — Preserve forecast flooding**
>
> When a supplied, valid forecast reaches or exceeds the location's flood stage,
> the assessment must identify forecast flooding even while the observed stage
> is below flood stage.
>
> **Why:** waiting for observed flooding loses the opportunity to warn before
> the water arrives.

**Executable check:** `FloodTests.test_flood_01_forecast_exceedance`
→ checks `assess_flood_risk`.

`FLOOD-01` is a stable name for this rule. We repeat it in the test name and
failure message so a failed check points back to the reason it exists.
We, as developers, write that connection; Python does not translate this paragraph.

Fixture preconditions: same location and datum, finite values in feet, and an
accepted forecast for the relevant near-term window. Those checks are outside
this small function; they are not silently implemented here.

### Decision contract and check links

`assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft)`
returns `observed_flooding` when the observed stage reaches or exceeds flood stage;
otherwise `forecast_flooding` when the forecast crest reaches or exceeds it;
otherwise `no_threshold_exceedance`. These are assessment labels, not public alerts.
An observed exceedance takes priority over a predicted exceedance.

FLOOD-01 is checked in the notebook by `run_gate(candidate)` and in the repository:
[gate: `notebooks/tests/test_lessons.py:RiverTests.test_flood_01_forecast_exceedance`; code: `assess_flood_risk`]
[gate: `notebooks/tests/test_lessons.py:RiverTests.test_flood_01_equal_threshold`; code: `assess_flood_risk`]

Run `python3 -m unittest discover -s notebooks/tests -v` for repository checks.
These links document the human-authored rule-to-test mapping; they do not install
hooks or require CI. The notebook's expected failed candidate is teaching evidence,
not a successful acceptance result for that candidate.

### Sources and scope

[NWS Wimberley forecast point](https://water.noaa.gov/gauges/wmbt2),
[USGS stage/discharge relationship](https://www.usgs.gov/faqs/how-a-rating-curve-used-convert-gage-height-streamflow).
The scenario values are synthetic. The function consumes a supplied forecast;
it does not estimate discharge, calculate a forecast, validate the fixture
preconditions, or issue an official warning.

### Changelog

- 2026-10-26 — Replaced the unit-conversion lesson with the forecast-flooding
  decision contract and FLOOD-01. The old RIV-01 through RIV-04 comparison rules
  are retired for this lesson; their validation behavior is not carried forward.
