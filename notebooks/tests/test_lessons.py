"""Behavioral checks for the exact code shipped in the notebooks."""
import contextlib
import io
import math
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

    def compare(self, **changes):
        reading = dict(self.ns["READING"], **changes)
        return self.ns["compare_reading"](reading, self.ns["THRESHOLD"], self.ns["NOW"])

    def test_riv_01_units_change_the_answer(self):
        self.assertEqual(self.compare()["status"], "at_or_above")
        self.assertAlmostEqual(self.compare()["value_ft"], 7.874015748)
        self.assertEqual(self.compare(value=7, unit="ft")["status"], "at_or_above")
        self.assertEqual(self.compare(value=6.9, unit="ft")["status"], "below")

    def test_riv_01_converted_equality_is_included_without_rounding_up(self):
        self.assertEqual(self.compare(value=2.1336, unit="m")["status"], "at_or_above")
        self.assertEqual(self.compare(value=2.133599999, unit="m")["status"], "below")

    def test_riv_02_wrong_context_is_unavailable(self):
        for field, value in [("gauge_id", "OTHER"), ("datum", "OTHER"), ("quantity", "discharge")]:
            with self.subTest(field=field):
                self.assertEqual(self.compare(**{field: value})["status"], "unavailable")

    def test_riv_03_time_boundary_and_timezone(self):
        cases = [("2026-10-25T11:45:00+00:00", "at_or_above"),
                 ("2026-10-25T11:44:59+00:00", "unavailable"),
                 ("2026-10-25T12:00:01+00:00", "unavailable"),
                 ("2026-10-25T06:55:00-05:00", "at_or_above"),
                 ("2026-10-25T11:55:00", "unavailable"),
                 ("bad-time", "unavailable")]
        for stamp, expected in cases:
            with self.subTest(stamp=stamp):
                self.assertEqual(self.compare(observed_at=stamp)["status"], expected)

    def test_riv_04_missing_and_nonfinite_are_unavailable(self):
        for value in [None, math.nan, math.inf, -math.inf, True, "2.4"]:
            with self.subTest(value=value):
                self.assertEqual(self.compare(value=value)["status"], "unavailable")
        self.assertEqual(self.compare(unit="cfs")["status"], "unavailable")
        for field in self.ns["READING"]:
            reading = dict(self.ns["READING"])
            del reading[field]
            self.assertEqual(self.ns["compare_reading"](reading, self.ns["THRESHOLD"], self.ns["NOW"])["status"], "unavailable")

    def test_negative_stage_is_not_automatically_invalid(self):
        self.assertEqual(self.compare(value=-0.1, unit="ft")["status"], "below")

    def test_bad_threshold_and_clock_raise(self):
        for change in [{"unit": "m"}, {"value": math.nan}, {"gauge_id": ""}, {"quantity": "discharge"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ns["compare_reading"](self.ns["READING"], dict(self.ns["THRESHOLD"], **change), self.ns["NOW"])
        with self.assertRaises(ValueError):
            self.ns["compare_reading"](self.ns["READING"], self.ns["THRESHOLD"], self.ns["NOW"].replace(tzinfo=None))

    def test_rule_checks_reject_faulty_candidate(self):
        self.assertGreater(len(self.ns["check_river_rules"](self.ns["compare_without_context"])), 0)
        self.assertEqual(self.ns["check_river_rules"](self.ns["compare_reading"]), [])

    def test_downloaded_river_checks_reject_missing_result_context(self):
        def status_only(reading, threshold, now):
            return {"status": self.ns["compare_reading"](reading, threshold, now)["status"]}
        self.assertGreater(len(self.ns["check_river_rules"](status_only)), 0)

    def test_downloaded_river_checks_require_fifteen_minute_boundary(self):
        def too_strict(reading, threshold, now):
            result = self.ns["compare_reading"](reading, threshold, now)
            if reading.get("observed_at") == "2026-10-25T11:45:00+00:00":
                return {"status": "unavailable", "reason": "too strict", "value_ft": None}
            return result
        self.assertGreater(len(self.ns["check_river_rules"](too_strict)), 0)


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
