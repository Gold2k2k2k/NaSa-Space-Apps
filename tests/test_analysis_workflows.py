"""Analysis identities, preserved inputs and consistent counterfactual evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents import apply_what_if, run_investigation
from app.canonical import sha256_of
from app.receipt import build_receipt, package_zip
from verify import check_receipt

ROOT = Path(__file__).resolve().parent.parent
REQUEST = {"lat": 0, "lon": 0, "radius_km": 10, "focus_year": 2026, "focus_month": 8}
ROWS = [{"latitude": .01, "longitude": .01, "acq_date": "2026-08-10",
         "instrument": "MODIS", "satellite": "T", "confidence": 90,
         "frp": 30, "daynight": "D", "acq_time": "1030", "type": 0}]


class TestAnalysisSnapshots(unittest.TestCase):
    def test_changed_source_content_changes_identity(self):
        first = run_investigation(REQUEST, raw_records_override=ROWS)
        changed = [{**ROWS[0], "frp": 60}]
        second = run_investigation(REQUEST, raw_records_override=changed)
        self.assertNotEqual(first["run_id"], second["run_id"])

    def test_caller_mutation_cannot_change_retained_source(self):
        rows = copy.deepcopy(ROWS)
        state = run_investigation(REQUEST, raw_records_override=rows)
        rows[0]["frp"] = 999
        self.assertEqual(state["_raw_records"][0]["frp"], 30)

    def test_counterfactual_has_new_identity_and_does_not_change_parent(self):
        state = run_investigation(REQUEST, raw_records_override=ROWS)
        before = sha256_of(state)
        changed = apply_what_if(state, "mode", "raw")
        self.assertNotEqual(state["run_id"], changed["run_id"])
        self.assertEqual(before, sha256_of(state))
        self.assertEqual(check_receipt(build_receipt(changed))["status"], "VALID")

    def test_all_toggles_preserve_full_geometry_and_records(self):
        geometry = {"type": "MultiPolygon", "coordinates": [
            [[[0, 0], [.1, 0], [.1, .1], [0, .1], [0, 0]],
             [[.03, .03], [.03, .05], [.05, .05], [.05, .03], [.03, .03]]],
            [[[.2, 0], [.3, 0], [.3, .1], [.2, .1], [.2, 0]]]]}
        state = run_investigation({"geojson": geometry, "focus_month": 8}, raw_records_override=ROWS)
        for field, value in [("mode", "raw"), ("flare_guard", False), ("focus_period", [2026, 7]),
                             ("confidence_min", "high"), ("persona", "scientist")]:
            with self.subTest(field=field):
                changed = apply_what_if(state, field, value)
                self.assertEqual(changed["aoi"]["geometry"], state["aoi"]["geometry"])
                self.assertEqual(changed["_raw_records"], state["_raw_records"])
                self.assertEqual(check_receipt(build_receipt(changed))["status"], "VALID")

    def test_invalid_counterfactual_values_are_not_coerced(self):
        state = run_investigation(REQUEST, raw_records_override=ROWS)
        for field, value in [("mode", "typo"), ("flare_guard", "false"), ("focus_period", []),
                             ("focus_year", True), ("focus_month", 0), ("persona", "typo")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                apply_what_if(state, field, value)

    def test_trace_and_package_do_not_depend_on_execution_clock(self):
        with patch("app.agents._now_iso", return_value="2026-01-01T00:00:00Z"):
            first = run_investigation(REQUEST, raw_records_override=ROWS)
        with patch("app.agents._now_iso", return_value="2026-02-01T00:00:00Z"):
            second = run_investigation(REQUEST, raw_records_override=ROWS)
        self.assertEqual(package_zip(first), package_zip(second))

    def test_median_counterfactual_rebuilds_calendar_queries_and_receipt(self):
        state = run_investigation({"aoi_id": "AOI-AMZ"})
        before = sha256_of(state)
        changed = apply_what_if(state, "focus_to_median", True)
        self.assertEqual(check_receipt(build_receipt(changed))["status"], "VALID")
        focus = changed["calendar"]["focus_comparison"]
        cell = next(c for c in changed["calendar"]["cells"] if (c["year"], c["month"]) == (focus["year"], focus["month"]))
        self.assertEqual(cell["value"], focus["value"])
        self.assertEqual(focus["value"], focus["hist_median"])
        self.assertEqual(changed["calendar"]["counterfactual"]["kind"], "focus_metric_to_median")
        self.assertEqual(changed["what_if"]["experiments"][0]["z_before"], 0.0)
        annual = next(r for r in changed["calendar"]["annual_series"] if r["year"] == focus["year"])
        self.assertAlmostEqual(annual["value"], sum(c["value"] for c in changed["calendar"]["cells"] if c["year"] == focus["year"] and c["is_observed"]), places=5)
        self.assertEqual(changed["_raw_records"], state["_raw_records"])
        self.assertNotEqual(changed["run_id"], state["run_id"])
        self.assertEqual(before, sha256_of(state))

    def test_cross_process_identity_receipt_and_archive_are_reproducible(self):
        script = ("import hashlib,json; from app.agents import run_investigation; "
                  "from app.receipt import build_receipt,package_zip; "
                  f"r=run_investigation({REQUEST!r},raw_records_override={ROWS!r}); "
                  "print(json.dumps([r['run_id'],build_receipt(r)['receipt_sha256'],hashlib.sha256(package_zip(r)).hexdigest()]))")
        results = []
        for seed in ("1", "123"):
            output = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=True)
            results.append(json.loads(output.stdout))
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
