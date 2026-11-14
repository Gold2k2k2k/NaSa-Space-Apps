"""HTTP validation, bounded uploads and immutable cached snapshots."""
from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from app.api import app
from tests.test_analysis_workflows import REQUEST

CSV = ("latitude,longitude,acq_date,instrument,satellite,confidence,frp,daynight,acq_time,type\n"
       "10,179.9,2026-08-10,MODIS,T,90,30,D,1030,0\n"
       "10,-179.9,2026-08-11,VIIRS,N20,h,20,D,1330,0\n"
       "bad,0,2026-08-12,MODIS,T,90,30,D,1030,0\n")


class TestHTTPBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_malformed_analysis_is_422(self):
        for payload in [[], None, {"aoi_id": "missing"}, {**REQUEST, "focus_month": 13},
                        {**REQUEST, "flare_guard": "false"}, {**REQUEST, "extra": 1},
                        {**REQUEST, "lat": float("nan")}]:
            with self.subTest(payload=payload):
                result = self.client.post("/api/analyze", content=json.dumps(payload), headers={"Content-Type": "application/json"})
                self.assertEqual(result.status_code, 422, result.text[:300])

    def test_deep_json_returns_controlled_error(self):
        result = self.client.post("/api/analyze", content="[" * 2000 + "0" + "]" * 2000,
                                  headers={"Content-Type": "application/json"})
        self.assertEqual(result.status_code, 422)

    def test_oversized_analysis_body_is_rejected(self):
        result = self.client.post("/api/analyze", json={"name": "a" * (300 * 1024)})
        self.assertEqual(result.status_code, 413)

    def test_streamed_upload_and_json_body_limits_are_enforced(self):
        boundary = b"firetrace-boundary"
        prefix = b"--" + boundary + b'\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n'
        result = self.client.post("/api/upload-csv", content=iter([prefix, b"x" * (12 * 1024 * 1024), b"\r\n--" + boundary + b"--\r\n"]),
            headers={"Content-Type": "multipart/form-data; boundary=firetrace-boundary"})
        self.assertEqual(result.status_code, 413, result.text[:300])
        result = self.client.post("/api/analyze", content=iter([b"[", b"0," * (150 * 1024), b"0]"]),
            headers={"Content-Type": "application/json"})
        self.assertEqual(result.status_code, 413, result.text[:300])

    def test_unspecified_focus_uses_requested_short_window(self):
        result = self.client.post("/api/analyze", json={"lat": 0, "lon": 0, "year_start": 2010, "year_end": 2011})
        self.assertEqual(result.status_code, 200, result.text[:300])
        self.assertEqual(result.json()["options"]["focus_year"], 2011)

    def test_upload_metadata_geometry_and_parent_are_preserved(self):
        result = self.client.post("/api/upload-csv", files={"file": ("mixed.csv", CSV, "text/csv")})
        self.assertEqual(result.status_code, 200, result.text[:300])
        original = result.json()
        self.assertEqual(original["aoi"]["aoi_id"][:4], "CSV-")
        self.assertEqual(original["aoi"]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(original["ingestion"]["rejected_rows"], 1)
        self.assertEqual(original["provenance"]["source_kind"], "uploaded_csv")
        parent_id = original["run_id"]
        changed = self.client.post(f"/runs/{parent_id}/what_if", json={"field": "mode", "value": "raw"})
        self.assertEqual(changed.status_code, 200, changed.text[:300])
        self.assertNotEqual(changed.json()["run_id"], parent_id)
        self.assertEqual(changed.json()["aoi"], original["aoi"])
        self.assertEqual(self.client.get(f"/runs/{parent_id}").json(), original)
        self.assertEqual(changed.json()["ingestion"], original["ingestion"])

    def test_invalid_upload_options_are_422(self):
        for query in ("focus_month=13", "focus_month=0", "mode=typo", "persona=typo", "confidence_min=typo"):
            with self.subTest(query=query):
                result = self.client.post("/api/upload-csv?" + query, files={"file": ("a.csv", CSV, "text/csv")})
                self.assertEqual(result.status_code, 422, result.text[:300])

    def test_upload_read_is_bounded(self):
        from app.datasets import MAX_CSV_BYTES
        result = self.client.post("/api/upload-csv", files={"file": ("large.csv", b"x" * (MAX_CSV_BYTES + 1), "text/csv")})
        self.assertEqual(result.status_code, 413)

    def test_malformed_what_if_and_unknown_run(self):
        self.assertEqual(self.client.get("/runs/missing").status_code, 404)
        self.assertEqual(self.client.get("/runs/missing/receipt").status_code, 404)
        result = self.client.post("/api/upload-csv", files={"file": ("a.csv", CSV, "text/csv")}).json()
        for body in ({"field": "focus_period", "value": []}, {"field": "mode", "value": "typo"},
                     {"field": "flare_guard", "value": "false"}, {"field": "unknown", "value": True}):
            with self.subTest(body=body):
                changed = self.client.post(f"/runs/{result['run_id']}/what_if", json=body)
                self.assertEqual(changed.status_code, 422)


if __name__ == "__main__":
    unittest.main()
