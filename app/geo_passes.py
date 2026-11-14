"""Approximate nominal observation opportunities, without orbital ephemerides."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.geometry import finite_number
from app.satellites import SATELLITES, SATELLITE_REFERENCE_VERSION, SNPP_DATA_END

EARTH_RADIUS_KM = 6371.0088


def viewing_geometry(cross_track_km, altitude_km):
    """Spherical-Earth line-of-sight geometry, distinct ground/sensor angles."""
    distance = finite_number(cross_track_km, "cross_track_km")
    altitude = finite_number(altitude_km, "altitude_km")
    if distance < 0 or altitude <= 0:
        raise ValueError("Distance must be nonnegative and altitude positive")
    angle = distance / EARTH_RADIUS_KM
    satellite_radius = EARTH_RADIUS_KM + altitude
    horizontal = satellite_radius * math.sin(angle)
    vertical = satellite_radius * math.cos(angle) - EARTH_RADIUS_KM
    elevation = math.degrees(math.atan2(vertical, horizontal))
    off_nadir = math.degrees(math.atan2(EARTH_RADIUS_KM * math.sin(angle),
                                       satellite_radius - EARTH_RADIUS_KM * math.cos(angle)))
    return {"max_elevation_deg": round(elevation, 6),
            "viewing_zenith_deg": round(90 - elevation, 6),
            "sensor_off_nadir_deg": round(off_nadir, 6)}


def _cross_track_distance(lat, longitude_offset, max_track_lat):
    ground_lat = max(-max_track_lat, min(max_track_lat, lat))
    a, b, delta = math.radians(lat), math.radians(ground_lat), math.radians(longitude_offset)
    haversine = math.sin((a - b) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(delta / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(max(0, min(1, haversine))))


def _iso(stamp):
    return stamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def predict_passes(lat, lon, *, days=5, start_dt=None):
    lat, lon = finite_number(lat, "latitude"), finite_number(lon, "longitude")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Coordinates must be within Earth bounds")
    if type(days) is not int or not 1 <= days <= 16:
        raise ValueError("days must be an integer from 1 to 16")
    if start_dt is not None and (not isinstance(start_dt, datetime) or start_dt.tzinfo is None or start_dt.utcoffset() is None):
        raise ValueError("start_dt must be a timezone-aware datetime")
    base = (start_dt or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    if not 2000 <= base.year <= 2100:
        raise ValueError("Modeled reference years must be between 2000 and 2100")
    end = base + timedelta(days=days)
    active, excluded = [], []
    for sat in SATELLITES:
        beginning = datetime.fromisoformat(sat["product_start"]).replace(tzinfo=timezone.utc)
        if sat["code"] == "N" and base >= SNPP_DATA_END:
            excluded.append({"satellite": sat["name"], "reason": "Science data delivery ended 2026-11-02 at 15:40 UTC (NOAA final update)."})
        elif end <= beginning:
            excluded.append({"satellite": sat["name"], "reason": "Reference window predates the modeled FIRMS product availability."})
        else:
            active.append(sat)
    passes = []
    # Include adjacent local dates; conversion retains UTC date rollover.
    first_day = base.replace(hour=0, minute=0, second=0) - timedelta(days=2)
    for index in range(days + 5):
        local_day = first_day + timedelta(days=index)
        for sat in active:
            beginning = datetime.fromisoformat(sat["product_start"]).replace(tzinfo=timezone.utc)
            for pass_type, key in (("DAY", "day_lst_hour"), ("NIGHT", "night_lst_hour")):
                minutes = round(sat[key] * 60)
                stamp = local_day + timedelta(minutes=round(minutes - lon * 4))
                if not base <= stamp < end or stamp < beginning or (sat["code"] == "N" and stamp >= SNPP_DATA_END):
                    continue
                # Schematic phase varies by absolute date and day/night track.
                # It is not a propagated satellite position.
                phase = ((local_day.toordinal() + sat["phase_offset"] +
                         (sat["repeat_days"] / 2 if pass_type == "NIGHT" else 0)) % sat["repeat_days"]) / sat["repeat_days"] - .5
                longitude_offset = phase * 360 / (1440 / sat["period_min"])
                cross = _cross_track_distance(lat, longitude_offset, 180 - sat["inclination_deg"])
                if cross > sat["swath_km"] / 2:
                    continue
                geometry = viewing_geometry(cross, sat["altitude_km"])
                if geometry["max_elevation_deg"] < 0:
                    continue
                finish = min(stamp + timedelta(minutes=10), end)
                if sat["code"] == "N":
                    finish = min(finish, SNPP_DATA_END)
                passes.append({"satellite": sat["name"], "norad": sat["norad"],
                    "instrument": sat["instrument"], "resolution_m": sat["resolution_m"],
                    "swath_km": sat["swath_km"], "daynight": pass_type[0], "pass_type": pass_type,
                    "utc_time": _iso(stamp), "end_utc": _iso(finish),
                    "local_solar_time": f"{minutes // 60:02d}:{minutes % 60:02d}",
                    **geometry, "off_nadir_km": round(cross, 6),
                    "afternoon_train": sat["code"] != "Terra",
                    "is_modeled": True, "model_version": SATELLITE_REFERENCE_VERSION})
    passes.sort(key=lambda row: (row["utc_time"], row["satellite"]))
    return {"lat": round(lat, 6), "lon": round(lon, 6), "window_days": days,
            "reference_time": _iso(base), "window_end": _iso(end),
            "model_version": SATELLITE_REFERENCE_VERSION, "is_modeled": True,
            "satellites_tracked": [sat["name"] for sat in active], "excluded_sources": excluded,
            "pass_count": len(passes), "passes": passes,
            "note": "Approximate modeled opportunities from nominal solar times, schematic ground-track phase and spherical viewing geometry. No ephemerides, cloud screening, actual instrument scheduling or operational accuracy are supplied. Day/night labels are nominal branches, not computed local illumination. Historical 50-minute NOAA-21/20 spacing is schematic; known source end dates are applied."}

