"""Input-boundary regressions; spatial contracts are exercised through AOIs."""
from __future__ import annotations

import math
import unittest

from app.agents import run_investigation
from app.datasets import parse_custom_aoi, parse_uploaded_csv
from app.schema_mapping import normalize_hotspot_row

HEADER = "latitude,longitude,acq_date,instrument,satellite,confidence,frp\n"
ROW = "10,105,2025-11-10,MODIS,T,90,0\n"


class TestAnalysisValidation(unittest.TestCase):
    def test_invalid_analysis_options_are_controlled_validation_errors(self) -> None:
        cases = [
            {"focus_month": 0}, {"focus_month": 13}, {"focus_month": True},
            {"focus_year": "2026"}, {"focus_year": 1999},
            {"year_start": 2025, "year_end": 2024},
            {"year_start": 2020, "year_end": 2022, "focus_year": 2026},
            {"mode": "invented"}, {"confidence_min": "invented"},
            {"persona": "invented"}, {"flare_guard": "false"},
        ]
        for values in cases:
            with self.subTest(values=values):
                caught = None
                try:
                    run_investigation({"aoi_id": "AOI-MEK", **values})
                except Exception as error:
                    caught = error
                self.assertIsInstance(caught, ValueError)

    def test_unspecified_focus_stays_inside_requested_year_window(self) -> None:
        result = run_investigation({"aoi_id": "AOI-MEK", "year_start": 2020, "year_end": 2022})
        self.assertEqual(result["options"]["focus_year"], 2022)
        self.assertEqual(result["calendar"]["focus_year"], 2022)


class TestCSVValidation(unittest.TestCase):
    def test_csv_byte_limit_rejects_large_otherwise_valid_rows(self) -> None:
        header = HEADER.rstrip("\n") + ",note\n"
        row = ROW.rstrip("\n") + "," + "x" * 600 + "\n"
        with self.assertRaisesRegex(ValueError, "10 MiB"):
            parse_uploaded_csv(header + row * 20000)

    def test_unclosed_quoted_fields_are_rejected_as_malformed_csv(self) -> None:
        header = HEADER.rstrip("\n") + ",note\n"
        for text in [header + ROW.rstrip("\n") + ',"unterminated\n',
                     '"latitude,longitude,acq_date\n10,105,2025-11-10\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_uploaded_csv(text)

    def test_impossible_dates_and_coordinates_cannot_become_valid_rows(self) -> None:
        for row in ["10,105,invalid,MODIS,T,90,10\n",
                    "10,105,2026-02-30,MODIS,T,90,10\n",
                    "99,105,2025-11-10,MODIS,T,90,10\n"]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_uploaded_csv(HEADER + row)

    def test_mixed_validity_upload_reports_rejections_and_uses_valid_bounds(self) -> None:
        rows, aoi = parse_uploaded_csv(HEADER + ROW + "99,105,invalid,MODIS,T,90,10\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual(aoi.get("ingestion", {}).get("rejected_rows"), 1)
        self.assertLessEqual(aoi["bbox"]["lat_max"], 90)

    def test_focus_month_belongs_to_latest_date_in_an_unsorted_archive(self) -> None:
        _, aoi = parse_uploaded_csv(HEADER + ROW + "10,105,2024-12-31,MODIS,T,90,10\n")
        self.assertEqual((aoi["default_focus_year"], aoi["default_focus_month"]), (2025, 11))

    def test_csv_row_limit_is_explicit_and_does_not_silently_truncate(self) -> None:
        with self.assertRaises(ValueError):
            parse_uploaded_csv(HEADER + ROW * 25001)

    def test_duplicate_csv_headers_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_uploaded_csv("latitude,latitude,longitude,acq_date\n10,11,105,2025-11-10\n")

    def test_bom_and_whitespace_headers_are_normalized(self) -> None:
        rows, _ = parse_uploaded_csv("\ufeff latitude , longitude , acq_date , instrument , satellite , confidence , frp\n" + ROW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["latitude"], "10")

    def test_uploaded_identity_depends_on_content_and_not_row_order(self) -> None:
        second = "10.1,105.1,2025-11-11,VIIRS,N20,h,20\n"
        _, first = parse_uploaded_csv(HEADER + ROW + second)
        _, reordered = parse_uploaded_csv(HEADER + second + ROW)
        _, changed = parse_uploaded_csv(HEADER + ROW.replace(",0\n", ",100\n") + second)
        self.assertEqual(first["aoi_id"], reordered["aoi_id"])
        self.assertNotEqual(first["aoi_id"], changed["aoi_id"])


class TestSchemaBoundaries(unittest.TestCase):
    def test_invalid_supplied_sensor_measurements_are_rejected(self) -> None:
        base = {"latitude": 10, "longitude": 105, "acq_date": "2025-11-10",
                "instrument": "MODIS", "satellite": "T", "confidence": 90,
                "frp": 0, "daynight": "D"}
        for values in [{"instrument": "AVHRR"}, {"satellite": "Atlantis"},
                       {"instrument": "VIIRS", "satellite": "T"},
                       {"confidence": -1}, {"confidence": 101}, {"confidence": "oops"},
                       {"scan": 0}, {"track": -1}, {"frp": -1}, {"frp": "oops"},
                       {"type": 2.5}, {"type": 9}, {"daynight": "oops"}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_hotspot_row({**base, **values})

    def test_enormous_hotspot_coordinates_do_not_escape_as_overflow_errors(self) -> None:
        error = None
        try:
            normalize_hotspot_row({"latitude": 10 ** 400, "longitude": 105,
                                   "acq_date": "2025-11-10"})
        except Exception as caught:
            error = caught
        self.assertIsInstance(error, ValueError)

    def test_jpss_aliases_are_not_misattributed_to_suomi(self) -> None:
        for satellite, expected in [("J1", "NOAA-20"), ("J2", "NOAA-21")]:
            with self.subTest(satellite=satellite):
                row = normalize_hotspot_row({"latitude": 10, "longitude": 105,
                    "acq_date": "2025-11-10", "instrument": "VIIRS",
                    "satellite": satellite, "confidence": "h", "frp": 0})
                self.assertEqual(row["satellite"], expected)
                self.assertEqual(row["frp_mw"], 0)

    def test_invalid_acquisition_times_are_rejected(self) -> None:
        for value in ["2460", "1260", "oops", "-1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_hotspot_row({"latitude": 10, "longitude": 105,
                    "acq_date": "2025-11-10", "instrument": "MODIS",
                    "satellite": "T", "confidence": 90, "acq_time": value})


class TestGeometryContracts(unittest.TestCase):
    def test_preset_area_agrees_with_its_actual_rectangle(self) -> None:
        aoi = parse_custom_aoi({"aoi_id": "AOI-AMZ"})
        west, south = aoi["polygon"][0]
        east, north = aoi["polygon"][2]
        expected = 6371.0088 ** 2 * math.radians(east - west) * (
            math.sin(math.radians(north)) - math.sin(math.radians(south)))
        self.assertAlmostEqual(aoi["area_km2"], expected, places=3)

    def test_vertex_limit_rejects_an_otherwise_valid_large_ring(self) -> None:
        ring = [[10 * math.cos(i * math.tau / 2000), 10 * math.sin(i * math.tau / 2000)]
                for i in range(2000)]
        ring.append(list(ring[0]))
        with self.assertRaisesRegex(ValueError, "2000"):
            parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [ring]}})

    def test_crossing_multipolygon_components_are_not_double_counted(self) -> None:
        horizontal = [[0, 1], [3, 1], [3, 2], [0, 2], [0, 1]]
        vertical = [[1, 0], [2, 0], [2, 3], [1, 3], [1, 0]]
        with self.assertRaises(ValueError):
            parse_custom_aoi({"geojson": {"type": "MultiPolygon", "coordinates": [[horizontal], [vertical]]}})

    def test_a_separate_island_inside_a_hole_is_a_valid_component(self) -> None:
        outer = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
        hole = [[1, 1], [1, 3], [3, 3], [3, 1], [1, 1]]
        island = [[1.5, 1.5], [2.5, 1.5], [2.5, 2.5], [1.5, 2.5], [1.5, 1.5]]
        aoi = parse_custom_aoi({"geojson": {"type": "MultiPolygon", "coordinates": [[outer, hole], [island]]}})
        from app.geometry import geometry_contains
        self.assertTrue(geometry_contains(2, 2, aoi["geometry"]))
        self.assertFalse(geometry_contains(1.2, 1.2, aoi["geometry"]))

    def test_thin_holed_polygon_has_a_valid_interior_sampling_point(self) -> None:
        outer = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
        hole = [[0.001, 0.001], [0.001, 3.999], [3.999, 3.999], [3.999, 0.001], [0.001, 0.001]]
        aoi = parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [outer, hole]}})
        from app.geometry import geometry_contains, interior_point
        lat, lon = interior_point(aoi["geometry"])
        self.assertTrue(geometry_contains(lon, lat, aoi["geometry"]))

    def test_nested_features_are_not_treated_as_valid_geometry(self) -> None:
        polygon = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]]]}
        feature = {"type": "Feature", "geometry": {"type": "Feature", "geometry": polygon}}
        with self.assertRaises(ValueError):
            parse_custom_aoi({"geojson": feature})

    def test_enormous_numeric_coordinates_are_controlled_validation_errors(self) -> None:
        error = None
        try:
            parse_custom_aoi({"custom_lat": 10 ** 400, "custom_lon": 0})
        except Exception as caught:
            error = caught
        self.assertIsInstance(error, ValueError)

    def test_holes_are_preserved_and_excluded_from_membership(self) -> None:
        outer = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
        hole = [[1, 1], [1, 3], [3, 3], [3, 1], [1, 1]]
        aoi = parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [outer, hole]}})
        self.assertIsInstance(aoi.get("geometry"), dict)
        self.assertEqual(len(aoi["geometry"]["coordinates"]), 2)
        from app.geometry import geometry_contains
        self.assertTrue(geometry_contains(0.5, 0.5, aoi["geometry"]))
        self.assertFalse(geometry_contains(2, 2, aoi["geometry"]))

    def test_feature_collection_keeps_every_polygon(self) -> None:
        first = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        second = [[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]
        features = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}}
                    for ring in (first, second)]
        aoi = parse_custom_aoi({"geojson": {"type": "FeatureCollection", "features": features}})
        self.assertEqual(aoi.get("geometry", {}).get("type"), "MultiPolygon")
        self.assertEqual(len(aoi["geometry"]["coordinates"]), 2)
        from app.geometry import geometry_contains
        self.assertTrue(geometry_contains(10.5, 10.5, aoi["geometry"]))
        self.assertFalse(geometry_contains(5, 5, aoi["geometry"]))

    def test_invalid_and_degenerate_polygons_are_rejected(self) -> None:
        rings = [
            [[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]],
            [[0, 0], [1, 0], [2, 0], [0, 0]],
            [[0, 0], [0, 0], [0, 0], [0, 0]],
        ]
        for ring in rings:
            with self.subTest(ring=ring), self.assertRaises(ValueError):
                parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [ring]}})

    def test_antimeridian_bounds_follow_the_short_interval(self) -> None:
        ring = [[179, 10], [-179, 10], [-179, 11], [179, 11], [179, 10]]
        aoi = parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [ring]}})
        self.assertAlmostEqual(aoi["bbox"]["lon_max"] - aoi["bbox"]["lon_min"], 2)
        self.assertAlmostEqual(abs(aoi["lon"]), 180)
        from app.geometry import geometry_contains
        self.assertTrue(geometry_contains(-179.5, 10.5, aoi["geometry"]))
        self.assertFalse(geometry_contains(0, 10.5, aoi["geometry"]))

    def test_geometry_identity_binds_shape_and_normalizes_ring_order(self) -> None:
        square = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
        shifted = square[2:-1] + square[:3]
        reverse = list(reversed(square))
        ids = [parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [r]}})["aoi_id"]
               for r in (square, shifted, reverse)]
        self.assertEqual(len(set(ids)), 1)
        extent = 2 ** 0.5
        diamond = [[1, 1 - extent], [1 + extent, 1], [1, 1 + extent],
                   [1 - extent, 1], [1, 1 - extent]]
        other = parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [diamond]}})
        self.assertNotEqual(ids[0], other["aoi_id"])

    def test_point_selections_stay_inside_earth_bounds_at_poles_and_dateline(self) -> None:
        for lat, lon in [(90.0, 180.0), (-90.0, -180.0), (10.0, 179.9)]:
            with self.subTest(lat=lat, lon=lon):
                aoi = parse_custom_aoi({"custom_lat": lat, "custom_lon": lon, "radius_km": 250})
                self.assertIsInstance(aoi.get("geometry"), dict)
                geometry = aoi["geometry"]
                polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
                for polygon in polygons:
                    for ring in polygon:
                        for x, y in ring:
                            self.assertTrue(-180 <= x <= 180 and -90 <= y <= 90)

    def test_invalid_coordinate_shapes_return_validation_errors(self) -> None:
        for coordinates in [[[1], [2, 3], [4, 5], [1]],
                            [[0, 0], [1, 0], [float("nan"), 1], [0, 0]]]:
            with self.subTest(coordinates=coordinates):
                error = None
                try:
                    parse_custom_aoi({"geojson": {"type": "Polygon", "coordinates": [coordinates]}})
                except Exception as caught:
                    error = caught
                self.assertIsInstance(error, ValueError)


if __name__ == "__main__":
    unittest.main()
