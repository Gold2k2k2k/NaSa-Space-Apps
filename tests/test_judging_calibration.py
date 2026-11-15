"""Known-ratio fixtures detect evaluation leakage in occupancy and FRP fits."""
import copy
from pathlib import Path
import unittest

from app.datasets import parse_custom_aoi
from app.harmonize import harmonize_records


def detection(day, instrument, *, lon=0, frp=10, time="1030", source_type=0, confidence=None):
    return {"latitude": 0, "longitude": lon, "acq_date": day, "acq_time": time,
            "satellite": "T" if instrument == "MODIS" else "N", "instrument": instrument,
            "confidence": confidence or (90 if instrument == "MODIS" else "h"),
            "frp": frp, "daynight": "N", "type": source_type}


def fixture():
    aoi = parse_custom_aoi({"lat": 0, "lon": 0})
    aoi["calibration_policy"] = {"name": "central-highlands-2013-2020-v1", "training_years": [2013, 2020], "evaluation_years": [2021, 2024]}
    rows = []
    for year in (2019, 2022):
        for month in (1, 2, 3):
            day = f"{year}-{month:02d}-10"
            rows += [detection(day, "MODIS", frp=20), detection(day, "VIIRS", frp=10), detection(day, "VIIRS", lon=.02)]
    return rows, aoi


class TestJudgingCalibration(unittest.TestCase):
    def test_fit_is_training_only_and_heldout_assesses_same_factors(self):
        rows, aoi = fixture()
        first = harmonize_records(rows, aoi)["sensor_calibration_audit"]
        self.assertIn("calibration_model", first, "A fixed training policy must be exposed")
        model = first["calibration_model"]
        self.assertEqual(model["kappa"], .5)
        self.assertEqual(model["frp_ratio"], 2)
        changed = copy.deepcopy(rows)
        for row in changed:
            if row["acq_date"].startswith("2022") and row["instrument"] == "VIIRS":
                row["frp"] = 999
        changed.append(detection("2022-01-10", "VIIRS", lon=.04, frp=999))
        second = harmonize_records(changed, aoi)["sensor_calibration_audit"]
        self.assertEqual(second["calibration_model"], model)
        self.assertNotEqual(first["model_evaluation"]["held_out"], second["model_evaluation"]["held_out"])
        held = first["model_evaluation"]["held_out"]
        self.assertEqual(held["occupancy"]["pairs"], 3)
        self.assertEqual(held["occupancy"]["agreement"]["rmse"], 0)
        self.assertEqual(held["power"]["pairs"], 3)
        self.assertEqual(held["power"]["agreement"]["rmse"], 0)
        self.assertIsNone(held["occupancy"]["agreement"]["r2"])

    def test_cross_boundary_window_never_leaks_heldout_power_into_training(self):
        rows, aoi = fixture()
        rows += [detection("2020-12-31", "MODIS", frp=50, time="2350"),
                 detection("2021-01-01", "VIIRS", frp=999, time="0010")]
        first = harmonize_records(rows, aoi)["sensor_calibration_audit"]
        self.assertIn("calibration_model", first)
        changed = copy.deepcopy(rows)
        changed[-1]["frp"] = 123456
        second = harmonize_records(changed, aoi)["sensor_calibration_audit"]
        self.assertEqual(first["calibration_model"], second["calibration_model"])
        self.assertEqual(first["calibration_model"]["frp_ratio"], 2)
        self.assertEqual(first["matched_frp_windows"], 3)

    def test_sparse_fallback_and_filter_profile_are_explicit(self):
        rows, aoi = fixture()
        sparse = harmonize_records(rows[:3], aoi)["sensor_calibration_audit"]
        self.assertIn("calibration_model", sparse)
        self.assertFalse(sparse["calibration_valid"])
        self.assertEqual(sparse["calibration_model"]["kappa"], .58)
        self.assertEqual(sparse["calibration_model"]["frp_ratio"], 1)
        self.assertEqual(sparse["model_evaluation"]["held_out"]["occupancy"]["pairs"], 0)
        before = harmonize_records(rows, aoi)["sensor_calibration_audit"]["calibration_model"]
        after = harmonize_records(rows, aoi, confidence_min="high")["sensor_calibration_audit"]["calibration_model"]
        self.assertNotEqual(before["model_id"], after["model_id"])
        self.assertEqual(after["filter_profile"]["confidence_min"], "high")


if __name__ == "__main__":
    unittest.main()
