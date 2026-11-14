"""Deterministic observation windows and per-satellite cell summaries."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.canonical import canonical_json, stable_id
from app.geometry import geometry_contains, wrap_longitude
from app.schema_mapping import normalize_hotspot_row

CONFIDENCE_ORDER = {"unknown": -1, "low": 0, "nominal": 1, "high": 2}


@dataclass
class ObservationWindow:
    cell_id: str
    daynight: str
    source_type: int
    rows: list[dict[str, Any]]
    has_time: bool


def normalize_observations(raw_records, aoi, confidence_min):
    selected = []
    invalid = outside = filtered = 0
    recorded = []
    missing = defaultdict(int)
    geometry = aoi.get("geometry")
    for raw in raw_records:
        try:
            row = normalize_hotspot_row(raw)
        except ValueError:
            invalid += 1
            continue
        if geometry is not None and not geometry_contains(row["lon"], row["lat"], geometry):
            outside += 1
            continue
        recorded.append(row)
        for name in ("frp", "mir", "tir", "confidence", "daynight", "acq_time", "firms_type"):
            missing[name] += bool(row.get(name + "_is_missing"))
        if CONFIDENCE_ORDER[row["confidence_class"]] < CONFIDENCE_ORDER[confidence_min]:
            filtered += 1
            continue
        selected.append(row)
    selected.sort(key=canonical_json)
    coverage = {
        "recorded_months": sorted({(r["year"], r["month"]) for r in recorded}),
        "recorded_dekads": sorted({(r["year"], r["dekad"]) for r in recorded}),
        "complete_months": aoi.get("complete_periods", []),
        "source_kind": aoi.get("source_kind", "provided_records"),
    }
    return selected, {"invalid_rows": invalid, "outside_aoi_rows": outside,
                      "confidence_filtered_rows": filtered,
                      "missing_measurements": dict(missing)}, coverage


def _minutes(row):
    time = row["acq_time"]
    return date.fromisoformat(row["acq_date"]).toordinal() * 1440 + int(time[:2]) * 60 + int(time[2:])


def observation_windows(rows, window_minutes=60):
    if type(window_minutes) is not int or not 1 <= window_minutes <= 180:
        raise ValueError("Observation window must be between 1 and 180 minutes")
    timed, daily = defaultdict(list), defaultdict(list)
    for row in rows:
        key = row["cell_id"], row["daynight"], row["firms_type"]
        if row["acq_time"] is None:
            daily[(*key, row["acq_date"], row["satellite"], row["instrument"])].append(row)
        else:
            timed[key].append(row)
    windows = []
    for (cell, daynight, kind), values in sorted(timed.items()):
        ordered = sorted(values, key=lambda row: (_minutes(row), canonical_json(row)))
        group = []
        anchor = None
        for row in ordered:
            stamp = _minutes(row)
            if group and stamp - anchor > window_minutes:
                windows.append(ObservationWindow(cell, daynight, kind, group, True))
                group = []
            if not group:
                anchor = stamp
            group.append(row)
        if group:
            windows.append(ObservationWindow(cell, daynight, kind, group, True))
    for (cell, daynight, kind, *_), values in sorted(daily.items()):
        windows.append(ObservationWindow(cell, daynight, kind, sorted(values, key=canonical_json), False))
    return sorted(windows, key=lambda window: (window.rows[0]["acq_date"],
                  window.rows[0]["acq_time"] or "", window.cell_id, window.daynight,
                  window.source_type, canonical_json(window.rows)))


def persistent_cells(rows):
    months = defaultdict(lambda: defaultdict(set))
    known_static = set()
    for row in rows:
        months[row["cell_id"]][row["year"]].add(row["month"])
        if row["firms_type"] == 2:
            known_static.add(row["cell_id"])
    inferred = {cell for cell, years in months.items() if len(years) >= 2 and (
        sum(len(mo) >= 8 for mo in years.values()) >= 2 or sum(map(len, years.values())) >= 14)}
    return inferred, known_static


def _priority(row):
    version = (row.get("source_version") or "").upper()
    match = re.fullmatch(r"\d+(?:\.\d+)*(URT|NRT|RT)?", version)
    processing = {None: 4, "NRT": 3, "RT": 2, "URT": 1}.get(match.group(1), 0) if match else 0
    return processing, row["confidence_weight"], not row["frp_is_missing"], canonical_json(row)


def unique_observations(rows):
    grouped = defaultdict(list)
    for row in rows:
        key = tuple(row[key] for key in ("instrument", "satellite", "acq_date", "acq_time", "lat", "lon", "firms_type"))
        grouped[key].append(row)
    return sorted((max(group, key=_priority) for group in grouped.values()), key=canonical_json)


def _sensor_summary(rows, family):
    satellites = defaultdict(list)
    for row in rows:
        if row["instrument"] == family:
            satellites[row["satellite"]].append(row)
    if not satellites:
        return 0.0, None, 0
    confidence, powers = [], []
    for records in satellites.values():
        # One occupied target cell per source, regardless of subpixel count.
        confidence.append(math.fsum(r["confidence_weight"] for r in records) / len(records))
        pixels = defaultdict(list)
        for row in records:
            if not row["frp_is_missing"]:
                pixels[(row["lat"], row["lon"])].append(row["frp_mw"])
        if pixels:
            powers.append(math.fsum(math.fsum(values) / len(values) for values in pixels.values()))
    return (math.fsum(confidence) / len(confidence),
            math.fsum(powers) / len(powers) if powers else None, len(satellites))


def summarize_window(window, inferred_cells, geometry=None):
    raw = window.rows
    rows = unique_observations(raw)
    first = raw[0]
    modis_weight, modis_frp, modis_satellites = _sensor_summary(rows, "MODIS")
    viirs_weight, viirs_frp, viirs_satellites = _sensor_summary(rows, "VIIRS")
    known_powers = [r["frp_mw"] for r in rows if not r["frp_is_missing"]]
    mean_power = math.fsum(known_powers) / len(known_powers) if known_powers else None
    categories = {1: "VOLCANIC_THERMAL", 2: "STATIC_LAND_SOURCE", 3: "OFFSHORE_THERMAL"}
    category = categories.get(window.source_type, "PERSISTENT_CELL_INFERRED" if window.cell_id in inferred_cells else
               "LOW_FRP_DAYTIME" if window.daynight == "D" and mean_power is not None and mean_power < 25 else "VEGETATION_THERMAL")
    weights = [r["frp_mw"] if not r["frp_is_missing"] and r["frp_mw"] > 0 else 0.0 for r in rows]
    if not any(weights):
        weights = [1.0] * len(rows)
    total = math.fsum(weights)
    lat = math.fsum(r["lat"] * w for r, w in zip(rows, weights)) / total
    sine = math.fsum(math.sin(math.radians(r["lon"])) * w for r, w in zip(rows, weights))
    cosine = math.fsum(math.cos(math.radians(r["lon"])) * w for r, w in zip(rows, weights))
    lon = wrap_longitude(math.degrees(math.atan2(sine, cosine)))
    point_method = "frp_weighted_centroid" if known_powers and any(known_powers) else "uniform_centroid"
    if geometry is not None and not geometry_contains(lon, lat, geometry):
        lat, lon = rows[0]["lat"], rows[0]["lon"]
        point_method = "observed_point_when_centroid_is_outside_aoi"
    def mean_known(key):
        values = [r[key] for r in rows if r[key] is not None]
        return round(math.fsum(values) / len(values), 6) if values else None
    def utc(row):
        time = row["acq_time"]
        return f"{row['acq_date']}T{time[:2]}:{time[2:]}:00Z" if time is not None else None
    both = modis_satellites > 0 and viirs_satellites > 0
    single_factor = 1 / (modis_satellites or viirs_satellites)
    identity = {"cell": window.cell_id, "daynight": window.daynight,
                "type": window.source_type, "anchor": utc(first) or first["acq_date"],
                "date_only_source": None if window.has_time else (first["satellite"], first["instrument"])}
    return {
        "hotspot_id": stable_id("H", identity, 16), "cell_id": window.cell_id,
        "lat": round(lat, 5), "lon": round(lon, 5), "point_method": point_method,
        "acq_date": first["acq_date"], "year": first["year"], "month": first["month"], "dekad": first["dekad"],
        "daynight": window.daynight, "temporal_precision": "minute" if window.has_time else "date",
        "window_start_utc": utc(first), "window_end_utc": utc(raw[-1]) if window.has_time else None,
        "observation_dates": sorted({r["acq_date"] for r in raw}),
        "sensor_family": "HARMONIZED_BOTH" if both else "MODIS" if modis_satellites else "VIIRS",
        "satellites": sorted({r["satellite"] for r in rows}),
        "mir_bt_k": mean_known("mir_bt_k"), "tir_bt_k": mean_known("tir_bt_k"),
        "confidence_class": max(rows, key=lambda r: CONFIDENCE_ORDER[r["confidence_class"]])["confidence_class"],
        "confidence_weight": max(r["confidence_weight"] for r in rows),
        "effective_area_km2": mean_known("effective_area_km2"),
        "raw_detections": len(raw), "unique_observations": len(rows),
        "duplicate_observation_rows": len(raw) - len(rows),
        "raw_modis": sum(r["instrument"] == "MODIS" for r in raw),
        "raw_viirs": sum(r["instrument"] == "VIIRS" for r in raw),
        "modis_w": modis_weight, "viirs_w": viirs_weight,
        "modis_frp_mw": modis_frp, "viirs_frp_mw": viirs_frp,
        "modis_satellite_factor": 1 / modis_satellites if modis_satellites else None,
        "viirs_satellite_factor": 1 / viirs_satellites if viirs_satellites else None,
        "overpass_dedup_factor": None if both else single_factor,
        "fire_category": category, "source_type": window.source_type,
        "classification_basis": "supplied_inferred_FIRMS_type" if window.source_type else "descriptive_thermal_pattern_not_fire_cause",
        "is_flare": window.source_type != 0,
        "is_persistent_inferred": window.cell_id in inferred_cells,
        "frp_observation_count": len(known_powers),
    }
