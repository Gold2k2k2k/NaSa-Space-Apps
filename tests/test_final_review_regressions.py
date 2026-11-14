"""Independent boundary reproductions from the final two-axis review."""
import copy
import unittest

from app.agents import run_investigation
from app.calendar_engine import build_burning_calendar
from app.canonical import sha256_of
from app.datasets import parse_custom_aoi, parse_uploaded_csv
from app.harmonize import harmonize_records
from app.receipt import build_receipt, package_zip
from app.rules import decide
from app.run_store import RunStore
from verify import check_receipt


class TestFinalReviewRegressions(unittest.TestCase):
    def test_records_in_every_month_do_not_establish_complete_transition_years(self):
        aoi = parse_custom_aoi({"lat": 0, "lon": 0})
        rows = [{"latitude": 0, "longitude": 0, "acq_date": f"{year}-{month:02d}-10",
                 "satellite": "T", "confidence": 90, "daynight": "D"}
                for year in range(2009, 2015) for month in range(1, 13)
                for _ in range(1 if year < 2012 else 2)]
        audit = harmonize_records(rows, aoi)["sensor_calibration_audit"]
        transition = audit["transition_audits"][0]
        self.assertEqual(transition["status"], "insufficient_complete_years")
        for key in ("raw_step_pct", "harmonized_step_pct", "bias_reduction_pct"):
            self.assertIsNone(transition[key])
        aoi["complete_periods"] = [(y, m) for y in range(2009, 2015) for m in range(1, 13)]
        complete = harmonize_records(rows, aoi)["sensor_calibration_audit"]["transition_audits"][0]
        self.assertEqual(complete["raw_step_pct"], 100)
        self.assertEqual(complete["harmonized_step_pct"], 0)

    def test_reordered_valid_and_mixed_csvs_have_identical_snapshots_and_packages(self):
        header = "latitude,longitude,acq_date,satellite,confidence\n"
        valid = ["0,0,2025-01-01,T,90\n", "0.01,0.01,2025-02-01,N20,h\n"]
        invalid = [f"{100+i},0,2025-01-01,T,90\n" for i in range(25)]
        for rows in (valid, valid + invalid):
            snapshots = []
            for ordered in (rows, list(reversed(rows))):
                accepted, aoi = parse_uploaded_csv(header + "".join(ordered))
                snapshots.append(run_investigation({}, raw_records_override=accepted, source_aoi=aoi))
            first, second = snapshots
            with self.subTest(mixed=len(rows) > 2):
                self.assertEqual(first["run_id"], second["run_id"])
                self.assertEqual(first, second)
                self.assertEqual(package_zip(first), package_zip(second))
                store = RunStore()
                store.put(first)
                store.put(second)
                self.assertEqual(len(store), 1)

    def test_collinear_overlap_is_rejected_but_shared_boundaries_are_allowed(self):
        first = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
        for offset in (1, -1):
            second = [[x+offset, y] for x, y in first]
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "Overlapping"):
                parse_custom_aoi({"geojson": {"type": "MultiPolygon", "coordinates": [[first], [second]]}})
        adjacent = [[x+2, y] for x, y in first]
        aoi = parse_custom_aoi({"geojson": {"type": "MultiPolygon", "coordinates": [[first], [adjacent]]}})
        self.assertEqual(len(aoi["geometry"]["coordinates"]), 2)

    def test_january_rule_context_survives_a_narrow_display_window(self):
        def event(year, month, value):
            return {"year": year, "month": month, "dekad": (month-1)*3+1,
                    "acq_date": f"{year}-{month:02d}-10", "hhe": value, "raw_detections": 1,
                    "raw_modis": 1, "raw_viirs": 0, "hfre_mw": 30, "daynight": "D", "include_in_calendar": True}
        aoi = parse_custom_aoi({"lat": 0, "lon": 0})
        rows = [event(y, m, 10 if m in (1, 12) else 1000 if m == 3 else 0)
                for y in range(2001, 2026) for m in range(1, 13)]
        rows[-1]["hhe"] = 13
        rows.append(event(2026, 1, 11.26))
        harmonized = {"hotspots": rows, "observation_coverage": {
            "complete_months": [(y, m) for y in range(2001, 2027) for m in range(1, 13)],
            "recorded_months": [(r["year"], r["month"]) for r in rows]}}
        audit = {"calibrated_kappa": .58, "flare_contamination_share": 0,
                 "total_raw_detections": len(rows), "static_flare_detections": 0, "calibration_valid": True}
        decisions = []
        for start in (2001, 2026):
            calendar = build_burning_calendar(harmonized, aoi, year_start=start, focus_year=2026, focus_month=1)
            self.assertEqual(len(calendar["cells"]), (2026-start+1)*12)
            decisions.append(decide({"aoi": aoi, "calendar": calendar, "sensor_calibration_audit": audit, "options": {}}))
        self.assertEqual(decisions[0]["verdict"], "ELEVATED_WATCH")
        self.assertEqual(decisions[1]["verdict"], decisions[0]["verdict"])
        self.assertEqual(decisions[1]["findings"], decisions[0]["findings"])

    def test_outside_window_context_is_bound_and_verified_in_receipt(self):
        snapshot = run_investigation({"aoi_id": "AOI-NSW", "year_start": 2026,
                                      "focus_year": 2026, "focus_month": 1})
        self.assertEqual(len(snapshot["calendar"]["cells"]), 12)
        context = snapshot["calendar"]["previous_month_context"]
        self.assertEqual((context["year"], context["month"]), (2025, 12))
        receipt = build_receipt(snapshot)
        self.assertEqual(check_receipt(receipt)["status"], "VALID")
        forged = copy.deepcopy(receipt)
        forged["calendar"]["previous_month_context"]["month"] = 11
        forged["calendar_summary"]["previous_month_context"]["month"] = 11
        forged["receipt_sha256"] = sha256_of({k: v for k, v in forged.items() if k != "receipt_sha256"})
        self.assertEqual(check_receipt(forged)["status"], "TAMPERED")


class TestRepeatCSVHTTP(unittest.TestCase):
    def test_reordered_uploads_can_reuse_the_same_snapshot_without_conflict(self):
        from fastapi.testclient import TestClient
        from app.api import app
        header = "latitude,longitude,acq_date,satellite,confidence\n"
        rows = ["0,0,2025-01-01,T,90\n", "0.01,0.01,2025-02-01,N20,h\n", "99,0,2025-01-01,T,90\n"]
        with TestClient(app) as client:
            runs = []
            for ordered in (rows, list(reversed(rows))):
                response = client.post("/api/upload-csv", files={"file": ("same.csv", header+"".join(ordered), "text/csv")})
                self.assertEqual(response.status_code, 200, response.text[:200])
                runs.append(response.json())
            self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    unittest.main()
