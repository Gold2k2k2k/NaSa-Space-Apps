"""Complete exports, reference-bound model schedules and independent geometry."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents import apply_what_if, run_investigation
from app.api import app
from app.exports import export_calendar_csv, export_calendar_ics, export_hotspots_csv, export_hotspots_geojson
from app.geo_passes import predict_passes
from app.receipt import package_zip
from tests.test_analysis_workflows import REQUEST, ROWS
from tests.test_http_boundaries import CSV

UTC = timezone.utc


class TestModeledPasses(unittest.TestCase):
    def test_spherical_geometry_has_defined_overhead_and_horizon_boundaries(self):
        from app.geo_passes import viewing_geometry
        overhead = viewing_geometry(0, 705)
        self.assertAlmostEqual(overhead["max_elevation_deg"], 90)
        self.assertAlmostEqual(overhead["viewing_zenith_deg"], 0)
        radius = 6371.0088
        distance = radius * math.acos(radius / (radius + 705))
        horizon = viewing_geometry(distance, 705)
        self.assertAlmostEqual(horizon["max_elevation_deg"], 0, places=5)
        self.assertAlmostEqual(horizon["viewing_zenith_deg"], 90, places=5)
        self.assertLess(horizon["sensor_off_nadir_deg"], horizon["viewing_zenith_deg"])

    def test_reference_window_is_complete_and_not_truncated(self):
        start = datetime(2026, 10, 10, 17, 47, tzinfo=UTC)
        result = predict_passes(30, 179.9, days=16, start_dt=start)
        self.assertEqual(result["pass_count"], len(result["passes"]))
        self.assertEqual(result.get("reference_time"), "2026-10-10T17:47:00Z")
        self.assertIn("approximate", result["note"].lower())
        for row in result["passes"]:
            stamp = datetime.fromisoformat(row["utc_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(row["end_utc"].replace("Z", "+00:00"))
            self.assertGreaterEqual(stamp, start)
            self.assertLess(stamp, start + timedelta(days=16))
            self.assertLessEqual(end, start + timedelta(days=16))
            self.assertGreater(end, stamp)
            self.assertLessEqual(row["off_nadir_km"], row["swath_km"] / 2 + .01)

    def test_date_rollover_and_constellation_spacing_are_preserved(self):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        result = predict_passes(0, -179.9, days=3, start_dt=start)
        for row in result["passes"]:
            stamp = datetime.fromisoformat(row["utc_time"].replace("Z", "+00:00"))
            local = stamp + timedelta(hours=-179.9 / 15)
            hours, minutes = map(int, row["local_solar_time"].split(":"))
            self.assertLess(abs(local.hour * 60 + local.minute - hours * 60 - minutes), 1.1)
        from app.geo_passes import SATELLITES
        sats = {s["name"]: s for s in SATELLITES}
        self.assertAlmostEqual((sats["NOAA-20"]["day_lst_hour"] - sats["NOAA-21"]["day_lst_hour"]) * 60, 50)

    def test_ended_sources_are_not_advertised_as_future_observation_opportunities(self):
        result = predict_passes(0, 0, days=5, start_dt=datetime(2026, 11, 14, tzinfo=UTC))
        self.assertNotIn("Suomi NPP", result["satellites_tracked"])
        self.assertFalse(any(p["satellite"] == "Suomi NPP" for p in result["passes"]))
        self.assertTrue(any("15:40" in item["reason"] for item in result.get("excluded_sources", [])))

    def test_invalid_inputs_are_rejected_instead_of_clamped(self):
        for arguments in [dict(lat=0, lon=0, days=0), dict(lat=0, lon=0, days=True),
                          dict(lat=True, lon=0), dict(lat=math.inf, lon=0),
                          dict(lat=0, lon=0, start_dt=datetime(2026, 1, 1))]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                predict_passes(**arguments)


class TestCompleteExports(unittest.TestCase):
    def setUp(self):
        self.state = run_investigation(REQUEST, raw_records_override=ROWS)

    def test_csv_and_geojson_export_every_hotspot_including_excluded_sources(self):
        spot = self.state["_hotspots_all"][0]
        self.state["_hotspots_all"] = [{**spot, "hotspot_id": f"H-{i}", "include_in_calendar": i != 6000} for i in range(6001)]
        rows = list(csv.DictReader(io.StringIO(export_hotspots_csv(self.state))))
        collection = export_hotspots_geojson(self.state)
        self.assertEqual(len(rows), 6001)
        self.assertEqual(len(collection["features"]), 6002)
        self.assertEqual(rows[-1]["include_in_calendar"], "False")
        self.assertEqual(collection["firetrace"]["export_scope"], "complete")
        self.assertEqual(collection["features"][-1]["properties"]["include_in_calendar"], False)

    def test_geojson_keeps_every_component_and_hole(self):
        geometry = {"type": "MultiPolygon", "coordinates": [
            [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]], [[.5, .5], [.5, 1], [1, 1], [1, .5], [.5, .5]]],
            [[[3, 0], [4, 0], [4, 1], [3, 1], [3, 0]]]]}
        self.state["aoi"]["geometry"] = geometry
        self.assertEqual(export_hotspots_geojson(self.state)["features"][0]["geometry"], geometry)

    def test_csv_has_active_metric_mode_coverage_and_formula_escaping(self):
        self.state["aoi"]["name"] = "=HYPERLINK(1)"
        rows = list(csv.DictReader(io.StringIO(export_calendar_csv(self.state))))
        focus = next(r for r in rows if r["year"] == "2026" and r["month"] == "8")
        self.assertEqual(focus["mode"], "harmonized")
        self.assertEqual(focus["coverage_status"], "records_only")
        self.assertEqual(float(focus["value"]), 1)
        self.assertTrue(focus["aoi_name"].startswith("'="))
        self.assertEqual(rows[0]["value"], "")

    def test_ics_escapes_controls_folds_utf8_and_uses_reference_year(self):
        self.state = run_investigation({**REQUEST, "reference_time": "2030-12-31T20:00:00Z"}, raw_records_override=ROWS)
        self.state["aoi"]["name"] = "Cháy rừng " * 30 + "\r\nBEGIN:VEVENT\rX-INJECTED:bad\x00\x7f"
        self.state["calendar"]["summary_records"]["peak_months"] = [2]
        text = export_calendar_ics(self.state)
        self.assertNotIn("\rX-INJECTED", text)
        self.assertNotIn("\x00", text)
        self.assertTrue("\x7f" not in text, "DEL controls must be removed")
        self.assertNotIn("\r\nBEGIN:VEVENT\\n", text)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        unfolded = text.replace("\r\n ", "")
        self.assertIn("DTSTAMP:20301231T200000Z", unfolded)
        self.assertIn("DTSTART;VALUE=DATE:20310201", unfolded)
        self.assertIn("DTEND;VALUE=DATE:20310301", unfolded)
        self.assertIn("MODELED", unfolded)
        self.assertIn("not a forecast", unfolded)

    def test_package_includes_source_and_dependency_free_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(io.BytesIO(package_zip(self.state))) as bundle:
                self.assertIn("source_records.json", bundle.namelist())
                self.assertIn("verify.py", bundle.namelist())
                self.assertEqual(json.loads(bundle.read("source_records.json")), ROWS)
                manifest = json.loads(bundle.read("manifest.sha256.json"))
                self.assertEqual(set(manifest), set(bundle.namelist()) - {"manifest.sha256.json"})
                for name, expected in manifest.items():
                    self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), expected)
                bundle.extractall(root)
            result = subprocess.run([sys.executable, "-S", "-B", str(root / "verify.py"), str(root / "receipt.json")],
                                    cwd=root, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout[:300] + result.stderr[:300])


class TestDownloadHTTP(unittest.TestCase):
    def test_all_downloads_and_passes_share_the_stored_snapshot(self):
        client = TestClient(app)
        output = client.post("/api/upload-csv", files={"file": ("mixed.csv", CSV, "text/csv")}).json()
        identity = output["run_id"]
        result = client.get("/api/passes", params={"run_id": identity})
        self.assertEqual(result.status_code, 200, result.text[:300])
        self.assertEqual(result.json()["reference_time"], output["reference_time"])
        changed = client.post(f"/runs/{identity}/what_if", json={"field": "mode", "value": "raw"}).json()
        self.assertEqual(changed["reference_time"], output["reference_time"])
        self.assertEqual(changed["passes"], output["passes"])
        for suffix in (f"/runs/{identity}/receipt", f"/runs/{identity}/package",
                       f"/api/export/{identity}/hotspots.csv", f"/api/export/{identity}/calendar.csv",
                       f"/api/export/{identity}/hotspots.geojson", f"/api/export/{identity}/calendar.ics"):
            with self.subTest(suffix=suffix):
                response = client.get(suffix)
                self.assertEqual(response.status_code, 200, response.text[:100] if "zip" not in response.headers.get("Content-Type", "") else "ZIP failure")
                self.assertGreater(len(response.content), 10)
        for parameters in ({"aoi_id": "missing"}, {"lat": 91, "lon": 0}, {"lat": 0, "lon": 0, "days": 0}, {"run_id": "missing"}):
            with self.subTest(parameters=parameters):
                self.assertIn(client.get("/api/passes", params=parameters).status_code, (404, 422))
