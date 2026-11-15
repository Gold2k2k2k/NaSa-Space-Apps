"""Independent reproductions of the three approved judging repairs."""
import copy
import subprocess
import sys
import unittest

from app.agents import run_investigation
from app.calendar_engine import build_burning_calendar
from app.datasets import parse_custom_aoi
from app.run_state import apply_calendar_scenario


def event(year, value):
    return {"year": year, "month": 8, "dekad": 22, "acq_date": f"{year}-08-10",
            "hhe": value, "raw_detections": 1, "raw_modis": 1, "raw_viirs": 0,
            "hfre_mw": 30, "daynight": "D", "include_in_calendar": True}


class TestJudgingRegressions(unittest.TestCase):
    def test_broad_wrapped_box_and_csv_terminate_and_retain_points(self):
        code = '''from app.geometry import box_geometry, geometry_contains
from app.datasets import parse_uploaded_csv
g = box_geometry(166,454,-1,1)
assert all(geometry_contains(x,0,g) for x in [-170,-50,70])
rows,aoi = parse_uploaded_csv("latitude,longitude,acq_date,satellite,confidence\\n" + "".join(f"0,{x},2024-01-01,T,90\\n" for x in [-170,-50,70]))
assert len(rows)==3 and all(geometry_contains(x,0,aoi["geometry"]) for x in [-170,-50,70])
'''
        try:
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=8)
        except subprocess.TimeoutExpired:
            self.fail("Valid wrapped longitude bounds must terminate")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_string_geojson_types_are_controlled_422(self):
        from fastapi.testclient import TestClient
        from app.api import app
        with TestClient(app, raise_server_exceptions=False) as client:
            for kind in ([], {}):
                for geometry in ({"type": kind}, {"type": "Feature", "geometry": {"type": kind}},
                                 {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": kind}}]}):
                    with self.subTest(geometry=geometry):
                        response = client.post("/api/analyze", json={"geojson": geometry})
                        self.assertEqual(response.status_code, 422, response.text[:100])

    def test_scenario_uses_reference_outside_display_with_asymmetric_ties(self):
        data = {"hotspots": [event(y, v) for y, v in zip(range(2001, 2008), [1, 2, 2, 2, 3, 3, 4])] + [event(2024, 10)]}
        aoi = parse_custom_aoi({"lat": 0, "lon": 0})
        values = []
        for start in (2001, 2024):
            calendar = build_burning_calendar(data, aoi, year_start=start, year_end=2024, focus_year=2024, focus_month=8)
            original = copy.deepcopy(calendar["focus_comparison"])
            apply_calendar_scenario(calendar)
            focus = calendar["focus_comparison"]
            values.append(focus["empirical_percentile"])
            self.assertEqual(focus["hhe_total"], original["hhe_total"])
            self.assertEqual(focus["value"], 2)
        for value in values:
            self.assertIsNotNone(value)
            self.assertAlmostEqual(value, 100 * 2.5 / 7, places=6)

    def test_generated_scenario_percentile_does_not_depend_on_display(self):
        values = []
        for start in (2001, 2026):
            run = run_investigation({"aoi_id": "AOI-AMZ", "year_start": start})
            calendar = copy.deepcopy(run["calendar"])
            apply_calendar_scenario(calendar)
            values.append(calendar["focus_comparison"]["empirical_percentile"])
        self.assertIsNotNone(values[1])
        self.assertEqual(values[0], values[1])

    def test_empty_reference_does_not_invent_median_scenario(self):
        calendar = build_burning_calendar({"hotspots": [event(2024, 1)]}, parse_custom_aoi({"lat": 0, "lon": 0}),
                                          year_start=2024, year_end=2024, focus_year=2024, focus_month=8)
        self.assertIsNone(calendar["focus_comparison"]["hist_median"])
        with self.assertRaises(ValueError):
            apply_calendar_scenario(calendar)


if __name__ == "__main__":
    unittest.main()
