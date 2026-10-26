"""Behavioral checks for the exact code shipped in the notebooks."""
import contextlib
import io
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


def lesson(name):
    path = ROOT / "lessons" / f"{name}.py"
    assert path.exists(), f"Missing lesson implementation: {name}"
    with contextlib.redirect_stdout(io.StringIO()):
        return runpy.run_path(str(path))


class RiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = lesson("river_reading")

    def test_flood_01_forecast_exceedance(self):
        for name in ["correct_assessment", "assess_flood_risk"]:
            with self.subTest(version=name):
                self.assertEqual(self.ns[name](12.0, 18.0, 13.0), "forecast_flooding",
                                 "FLOOD-01: below now must not suppress forecast flooding")

    def test_flood_01_equal_threshold(self):
        self.assertEqual(self.ns["assess_flood_risk"](12.0, 13.0, 13.0),
                         "forecast_flooding", "FLOOD-01: reaching flood stage counts")

    def test_observed_flooding_has_priority_including_equality(self):
        for observed in [13.0, 14.0]:
            for forecast in [12.5, 18.0]:
                with self.subTest(observed=observed, forecast=forecast):
                    self.assertEqual(self.ns["assess_flood_risk"](observed, forecast, 13.0),
                                     "observed_flooding")

    def test_both_below_threshold(self):
        self.assertEqual(self.ns["assess_flood_risk"](12.0, 12.5, 13.0),
                         "no_threshold_exceedance")

    def test_deliberate_shortcut_fails_named_forecast_checks(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            passed = self.ns["run_gate"](self.ns["broken_assessment"])
        self.assertFalse(passed)
        self.assertIn("FAILED (failures=2)", output.getvalue())
        self.assertIn("FAIL: test_flood_01_forecast_exceedance", output.getvalue())
        self.assertIn("FAIL: test_flood_01_equal_threshold", output.getvalue())
        self.assertIn("FLOOD-01", output.getvalue())

    def test_gate_rejects_excluding_the_equality_boundary(self):
        def excludes_equality(observed, forecast, threshold):
            if observed >= threshold:
                return "observed_flooding"
            if forecast > threshold:
                return "forecast_flooding"
            return "no_threshold_exceedance"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(self.ns["run_gate"](excludes_equality))

    def test_unchanged_gate_passes_baseline_and_repair(self):
        self.assertIs(self.ns["baseline_passed"], True)
        self.assertIs(self.ns["broken_passed"], False)
        self.assertIs(self.ns["repaired_passed"], True)
        for name in ["correct_assessment", "assess_flood_risk"]:
            with self.subTest(version=name), contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(self.ns["run_gate"](self.ns[name]))


class HigherEducationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = lesson("one_person_one_count")

    def test_edu_01_people_are_not_profile_rows(self):
        self.assertEqual(len(self.ns["PROFILE_ROWS"]), 5)
        self.assertEqual(self.ns["count_graduates"](self.ns["COMPLETIONS"], "north"), 2)

    def test_edu_02_institution_and_completion_define_membership(self):
        self.assertEqual(self.ns["count_graduates"](self.ns["COMPLETIONS"], "south"), 1)
        self.assertEqual(self.ns["count_graduates"](self.ns["COMPLETIONS"], "empty"), 0)
        self.assertEqual(self.ns["count_graduates"]([], "north"), 0)

    def test_edu_03_missing_jobs_do_not_remove_people(self):
        counter = self.ns["graduate_report"]
        self.assertEqual(counter(self.ns["COMPLETIONS"], [], "north"), 2)
        self.assertEqual(counter(self.ns["COMPLETIONS"], self.ns["JOBS"] * 3, "north"), 2)

    def test_repeated_completion_does_not_inflate_either_report(self):
        rows = self.ns["COMPLETIONS"] * 2
        self.assertEqual(self.ns["count_graduates"](rows, "north"), 2)
        self.assertEqual(self.ns["count_completions"](rows, "north"), 3)

    def test_edu_04_changed_report_has_changed_unit(self):
        self.assertEqual(self.ns["count_completions"](self.ns["COMPLETIONS"], "north"), 3)

    def test_missing_identity_is_not_a_person(self):
        for field in ["person_id", "completion_id", "institution_id", "status"]:
            for value in [None, "", "   "]:
                rows = [dict(self.ns["COMPLETIONS"][0], **{field: value})]
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.ns["count_graduates"](rows, "north")
        with self.assertRaises(ValueError):
            self.ns["count_graduates"](self.ns["COMPLETIONS"], "")

    def test_conflicting_completion_identity_is_rejected(self):
        first = self.ns["COMPLETIONS"][0]
        with self.assertRaises(ValueError):
            self.ns["count_graduates"]([first, dict(first, person_id="different")], "north")

    def test_rule_checks_reject_row_count_and_job_dependency(self):
        failures = self.ns["check_education_rules"](self.ns["count_profile_rows"])
        self.assertIn("EDU-01", {row["rule"] for row in failures})
        self.assertIn("EDU-03", {row["rule"] for row in failures})
        self.assertEqual(self.ns["check_education_rules"](self.ns["graduate_report"]), [])

    def test_downloaded_education_checks_require_conflict_detection(self):
        def ignores_conflicts(completions, jobs, institution):
            return len({row["person_id"] for row in completions
                        if row["institution_id"] == institution and row["status"] == "completed"})
        self.assertGreater(len(self.ns["check_education_rules"](ignores_conflicts)), 0)


if __name__ == "__main__":
    unittest.main()
