"""Real-case entry, immutable experiments and independently verified evidence."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from app.canonical import sha256_of
from app.agents import apply_what_if
from app.receipt import build_receipt, package_zip
from verify import check_receipt

ROOT = Path(__file__).resolve().parents[1]


class TestJudgingWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import case_studies
        if hasattr(case_studies, "run_case_study"):
            cls.snapshot = case_studies.run_case_study("central-highlands")
        else:
            cls.snapshot = None

    def test_real_case_defaults_and_experiments_keep_source_and_model(self):
        self.assertIsNotNone(self.snapshot, "Real-case execution entry is missing")
        run = self.snapshot
        self.assertEqual(run["verdict"], "UNVERIFIABLE")
        self.assertEqual((run["options"]["year_start"], run["options"]["year_end"], run["options"]["focus_year"]), (2001, 2024, 2024))
        self.assertEqual(run["options"]["persona"], "land_manager")
        self.assertEqual(run["options"]["confidence_min"], "nominal")
        self.assertEqual(run["options"]["focus_month"], max(run["calendar"]["climatology"], key=lambda r: r["median"] if r["median"] is not None else -1)["month"])
        original = sha256_of(run)
        for field, value in [("mode", "raw"), ("persona", "scientist"), ("focus_period", [2023, 3]), ("focus_to_median", True),
                             ("confidence_min", "high"), ("flare_guard", False)]:
            with self.subTest(field=field):
                changed = apply_what_if(run, field, value)
                self.assertEqual(changed["provenance"]["source_kind"], "nasa_firms_archive")
                self.assertEqual(changed["source_manifest"], run["source_manifest"])
                self.assertEqual(changed["_raw_records"], run["_raw_records"])
                self.assertEqual(changed["verdict"], "UNVERIFIABLE")
                model = changed["sensor_calibration_audit"]["calibration_model"]
                if field not in ("confidence_min", "flare_guard"):
                    self.assertEqual(model, run["sensor_calibration_audit"]["calibration_model"])
                else:
                    self.assertNotEqual(model["model_id"], run["sensor_calibration_audit"]["calibration_model"]["model_id"])
                self.assertEqual(check_receipt(build_receipt(changed))["status"], "VALID")
        self.assertEqual(sha256_of(run), original)

    def test_receipt_links_manifest_model_and_evaluation_and_zip_verifies(self):
        self.assertIsNotNone(self.snapshot, "Real-case execution entry is missing")
        receipt = build_receipt(self.snapshot)
        self.assertEqual(check_receipt(receipt)["status"], "VALID")
        for mutate in (lambda r: r["source_manifest"]["bbox"].__setitem__(0, 0),
                       lambda r: r["manager_brief"]["comparison"].__setitem__("status", "CRITICAL_ANOMALY"),
                       lambda r: r["sensor_calibration_audit"]["model_evaluation"]["training"]["power"].__setitem__("pairs", 999999),
                       lambda r: r["sensor_calibration_audit"]["model_evaluation"]["held_out"]["occupancy"]["agreement"].__setitem__("sample_count", 999999),
                       lambda r: r["sensor_calibration_audit"]["model_evaluation"].__setitem__("applied_kappa", 99)):
            forged = copy.deepcopy(receipt)
            mutate(forged)
            forged["receipt_sha256"] = sha256_of({k: v for k, v in forged.items() if k != "receipt_sha256"})
            self.assertEqual(check_receipt(forged)["status"], "TAMPERED")
        payload = package_zip(self.snapshot)
        self.assertEqual(payload, package_zip(self.snapshot))
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                self.assertIn("case_manifest.json", archive.namelist())
                self.assertIn("model_evaluation.json", archive.namelist())
                archive.extractall(directory)
            result = subprocess.run([sys.executable, "-S", "-B", "verify.py", "receipt.json"], cwd=directory,
                                    capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_http_case_route_rejects_geometry_and_unknown_ids(self):
        from fastapi.testclient import TestClient
        from app.api import app
        with TestClient(app) as client:
            listed = client.get("/api/case-studies")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()[0]["case_id"], "central-highlands")
            self.assertEqual(client.post("/api/case-studies/unknown/analyze", json={}).status_code, 404)
            for invalid in ({"lat": 0}, {"year_start": 2024, "year_end": 2020}, {"extra": True}):
                response = client.post("/api/case-studies/central-highlands/analyze", json=invalid)
                self.assertEqual(response.status_code, 422, response.text[:200])
            response = client.post("/api/case-studies/central-highlands/analyze", json={"focus_month": 3})
            self.assertEqual(response.status_code, 200, response.text[:200])
            self.assertEqual(response.json()["provenance"]["source_kind"], "nasa_firms_archive")

    def test_cli_uses_case_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            result = subprocess.run([sys.executable, "run.py", "--case-study", "central-highlands", "--output", str(path)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr[:1000])
            run = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(run["options"]["confidence_min"], "nominal")
            self.assertEqual(run["options"]["persona"], "land_manager")
            self.assertEqual(run["provenance"]["source_kind"], "nasa_firms_archive")

    def test_cli_case_reference_time_reaches_analysis_and_exported_evidence(self):
        expected = "2024-06-01T00:00:00Z"
        for reference in (expected, "2024-06-01T07:00:00+07:00"):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as directory:
                output, receipt, package = (Path(directory) / name for name in ("analysis.json", "receipt.json", "audit.zip"))
                result = subprocess.run(
                    [sys.executable, "-B", "run.py", "--case-study", "central-highlands",
                     "--reference-time", reference, "--output", str(output),
                     "--receipt", str(receipt), "--package", str(package)],
                    cwd=ROOT, capture_output=True, text=True, timeout=90,
                )
                self.assertEqual(result.returncode, 0, result.stderr[:1000])
                run = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(run["reference_time"], expected)
                self.assertEqual(run["passes"]["reference_time"], expected)
                self.assertTrue(all(stage["timestamp"] == expected for stage in run["trace"]))
                self.assertNotEqual(run["run_id"], self.snapshot["run_id"])
                self.assertEqual(run["provenance"], self.snapshot["provenance"])
                self.assertEqual(run["sensor_calibration_audit"]["calibration_model"],
                                 self.snapshot["sensor_calibration_audit"]["calibration_model"])
                exported = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(exported["reference_time"], expected)
                self.assertEqual(exported["run_id"], run["run_id"])
                self.assertEqual(check_receipt(exported)["status"], "VALID")
                with zipfile.ZipFile(package) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(json.loads(archive.read("receipt.json")), exported)

    def test_cli_case_rejects_invalid_reference_times_without_writing_exports(self):
        for reference, message in (("2024-06-01T00:00:00", "UTC offset"),
                                   ("not-a-timestamp", "ISO timestamp"),
                                   ("2101-06-01T00:00:00Z", "between 2000 and 2100")):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as directory:
                targets = [Path(directory) / name for name in ("analysis.json", "receipt.json", "audit.zip")]
                result = subprocess.run(
                    [sys.executable, "-B", "run.py", "--case-study", "central-highlands",
                     "--reference-time", reference, "--output", str(targets[0]),
                     "--receipt", str(targets[1]), "--package", str(targets[2])],
                    cwd=ROOT, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertTrue(all(not target.exists() for target in targets))


if __name__ == "__main__":
    unittest.main()

