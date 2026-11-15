"""The real case must be an auditable NASA subset, usable without a network."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"


class TestJudgingCaseData(unittest.TestCase):
    def test_crlf_git_checkout_can_load_the_pinned_case(self):
        from app import case_studies
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "app" / "data"
            destination.mkdir(parents=True)
            names = ["central-highlands.csv", "central-highlands.manifest.json"]
            for name in names:
                shutil.copyfile(DATA / name, destination / name)
            if (ROOT / ".gitattributes").is_file():
                shutil.copyfile(ROOT / ".gitattributes", root / ".gitattributes")
            def git(*args):
                subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
                               check=True, capture_output=True)
            git("init", "-q")
            git("config", "core.autocrlf", "true")
            git("add", ".")
            for name in names:
                (destination / name).unlink()
            git("checkout-index", "--all", "--force")
            try:
                with patch.object(case_studies, "DATA_DIR", destination):
                    rows, aoi = case_studies.load_case_study("central-highlands")
            except ValueError as error:
                self.fail(f"Fresh Windows-style checkout must retain pinned bytes: {error}")
            self.assertEqual(len(rows), 16258)
            self.assertEqual(aoi["subset_sha256"], "5d28887cfc0e10d29facb805147b6743ca3353d30b496e3d21a59579f4380ef0")

    def test_committed_judging_results_match_the_verifiable_receipt(self):
        receipt_path = ROOT / "output_examples" / "central_highlands_receipt.json"
        self.assertTrue(receipt_path.is_file(), "A reproducible real-case example is missing")
        from verify import check_receipt
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        report = json.loads((ROOT / "docs" / "judging" / "results" / "model-evaluation.json").read_text(encoding="utf-8"))
        brief = json.loads((ROOT / "docs" / "judging" / "results" / "manager-brief.json").read_text(encoding="utf-8"))
        self.assertEqual(check_receipt(receipt)["status"], "VALID")
        self.assertEqual(receipt["verdict"], "UNVERIFIABLE")
        self.assertEqual(report, receipt["sensor_calibration_audit"]["model_evaluation"])
        self.assertEqual(brief, receipt["manager_brief"])

    def test_bundle_matches_declared_sources_and_extent(self):
        path = DATA / "central-highlands.manifest.json"
        self.assertTrue(path.is_file(), "The approved real NASA case is not bundled")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        payload = (DATA / "central-highlands.csv").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["subset"]["sha256"])
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        self.assertEqual(len(rows), 16258)
        self.assertEqual(sum(r["instrument"] == "MODIS" for r in rows), 4143)
        self.assertEqual(sum(r["instrument"] == "VIIRS" for r in rows), 12115)
        self.assertTrue(all(107.8 <= float(r["longitude"]) <= 108.5 and 12.5 <= float(r["latitude"]) <= 13.1 for r in rows))
        keys = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for r in rows]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(manifest["bbox"], [107.8, 12.5, 108.5, 13.1])
        sources = manifest["source_files"]
        self.assertEqual(len(sources), 37)
        expected = {f"https://firms.modaps.eosdis.nasa.gov/data/country/{family}/{y}/{family}_{y}_Vietnam.csv"
                    for family, start in [("modis", 2001), ("viirs-snpp", 2012)] for y in range(start, 2025)}
        self.assertEqual({s["url"] for s in sources}, expected)
        first = next(s for s in sources if s["filename"] == "modis_2001_Vietnam.csv")
        self.assertEqual(first["sha256"], "1a29e2bb33d40bef4606923aa47eb3c15d7be08a05e9027abd7d7e65a5fabfe9")
        self.assertEqual(first["bytes"], 234740)

    def test_loader_is_strict_fresh_and_detects_corruption(self):
        self.assertTrue((ROOT / "app" / "case_studies.py").is_file(), "Case loader is missing")
        from app import case_studies
        records, aoi = case_studies.load_case_study("central-highlands")
        self.assertEqual(len(records), 16258)
        self.assertEqual(aoi["source_kind"], "nasa_firms_archive")
        self.assertEqual(aoi.get("complete_periods", []), [])
        self.assertEqual(aoi["calibration_policy"]["training_years"], [2013, 2020])
        self.assertEqual(aoi["calibration_policy"]["evaluation_years"], [2021, 2024])
        records[0]["latitude"] = "0"
        aoi["source_manifest"]["bbox"][0] = 0
        again, source = case_studies.load_case_study("central-highlands")
        self.assertNotEqual(again[0]["latitude"], "0")
        self.assertEqual(source["source_manifest"]["bbox"][0], 107.8)
        for case_id in ("../central-highlands", "central-highlands.csv", "unknown"):
            with self.subTest(case_id=case_id), self.assertRaises(ValueError):
                case_studies.load_case_study(case_id)
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for name in ("central-highlands.csv", "central-highlands.manifest.json"):
                (temp / name).write_bytes((DATA / name).read_bytes())
            (temp / "central-highlands.csv").write_bytes(b"corrupt")
            with patch.object(case_studies, "DATA_DIR", temp), self.assertRaisesRegex(ValueError, "integrity"):
                case_studies.load_case_study("central-highlands")


if __name__ == "__main__":
    unittest.main()
