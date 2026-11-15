"""Checksums must not hide contradictory or missing calendar evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.canonical import sha256_of
from verify import check_receipt

ROOT = Path(__file__).resolve().parents[1]


def rehash(receipt):
    receipt["calendar_summary"]["cells_sha256"] = sha256_of(receipt["calendar"]["cells"])
    receipt["receipt_sha256"] = sha256_of({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    return receipt


class TestReceiptCalendarConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((ROOT / "output_examples" / "central_highlands_receipt.json").read_text(encoding="utf-8"))

    def test_rehashed_missing_or_duplicate_periods_are_rejected(self):
        for action in ("empty", "missing", "duplicate", "replace_with_duplicate", "outside_window", "invalid_month"):
            receipt = copy.deepcopy(self.receipt)
            cells = receipt["calendar"]["cells"]
            if action == "empty":
                cells.clear()
            elif action == "missing":
                cells.pop(0)
            elif action == "duplicate":
                cells.append(copy.deepcopy(cells[-1]))
            elif action == "replace_with_duplicate":
                cells[0] = copy.deepcopy(cells[-1])
            elif action == "outside_window":
                cells[0]["year"] = 2000
            else:
                cells[0]["month"] = 13
            with self.subTest(action=action):
                self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_rehashed_focus_cell_must_match_its_comparison(self):
        for field, value in (("value", 99999999), ("raw_total", 99999999), ("z_robust", 99),
                             ("hist_median_hhe", 99999999), ("is_complete", True)):
            receipt = copy.deepcopy(self.receipt)
            cell = next(c for c in receipt["calendar"]["cells"] if (c["year"], c["month"]) == (2024, 2))
            cell[field] = value
            with self.subTest(field=field):
                self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_nonfocus_values_must_match_annual_evidence(self):
        receipt = copy.deepcopy(self.receipt)
        next(c for c in receipt["calendar"]["cells"] if (c["year"], c["month"]) == (2023, 3))["value"] = 99999999
        self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_rehashed_annual_summaries_must_match_cells(self):
        for field, value in (("value", 99999999), ("observed_months", 99), ("is_complete", True)):
            receipt = copy.deepcopy(self.receipt)
            for container in (receipt["calendar"], receipt["calendar_summary"]):
                next(r for r in container["annual_series"] if r["year"] == 2024)[field] = value
            with self.subTest(field=field):
                self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_rehashed_peak_summary_must_match_cells(self):
        receipt = copy.deepcopy(self.receipt)
        for container in (receipt["calendar"], receipt["calendar_summary"]):
            container["summary_records"]["peak_month_record"]["value"] = 99999999
        self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_rehashed_extrema_and_trends_must_match_cells(self):
        for field in ("max_cell_value", "max_hhe_value", "harmonized_trend_slope_per_decade", "raw_trend_slope_per_decade"):
            receipt = copy.deepcopy(self.receipt)
            for container in (receipt["calendar"], receipt["calendar_summary"]):
                target = container["summary_records"] if "trend" in field else container
                target[field] = 99999999
            with self.subTest(field=field):
                self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_non_numeric_cell_values_are_controlled_validation_errors(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["calendar"]["cells"][0]["value"] = "invented"
        with self.assertRaises(ValueError):
            check_receipt(rehash(receipt))

    def test_missing_nullable_evidence_is_not_treated_as_explicit_null(self):
        from app.agents import run_investigation
        from app.receipt import build_receipt
        state = run_investigation({"lat": 0, "lon": 0, "year_start": 2024, "year_end": 2024,
                                   "focus_year": 2024}, raw_records_override=[])
        base = json.loads(json.dumps(build_receipt(state)))
        self.assertEqual(check_receipt(base)["status"], "VALID")
        for container, field in (("annual_series", "frp_total_mw"), ("focus_comparison", "hist_iqr"),
                                 ("summary_records", "theil_sen_slope_per_decade")):
            receipt = copy.deepcopy(base)
            for calendar in (receipt["calendar"], receipt["calendar_summary"]):
                evidence = calendar[container][0] if container == "annual_series" else calendar[container]
                self.assertIsNone(evidence.pop(field))
            with self.subTest(container=container):
                self.assertEqual(check_receipt(rehash(receipt))["status"], "TAMPERED")

    def test_cell_order_is_not_an_evidence_change(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["calendar"]["cells"].reverse()
        self.assertEqual(check_receipt(rehash(receipt))["status"], "VALID")

    def test_cli_rejects_rehashed_missing_cells_with_exit_one(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["calendar"]["cells"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(rehash(receipt)), encoding="utf-8")
            result = subprocess.run([sys.executable, "-S", "-B", str(ROOT / "verify.py"), str(path)],
                                    capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("TAMPERED", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_cli_handles_malformed_calendar_objects_without_traceback(self):
        for field in ("focus_comparison", "summary_records"):
            receipt = copy.deepcopy(self.receipt)
            receipt["calendar"][field] = []
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "receipt.json"
                path.write_text(json.dumps(rehash(receipt)), encoding="utf-8")
                result = subprocess.run([sys.executable, "-S", "-B", str(ROOT / "verify.py"), str(path)],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
