# %% [markdown]
# # 1. A river reading: context before comparison
# **Context Is the Team — Michael Porter / Muddy Boots Code — ODSC AI West 2026**
#
# What does `2.4` mean? Before asking an agent to use it, name the thing measured,
# its relationships and the rules that make a comparison meaningful.
#
# This is a synthetic teaching example. The values and threshold are invented.
# All cells run offline using Python's standard library. No API key is needed.
#
# **Path:** see the record → read the ontology → challenge a candidate → repair
# → explain what the checks establish. Suggested live walkthrough: 4–6 minutes;
# the optional agent exercise is take-home material.
# %%
from datetime import datetime, timedelta
from decimal import Decimal
import math
from pprint import pprint

NOW = datetime.fromisoformat("2026-10-25T12:00:00+00:00")
READING = {
    "gauge_id": "DEMO-RIVER-A",
    "quantity": "gage_height",
    "value": 2.4,
    "unit": "m",
    "datum": "DEMO-LOCAL-A",
    "observed_at": "2026-10-25T11:55:00+00:00",
}
THRESHOLD = {
    "gauge_id": "DEMO-RIVER-A",
    "quantity": "gage_height",
    "value": 7.0,
    "unit": "ft",
    "datum": "DEMO-LOCAL-A",
}
pprint({"observation": READING, "classroom_threshold": THRESHOLD})
# %% [markdown]
# ## Predict before running
# Is this reading below 7 feet? What information determines the answer?
#
# | Thing | Relationship | Meaning for the comparison |
# |---|---|---|
# | Observation | observed at a gauge | Location is part of the value's meaning |
# | Observation and threshold | use a datum | Their height reference must match |
# | Observation | records a quantity, unit and time | Convert the right quantity; check time |
#
# The next cell is embedded from the repository's versioned ontology file.
# It supplies the domain context for the code and the agent exercise.
# %% [ontology] river.md
# %% [markdown]
# ## A plausible implementation with the domain omitted
# This deliberately faulty reference compares the two numbers. It is authored
# teaching code, **not an observed response from a model**.
# %%
def compare_without_context(reading, threshold, now):
    return {"status": "at_or_above" if reading["value"] >= threshold["value"] else "below",
            "reason": "Compared raw numbers only", "value_ft": reading["value"]}

pprint(compare_without_context(READING, THRESHOLD, NOW))
# %% [markdown]
# ## Let the ontology choose the counterexamples
# RIV-01 asks about units; RIV-02 asks about identity and reference;
# RIV-03 asks about time; RIV-04 asks what absence means. Each expected result
# comes from a domain statement, not from whatever the current function returns.
# %%
def check_river_rules(candidate):
    cases = [
        ("RIV-01", "meters converted to feet", {}, "at_or_above"),
        ("RIV-01", "equality is included", {"value": 7.0, "unit": "ft"}, "at_or_above"),
        ("RIV-01", "equality after conversion", {"value": 2.1336, "unit": "m"}, "at_or_above"),
        ("RIV-01", "just below after conversion", {"value": 2.133599999, "unit": "m"}, "below"),
        ("RIV-01", "below in feet", {"value": 6.9, "unit": "ft"}, "below"),
        ("RIV-02", "different gauge", {"gauge_id": "DEMO-RIVER-B"}, "unavailable"),
        ("RIV-02", "different datum", {"datum": "DEMO-LOCAL-B"}, "unavailable"),
        ("RIV-02", "different quantity", {"quantity": "discharge"}, "unavailable"),
        ("RIV-03", "older than policy", {"observed_at": "2026-10-25T11:44:59+00:00"}, "unavailable"),
        ("RIV-03", "exactly fifteen minutes", {"observed_at": "2026-10-25T11:45:00+00:00"}, "at_or_above"),
        ("RIV-03", "missing timezone offset", {"observed_at": "2026-10-25T11:55:00"}, "unavailable"),
        ("RIV-03", "future observation", {"observed_at": "2026-10-25T12:01:00+00:00"}, "unavailable"),
        ("RIV-04", "missing value", {"value": None}, "unavailable"),
        ("RIV-04", "nonfinite value", {"value": math.nan}, "unavailable"),
    ]
    failures = []
    for rule, case, changes, expected in cases:
        try:
            result = candidate(dict(READING, **changes), THRESHOLD, NOW)
            actual = result["status"]
            if not isinstance(result.get("reason"), str) or not result["reason"].strip():
                actual = "missing explanation"
            elif "value_ft" not in result:
                actual = "missing normalized value field"
            elif actual == "unavailable" and result["value_ft"] is not None:
                actual = "unavailable must not supply a comparison value"
            elif actual in ("below", "at_or_above"):
                value = result["value_ft"]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    actual = "comparison requires a finite normalized value"
                elif case == "meters converted to feet" and not math.isclose(value, 7.874015748031496, rel_tol=1e-12):
                    actual = "incorrect normalized value"
        except Exception as exc:
            actual = type(exc).__name__
        if actual != expected:
            failures.append({"rule": rule, "case": case, "expected": expected, "actual": actual})
    return failures

candidate = compare_without_context  # Replace with your implementation for the exercise.
failures = check_river_rules(candidate)
print(f"Candidate: {len(failures)} rule counterexamples failed")
pprint(failures)
# %% [markdown]
# ## Give your agent the domain, then ask for the repair
# Open a fresh agent conversation. Paste the ontology above, the fixture, the
# function and the counterexamples with this prompt:
#
# > Implement `compare_reading(reading, threshold, now)` using this ontology.
# > First explain which rule IDs govern your choices and what each input means.
# > Preserve the ontology and expected outcomes. Return a dictionary containing
# > `status`, `reason`, and `value_ft` (None when unavailable). Keep the same
# > signature and use the Python standard library. Do not add forecasts or
# > safety judgments. Explain how your code handles missing context.
#
# Stop here to try it. Paste the candidate into a new code cell and call
# `check_river_rules(your_function)`. Keep any failures as evidence.
# The next cell is an authored reference repair; it is not a recorded agent run.
# %%
def compare_reading(reading, threshold, now):
    """RIV-01..04: one explicitly scoped stage comparison."""
    def finite_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def unavailable(reason):
        return {"status": "unavailable", "reason": reason, "value_ft": None}

    if (threshold.get("unit") != "ft" or threshold.get("quantity") != "gage_height"
            or not finite_number(threshold.get("value"))
            or any(not isinstance(threshold.get(key), str) or not threshold[key].strip()
                   for key in ("gauge_id", "datum"))):
        raise ValueError("Threshold must name a gauge, datum and finite gage height in feet")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Evaluation time must be offset-aware")

    # RIV-02: units cannot repair a different location, quantity or datum.
    for key in ("gauge_id", "quantity", "datum"):
        if reading.get(key) != threshold[key]:
            return unavailable(f"RIV-02: missing or mismatched {key}")
    # RIV-04: never turn an absent measurement into zero.
    if not finite_number(reading.get("value")) or reading.get("unit") not in ("ft", "m"):
        return unavailable("RIV-04: finite numeric value and supported unit required")
    try:
        observed = datetime.fromisoformat(reading.get("observed_at", ""))
    except (ValueError, TypeError):
        return unavailable("RIV-04: observation timestamp cannot be parsed")
    # RIV-03: fixed classroom policy, inclusive at both boundaries.
    if observed.utcoffset() is None:
        return unavailable("RIV-03: observation timezone offset required")
    age = now - observed
    if not timedelta(0) <= age <= timedelta(minutes=15):
        return unavailable("RIV-03: observation is future-dated or older than 15 minutes")
    # RIV-01: compare lengths in the same unit.
    # Decimal preserves the equality boundary of the supplied decimal values.
    value = Decimal(str(reading["value"]))
    normalized = value if reading["unit"] == "ft" else value / Decimal("0.3048")
    value_ft = float(normalized)
    if not math.isfinite(value_ft):
        return unavailable("RIV-04: conversion produced a nonfinite value")
    status = "at_or_above" if normalized >= Decimal(str(threshold["value"])) else "below"
    return {"status": status, "reason": "RIV-01..04: comparison context satisfied", "value_ft": value_ft}

pprint(compare_reading(READING, THRESHOLD, NOW))
reference_failures = check_river_rules(compare_reading)
assert reference_failures == [], reference_failures
print("Reference repair: all ontology counterexamples passed")
# %% [markdown]
# ## The domain makes these different answers
# A high reading with the wrong datum cannot become a valid threshold comparison.
# Below and unavailable must remain visibly different to whoever uses the result.
# %%
for label, changes in [
    ("Comparable meters", {}),
    ("Below threshold in feet", {"value": 6.0, "unit": "ft"}),
    ("High number, wrong datum", {"value": 99.0, "datum": "DEMO-LOCAL-B"}),
    ("Old reading", {"observed_at": "2026-10-25T10:00:00+00:00"}),
]:
    result = compare_reading(dict(READING, **changes), THRESHOLD, NOW)
    print(f"{label}: {result['status']} — {result['reason']}")
# %% [markdown]
# ## Explain what was proved
# - The domain definitions determined whether the comparison was meaningful.
# - Named counterexamples exercised those decisions in the reference function.
# - A passed check covers these cases and scope. It does not establish a valid
#   flood forecast, physical sensor accuracy, complete coverage or a required CI gate.
#
# **Change exercise:** accept observations exactly 30 minutes old. That is a policy
# change: revise RIV-03, its boundary checks and the implementation together.
# Replacing a failing expectation merely to get green is not the same operation.
#
# **Optional controlled comparison:** give the same task to fresh agent sessions,
# one with this ontology and one without it. Use the same model/settings and checks.
# Save actual prompts, responses, code and results; record successes in both arms.
# A model may solve it without the ontology. One paired run demonstrates only that run.
