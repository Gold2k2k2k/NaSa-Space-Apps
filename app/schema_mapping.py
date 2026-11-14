"""Semantic Schema Mapping Manifesto & Defensive Row Normalization for MODIS + VIIRS FIRMS Data.

Maps three heterogeneous NASA Earthdata FIRMS source schemas:
  1. firms_modis_c61        (Terra & Aqua MODIS Collection 6.1, 1000 m nadir)
  2. firms_viirs_snpp       (Suomi NPP VIIRS 375 m, 2012 to known S-NPP cessation)
  3. firms_viirs_noaa20_21  (NOAA-20 / NOAA-21 VIIRS 375 m, from declared FIRMS product availability)

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

from app.schema_manifest import MAPPING_MANIFESTO, SOURCE_SCHEMAS, TARGET_SCHEMAS

NULL_MARKERS = {"", "null", "none", "n/a", "na", "nan", "-"}
CONFIDENCE_WEIGHTS = {"unknown": 0.0, "low": 0.45, "nominal": 0.80, "high": 1.00}
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

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
        try:
            parsed = float(val)
        except OverflowError:
            return default
        return parsed if math.isfinite(parsed) else default
    text = clean_str(val)
    if text is None:
        return default
    try:
        parsed = float(text)
        return parsed if math.isfinite(parsed) else default
    except (ValueError, OverflowError):
        return default


def normalize_satellite(raw_sat: Any, instrument: str) -> tuple[str, bool]:
    """Return (canonical_satellite_name, is_afternoon_train)."""
    text = (clean_str(raw_sat) or "").upper()
    aliases = {
        "Terra": {"T", "TERRA", "MODIS_TERRA", "AM"},
        "Aqua": {"A", "AQUA", "MODIS_AQUA"},
        "S-NPP": {"N", "NPP", "SNPP", "S-NPP", "SUOMI NPP", "SUOMI_NPP"},
        "NOAA-20": {"1", "J1", "N20", "NOAA20", "NOAA-20", "JPSS-1", "JPSS1"},
        "NOAA-21": {"2", "J2", "N21", "NOAA21", "NOAA-21", "JPSS-2", "JPSS2"},
    }
    if not text:
        return "UNKNOWN", False
    name = next((name for name, names in aliases.items() if text in names), None)
    if name is None:
        raise ValueError(f"Unknown satellite identifier: {raw_sat!r}")
    family = "MODIS" if name in {"Terra", "Aqua"} else "VIIRS"
    if instrument and instrument != family:
        raise ValueError(f"Satellite {name} does not carry the stated {instrument} instrument")
    return name, name != "Terra"


def normalize_confidence(instrument: str, raw_conf: Any) -> tuple[str, float]:
    """Resolve numeric MODIS (0..100) and categorical VIIRS (l/n/h) confidence."""
    if clean_str(raw_conf) is None:
        return "unknown", CONFIDENCE_WEIGHTS["unknown"]
    text = str(raw_conf).strip().lower()
    if text in {"l", "low"}:
        return "low", CONFIDENCE_WEIGHTS["low"]
    if text in {"n", "nom", "nominal"}:
        return "nominal", CONFIDENCE_WEIGHTS["nominal"]
    if text in {"h", "hi", "high"}:
        return "high", CONFIDENCE_WEIGHTS["high"]
    num = clean_float(raw_conf)
    if num is not None:
        if not 0 <= num <= 100:
            raise ValueError("Numeric confidence must be between 0 and 100")
        clamped = num
        if clamped < 30.0:
            cls = "low"
        elif clamped < 80.0:
            cls = "nominal"
        else:
            cls = "high"
        return cls, CONFIDENCE_WEIGHTS[cls]
    raise ValueError(f"Invalid confidence value: {raw_conf!r}")


def _measurement(raw: dict[str, Any], key: str, default: float | None, *, positive: bool = False) -> float | None:
    value = clean_float(raw.get(key))
    if value is None:
        if clean_str(raw.get(key)) is not None:
            raise ValueError(f"{key} must be a finite number")
        return default
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{key} must be {'positive' if positive else 'non-negative'}")
    if value > 1e12:
        raise ValueError(f"{key} exceeds the numeric safety limit")
    return value


def cell_id_for(lat: float, lon: float) -> str:
    """1,000-m cells on the MODIS reference sphere; not the native tile grid."""
    radius_m = 6371007.181
    wrapped_lon = (lon + 180.0) % 360.0 - 180.0
    cosine = math.cos(math.radians(lat))
    x = 0.0 if abs(cosine) < 1e-12 else radius_m * math.radians(wrapped_lon) * cosine
    y = radius_m * math.radians(lat)
    gx, gy = math.floor(x / 1000.0), math.floor(y / 1000.0)
    return f"G1K_{gy}_{gx}"


def dekad_for(d: date) -> int:
    """Return 1..36 dekad index (three ~10-day periods per month)."""
    in_month = min(3, (d.day - 1) // 10 + 1)
    return (d.month - 1) * 3 + in_month


def normalize_hotspot_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw FIRMS MODIS or VIIRS row into the unified intermediate schema."""
    if not isinstance(raw, dict):
        raise ValueError("Hotspot rows must be objects")
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
        hint, _ = normalize_satellite(raw.get("satellite"), "")
        if hint in {"Terra", "Aqua"}:
            inst_raw = "MODIS"
        elif hint != "UNKNOWN" or clean_float(raw.get("bright_ti4")) is not None or clean_float(raw.get("bright_ti5")) is not None:
            inst_raw = "VIIRS"
        elif clean_float(raw.get("brightness")) is not None:
            inst_raw = "MODIS"
        else:
            raise ValueError("Cannot infer MODIS/VIIRS instrument from this row")
    if inst_raw not in {"MODIS", "VIIRS"}:
        raise ValueError(f"Unsupported instrument: {inst_raw!r}")

    sat_name, is_afternoon = normalize_satellite(raw.get("satellite"), inst_raw)

    mir_keys = ("bright_ti4", "brightness") if inst_raw == "VIIRS" else ("brightness", "bright_ti4")
    tir_keys = ("bright_ti5", "bright_t31") if inst_raw == "VIIRS" else ("bright_t31", "bright_ti5")
    mir = next((_measurement(raw, key, None, positive=True) for key in mir_keys if clean_str(raw.get(key)) is not None), None)
    tir = next((_measurement(raw, key, None, positive=True) for key in tir_keys if clean_str(raw.get(key)) is not None), None)

    conf_cls, conf_weight = normalize_confidence(inst_raw, raw.get("confidence"))
    default_scan, default_track = (0.375, 0.375) if inst_raw == "VIIRS" else (1.0, 1.0)
    scan = _measurement(raw, "scan", default_scan, positive=True)
    track = _measurement(raw, "track", default_track, positive=True)
    frp_is_missing = clean_str(raw.get("frp")) is None
    frp = _measurement(raw, "frp", 0.0)

    daynight = (clean_str(raw.get("daynight")) or "U").upper()
    daynight = {"DAY": "D", "NIGHT": "N"}.get(daynight, daynight)
    if daynight not in {"D", "N", "U"}:
        raise ValueError("daynight must be D or N")

    acq_time = clean_str(raw.get("acq_time"))
    if acq_time is not None:
        if not re.fullmatch(r"\d{1,4}", acq_time):
            raise ValueError(f"Invalid acq_time (expected HHMM): {raw.get('acq_time')!r}")
        acq_time = acq_time.zfill(4)
        if int(acq_time[:2]) > 23 or int(acq_time[2:]) > 59:
            raise ValueError(f"Invalid acq_time (expected HHMM): {raw.get('acq_time')!r}")
    fire_type_value = _measurement(raw, "type", 0.0)
    if fire_type_value not in {0.0, 1.0, 2.0, 3.0}:
        raise ValueError("FIRMS type must be an integer from 0 to 3")
    fire_type = int(fire_type_value)

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
        "mir_bt_k": round(mir, 2) if mir is not None else None,
        "tir_bt_k": round(tir, 2) if tir is not None else None,
        "confidence_class": conf_cls,
        "confidence_weight": conf_weight,
        "scan_km": round(scan, 3),
        "track_km": round(track, 3),
        "effective_area_km2": round(scan * track, 4),
        "frp_mw": round(frp, 2),
        "daynight": daynight,
        "firms_type": fire_type,
        "frp_is_missing": frp_is_missing,
        "mir_is_missing": mir is None,
        "tir_is_missing": tir is None,
        "confidence_is_missing": conf_cls == "unknown",
        "daynight_is_missing": daynight == "U",
        "acq_time_is_missing": acq_time is None,
        "firms_type_is_missing": clean_str(raw.get("type")) is None,
        "source_version": clean_str(raw.get("version")),
        "scan_is_missing": clean_str(raw.get("scan")) is None,
        "track_is_missing": clean_str(raw.get("track")) is None,
    }


def get_manifesto() -> dict[str, Any]:
    return {
        "source_schemas": SOURCE_SCHEMAS,
        "target_schemas": TARGET_SCHEMAS,
        "manifesto": MAPPING_MANIFESTO,
    }

