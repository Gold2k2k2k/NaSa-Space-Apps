"""Comprehensive Unit & Integration Tests for FireTrace."""
from __future__ import annotations

import copy
import io
import unittest
import zipfile

from fastapi.testclient import TestClient

from app.agents import apply_what_if, run_investigation
from app.api import app
from app.exports import (
    export_calendar_csv,
    export_calendar_ics,
    export_hotspots_csv,
    export_hotspots_geojson,
)
from app.geo_passes import predict_passes
from app.receipt import build_receipt
from app.schema_mapping import normalize_hotspot_row
from verify import check_receipt


class TestSchemaMapping(unittest.TestCase):
    def test_modis_and_viirs_synonym_resolution(self) -> None:
        modis = normalize_hotspot_row({
            "latitude": -11.524,
            "longitude": -55.175,
            "brightness": 334.5,
            "bright_t31": 294.1,
            "scan": 1.4,
            "track": 1.1,
            "acq_date": "2024-09-12",
            "acq_time": "1335",
            "satellite": "Aqua",
            "instrument": "MODIS",
            "confidence": 85,
            "frp": 48.2,
            "daynight": "D",
            "type": 0,
        })
        viirs = normalize_hotspot_row({
            "latitude": -11.526,
            "longitude": -55.176,
            "bright_ti4": 348.0,
            "bright_ti5": 293.0,
            "scan": 0.41,
            "track": 0.39,
            "acq_date": "2024-09-12",
            "acq_time": "1330",
            "satellite": "N20",
            "instrument": "VIIRS",
            "confidence": "h",
            "frp": 21.5,
            "daynight": "d",
            "type": 0,
        })
        self.assertEqual(modis["cell_id"], viirs["cell_id"])
        self.assertEqual(modis["mir_bt_k"], 334.5)
        self.assertEqual(viirs["mir_bt_k"], 348.0)
        self.assertEqual(modis["confidence_class"], "high")
        self.assertEqual(viirs["confidence_class"], "high")
        self.assertEqual(viirs["satellite"], "NOAA-20")
        self.assertTrue(viirs["is_afternoon_train"])

    def test_invalid_coordinates_raise(self) -> None:
        with self.assertRaises(ValueError):
            normalize_hotspot_row({"latitude": 99.0, "longitude": 10.0, "acq_date": "2024-01-01"})


class TestHarmonizationAndRules(unittest.TestCase):
    def test_all_six_benchmark_regimes_and_determinism(self) -> None:
        expected = {
            "AOI-AMZ": "CRITICAL_ANOMALY",
            "AOI-MEK": "ELEVATED_WATCH",
            "AOI-CAL": "CRITICAL_ANOMALY",
            "AOI-NSW": "NOMINAL_REGIME",
            "AOI-MIO": "NOMINAL_REGIME",
            "AOI-FLR": "UNVERIFIABLE",
        }
        for aoi_id, want in expected.items():
            r1 = run_investigation({"aoi_id": aoi_id})
            r2 = run_investigation({"aoi_id": aoi_id})
            self.assertEqual(r1["verdict"], want, f"Mismatch on {aoi_id}")
            self.assertEqual(r1["verdict_sha256"], r2["verdict_sha256"])

    def test_mekong_raw_trap_flips_verdict(self) -> None:
        harm = run_investigation({"aoi_id": "AOI-MEK", "mode": "harmonized"})
        raw = apply_what_if(harm, "mode", "raw")
        self.assertEqual(harm["verdict"], "ELEVATED_WATCH")
        self.assertEqual(raw["verdict"], "CRITICAL_ANOMALY")
        self.assertGreaterEqual(harm["sensor_calibration_audit"]["bias_reduction_pct"], 80.0)

    def test_basra_flare_guard_flip(self) -> None:
        guarded = run_investigation({"aoi_id": "AOI-FLR", "flare_guard": True})
        unguarded = apply_what_if(guarded, "flare_guard", False)
        self.assertEqual(guarded["verdict"], "UNVERIFIABLE")
        self.assertEqual(unguarded["verdict"], "NOMINAL_REGIME")

    def test_receipt_verify_and_tamper_detection(self) -> None:
        out = run_investigation({"aoi_id": "AOI-CAL"})
        receipt = build_receipt(out)
        valid = check_receipt(receipt)
        self.assertEqual(valid["status"], "VALID")

        forged = copy.deepcopy(receipt)
        forged["calendar_summary"]["focus_comparison"]["value"] = 1.0
        tampered = check_receipt(forged)
        self.assertEqual(tampered["status"], "TAMPERED")

    def test_exports_and_satellite_passes(self) -> None:
        out = run_investigation({"aoi_id": "AOI-AMZ"})
        self.assertIn("hotspot_id,cell_id", export_hotspots_csv(out))
        self.assertIn("hist_median_hhe", export_calendar_csv(out))
        gj = export_hotspots_geojson(out)
        self.assertEqual(gj["type"], "FeatureCollection")
        ics = export_calendar_ics(out)
        self.assertIn("BEGIN:VCALENDAR", ics)
        passes = predict_passes(-11.5, -55.2, days=3)
        self.assertGreater(passes["pass_count"], 0)


class TestHTTPAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_full_api_workflow(self) -> None:
        h = self.client.get("/health")
        self.assertEqual(h.status_code, 200)
        self.assertEqual(h.json()["status"], "ok")

        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("FireTrace", page.text)
        for asset in ("/static/app.css", "/static/app.js", "/static/mark.svg", "/static/fonts/Geist-Variable.woff2"):
            self.assertEqual(self.client.get(asset).status_code, 200, f"Missing static asset {asset}")

        setup = self.client.get("/ui/setup").json()
        self.assertEqual(len(setup["aois"]), 6)

        manifesto = self.client.get("/api/schema-mapping").json()
        self.assertEqual(len(manifesto["manifesto"]), 4)

        res = self.client.post("/api/analyze", json={"aoi_id": "AOI-MEK"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        run_id = data["run_id"]
        self.assertEqual(data["verdict"], "ELEVATED_WATCH")

        wf = self.client.post(f"/runs/{run_id}/what_if", json={"field": "mode", "value": "raw"})
        self.assertEqual(wf.status_code, 200)
        self.assertEqual(wf.json()["verdict"], "CRITICAL_ANOMALY")

        # Export endpoints
        self.assertEqual(self.client.get(f"/api/export/{run_id}/hotspots.csv").status_code, 200)
        self.assertEqual(self.client.get(f"/api/export/{run_id}/calendar.csv").status_code, 200)
        self.assertEqual(self.client.get(f"/api/export/{run_id}/hotspots.geojson").status_code, 200)
        self.assertEqual(self.client.get(f"/api/export/{run_id}/calendar.ics").status_code, 200)
        self.assertEqual(self.client.get(f"/runs/{run_id}/receipt").status_code, 200)

        pkg = self.client.get(f"/runs/{run_id}/package")
        self.assertEqual(pkg.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(pkg.content)) as zf:
            names = set(zf.namelist())
            self.assertIn("receipt.json", names)
            self.assertIn("hotspots_harmonized.csv", names)
            self.assertIn("burning_calendar.csv", names)

    def test_csv_upload_and_bench(self) -> None:
        csv_payload = (
            "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,bright_t31,frp,daynight,type\n"
            "-11.50,-55.20,330.0,1.0,1.0,2020-09-10,1330,Aqua,MODIS,85,292.0,32.0,D,0\n"
            "-11.51,-55.21,328.0,1.0,1.0,2021-09-12,1330,Aqua,MODIS,82,291.0,28.0,D,0\n"
            "-11.50,-55.20,342.0,0.4,0.4,2024-09-15,1335,N20,VIIRS,h,293.0,25.0,D,0\n"
        )
        up = self.client.post("/api/upload-csv", files={"file": ("sample_firms.csv", csv_payload, "text/csv")})
        self.assertEqual(up.status_code, 200)
        self.assertEqual(up.json()["status"], "success")

        bench = self.client.post("/api/bench")
        self.assertEqual(bench.status_code, 200)
        self.assertTrue(bench.json()["all_pass"])


if __name__ == "__main__":
    unittest.main()

