# %% [markdown]
# # Cell 1 · The river hasn't reached flood stage. Do we wait?
# **Muddy Boots Code · Crayons and glue walkthrough**
#
# Start with the job: **recognize forecast flooding before the water gets there.**
#
# We will keep asking three questions:
# 1. **What does this mean in the real world?** Write down the terms and rule.
# 2. **Where does the code express that meaning?** Point to the name or decision.
# 3. **How do we catch a mistake?** Check the result against the rule.
#
# **Meaning → code → check.** That is the connection we are going to make visible.
#
# We will read one cell, predict what it should do, then run it with **Shift + Enter**.
# This first cell is an explanation; it does not run Python.
#
# Our classroom example uses a supplied forecast. It assesses a flood condition;
# it does not create the forecast or issue an official warning.
#
# **Pause here:** the goal is to preserve the meaning of a forecast in our code.

# %% [ontology] river.md

# %% [markdown]
# ## Cell 3 · Put concrete values beside those names
#
# | What we know | Classroom value |
# |---|---|
# | Forecast point | Blanco River at Wimberley (WMBT2 / USGS 08171000) |
# | Observed stage at noon | **12 ft** |
# | Forecast crest at 4 p.m. | **18 ft** |
# | Local flood stage | **13 ft** |
#
# The published Wimberley thresholds are action 10 ft, minor flood 13 ft,
# moderate flood 17 ft and major flood 26 ft. The **12-ft observation and 18-ft
# forecast are invented for this demonstration**, not current conditions or a
# historical forecast. We do not invent a discharge value or a rating curve.
#
# **Audience question:** should being below flood stage *now* suppress the
# forecast-flooding assessment?
#
# In the next cell, `observed_` means measured, `forecast_` means predicted,
# and `_ft` means feet. The names carry context that a bare `12` or `18` does not.
# The numbers are inputs; they are not yet the decision.

# %%
# Cell 4: translate the scenario into named inputs.
# Measured water height now: observation, not prediction.
observed_stage_ft = 12.0
# Highest water level in the supplied forecast: prediction, not observation.
forecast_crest_ft = 18.0
# Flood threshold for this location: a rule boundary, not another reading.
flood_stage_ft = 13.0
# Show our inputs. Printing them makes no flood decision.
print(f"Observed: {observed_stage_ft:g} ft | Forecast: {forecast_crest_ft:g} ft | Flood stage: {flood_stage_ft:g} ft")

# %% [markdown]
# ## Cell 5 · Decide what a correct answer must be
#
# **Crayons and glue:** write the answer key before checking the work.
# For 12 ft observed, 18 ft forecast and a 13-ft threshold, FLOOD-01 requires
# `forecast_flooding`. The river need not already be at 13 ft.
#
# The expected result comes from **FLOOD-01**, not from the candidate's code.
# The first two checks protect forecast assessment and its equality boundary.
# The other two keep the already-flooding and below-threshold cases distinct.
#
# The runner takes a candidate function, so all three versions face the same tests.
#
# | Piece of the next cell | Its job |
# |---|---|
# | `candidate(12.0, 18.0, 13.0)` | Ask the version of the code being checked for its answer. |
# | `"forecast_flooding"` | The answer required by our rule for this case. |
# | `assertEqual` | Compare the actual answer with that required answer. |
# | `FLOOD-01` in the message | Point the failure back to the ontology rule. |
# | `unittest` and `StringIO` | Run checks and collect the report; these are test machinery. |
#
# The test cases are fixed independently of Cell 4. Changing the demonstration
# inputs does not change the answer key. Running Cell 6 defines the gate;
# the first call that actually runs it is in Cell 8.

# %%
# Cell 6: define an executable answer key for the domain rule.
import io        # Collect printed test results in memory.
import unittest  # Python's ordinary testing tools.

def run_gate(candidate):
    # candidate is whichever version of the function we want to check.
    class FloodTests(unittest.TestCase):
        def test_flood_01_forecast_exceedance(self):
            # Same rule, concrete case: below now, above in the forecast.
            self.assertEqual(
                candidate(12.0, 18.0, 13.0),  # The code's actual answer.
                "forecast_flooding",        # The rule's required answer.
                # If they differ, explain which meaning was lost.
                "FLOOD-01: forecast exceeds flood stage; "
                "current reading must not suppress assessment",
            )

        def test_flood_01_equal_threshold(self):
            # "Reaches or exceeds" includes exactly 13 ft, not just more.
            self.assertEqual(
                candidate(12.0, 13.0, 13.0),
                "forecast_flooding",
                "FLOOD-01: reaching flood stage counts",
            )

        def test_observed_flooding(self):
            # A measured exceedance must remain distinct from a prediction.
            self.assertEqual(candidate(14.0, 18.0, 13.0), "observed_flooding")

        def test_no_threshold_exceedance(self):
            # Neither supplied value reaches 13 ft in this separate case.
            self.assertEqual(candidate(12.0, 12.5, 13.0), "no_threshold_exceedance")

    # Test machinery: run every check and capture its report.
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FloodTests)
    )
    print(output.getvalue())
    passed = result.wasSuccessful()  # True only when every check passes.
    print("GATE: PASS" if passed else "GATE: FAIL — see the failed rule checks above")
    return passed

# %% [markdown]
# ## Cell 7 · Translate the meaning into decisions
#
# **Crayons and glue:** read each `if` as a question and each `return` as an answer.
# A `return` ends this call, so its position matters.
#
# | Domain meaning | Line that expresses it |
# |---|---|
# | Flooding is observed when the measured stage reaches the threshold. | First `if`, using `observed_stage_ft`. |
# | FLOOD-01 still requires checking the forecast when the river is below it now. | Second `if`, using `forecast_crest_ft`. |
# | “Reaches or exceeds” includes equality. | The `>=` operator. |
# | Observed and forecast flooding are different claims. | Different returned labels. |
#
# `def` creates a reusable decision. Its three parameter names say what inputs it
# needs. Calling `run_gate(assess_flood_risk)` then checks that decision against
# the unchanged answer key from Cell 6.
#
# Check what has happened and what is forecast to happen. Returning
# `no_threshold_exceedance` means only that neither supplied value reaches this
# threshold; it is not a claim that the area is safe.

# %%
# Cell 8: implement the domain decisions, then check them.
def assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft):
    # First ask: has the measured water level reached flood stage?
    if observed_stage_ft >= flood_stage_ft:
        return "observed_flooding"
    # FLOOD-01: below now does not mean we can ignore the forecast.
    if forecast_crest_ft >= flood_stage_ft:
        return "forecast_flooding"
    # We reach this answer only after checking BOTH supplied values.
    return "no_threshold_exceedance"

# Keep a reference to this version; no copy of the rule or tests is made.
correct_assessment = assess_flood_risk
print("Assessment:", assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft))
baseline_passed = run_gate(assess_flood_risk)  # Run the answer key.
assert baseline_passed  # Stop if this supposedly correct version fails.

# %% [markdown]
# ## Cell 9 · Spot the meaning lost by one shortcut
#
# Imagine an agent adds an early exit: “If the river is below flood stage, stop checking.”
# This is an authored teaching change, not a recorded agent incident.
#
# ```diff
#  def assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft):
# +    if observed_stage_ft < flood_stage_ft:
# +        return "no_threshold_exceedance"
# ```
#
# **Predict before running:** which two checks will fail, and why?
#
# **Crayons and glue:** the new `return` is an exit door placed before the
# forecast question. With our inputs, `12 < 13` is true, so the function leaves
# before it ever looks at `18`. The forecast code is still printed below it,
# but cannot be reached for this case. That is the violation of FLOOD-01.

# %%
# Cell 10: redefine the same function with the deliberate shortcut.
def assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft):
    # Deliberate bug: this skips the forecast while the observed river is lower.
    if observed_stage_ft < flood_stage_ft:
        # return ends the call; the forecast below never gets a vote.
        return "no_threshold_exceedance"

    if observed_stage_ft >= flood_stage_ft:
        return "observed_flooding"
    if forecast_crest_ft >= flood_stage_ft:
        return "forecast_flooding"
    return "no_threshold_exceedance"

# Keep the deliberately broken version available for repository regression tests.
broken_assessment = assess_flood_risk
print("Broken assessment:", assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft))
broken_passed = run_gate(assess_flood_risk)  # SAME rule and SAME tests.
# This asserts the demo caught the bug. It does not approve the broken code.
assert not broken_passed, "The demonstration must catch this deliberate regression."

# %% [markdown]
# ## Cell 11 · Repair the decision, not the answer key
#
# Remove the early exit. The rule, test fixtures and expected outcomes stay unchanged.
# The expected failure above is captured so **Run All** can continue to this repair.
#
# **Crayons and glue:** move the exit back after both questions. We keep
# `forecast_flooding` as the expected answer. Editing the test to accept the
# broken result would erase our protection rather than repair the decision.

# %%
# Cell 12: remove the shortcut and restore the two distinct questions.
def assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft):
    # What has been measured?
    if observed_stage_ft >= flood_stage_ft:
        return "observed_flooding"
    # What does the supplied forecast say? FLOOD-01 preserves this question.
    if forecast_crest_ft >= flood_stage_ft:
        return "forecast_flooding"
    # Neither supplied value reaches this location's threshold.
    return "no_threshold_exceedance"

print("Repaired assessment:", assess_flood_risk(observed_stage_ft, forecast_crest_ft, flood_stage_ft))
repaired_passed = run_gate(assess_flood_risk)  # Still the original answer key.
assert repaired_passed
print("Verified sequence:", baseline_passed, "→", broken_passed, "→", repaired_passed)

# %% [markdown]
# ## Cell 13 · Connect the whole chain
#
# **Ontology → named invariant → executable check → failure → repair**
#
# | Where we put the context | How it helps |
# |---|---|
# | Terms and relationships (Cell 2) | Explain what the inputs represent and which things belong together. |
# | Rule and rationale (Cell 2) | Explain what must stay true and why. |
# | Variable names (Cell 4) | Carry those distinctions into the code. |
# | Decisions and return labels (Cell 8) | Express the rule in behavior. |
# | Independent expected answers (Cell 6) | Check whether that behavior still respects the rule. |
# | Rule ID in the failing test (Cell 10) | Connect the observed failure back to its meaning. |
#
# The ontology supplies the vocabulary, relationships and rationale. The linked
# unit test supplies the mechanical failure. A hook can request rule review;
# blocking acceptance requires a hook or required CI check that actually runs the
# test and treats failure as failure. A Markdown rule alone does not execute.
#
# This notebook intentionally captures the failed test result to continue the
# teaching sequence. A blocking runner would use `raise SystemExit(0 if
# run_gate(candidate) else 1)` in a separate process. No hook, CI requirement,
# warning service or public notification has been installed by this demonstration.
#
# **Discussion:** what if the forecast is for the wrong gauge, is stale, or is missing?
# Those need their own explicit rules and tests; these four checks do not establish
# complete flood-system correctness.
#
# > “The code still runs. But it has forgotten what a forecast is for.
# > We wrote that meaning down and connected it to a check.”
#
# ### Domain references
# - [NWS: Blanco River at Wimberley — thresholds and forecast context](https://water.noaa.gov/gauges/wmbt2)
# - [USGS: how a rating curve relates stage and discharge](https://www.usgs.gov/faqs/how-a-rating-curve-used-convert-gage-height-streamflow)
# - [NWS: stage terminology](https://forecast.weather.gov/glossary.php?word=STAGE)
# - [NWS: flood watches and warnings](https://www.weather.gov/safety/flood-watch-warning)
