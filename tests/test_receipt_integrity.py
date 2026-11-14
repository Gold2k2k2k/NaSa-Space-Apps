"""Regressions for independently verified receipt integrity failures."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents import run_investigation
from app.canonical import sha256_of
from app.receipt import build_receipt, package_zip
from verify import check_receipt

ROOT = Path(__file__).resolve().parent.parent


class TestReceiptIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analysis = run_investigation({"aoi_id": "AOI-MEK"})
        cls.receipt = build_receipt(cls.analysis)

    def test_real_receipt_survives_json_round_trip(self) -> None:
        receipt = json.loads(json.dumps(self.receipt))
        self.assertEqual(check_receipt(receipt)["status"], "VALID")

    def test_committed_legacy_examples_use_their_frozen_rules(self):
        paths = sorted((ROOT / "output_examples").glob("*receipt.json"))
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertEqual(check_receipt(json.loads(path.read_text(encoding="utf-8")))["status"], "VALID")

    def test_deep_receipt_cli_exits_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "verify.py"), str(path)],
                                    capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_fixed_run_archive_does_not_depend_on_wall_clock(self) -> None:
        with patch("zipfile.time.localtime", return_value=(2026, 1, 1, 0, 0, 0, 3, 1, -1)):
            first = package_zip(self.analysis)
        with patch("zipfile.time.localtime", return_value=(2026, 2, 1, 0, 0, 0, 6, 32, -1)):
            second = package_zip(self.analysis)
        self.assertEqual(first, second)

    def test_combined_csv_columns_do_not_change_sensor_counts(self) -> None:
        shared = {"latitude": 10.0, "longitude": 105.0, "acq_date": "2026-08-10",
                  "frp": 30, "daynight": "D", "confidence": "high"}
        rows = [
            {**shared, "instrument": "MODIS", "satellite": "T", "brightness": 330,
             "bright_ti4": ""},
            {**shared, "instrument": "VIIRS", "satellite": "N20", "brightness": "",
             "bright_ti4": 340},
        ]
        output = run_investigation({"custom_lat": 10.0, "custom_lon": 105.0},
                                   raw_records_override=rows)
        queries = {q["query_id"]: q["rows"][0] for q in output["queries"]}
        self.assertEqual(queries["Q1"]["raw_detections"], 1)
        self.assertEqual(queries["Q2"]["raw_detections"], 1)
        self.assertEqual(check_receipt(build_receipt(output))["status"], "VALID")

    def test_query_cluster_count_includes_filtered_thermal_sources(self) -> None:
        rows = [{"latitude": 10.0 + i * 0.05, "longitude": 105.0,
                 "acq_date": "2026-08-10", "frp": 30, "daynight": "D",
                 "instrument": "MODIS", "satellite": "T", "confidence": 90,
                 "type": 2 if i == 0 else 0} for i in range(3)]
        output = run_investigation({"custom_lat": 10.0, "custom_lon": 105.0},
                                   raw_records_override=rows)
        query = next(q for q in output["queries"] if q["query_id"] == "Q3")
        self.assertEqual(query["rows"][0]["harmonized_cell_events"], 3)
        self.assertEqual(output["sensor_calibration_audit"]["total_harmonized_events"], 2)
        self.assertEqual(check_receipt(build_receipt(output))["status"], "VALID")

    def test_changed_displayed_decision_is_rejected(self) -> None:
        for field, value in [
            ("verdict", "CRITICAL_ANOMALY"),
            ("deciding_rule", 99),
            ("rules_version", "invented-rules"),
            ("findings", []),
        ]:
            with self.subTest(field=field):
                receipt = copy.deepcopy(self.receipt)
                receipt[field] = value
                self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_changed_finding_detail_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["findings"][0]["detail"] = "Invented scientific conclusion"
        self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_missing_or_duplicated_query_is_rejected(self) -> None:
        for action in ("remove", "duplicate"):
            with self.subTest(action=action):
                receipt = copy.deepcopy(self.receipt)
                if action == "remove":
                    receipt["queries"].pop(0)
                else:
                    receipt["queries"].append(copy.deepcopy(receipt["queries"][0]))
                self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_incorrect_query_row_count_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["queries"][0]["row_count"] += 1
        self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_changed_calendar_digest_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["calendar_summary"]["cells_sha256"] = "0" * 64
        self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_rehashed_query_still_has_to_match_its_evidence(self) -> None:
        changes = {
            "Q0": ("lat", 12.0), "Q1": ("raw_detections", 1),
            "Q2": ("raw_detections", 1), "Q3": ("calibrated_kappa", 9.0),
            "Q4": ("focus_night_share", 9.0),
            "Q5": ("flare_contamination_share", 9.0),
            "Q6": ("hist_p95", 90000.0), "Q7": ("rank_in_history", 999),
            "Q8": ("bridge_r2", 9.0),
        }
        for query_id, (field, value) in changes.items():
            with self.subTest(query=query_id):
                receipt = copy.deepcopy(self.receipt)
                query = next(q for q in receipt["queries"] if q["query_id"] == query_id)
                query["rows"][0][field] = value
                query["sha256"] = sha256_of(query["rows"])
                if "receipt_sha256" in receipt:
                    receipt["receipt_sha256"] = sha256_of({
                        k: v for k, v in receipt.items() if k != "receipt_sha256"
                    })
                self.assertEqual(check_receipt(receipt)["status"], "TAMPERED")

    def test_modified_receipt_cli_exits_one(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["verdict"] = "CRITICAL_ANOMALY"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "verify.py"), str(path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("TAMPERED", result.stdout)

    def test_malformed_receipt_cli_exits_two_without_traceback(self) -> None:
        for payload in [[], {"queries": [3]}, {"receipt_version": "unknown"}]:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "receipt.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "verify.py"), str(path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
