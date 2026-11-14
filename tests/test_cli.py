"""Public CLI accepts the same meaningful inputs and validation as HTTP."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from verify import check_receipt
from tests.test_http_boundaries import CSV

ROOT = Path(__file__).resolve().parent.parent


class TestCLI(unittest.TestCase):
    def command(self, *arguments, env=None):
        return subprocess.run([sys.executable, str(ROOT / "run.py"), *arguments], cwd=ROOT,
                              capture_output=True, timeout=20, env=env)

    def test_invalid_focus_and_preset_exit_two_without_traceback(self):
        for args in [("--aoi", "AOI-AMZ", "--month", "0"), ("--aoi", "missing")]:
            with self.subTest(args=args):
                result = self.command(*args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn(b"Traceback", result.stderr)

    def test_csv_and_unicode_output_receipt_and_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, receipt, package = root / "sample.csv", root / "receipt.json", root / "evidence.zip"
            source.write_text(CSV, encoding="utf-8")
            result = self.command("--csv", str(source), "--name", "Dữ liệu cháy", "--receipt", str(receipt), "--package", str(package),
                                  env={**os.environ, "PYTHONIOENCODING": "ascii"})
            self.assertEqual(result.returncode, 0, result.stderr[:300])
            state = json.loads(result.stdout.decode("utf-8"))
            self.assertEqual(state["aoi"]["name"], "Dữ liệu cháy")
            self.assertEqual(state["provenance"]["source_kind"], "uploaded_csv")
            self.assertEqual(check_receipt(json.loads(receipt.read_text(encoding="utf-8")))["status"], "VALID")
            with zipfile.ZipFile(package) as bundle:
                self.assertEqual(json.loads(bundle.read("receipt.json"))["run_id"], state["run_id"])

    def test_geojson_and_point_inputs_work(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "aoi.json"
            source.write_text(json.dumps({"type": "Point", "coordinates": [105, 10]}), encoding="utf-8")
            for args in [("--geojson", str(source)), ("--lat", "10", "--lon", "105", "--radius-km", "5")]:
                with self.subTest(args=args):
                    result = self.command(*args)
                    self.assertEqual(result.returncode, 0, result.stderr[:300])
                    self.assertEqual(json.loads(result.stdout)["aoi"]["source_kind"], "generated_demo")
