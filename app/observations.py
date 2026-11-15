"""Deterministic observation windows and per-satellite cell summaries."""
from __future__ import annotations

import hashlib
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
_ROW_CACHE: dict[int, tuple[dict, dict]] = {}
_ROW_CANON_CACHE: dict[int, str] = {}
_ROW_KEY_CACHE: dict[tuple, tuple[dict, str]] = {}


def _raw_tuple_key(r: dict) -> tuple:
    return (
        r.get("latitude"),
        r.get("longitude"),
        r.get("acq_date"),
        r.get("acq_time"),
        r.get("satellite"),
        r.get("instrument"),
        r.get("confidence"),
        r.get("frp"),
        r.get("bright_ti4"),
        r.get("brightness"),
        r.get("daynight"),
        r.get("type"),
    )


def get_normalized_row_and_canon(raw: dict) -> tuple[dict, str]:
    key = _raw_tuple_key(raw)
    cached_key = _ROW_KEY_CACHE.get(key)
    if cached_key is not None:
        _ROW_CANON_CACHE[id(cached_key[0])] = cached_key[1]
        return cached_key
    row = normalize_hotspot_row(raw)
    canon = canonical_json(row)
    if len(_ROW_KEY_CACHE) > 200000:
        _ROW_KEY_CACHE.clear()
    _ROW_KEY_CACHE[key] = (row, canon)
    _ROW_CANON_CACHE[id(row)] = canon
    return row, canon


def _get_row_canon(row: dict) -> str:
    rid = id(row)
    val = _ROW_CANON_CACHE.get(rid)
    if val is not None:
        return val
    val = canonical_json(row)
    if len(_ROW_CANON_CACHE) > 200000:
        _ROW_CANON_CACHE.clear()
    _ROW_CANON_CACHE[rid] = val
    return val


def _row_sort_key(r: dict) -> tuple:
    return (
        r["acq_date"],
        r["acq_time"] or "",
        r["lat"],
        r["lon"],
        r["instrument"],
        r["satellite"],
        r["cell_id"],
        r["daynight"],
        r["firms_type"],
        r.get("frp_mw", 0.0),
        r.get("confidence_weight", 0.0),
        r.get("row_id") or "",
    )


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
            row, _ = get_normalized_row_and_canon(raw)
        except ValueError:
            invalid += 1
            continue
        if geometry is not None and not geometry_contains(row["lon"], row["lat"], geometry):
            outside += 1
            continue
        recorded.append(row)
        for name in ("frp", "mir", "tir", "confidence", "daynight", "acq_time", "firms_type", "scan", "track"):
            missing[name] += bool(row.get(name + "_is_missing"))
        if CONFIDENCE_ORDER[row["confidence_class"]] < CONFIDENCE_ORDER[confidence_min]:
            filtered += 1
            continue
        selected.append(row)
    selected.sort(key=_get_row_canon)
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
        ordered = sorted(values, key=lambda row: (_minutes(row), _row_sort_key(row)))
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
        windows.append(ObservationWindow(cell, daynight, kind, sorted(values, key=_row_sort_key), False))
    return sorted(windows, key=lambda window: (window.rows[0]["acq_date"],
                  window.rows[0]["acq_time"] or "", window.cell_id, window.daynight,
                  window.source_type, _row_sort_key(window.rows[0])))


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
    return processing, row["confidence_weight"], not row["frp_is_missing"], _row_sort_key(row)


def unique_observations(rows):
    if len(rows) <= 1:
        return rows
    grouped = defaultdict(list)
    for row in rows:
        key = tuple(row[key] for key in ("instrument", "satellite", "acq_date", "acq_time", "lat", "lon", "firms_type"))
        grouped[key].append(row)
    return sorted((max(group, key=_priority) for group in grouped.values()), key=_row_sort_key)


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
    first = raw[0]
    n_raw = len(raw)
    if n_raw == 1:
        rows = raw
        r0 = first
        inst = r0["instrument"]
        if inst == "MODIS":
            modis_weight = r0["confidence_weight"]
            modis_frp = None if r0["frp_is_missing"] else r0["frp_mw"]
            modis_satellites = 1
            viirs_weight = 0.0
            viirs_frp = None
            viirs_satellites = 0
            raw_modis = 1
            raw_viirs = 0
        else:
            modis_weight = 0.0
            modis_frp = None
            modis_satellites = 0
            viirs_weight = r0["confidence_weight"]
            viirs_frp = None if r0["frp_is_missing"] else r0["frp_mw"]
            viirs_satellites = 1
            raw_modis = 0
            raw_viirs = 1
        mean_power = None if r0["frp_is_missing"] else r0["frp_mw"]
        categories = {1: "VOLCANIC_THERMAL", 2: "STATIC_LAND_SOURCE", 3: "OFFSHORE_THERMAL"}
        category = categories.get(window.source_type, "PERSISTENT_CELL_INFERRED" if window.cell_id in inferred_cells else
                   "LOW_FRP_DAYTIME" if window.daynight == "D" and mean_power is not None and mean_power < 25 else "VEGETATION_THERMAL")
        lat, lon = r0["lat"], r0["lon"]
        point_method = "frp_weighted_centroid" if not r0["frp_is_missing"] and r0["frp_mw"] > 0 else "uniform_centroid"
        obs_dates = [r0["acq_date"]]
        satellites = [r0["satellite"]]
        mir_bt_k = r0["mir_bt_k"]
        tir_bt_k = r0["tir_bt_k"]
        eff_area = r0["effective_area_km2"]
        conf_class = r0["confidence_class"]
        conf_weight = r0["confidence_weight"]
        footprint = "contains_nominal_defaults" if (r0["scan_is_missing"] or r0["track_is_missing"]) else "supplied_dimensions"
        frp_count = 0 if r0["frp_is_missing"] else 1
    else:
        rows = unique_observations(raw)
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
        mir_bt_k = mean_known("mir_bt_k")
        tir_bt_k = mean_known("tir_bt_k")
        eff_area = mean_known("effective_area_km2")
        obs_dates = sorted({r["acq_date"] for r in raw})
        satellites = sorted({r["satellite"] for r in rows})
        conf_class = max(rows, key=lambda r: CONFIDENCE_ORDER[r["confidence_class"]])["confidence_class"]
        conf_weight = max(r["confidence_weight"] for r in rows)
        footprint = "contains_nominal_defaults" if any(r["scan_is_missing"] or r["track_is_missing"] for r in rows) else "supplied_dimensions"
        raw_modis = sum(r["instrument"] == "MODIS" for r in raw)
        raw_viirs = sum(r["instrument"] == "VIIRS" for r in raw)
        frp_count = len(known_powers)

    def utc(row):
        time = row["acq_time"]
        return f"{row['acq_date']}T{time[:2]}:{time[2:]}:00Z" if time is not None else None
    both = modis_satellites > 0 and viirs_satellites > 0
    single_factor = 1 / (modis_satellites or viirs_satellites)
    anchor = utc(first) or first["acq_date"]
    if window.has_time:
        raw_id_str = f'{{"anchor":"{anchor}","cell":"{window.cell_id}","date_only_source":null,"daynight":"{window.daynight}","type":{window.source_type}}}'
    else:
        raw_id_str = f'{{"anchor":"{anchor}","cell":"{window.cell_id}","date_only_source":["{first["satellite"]}","{first["instrument"]}"],"daynight":"{window.daynight}","type":{window.source_type}}}'
    hotspot_id = "H-" + hashlib.sha256(raw_id_str.encode("utf-8")).hexdigest()[:16]
    return {
        "hotspot_id": hotspot_id, "cell_id": window.cell_id,
        "lat": round(lat, 5), "lon": round(lon, 5), "point_method": point_method,
        "acq_date": first["acq_date"], "year": first["year"], "month": first["month"], "dekad": first["dekad"],
        "daynight": window.daynight, "temporal_precision": "minute" if window.has_time else "date",
        "window_start_utc": utc(first), "window_end_utc": utc(raw[-1]) if window.has_time else None,
        "observation_dates": obs_dates,
        "sensor_family": "HARMONIZED_BOTH" if both else "MODIS" if modis_satellites else "VIIRS",
        "satellites": satellites,
        "mir_bt_k": mir_bt_k, "tir_bt_k": tir_bt_k,
        "confidence_class": conf_class,
        "confidence_weight": conf_weight,
        "effective_area_km2": eff_area,
        "footprint_basis": footprint,
        "raw_detections": n_raw, "unique_observations": len(rows),
        "duplicate_observation_rows": n_raw - len(rows),
        "raw_modis": raw_modis,
        "raw_viirs": raw_viirs,
        "modis_w": modis_weight, "viirs_w": viirs_weight,
        "modis_frp_mw": modis_frp, "viirs_frp_mw": viirs_frp,
        "modis_satellite_factor": 1 / modis_satellites if modis_satellites else None,
        "viirs_satellite_factor": 1 / viirs_satellites if viirs_satellites else None,
        "overpass_dedup_factor": None if both else single_factor,
        "fire_category": category, "source_type": window.source_type,
        "classification_basis": "supplied_inferred_FIRMS_type" if window.source_type else "descriptive_thermal_pattern_not_fire_cause",
        "is_flare": window.source_type != 0,
        "is_persistent_inferred": window.cell_id in inferred_cells,
        "frp_observation_count": frp_count,
    }
