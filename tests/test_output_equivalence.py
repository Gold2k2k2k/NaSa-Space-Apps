"""Output equivalence test suite for Central Highlands dynamic analysis pipeline.

Validates that optimized execution outputs produce deterministic, contract-compliant
results identical in structure and business logic to canonical baselines:
- Verdict and deciding rule match exactly.
- Sensor calibration audit factors match within 1e-8.
- 288 calendar cells match within 1e-6 float precision across all metrics and stats.
- Annual series and summary records match precisely.
- Land manager brief preserves identical structure, comparisons, and limitations.
- Offline receipt verifier (`verify.py`) confirms full cryptographic validity (9 queries).
"""
import json
from pathlib import Path
import unittest

from app.case_studies import run_case_study
from app.receipt import build_receipt
from verify import check_receipt

ROOT = Path(__file__).resolve().parents[1]


class TestOutputEquivalence(unittest.TestCase):
    """Validate optimized execution outputs match canonical baselines precisely."""

    @classmethod
    def setUpClass(cls):
        cls.baseline_evidence = json.loads(
            (ROOT / "output_examples" / "central_highlands_evidence.json").read_text(encoding="utf-8")
        )
        cls.baseline_receipt = json.loads(
            (ROOT / "output_examples" / "central_highlands_receipt.json").read_text(encoding="utf-8")
        )
        cls.baseline_model_eval = json.loads(
            (ROOT / "docs" / "judging" / "results" / "model-evaluation.json").read_text(encoding="utf-8")
        )
        cls.baseline_manager_brief = json.loads(
            (ROOT / "docs" / "judging" / "results" / "manager-brief.json").read_text(encoding="utf-8")
        )
        cls.optimized_run = run_case_study("central-highlands")

    def test_verdict_and_deciding_rule_exact_match(self):
        """Verdict, deciding rule, findings, and status must match baseline."""
        self.assertEqual(self.optimized_run["verdict"], self.baseline_evidence["verdict"])
        self.assertEqual(self.optimized_run["deciding_rule"], self.baseline_evidence["deciding_rule"])
        self.assertEqual(self.optimized_run["status"], self.baseline_evidence["status"])

        # Findings comparison with JSON sequence normalization (tuples serialize to lists in JSON)
        findings_opt = json.loads(json.dumps(self.optimized_run["findings"]))
        self.assertEqual(findings_opt, self.baseline_evidence["findings"])

    def test_sensor_calibration_audit_equivalence(self):
        """Sensor calibration factors must match within 1e-8 and model evaluation must be identical."""
        audit_opt = self.optimized_run["sensor_calibration_audit"]
        audit_base = self.baseline_evidence["sensor_calibration_audit"]

        self.assertAlmostEqual(audit_opt["calibrated_kappa"], audit_base["calibrated_kappa"], places=8)
        self.assertAlmostEqual(audit_opt["frp_conversion_ratio"], audit_base["frp_conversion_ratio"], places=8)
        self.assertEqual(
            audit_opt["calibration_model"]["model_id"],
            audit_base["calibration_model"]["model_id"],
        )

        # Deep comparison of model evaluation
        self.assertEqual(audit_opt["model_evaluation"], self.baseline_model_eval)

        # Audit scalar consistency
        self.assertAlmostEqual(
            audit_opt["raw_viirs_to_modis_ratio"],
            audit_base["raw_viirs_to_modis_ratio"],
            places=8,
        )
        self.assertAlmostEqual(audit_opt["bridge_r2"], audit_base["bridge_r2"], places=6)
        self.assertEqual(audit_opt["total_raw_detections"], audit_base["total_raw_detections"])
        self.assertEqual(audit_opt["total_harmonized_events"], audit_base["total_harmonized_events"])

    def test_calendar_cells_numerical_equivalence(self):
        """All 288 calendar cells must match baseline metrics and stats within 1e-6."""
        cells_opt = {(c["year"], c["month"]): c for c in self.optimized_run["calendar"]["cells"]}
        cells_base = {(c["year"], c["month"]): c for c in self.baseline_evidence["calendar"]["cells"]}

        self.assertEqual(set(cells_opt.keys()), set(cells_base.keys()))
        self.assertEqual(len(cells_opt), 288, "Expected exactly 288 monthly cells (2001-2024)")

        metrics = (
            "value",
            "hhe_total",
            "raw_total",
            "raw_modis",
            "raw_viirs",
            "frp_total_mw",
            "night_share",
        )
        stats = (
            "z_robust",
            "empirical_percentile",
            "anomaly_abs",
            "anomaly_pct",
            "hist_median_hhe",
            "hist_mean_hhe",
            "hist_iqr_hhe",
            "hist_p90_hhe",
            "hist_p95_hhe",
        )

        for key in sorted(cells_base.keys()):
            c_opt = cells_opt[key]
            c_base = cells_base[key]

            self.assertEqual(c_opt["is_observed"], c_base["is_observed"], f"is_observed mismatch at {key}")
            self.assertEqual(c_opt["is_complete"], c_base["is_complete"], f"is_complete mismatch at {key}")
            self.assertEqual(c_opt["coverage_status"], c_base["coverage_status"], f"coverage_status mismatch at {key}")
            self.assertEqual(c_opt["severity_band"], c_base["severity_band"], f"severity_band mismatch at {key}")

            for m in metrics:
                v_opt, v_base = c_opt.get(m), c_base.get(m)
                if v_base is None:
                    self.assertIsNone(v_opt, f"Expected None for metric {m} at {key}, got {v_opt}")
                else:
                    self.assertIsNotNone(v_opt, f"Expected non-None for metric {m} at {key}")
                    self.assertAlmostEqual(v_opt, v_base, places=6, msg=f"Mismatch at cell {key} metric {m}")

            for s in stats:
                v_opt, v_base = c_opt.get(s), c_base.get(s)
                if v_base is None:
                    self.assertIsNone(v_opt, f"Expected None for stat {s} at {key}, got {v_opt}")
                else:
                    self.assertIsNotNone(v_opt, f"Expected non-None for stat {s} at {key}")
                    self.assertAlmostEqual(v_opt, v_base, places=6, msg=f"Mismatch at cell {key} stat {s}")

    def test_annual_series_and_records_equivalence(self):
        """Annual series aggregations and summary records must match within 1e-6."""
        cal_opt = self.optimized_run["calendar"]
        cal_base = self.baseline_evidence["calendar"]

        self.assertEqual(cal_opt["summary_records"], cal_base["summary_records"])
        self.assertEqual(len(cal_opt["annual_series"]), len(cal_base["annual_series"]))

        for a_opt, a_base in zip(cal_opt["annual_series"], cal_base["annual_series"]):
            self.assertEqual(a_opt["year"], a_base["year"])
            self.assertEqual(a_opt["is_complete"], a_base["is_complete"])
            self.assertEqual(a_opt["observed_months"], a_base["observed_months"])
            for m in ("value", "hhe_total", "raw_total"):
                self.assertAlmostEqual(
                    a_opt[m],
                    a_base[m],
                    places=6,
                    msg=f"Annual series mismatch at year {a_base['year']} metric {m}",
                )

    def test_manager_brief_deep_equivalence(self):
        """Manager brief contents must preserve structure, comparisons, and limitations."""
        mb_opt = self.optimized_run["manager_brief"]
        mb_base = self.baseline_manager_brief

        # Verify run_id link
        self.assertEqual(mb_opt["run_id"], self.optimized_run["run_id"])

        # Deep comparison of semantic sections
        for section in (
            "question",
            "extent",
            "period",
            "source",
            "descriptive_periods",
            "comparison",
            "limitations",
            "next_review_action",
        ):
            self.assertEqual(
                mb_opt[section],
                mb_base[section],
                f"Manager brief section '{section}' mismatch",
            )

    def test_offline_verifier_rederivation(self):
        """A newly built receipt from the run must pass offline check_receipt as VALID with 9 queries."""
        receipt = build_receipt(self.optimized_run)
        verdict_res = check_receipt(receipt)

        self.assertEqual(
            verdict_res["status"],
            "VALID",
            f"check_receipt failed: {verdict_res.get('problems')}",
        )
        self.assertEqual(verdict_res["queries_checked"], 9)
        self.assertEqual(receipt["verdict"], "UNVERIFIABLE")
        self.assertEqual(receipt["deciding_rule"], self.baseline_evidence["deciding_rule"])


if __name__ == "__main__":
    unittest.main()
