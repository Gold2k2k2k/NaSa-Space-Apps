"""A manager summary must preserve evidence limits and model/source identity."""
import copy
from pathlib import Path
import unittest

from app.agents import run_investigation
from app.case_studies import run_case_study


class TestJudgingBrief(unittest.TestCase):
    def test_real_case_brief_is_traceable_and_cannot_claim_verified_hazard(self):
        run = run_case_study("central-highlands")
        self.assertTrue("manager_brief" in run, "The approved land-manager brief is missing")
        brief = run["manager_brief"]
        self.assertEqual(brief["run_id"], run["run_id"])
        self.assertEqual(brief["comparison"]["status"], "UNVERIFIABLE")
        self.assertEqual(brief["source"]["subset_sha256"], run["provenance"]["subset_sha256"])
        self.assertEqual(brief["comparison"]["model_id"], run["sensor_calibration_audit"]["calibration_model"]["model_id"])
        self.assertTrue(all(p["complete_samples"] == 0 for p in brief["descriptive_periods"]))
        self.assertIn("not", brief["extent"]["boundary_note"].lower())
        self.assertTrue(any("cause" in line for line in brief["limitations"]))
        self.assertTrue(any("coverage" in line for line in brief["limitations"]))
        self.assertTrue(brief["next_review_action"])

    def test_empty_reference_and_hypothetical_metric_are_explicit(self):
        aoi = {"lat": 0, "lon": 0, "focus_year": 2024, "focus_month": 8}
        raw = [{"latitude": 0, "longitude": 0, "acq_date": "2024-08-10", "satellite": "T", "confidence": 90}]
        from app.datasets import parse_custom_aoi
        run = run_investigation(aoi, raw_records_override=raw, source_aoi=parse_custom_aoi(aoi))
        self.assertTrue("manager_brief" in run, "Missing manager brief")
        brief = run["manager_brief"]
        self.assertIsNone(brief["comparison"]["historical_median"])
        self.assertEqual(brief["descriptive_periods"], [])
        self.assertEqual(brief["comparison"]["reference_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
