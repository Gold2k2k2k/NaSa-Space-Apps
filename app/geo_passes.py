"""MODIS & VIIRS Sun-Synchronous Satellite Overpass Predictor.

Models passes of Terra (MODIS), Aqua (MODIS), Suomi NPP (VIIRS), NOAA-20 (VIIRS),
and NOAA-21 (VIIRS) over any (lat, lon) coordinate using sun-synchronous orbital
geometry, local solar crossing times, and swath widths (2330 km MODIS vs 3060 km VIIRS).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

SATELLITES: list[dict[str, Any]] = [
    {
        "name": "Terra",
        "norad": 25994,
        "instrument": "MODIS",
        "resolution_m": 1000,
        "swath_km": 2330,
        "altitude_km": 705,
        "period_min": 98.88,
        "day_lst_hour": 10.50,
        "night_lst_hour": 22.50,
        "repeat_days": 16,
        "phase_offset": 0,
    },
    {
        "name": "Aqua",
        "norad": 27424,
        "instrument": "MODIS",
        "resolution_m": 1000,
        "swath_km": 2330,
        "altitude_km": 705,
        "period_min": 98.88,
        "day_lst_hour": 13.50,
        "night_lst_hour": 1.50,
        "repeat_days": 16,
        "phase_offset": 4,
    },
    {
        "name": "Suomi NPP",
        "norad": 37849,
        "instrument": "VIIRS",
        "resolution_m": 375,
        "swath_km": 3060,
        "altitude_km": 824,
        "period_min": 101.4,
        "day_lst_hour": 13.50,
        "night_lst_hour": 1.50,
        "repeat_days": 16,
        "phase_offset": 2,
    },
    {
        "name": "NOAA-20",
        "norad": 43013,
        "instrument": "VIIRS",
        "resolution_m": 375,
        "swath_km": 3060,
        "altitude_km": 824,
        "period_min": 101.4,
        "day_lst_hour": 13.42,
        "night_lst_hour": 1.42,
        "repeat_days": 16,
        "phase_offset": 7,
    },
    {
        "name": "NOAA-21",
        "norad": 54234,
        "instrument": "VIIRS",
        "resolution_m": 375,
        "swath_km": 3060,
        "altitude_km": 824,
        "period_min": 101.4,
        "day_lst_hour": 13.33,
        "night_lst_hour": 1.33,
        "repeat_days": 16,
        "phase_offset": 11,
    },
]


def predict_passes(
    lat: float,
    lon: float,
    *,
    days: int = 5,
    start_dt: Optional[datetime] = None,
) -> dict[str, Any]:
    """Predict MODIS and VIIRS overpasses for (lat, lon) over the next N days."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Coordinates out of bounds: lat={lat}, lon={lon}")

    base = (start_dt or datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)).astimezone(timezone.utc)
    days = max(1, min(16, int(days)))
    lon_offset_hours = lon / 15.0
    lat_factor = 1.0 + 0.35 * (abs(lat) / 90.0)

    passes: list[dict[str, Any]] = []
    for d in range(days):
        day_dt = (base + timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_of_year = day_dt.timetuple().tm_yday

        for sat in SATELLITES:
            # Ground-track phase determines off-nadir angle for that day
            phase = ((day_of_year + sat["phase_offset"] + int(round((lon + 180.0) / 22.5))) % sat["repeat_days"])
            # Effective swath fraction needed for visibility (VIIRS 3060 km covers nearly daily; MODIS 2330 km ~1-2 days)
            half_swath_deg = (sat["swath_km"] / 2.0) / 111.32
            track_spacing_deg = (360.0 / 14.2) * max(0.25, math.cos(math.radians(lat)))
            dist_deg = abs(((phase / sat["repeat_days"]) - 0.5) * track_spacing_deg)
            if dist_deg > half_swath_deg * lat_factor:
                continue

            cross_km = round(dist_deg * 111.32, 1)
            zenith_deg = round(math.degrees(math.atan2(cross_km, sat["altitude_km"])), 1)
            elevation_deg = round(90.0 - zenith_deg, 1)

            for pass_type, lst_hour in (("DAY", sat["day_lst_hour"]), ("NIGHT", sat["night_lst_hour"])):
                # Convert local solar time to UTC
                utc_hour = (lst_hour - lon_offset_hours) % 24.0
                # Slight latitudinal shift (~ +/- 18 min)
                utc_hour = (utc_hour + (lat / 90.0) * 0.25) % 24.0
                aos = day_dt + timedelta(hours=utc_hour)
                if aos < base:
                    continue
                los = aos + timedelta(minutes=10)
                passes.append({
                    "satellite": sat["name"],
                    "norad": sat["norad"],
                    "instrument": sat["instrument"],
                    "resolution_m": sat["resolution_m"],
                    "swath_km": sat["swath_km"],
                    "daynight": "D" if pass_type == "DAY" else "N",
                    "pass_type": pass_type,
                    "utc_time": aos.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_utc": los.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "local_solar_time": f"{int(lst_hour):02d}:{int((lst_hour % 1) * 60):02d}",
                    "max_elevation_deg": elevation_deg,
                    "viewing_zenith_deg": zenith_deg,
                    "off_nadir_km": cross_km,
                    "afternoon_train": sat["name"] in {"Aqua", "Suomi NPP", "NOAA-20", "NOAA-21"},
                })

    passes.sort(key=lambda p: p["utc_time"])
    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "window_days": days,
        "satellites_tracked": [s["name"] for s in SATELLITES],
        "pass_count": len(passes),
        "passes": passes[:40],
        "note": (
            "Sun-synchronous orbital pass predictions for Terra, Aqua (MODIS 1000 m) and "
            "Suomi NPP, NOAA-20, NOAA-21 (VIIRS 375 m). Geometric overpass coverage, cloud cover not modeled."
        ),
    }

