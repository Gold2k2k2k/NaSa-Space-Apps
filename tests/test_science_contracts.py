"""Small independent fixtures for scientific semantics, not fixture score claims."""
from __future__ import annotations

import copy
import math
import random
import unittest

from app.calendar_engine import build_burning_calendar
from app.canonical import sha256_of
from app.datasets import AOIS, generate_firms_records, parse_custom_aoi
from app.harmonize import harmonize_records
from app.schema_mapping import cell_id_for, normalize_hotspot_row


def detection(day="2020-08-10", *, instrument="MODIS", satellite="T", time="1030", **values):
    return {"latitude": 0.004, "longitude": 0.004, "acq_date": day,
            "acq_time": time, "instrument": instrument, "satellite": satellite,
            "confidence": 90 if instrument == "MODIS" else "h", "frp": 30,
            "daynight": "D", "type": 0, **values}


def event(year, month, *, hhe=1.0, night=False):
    return {"year": year, "month": month, "dekad": (month - 1) * 3 + 1,
            "acq_date": f"{year:04d}-{month:02d}-10", "hhe": hhe,
            "raw_detections": 1, "raw_modis": 1, "raw_viirs": 0,
            "hfre_mw": 30, "daynight": "N" if night else "D",
            "fire_category": "WILDFIRE", "include_in_calendar": True}


class TestMeasurementSemantics(unittest.TestCase):
    def test_grid_is_one_thousand_metres_in_the_sinusoidal_projection(self) -> None:
        self.assertEqual(cell_id_for(0, 0), "G1K_0_0")
        self.assertEqual(cell_id_for(0.009, 0.009), "G1K_1_1")
        self.assertEqual(cell_id_for(0, -0.001), "G1K_0_-1")
        self.assertEqual(cell_id_for(90, -120), cell_id_for(90, 120))
        self.assertEqual(cell_id_for(0, 180), cell_id_for(0, -180))

    def test_missing_power_is_distinct_from_observed_zero(self) -> None:
        missing = normalize_hotspot_row(detection(frp=None))
        zero = normalize_hotspot_row(detection(frp=0))
        self.assertEqual(missing["frp_mw"], 0)
        self.assertTrue(missing.get("frp_is_missing"))
        self.assertEqual(zero["frp_mw"], 0)
        self.assertFalse(zero.get("frp_is_missing", True))

    def test_missing_temperature_is_not_a_fabricated_measurement(self) -> None:
        row = normalize_hotspot_row(detection())
        self.assertIsNone(row["mir_bt_k"])
        self.assertIsNone(row["tir_bt_k"])

    def test_missing_time_daynight_and_confidence_remain_unknown(self) -> None:
        row = normalize_hotspot_row(detection(acq_time=None, daynight=None, confidence=None))
        self.assertIsNone(row["acq_time"])
        self.assertEqual(row["daynight"], "U")
        self.assertEqual(row["confidence_class"], "unknown")
        self.assertEqual(row["confidence_weight"], 0)

    def test_supplied_nonpositive_temperatures_are_not_measurements(self) -> None:
        for value in [0, -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_hotspot_row(detection(brightness=value))

    def test_supplied_measurements_cannot_overflow_aggregates(self) -> None:
        for values in [{"frp": 1e308}, {"scan": 1e308}, {"brightness": 1e308}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_hotspot_row(detection(**values))

    def test_confidence_classes_use_the_same_declared_weight_across_sensors(self) -> None:
        modis = normalize_hotspot_row(detection(confidence=55))
        viirs = normalize_hotspot_row(detection(instrument="VIIRS", satellite="N20", confidence="n"))
        self.assertEqual(modis["confidence_weight"], 0.8)
        self.assertEqual(viirs["confidence_weight"], 0.8)


class TestHarmonizationSemantics(unittest.TestCase):
    def setUp(self) -> None:
        self.aoi = parse_custom_aoi({"lat": 0.004, "lon": 0.004, "radius_km": 5})

    def test_morning_and_afternoon_observations_are_separate_windows(self) -> None:
        rows = [detection(), detection(satellite="A", time="1330"),
                detection(instrument="VIIRS", satellite="N20", time="1340")]
        result = harmonize_records(rows, self.aoi)
        self.assertEqual(len(result["hotspots"]), 2)
        self.assertEqual(result["sensor_calibration_audit"]["overpass_duplicates_removed"], 1)

    def test_more_coincident_satellites_do_not_inflate_a_cell_window(self) -> None:
        single = [detection(instrument="VIIRS", satellite="N20", time="1330")]
        pair = single + [detection(instrument="VIIRS", satellite="N21", time="1340")]
        first = harmonize_records(single, self.aoi)
        second = harmonize_records(pair, self.aoi)
        self.assertEqual(sum(h["hhe"] for h in first["hotspots"]),
                         sum(h["hhe"] for h in second["hotspots"]))

    def test_exact_duplicate_rows_do_not_inflate_hhe_or_radiative_power(self) -> None:
        row = detection(instrument="VIIRS", satellite="N20", time="1330",
                        bright_ti4=340, bright_ti5=290)
        first = harmonize_records([row], self.aoi)
        repeated = harmonize_records([row, copy.deepcopy(row)], self.aoi)
        self.assertEqual(first["hotspots"][0]["hhe"], repeated["hotspots"][0]["hhe"])
        self.assertEqual(first["hotspots"][0]["hfre_mw"], repeated["hotspots"][0]["hfre_mw"])

    def test_subpixels_in_the_same_cell_do_not_create_extra_cell_occupancy(self) -> None:
        rows = [detection(instrument="VIIRS", satellite="N20", time="1330",
                          latitude=lat, bright_ti4=340, bright_ti5=290)
                for lat in (0.001, 0.004, 0.007)]
        first = harmonize_records([rows[1]], self.aoi)
        multiple = harmonize_records(rows, self.aoi)
        self.assertEqual(first["hotspots"][0]["hhe"], multiple["hotspots"][0]["hhe"])

    def test_coincident_window_can_cross_a_utc_date_boundary(self) -> None:
        rows = [detection("2020-01-31", satellite="A", time="2355", daynight="N"),
                detection("2020-02-01", instrument="VIIRS", satellite="N20", time="0010", daynight="N")]
        result = harmonize_records(rows, self.aoi)
        self.assertEqual(len(result["hotspots"]), 1)
        self.assertEqual(result["hotspots"][0].get("observation_dates"), ["2020-01-31", "2020-02-01"])

    def test_row_order_does_not_change_harmonized_evidence(self) -> None:
        rows = generate_firms_records(AOIS["AOI-MEK"])
        expected = harmonize_records(rows, AOIS["AOI-MEK"])
        random.Random(7).shuffle(rows)
        actual = harmonize_records(rows, AOIS["AOI-MEK"])
        self.assertEqual(sha256_of(actual), sha256_of(expected))

    def test_volcanic_and_offshore_sources_are_not_called_industrial_flares(self) -> None:
        for code, category in [(1, "VOLCANIC_THERMAL"), (2, "STATIC_LAND_SOURCE"), (3, "OFFSHORE_THERMAL")]:
            with self.subTest(code=code):
                result = harmonize_records([detection(type=code)], self.aoi)
                self.assertEqual(result["hotspots"][0]["fire_category"], category)
                self.assertFalse(result["hotspots"][0]["include_in_calendar"])

    def test_zero_transition_change_is_not_fabricated_as_95_percent_reduction(self) -> None:
        rows = [detection(f"{year}-{month:02d}-10") for year in range(2009, 2015) for month in range(1, 13)]
        result = harmonize_records(rows, self.aoi)
        self.assertIsNone(result["sensor_calibration_audit"]["bias_reduction_pct"])

    def test_persistence_alone_does_not_establish_an_industrial_source(self):
        rows = [detection(f"{year}-{month:02d}-10") for year in (2019, 2020) for month in range(1, 13)]
        result = harmonize_records(rows, self.aoi)
        self.assertTrue(result["persistent_inferred_cells"])
        self.assertTrue(all(e["include_in_calendar"] for e in result["hotspots"]))
        self.assertTrue(all(e["fire_category"] == "PERSISTENT_CELL_INFERRED" for e in result["hotspots"]))

    def test_era_audits_expose_different_overlap_ratios(self):
        rows = []
        for year, count in [(2014, 2), (2020, 4)]:
            for month in (2, 3, 4):
                day = f"{year}-{month:02d}-10"
                rows.append(detection(day))
                for index in range(count):
                    rows.append(detection(day, instrument="VIIRS", satellite="N20",
                                          latitude=.004 + index * .02))
        larger_aoi = parse_custom_aoi({"lat": .004, "lon": .004, "radius_km": 10})
        audit = harmonize_records(rows, larger_aoi)["sensor_calibration_audit"]
        eras = audit.get("era_diagnostics", [])
        self.assertEqual([e["empirical_kappa"] for e in eras[:2]], [.5, .25])


class TestGeneratedFixtureDates(unittest.TestCase):
    def test_mission_availability_and_utc_conversion_are_explicit(self):
        rows = generate_firms_records(AOIS["AOI-AMZ"])
        starts = {"Terra": "2000-11-01", "Aqua": "2002-07-01", "N": "2012-01-20",
                  "N20": "2018-04-01", "N21": "2024-01-17"}
        self.assertIn("N21", {r["satellite"] for r in rows})
        for row in rows:
            self.assertGreaterEqual(row["acq_date"], starts[row["satellite"]])
            if row["satellite"] == "N":
                self.assertLess(row["acq_date"] + "T" + row["acq_time"], "2026-11-02T1300")
        terra = next(r for r in rows if r["satellite"] == "Terra" and r["daynight"] == "D")
        utc = int(terra["acq_time"][:2]) * 60 + int(terra["acq_time"][2:])
        self.assertLessEqual(abs((utc + terra["longitude"] * 4) % 1440 - 630), 1)
        self.assertTrue(all(r["fixture_version"] == "generated-demo-v2" for r in rows))


class TestCalendarCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.aoi = parse_custom_aoi({"lat": 0, "lon": 0})

    def test_missing_months_are_not_observed_zeroes(self) -> None:
        calendar = build_burning_calendar({"hotspots": [event(2026, 8)]}, self.aoi,
                                          focus_year=2026, focus_month=8)
        january = next(c for c in calendar["cells"] if c["year"] == 2000 and c["month"] == 1)
        self.assertFalse(january["is_observed"])
        self.assertIsNone(january["value"])

    def test_december_records_are_not_discarded_or_relabelled_november(self) -> None:
        calendar = build_burning_calendar({"hotspots": [event(2026, 12)]}, self.aoi,
                                          focus_year=2026, focus_month=12)
        self.assertEqual(calendar["focus_month"], 12)
        self.assertEqual(calendar["focus_comparison"]["value"], 1.0)

    def test_baseline_sufficiency_is_specific_to_the_focus_month(self) -> None:
        rows = [event(year, 1) for year in range(2001, 2021)] + [event(2026, 8)]
        calendar = build_burning_calendar({"hotspots": rows}, self.aoi,
                                          focus_year=2026, focus_month=8)
        self.assertEqual(calendar["baseline_year_count"], 0)
        self.assertIsNone(calendar["focus_comparison"]["hist_median"])

    def test_missing_reference_history_does_not_fall_back_to_the_focus_data(self) -> None:
        rows = [event(year, 8) for year in (2024, 2025, 2026)]
        calendar = build_burning_calendar({"hotspots": rows}, self.aoi,
                                          focus_year=2026, focus_month=8)
        self.assertEqual(calendar["baseline_year_count"], 0)

    def test_night_share_uses_unrounded_totals(self) -> None:
        calendar = build_burning_calendar({"hotspots": [event(2026, 9, hhe=0.0149, night=True)]},
                                          self.aoi, focus_year=2026, focus_month=9)
        self.assertEqual(calendar["focus_comparison"]["night_share"], 1.0)


class TestDefinedStatistics(unittest.TestCase):
    def test_correlation_is_distinct_from_one_to_one_agreement(self) -> None:
        from app.stats import calibration_agreement
        metrics = calibration_agreement([1, 2, 3], [2, 4, 6])
        self.assertAlmostEqual(metrics["r2"], 1.0)
        self.assertAlmostEqual(metrics["efficiency"], -6.0)
        self.assertAlmostEqual(metrics["rmse"], math.sqrt(14 / 3), places=6)

    def test_robust_trend_resists_one_large_outlier(self) -> None:
        from app.stats import ols_slope_per_decade, theil_sen_per_decade
        points = [(2000, 0), (2001, 1), (2002, 2), (2003, 3), (2004, 100)]
        self.assertAlmostEqual(theil_sen_per_decade(points), 10.0)
        self.assertAlmostEqual(ols_slope_per_decade(points), 202.0)

    def test_empirical_percentile_handles_ties(self) -> None:
        from app.stats import empirical_percentile
        self.assertEqual(empirical_percentile([1, 2, 3, 4], 2), 37.5)
        self.assertEqual(empirical_percentile([1, 2, 3, 4], 9), 100.0)
        self.assertEqual(empirical_percentile([2, 2, 2], 2), 50.0)

    def test_season_window_can_wrap_across_the_year_boundary(self) -> None:
        from app.stats import season_phenology
        profile = [0.0] * 36
        for index in (34, 35, 0, 1):
            profile[index] = 10.0
        season = season_phenology(profile)
        self.assertEqual(season["season_onset_dekad"], 35)
        self.assertEqual(season["season_cessation_dekad"], 2)
        self.assertEqual(season["season_duration_dekads"], 4)


class TestRuleBoundaries(unittest.TestCase):
    def evidence(self, month=1):
        focus = {"year": 2026, "month": month, "month_name": "Jan", "value": 12,
                 "hist_median": 10, "hist_p90": 19, "hist_p95": 20,
                 "z_robust": .7, "anomaly_pct": 20, "night_share": 0,
                 "frp_total_mw": None, "is_observed": True, "is_complete": True,
                 "is_pre_peak": True, "is_peak_season": False, "raw_viirs": 0}
        return {"aoi": {"aoi_id": "TEST", "lat": 0, "lon": 0}, "options": {},
                "calendar": {"focus_comparison": focus, "baseline_year_count": 20,
                    "baseline_complete_year_count": 20, "baseline_window": "2001-2020",
                    "mode": "harmonized", "climatology": [{"median": 10}],
                    "summary_records": {"trend_slope_per_decade": 0},
                    "annual_series": [], "cells": []},
                "sensor_calibration_audit": {"calibrated_kappa": .58,
                    "flare_contamination_share": 0, "total_raw_detections": 1,
                    "static_flare_detections": 0, "calibration_valid": True}}

    def test_january_uses_previous_december_not_future_december(self):
        from app.rules import decide
        evidence = self.evidence()
        evidence["calendar"]["cells"] = [
            {"year": 2025, "month": 12, "month_name": "Dec", "z_robust": 1.5, "is_observed": True},
            {"year": 2026, "month": 12, "month_name": "Dec", "z_robust": 0, "is_observed": True}]
        decision = decide(evidence)
        self.assertEqual(decision["verdict"], "ELEVATED_WATCH")
        finding = next(f for f in decision["findings"] if f["code"] == "early_season_onset")
        self.assertIn("cell:2025-12", finding["refs"])

    def test_post_peak_activity_is_not_called_early_season(self):
        from app.rules import decide
        evidence = self.evidence(11)
        evidence["calendar"]["focus_comparison"]["is_pre_peak"] = False
        evidence["calendar"]["cells"] = [{"year": 2026, "month": 10, "month_name": "Oct", "z_robust": 1.5, "is_observed": True}]
        self.assertFalse(any(f["code"] == "early_season_onset" for f in decide(evidence)["findings"]))

    def test_high_z_without_exceeding_p95_is_still_elevated(self):
        from app.rules import decide
        evidence = self.evidence()
        evidence["calendar"]["focus_comparison"]["z_robust"] = 2
        self.assertEqual(decide(evidence)["verdict"], "ELEVATED_WATCH")

    def test_missing_focus_is_unverifiable_not_a_numeric_exception(self):
        from app.rules import decide
        evidence = self.evidence()
        evidence["calendar"]["focus_comparison"].update(value=None, z_robust=None, is_observed=False)
        self.assertEqual(decide(evidence)["verdict"], "UNVERIFIABLE")

    def test_assumed_viirs_bridge_is_unverifiable(self):
        from app.rules import decide
        evidence = self.evidence()
        evidence["sensor_calibration_audit"]["calibration_valid"] = False
        evidence["calendar"]["focus_comparison"]["raw_viirs"] = 1
        self.assertEqual(decide(evidence)["verdict"], "UNVERIFIABLE")


if __name__ == "__main__":
    unittest.main()
