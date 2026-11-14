"""Semantic Schema Mapping Manifesto & Defensive Row Normalization for MODIS + VIIRS FIRMS Data.

Maps three heterogeneous NASA Earthdata FIRMS source schemas:
  1. firms_modis_c61        (Terra & Aqua MODIS Collection 6.1, 1000 m nadir)
  2. firms_viirs_snpp       (Suomi NPP VIIRS 375 m, 2012-present)
  3. firms_viirs_noaa20_21  (NOAA-20 / NOAA-21 VIIRS 375 m, 2018-present)

Into four harmonized target schemas:
  1. harmonized_hotspots
  2. burning_calendar_cells
  3. fire_regime_summaries
  4. sensor_calibration_audit
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Optional

NULL_MARKERS = {"", "null", "none", "n/a", "na", "nan", "-"}
CONFIDENCE_WEIGHTS = {"low": 0.45, "nominal": 0.80, "high": 1.00}
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

SOURCE_SCHEMAS: dict[str, dict[str, Any]] = {
    "firms_modis_c61": {
        "description": "MODIS Collection 6.1 Active Fire (Terra & Aqua, 2000-present, 1000 m nadir)",
        "fields": {
            "latitude": "float",
            "longitude": "float",
            "brightness": "float (Kelvin, MODIS Ch 21/22 MIR)",
            "scan": "float (along-scan pixel km)",
            "track": "float (along-track pixel km)",
            "acq_date": "string (YYYY-MM-DD)",
            "acq_time": "string (HHMM UTC)",
            "satellite": "string ('Terra' | 'Aqua' | 'T' | 'A')",
            "instrument": "string ('MODIS')",
            "confidence": "int (0..100)",
            "version": "string (e.g. '6.1NRT' or '61')",
            "bright_t31": "float (Kelvin, MODIS Ch 31 TIR)",
            "frp": "float (MW)",
            "daynight": "string ('D' | 'N')",
            "type": "int (0=presumed vegetation fire, 1=active volcano, 2=other static land source, 3=offshore)",
        },
    },
    "firms_viirs_snpp": {
        "description": "VIIRS Suomi NPP 375 m Active Fire (2012-present)",
        "fields": {
            "latitude": "float",
            "longitude": "float",
            "bright_ti4": "float (Kelvin, VIIRS I4 MIR)",
            "scan": "float (along-scan pixel km)",
            "track": "float (along-track pixel km)",
            "acq_date": "string (YYYY-MM-DD)",
            "acq_time": "string (HHMM UTC)",
            "satellite": "string ('N' | 'Suomi NPP')",
            "instrument": "string ('VIIRS')",
            "confidence": "string ('l' | 'n' | 'h')",
            "version": "string (e.g. '2.0NRT' or '2')",
            "bright_ti5": "float (Kelvin, VIIRS I5 TIR)",
            "frp": "float (MW)",
            "daynight": "string ('D' | 'N')",
            "type": "int (0=vegetation fire, 1=volcano, 2=static land source, 3=offshore)",
        },
    },
    "firms_viirs_noaa20_21": {
        "description": "VIIRS NOAA-20 / JPSS-1 (2018+) & NOAA-21 / JPSS-2 (2023+) 375 m Active Fire",
        "fields": {
            "latitude": "float",
            "longitude": "float",
            "bright_ti4": "float (Kelvin, VIIRS I4 MIR)",
            "scan": "float",
            "track": "float",
            "acq_date": "string (YYYY-MM-DD)",
            "acq_time": "string (HHMM UTC)",
            "satellite": "string ('N20' | 'N21' | 'NOAA-20' | 'NOAA-21' | '1' | '2')",
            "instrument": "string ('VIIRS')",
            "confidence": "string ('l' | 'n' | 'h' | 'low' | 'nominal' | 'high')",
            "version": "string",
            "bright_ti5": "float (Kelvin, VIIRS I5 TIR)",
            "frp": "float (MW)",
            "daynight": "string ('D' | 'N')",
            "type": "int",
        },
    },
}

TARGET_SCHEMAS: dict[str, dict[str, str]] = {
    "harmonized_hotspots": {
        "hotspot_id": "string NOT NULL",
        "cell_id": "string NOT NULL",
        "lat": "float NOT NULL",
        "lon": "float NOT NULL",
        "acq_date": "date (YYYY-MM-DD) NOT NULL",
        "year": "int NOT NULL",
        "month": "int NOT NULL",
        "dekad": "int (1..36) NOT NULL",
        "daynight": "string ('D'|'N') NOT NULL",
        "sensor_family": "string ('MODIS'|'VIIRS'|'HARMONIZED_BOTH') NOT NULL",
        "mir_bt_k": "float NOT NULL",
        "tir_bt_k": "float NOT NULL",
        "confidence_class": "string ('low'|'nominal'|'high') NOT NULL",
        "confidence_weight": "float NOT NULL",
        "effective_area_km2": "float NOT NULL",
        "raw_detections": "int NOT NULL",
        "overpass_dedup_factor": "float NOT NULL",
        "hhe": "float NOT NULL",
        "hfre_mw": "float NOT NULL",
        "fire_category": "string ('WILDFIRE'|'AGRICULTURAL_BURN'|'STATIC_FLARE') NOT NULL",
    },
    "burning_calendar_cells": {
        "aoi_id": "string NOT NULL",
        "year": "int NOT NULL",
        "month": "int NOT NULL",
        "hhe_total": "float NOT NULL",
        "raw_total": "int NOT NULL",
        "raw_modis": "int NOT NULL",
        "raw_viirs": "int NOT NULL",
        "frp_total_mw": "float NOT NULL",
        "night_share": "float NOT NULL",
        "hist_median_hhe": "float NOT NULL",
        "hist_mean_hhe": "float NOT NULL",
        "hist_iqr_hhe": "float NOT NULL",
        "hist_p90_hhe": "float NOT NULL",
        "hist_p95_hhe": "float NOT NULL",
        "anomaly_abs": "float NOT NULL",
        "anomaly_pct": "float NOT NULL",
        "z_robust": "float NOT NULL",
        "severity_band": "string NOT NULL",
    },
    "fire_regime_summaries": {
        "aoi_id": "string NOT NULL",
        "year_start": "int NOT NULL",
        "year_end": "int NOT NULL",
        "focus_year": "int NOT NULL",
        "focus_month": "int NOT NULL",
        "peak_months": "array<int> NOT NULL",
        "peak_year": "int NOT NULL",
        "peak_month_record": "object NOT NULL",
        "focus_hhe": "float NOT NULL",
        "focus_hist_median": "float NOT NULL",
        "focus_anomaly_pct": "float NOT NULL",
        "focus_z_robust": "float NOT NULL",
        "trend_slope_per_decade": "float NOT NULL",
        "wildfire_share": "float NOT NULL",
        "agricultural_share": "float NOT NULL",
        "flare_contamination_share": "float NOT NULL",
        "verdict": "string NOT NULL",
        "verdict_sha256": "string NOT NULL",
    },
    "sensor_calibration_audit": {
        "aoi_id": "string NOT NULL",
        "overlap_years": "string NOT NULL",
        "raw_viirs_to_modis_ratio": "float NOT NULL",
        "calibrated_kappa": "float NOT NULL",
        "overpass_duplicates_removed": "int NOT NULL",
        "raw_step_jump_2012_pct": "float NOT NULL",
        "harmonized_step_diff_2012_pct": "float NOT NULL",
        "bias_reduction_pct": "float NOT NULL",
        "bridge_r2": "float NOT NULL",
    },
}

MAPPING_MANIFESTO: list[dict[str, Any]] = [
    {
        "target_table": "harmonized_hotspots",
        "anchor_source": "Union of firms_modis_c61, firms_viirs_snpp, firms_viirs_noaa20_21 clustered onto 1 km x 1 km grid (cell_id, acq_date, daynight)",
        "join_paths": [
            "UNION ALL normalized MODIS C6.1 + VIIRS S-NPP + VIIRS NOAA-20/21 on common intermediate schema",
            "GROUP BY (cell_id, acq_date, daynight) to cluster 375 m VIIRS sub-pixels onto 1 km MODIS-equivalent cell",
            "LEFT JOIN sensor_calibration_audit ON aoi_id for cross-sensor kappa bridging factor",
        ],
        "fields": [
            {"target": "hotspot_id", "source": "SHA256(cell_id, acq_date, daynight)[:12]", "type": "Derived", "rationale": "Deterministic unique identifier per harmonized 1 km cell-pass event"},
            {"target": "cell_id", "source": "G1K_{floor(lat*100)}_{floor(lon*100*cos(lat))}", "type": "Derived", "rationale": "Equal-area ~1 km grid eliminates 1 km MODIS vs 375 m VIIRS pixel-size mismatch"},
            {"target": "lat, lon", "source": "FRP-weighted AVG(latitude), AVG(longitude)", "type": "Aggregated", "rationale": "Preserves sub-grid thermal centroid within each 1 km cell"},
            {"target": "acq_date, year, month, dekad", "source": "ISO8601(acq_date) -> Y, M, dekad (1..36)", "type": "Direct / Derived", "rationale": "Standardizes temporal keys for monthly and 10-day burning calendars"},
            {"target": "daynight", "source": "UPPER(TRIM(daynight))", "type": "Derived", "rationale": "Separates daytime agricultural burns from nighttime-persistent wildfires"},
            {"target": "sensor_family", "source": "MODIS | VIIRS | HARMONIZED_BOTH", "type": "Derived", "rationale": "Tracks sensor provenance while downstream calendar metrics remain sensor-agnostic"},
            {"target": "mir_bt_k", "source": "COALESCE(bright_ti4, brightness)", "type": "Synonym Resolution", "rationale": "Unifies MODIS Ch 21/22 (brightness) and VIIRS I4 (bright_ti4) mid-infrared Kelvin"},
            {"target": "tir_bt_k", "source": "COALESCE(bright_ti5, bright_t31)", "type": "Synonym Resolution", "rationale": "Unifies MODIS Ch 31 (bright_t31) and VIIRS I5 (bright_ti5) thermal infrared Kelvin"},
            {"target": "confidence_class, confidence_weight", "source": "MODIS 0-100 & VIIRS l/n/h -> {low:0.45, nominal:0.80, high:1.00}", "type": "Derived", "rationale": "Resolves numeric vs categorical confidence mismatch across sensors"},
            {"target": "effective_area_km2", "source": "scan * track", "type": "Derived", "rationale": "Captures off-nadir bow-tie footprint growth vs nadir (1.0 vs 0.1406 km2)"},
            {"target": "raw_detections", "source": "COUNT(*)", "type": "Aggregated", "rationale": "Retains raw unharmonized count to audit 5x-8x VIIRS inflation"},
            {"target": "overpass_dedup_factor", "source": "1.0 / COUNT(DISTINCT afternoon_satellites)", "type": "Derived", "rationale": "Deduplicates Aqua + S-NPP + NOAA-20 + NOAA-21 afternoon constellation passes"},
            {"target": "hhe", "source": "Harmonized Hotspot Equivalent", "type": "Derived", "rationale": "Sensor-agnostic active burning unit calibrated across 2012-2024 overlap bridge"},
            {"target": "hfre_mw", "source": "Calibrated Fire Radiative Power (MW)", "type": "Derived", "rationale": "Cross-sensor harmonized radiative fire energy"},
            {"target": "fire_category", "source": "STATIC_FLARE | AGRICULTURAL_BURN | WILDFIRE", "type": "Derived", "rationale": "Separates vegetation fires from static gas flares (type!=0 or >=8 mo/yr persistence)"},
        ],
    },
    {
        "target_table": "burning_calendar_cells",
        "anchor_source": "harmonized_hotspots aggregated by (aoi_id, year, month)",
        "join_paths": [
            "GROUP BY (aoi_id, year, month) from harmonized_hotspots (excluding static flares when filter enabled)",
            "LEFT JOIN 2001-2020 monthly baseline climatology ON (aoi_id, month)",
        ],
        "fields": [
            {"target": "aoi_id, year, month", "source": "AOI identifier + calendar coordinates (2000-2026, 1-12)", "type": "Direct", "rationale": "Primary composite key for the 27 x 12 burning calendar matrix"},
            {"target": "hhe_total, raw_total, raw_modis, raw_viirs", "source": "SUM(hhe), SUM(raw_detections), sensor splits", "type": "Aggregated", "rationale": "Enables side-by-side comparison of harmonized vs unharmonized records"},
            {"target": "frp_total_mw, night_share", "source": "SUM(hfre_mw), SUM(hhe WHERE daynight='N') / hhe_total", "type": "Aggregated", "rationale": "Quantifies radiative intensity and nocturnal fire persistence"},
            {"target": "hist_median_hhe, hist_mean_hhe, hist_iqr_hhe, hist_p90_hhe, hist_p95_hhe", "source": "2001-2020 baseline statistics per month", "type": "Joined", "rationale": "Non-parametric climatology reference immune to single mega-fire years"},
            {"target": "anomaly_abs, anomaly_pct, z_robust", "source": "(hhe_total - hist_median) / MAX(0.7413*hist_iqr, 0.5)", "type": "Derived", "rationale": "Measures severity relative to multi-year historical median"},
            {"target": "severity_band", "source": "low | normal | elevated | high | extreme", "type": "Derived", "rationale": "Maps robust anomaly into accessible perceptual severity tiers"},
        ],
    },
    {
        "target_table": "fire_regime_summaries",
        "anchor_source": "burning_calendar_cells across selected AOI & date window",
        "join_paths": [
            "AGGREGATE burning_calendar_cells over (year_start..year_end)",
            "JOIN sensor_calibration_audit ON aoi_id",
        ],
        "fields": [
            {"target": "peak_months, peak_year, peak_month_record", "source": "ARGMAX over baseline median & historical cells", "type": "Aggregated", "rationale": "Identifies critical fire months and historical worst years"},
            {"target": "focus_hhe, focus_hist_median, focus_anomaly_pct, focus_z_robust", "source": "Lookup (focus_year, focus_month) cell", "type": "Joined", "rationale": "Directly compares current/selected month against historical median"},
            {"target": "trend_slope_per_decade", "source": "Theil-Sen / OLS slope of annual harmonized HHE (2000-2026)", "type": "Derived", "rationale": "Measures genuine multi-decadal fire regime change without sensor artifact"},
            {"target": "wildfire_share, agricultural_share, flare_contamination_share", "source": "Shares of total thermal detections by fire_category", "type": "Aggregated", "rationale": "Disentangles ecological/wildfire burning, crop residue fires, and industrial flares"},
            {"target": "verdict, verdict_sha256", "source": "app/rules.py deterministic decision + canonical SHA-256", "type": "Derived", "rationale": "Reproducible, auditable regime classification"},
        ],
    },
    {
        "target_table": "sensor_calibration_audit",
        "anchor_source": "Overlap period (2012-2025) detections in firms_modis_c61 + firms_viirs_*",
        "join_paths": [
            "INNER JOIN monthly MODIS & VIIRS series over overlap years (2012..2025)",
        ],
        "fields": [
            {"target": "raw_viirs_to_modis_ratio", "source": "SUM(raw_viirs) / SUM(raw_modis) in overlap", "type": "Aggregated", "rationale": "Quantifies raw sensor count inflation (typically 4x to 9x)"},
            {"target": "calibrated_kappa", "source": "Empirical regional HHE transfer coefficient", "type": "Derived", "rationale": "Bridges VIIRS 375 m clusters to 1 km MODIS-equivalent activity"},
            {"target": "overpass_duplicates_removed", "source": "Raw detections collapsed during afternoon constellation passes", "type": "Aggregated", "rationale": "Proves elimination of Aqua + S-NPP + NOAA-20/21 double counting"},
            {"target": "raw_step_jump_2012_pct, harmonized_step_diff_2012_pct", "source": "Pre/Post-2012 transition discontinuity (%) before vs after", "type": "Derived", "rationale": "Verifies removal of the artificial 2012 VIIRS launch cliff"},
            {"target": "bias_reduction_pct, bridge_r2", "source": "1 - |harm_diff|/|raw_jump| and Pearson R^2 on overlap", "type": "Derived", "rationale": "Quantifies harmonization quality across the overlap bridge"},
        ],
    },
]


def clean_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    text = str(val).strip()
    if text.lower() in NULL_MARKERS:
        return None
    return text


def clean_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val) if math.isfinite(float(val)) else default
    text = clean_str(val)
    if text is None:
        return default
    try:
        parsed = float(text)
        return parsed if math.isfinite(parsed) else default
    except ValueError:
        return default


def normalize_satellite(raw_sat: Any, instrument: str) -> tuple[str, bool]:
    """Return (canonical_satellite_name, is_afternoon_train)."""
    text = (clean_str(raw_sat) or "").upper()
    if text in {"T", "TERRA", "MODIS_TERRA", "AM"}:
        return "Terra", False
    if text in {"A", "AQUA", "MODIS_AQUA"}:
        return "Aqua", True
    if text in {"N", "NPP", "SNPP", "S-NPP", "SUOMI NPP", "SUOMI_NPP"}:
        return "S-NPP", True
    if text in {"1", "N20", "NOAA20", "NOAA-20", "JPSS-1", "JPSS1"}:
        return "NOAA-20", True
    if text in {"2", "N21", "NOAA21", "NOAA-21", "JPSS-2", "JPSS2"}:
        return "NOAA-21", True
    if instrument == "MODIS":
        return "Aqua", True
    return "S-NPP", True


def normalize_confidence(instrument: str, raw_conf: Any) -> tuple[str, float]:
    """Resolve numeric MODIS (0..100) and categorical VIIRS (l/n/h) confidence."""
    if raw_conf is None:
        return "nominal", CONFIDENCE_WEIGHTS["nominal"]
    text = str(raw_conf).strip().lower()
    if text in {"l", "low"}:
        return "low", CONFIDENCE_WEIGHTS["low"]
    if text in {"n", "nom", "nominal"}:
        return "nominal", CONFIDENCE_WEIGHTS["nominal"]
    if text in {"h", "hi", "high"}:
        return "high", CONFIDENCE_WEIGHTS["high"]
    num = clean_float(raw_conf)
    if num is not None:
        clamped = max(0.0, min(100.0, num))
        if clamped < 30.0:
            cls = "low"
        elif clamped < 80.0:
            cls = "nominal"
        else:
            cls = "high"
        weight = round(max(0.25, min(1.0, clamped / 100.0)), 4) if instrument == "MODIS" else CONFIDENCE_WEIGHTS[cls]
        return cls, weight
    return "nominal", CONFIDENCE_WEIGHTS["nominal"]


def cell_id_for(lat: float, lon: float) -> str:
    """Compute an equal-area ~1 km sinusoidal grid identifier."""
    cos_lat = max(0.05, math.cos(math.radians(lat)))
    gx = math.floor(lon * 100.0 * cos_lat)
    gy = math.floor(lat * 100.0)
    return f"G1K_{gy}_{gx}"


def dekad_for(d: date) -> int:
    """Return 1..36 dekad index (three ~10-day periods per month)."""
    in_month = min(3, (d.day - 1) // 10 + 1)
    return (d.month - 1) * 3 + in_month


def normalize_hotspot_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw FIRMS MODIS or VIIRS row into the unified intermediate schema."""
    lat = clean_float(raw.get("latitude", raw.get("lat")))
    lon = clean_float(raw.get("longitude", raw.get("lon")))
    if lat is None or lon is None or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Invalid hotspot coordinates: lat={raw.get('latitude')}, lon={raw.get('longitude')}")

    acq_date_str = clean_str(raw.get("acq_date"))
    if not acq_date_str or not _DATE_RE.match(acq_date_str):
        raise ValueError(f"Invalid acq_date (expected YYYY-MM-DD): {raw.get('acq_date')!r}")
    acq_d = date.fromisoformat(acq_date_str)

    inst_raw = (clean_str(raw.get("instrument")) or "").upper()
    if not inst_raw:
        inst_raw = "VIIRS" if ("bright_ti4" in raw or "bright_ti5" in raw) else "MODIS"
    if inst_raw not in {"MODIS", "VIIRS"}:
        inst_raw = "VIIRS" if "VIIRS" in inst_raw else "MODIS"

    sat_name, is_afternoon = normalize_satellite(raw.get("satellite"), inst_raw)

    mir = clean_float(raw.get("bright_ti4")) if inst_raw == "VIIRS" else clean_float(raw.get("brightness"))
    if mir is None:
        mir = clean_float(raw.get("brightness")) or clean_float(raw.get("bright_ti4")) or 315.0

    tir = clean_float(raw.get("bright_ti5")) if inst_raw == "VIIRS" else clean_float(raw.get("bright_t31"))
    if tir is None:
        tir = clean_float(raw.get("bright_t31")) or clean_float(raw.get("bright_ti5")) or 292.0

    conf_cls, conf_weight = normalize_confidence(inst_raw, raw.get("confidence"))
    default_scan, default_track = (0.375, 0.375) if inst_raw == "VIIRS" else (1.0, 1.0)
    scan = max(0.1, clean_float(raw.get("scan"), default_scan) or default_scan)
    track = max(0.1, clean_float(raw.get("track"), default_track) or default_track)
    frp = max(0.0, clean_float(raw.get("frp"), 12.0) or 0.0)

    daynight = (clean_str(raw.get("daynight")) or "D").upper()
    if daynight not in {"D", "N"}:
        daynight = "N" if daynight.startswith("N") else "D"

    acq_time = (clean_str(raw.get("acq_time")) or "1330").zfill(4)[:4]
    fire_type = int(clean_float(raw.get("type"), 0.0) or 0)

    return {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "cell_id": cell_id_for(lat, lon),
        "acq_date": acq_date_str,
        "acq_time": acq_time,
        "year": acq_d.year,
        "month": acq_d.month,
        "dekad": dekad_for(acq_d),
        "instrument": inst_raw,
        "satellite": sat_name,
        "is_afternoon_train": is_afternoon,
        "mir_bt_k": round(mir, 2),
        "tir_bt_k": round(tir, 2),
        "confidence_class": conf_cls,
        "confidence_weight": conf_weight,
        "scan_km": round(scan, 3),
        "track_km": round(track, 3),
        "effective_area_km2": round(scan * track, 4),
        "frp_mw": round(frp, 2),
        "daynight": daynight,
        "firms_type": fire_type,
    }


def get_manifesto() -> dict[str, Any]:
    return {
        "source_schemas": SOURCE_SCHEMAS,
        "target_schemas": TARGET_SCHEMAS,
        "manifesto": MAPPING_MANIFESTO,
    }

