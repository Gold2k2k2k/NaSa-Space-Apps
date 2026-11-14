"""Benchmark Multi-Decadal MODIS & VIIRS Datasets, Custom AOI Parsers, and FIRMS CSV Ingestion.

Provides six real-world benchmark fire regimes (2000-2026) plus deterministic,
biome-aware raw FIRMS MODIS C6.1 and VIIRS S-NPP / NOAA-20 / NOAA-21 record
generation for any user-drawn polygon or lat/lon AOI on Earth, and direct CSV
parsing for downloaded NASA FIRMS archives.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import random
from datetime import date, timedelta
from typing import Any, Optional

from app.schema_mapping import clean_float, clean_str


def _square_ring(lat: float, lon: float, half_km: float) -> list[list[float]]:
    dlat = half_km / 111.32
    cos_lat = max(0.15, math.cos(math.radians(lat)))
    dlon = half_km / (111.32 * cos_lat)
    return [
        [round(lon - dlon, 5), round(lat - dlat, 5)],
        [round(lon + dlon, 5), round(lat - dlat, 5)],
        [round(lon + dlon, 5), round(lat + dlat, 5)],
        [round(lon - dlon, 5), round(lat + dlat, 5)],
        [round(lon - dlon, 5), round(lat - dlat, 5)],
    ]


def bbox_from_ring(ring: list[list[float]]) -> dict[str, float]:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return {
        "lon_min": round(min(lons), 5),
        "lon_max": round(max(lons), 5),
        "lat_min": round(min(lats), 5),
        "lat_max": round(max(lats), 5),
    }


def centroid_of_ring(ring: list[list[float]]) -> tuple[float, float]:
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not pts:
        return 0.0, 0.0
    return round(sum(p[1] for p in pts) / len(pts), 5), round(sum(p[0] for p in pts) / len(pts), 5)


def polygon_area_km2(ring: list[list[float]]) -> float:
    if len(ring) < 3:
        return 0.0
    lat0, _ = centroid_of_ring(ring)
    kx = 111.32 * max(0.1, math.cos(math.radians(lat0)))
    ky = 111.32
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * kx, ring[i][1] * ky
        x2, y2 = ring[i + 1][0] * kx, ring[i + 1][1] * ky
        area += x1 * y2 - x2 * y1
    return round(abs(area) * 0.5, 2)


def point_in_polygon(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


AOIS: dict[str, dict[str, Any]] = {
    "AOI-AMZ": {
        "aoi_id": "AOI-AMZ",
        "name": "Amazon Arc — Mato Grosso",
        "country": "Brazil",
        "biome": "Tropical Moist Forest / Cerrado Frontier",
        "lat": -11.50,
        "lon": -55.20,
        "radius_km": 110.0,
        "area_km2": 48400.0,
        "default_focus_year": 2026,
        "default_focus_month": 9,
        "peak_season": "Aug–Oct",
        "expected_verdict": "CRITICAL_ANOMALY",
        "description": (
            "Southern Amazon deforestation and drought frontier. Severe late-dry-season fires "
            "in 2024 and September 2026 exceed the 2001–2020 historical 95th percentile."
        ),
        "monthly_weights": [0.06, 0.05, 0.07, 0.10, 0.18, 0.35, 0.65, 1.35, 1.85, 1.10, 0.28, 0.10],
        "base_scale": 14.0,
        "viirs_small_fire_mult": 4.2,
        "night_prob": 0.44,
        "ag_share_bias": 0.22,
        "flare_count": 0,
        "trend_per_year": 0.012,
        "year_shocks": {
            2005: {8: 1.55, 9: 1.65},
            2007: {8: 1.70, 9: 1.85, 10: 1.50},
            2010: {8: 1.80, 9: 1.95},
            2020: {8: 1.45, 9: 1.60},
            2024: {8: 2.15, 9: 2.55, 10: 1.95},
            2026: {8: 1.75, 9: 2.45},
        },
    },
    "AOI-MEK": {
        "aoi_id": "AOI-MEK",
        "name": "Mekong Agricultural Belt",
        "country": "Thailand / Laos",
        "biome": "Seasonal Monsoon Cropland & Mixed Deciduous",
        "lat": 19.20,
        "lon": 100.45,
        "radius_km": 105.0,
        "area_km2": 44100.0,
        "default_focus_year": 2026,
        "default_focus_month": 3,
        "peak_season": "Feb–Apr",
        "expected_verdict": "ELEVATED_WATCH",
        "description": (
            "Intensive smallholder crop-residue burning (maize, rice stubble). Unharmonized raw counts "
            "jump +380% after VIIRS launch in 2012 because 375 m pixels detect small agricultural burns "
            "that 1 km MODIS missed; harmonization bridges the discontinuity and isolates true elevated activity."
        ),
        "monthly_weights": [0.35, 0.95, 1.85, 1.40, 0.30, 0.08, 0.05, 0.05, 0.07, 0.12, 0.22, 0.30],
        "base_scale": 12.0,
        "viirs_small_fire_mult": 6.4,
        "night_prob": 0.14,
        "ag_share_bias": 0.78,
        "flare_count": 0,
        "trend_per_year": 0.006,
        "year_shocks": {
            2016: {3: 1.35, 4: 1.30},
            2020: {3: 1.30},
            2023: {3: 1.45, 4: 1.25},
            2026: {3: 1.36, 4: 1.22},
        },
    },
    "AOI-CAL": {
        "aoi_id": "AOI-CAL",
        "name": "Sierra Nevada & Plumas",
        "country": "United States",
        "biome": "Temperate Conifer Forest",
        "lat": 39.95,
        "lon": -121.15,
        "radius_km": 97.5,
        "area_km2": 38025.0,
        "default_focus_year": 2026,
        "default_focus_month": 8,
        "peak_season": "Jul–Oct",
        "expected_verdict": "CRITICAL_ANOMALY",
        "description": (
            "High-intensity western North America conifer wildfire regime featuring extreme nighttime "
            "radiative power (FRP) persistence during August 2026 and historic megafire years (2020, 2021)."
        ),
        "monthly_weights": [0.04, 0.04, 0.06, 0.10, 0.22, 0.45, 0.95, 1.45, 1.25, 0.55, 0.14, 0.05],
        "base_scale": 8.0,
        "viirs_small_fire_mult": 3.8,
        "night_prob": 0.56,
        "ag_share_bias": 0.08,
        "flare_count": 0,
        "trend_per_year": 0.015,
        "year_shocks": {
            2018: {7: 1.85, 8: 2.10, 11: 2.60},
            2020: {8: 2.65, 9: 2.85},
            2021: {7: 2.40, 8: 2.95, 9: 2.30},
            2026: {8: 2.60, 9: 1.90},
        },
    },
    "AOI-NSW": {
        "aoi_id": "AOI-NSW",
        "name": "Blue Mountains, NSW",
        "country": "Australia",
        "biome": "Temperate Eucalypt Woodland",
        "lat": -33.40,
        "lon": 150.30,
        "radius_km": 95.5,
        "area_km2": 36481.0,
        "default_focus_year": 2026,
        "default_focus_month": 1,
        "peak_season": "Nov–Feb",
        "expected_verdict": "NOMINAL_REGIME",
        "description": (
            "Southern Hemisphere summer fire calendar. Captures the catastrophic 2019–2020 Black Summer "
            "megafires in the historical record while January 2026 remains within normal climatological bounds."
        ),
        "monthly_weights": [1.30, 0.95, 0.35, 0.18, 0.12, 0.08, 0.07, 0.12, 0.28, 0.65, 1.15, 1.45],
        "base_scale": 8.5,
        "viirs_small_fire_mult": 3.6,
        "night_prob": 0.48,
        "ag_share_bias": 0.12,
        "flare_count": 0,
        "trend_per_year": 0.002,
        "year_shocks": {
            2001: {12: 2.20},
            2002: {1: 2.00},
            2006: {11: 1.70, 12: 1.80},
            2019: {11: 2.90, 12: 3.40},
            2020: {1: 3.20, 2: 1.80},
            2026: {1: 0.96, 2: 0.92},
        },
    },
    "AOI-MIO": {
        "aoi_id": "AOI-MIO",
        "name": "Miombo Savanna, Moxico",
        "country": "Angola",
        "biome": "Tropical Savanna & Miombo Woodland",
        "lat": -10.80,
        "lon": 19.50,
        "radius_km": 107.0,
        "area_km2": 45796.0,
        "default_focus_year": 2026,
        "default_focus_month": 7,
        "peak_season": "May–Aug",
        "expected_verdict": "NOMINAL_REGIME",
        "description": (
            "Fire-adapted African Miombo ecosystem with stable periodic dry-season burning from May to August. "
            "Demonstrates an ecological fire regime tracking near its 20-year historical median."
        ),
        "monthly_weights": [0.05, 0.06, 0.12, 0.35, 1.10, 1.75, 1.95, 1.65, 0.75, 0.22, 0.08, 0.05],
        "base_scale": 15.0,
        "viirs_small_fire_mult": 3.9,
        "night_prob": 0.22,
        "ag_share_bias": 0.30,
        "flare_count": 0,
        "trend_per_year": -0.001,
        "year_shocks": {
            2026: {7: 0.98, 8: 1.02},
        },
    },
    "AOI-FLR": {
        "aoi_id": "AOI-FLR",
        "name": "Basra Industrial Flare Zone",
        "country": "Iraq",
        "biome": "Arid Basin / Hydrocarbon Extraction (Trap Case)",
        "lat": 30.45,
        "lon": 47.70,
        "radius_km": 68.0,
        "area_km2": 18496.0,
        "default_focus_year": 2026,
        "default_focus_month": 8,
        "peak_season": "Year-round static emitters",
        "expected_verdict": "UNVERIFIABLE",
        "description": (
            "Scientific trap case: >75% of raw thermal detections originate from stationary oil/gas flares "
            "(FIRMS type=2, persistent 12 months/yr at identical 1 km cells). FireTrace's Evaluator flags "
            "static flare dominance as UNVERIFIABLE for wildfire trend inference unless explicitly separated."
        ),
        "monthly_weights": [0.10, 0.10, 0.12, 0.14, 0.20, 0.30, 0.35, 0.38, 0.30, 0.18, 0.12, 0.10],
        "base_scale": 3.0,
        "viirs_small_fire_mult": 4.0,
        "night_prob": 0.50,
        "ag_share_bias": 0.25,
        "flare_count": 9,
        "trend_per_year": 0.001,
        "year_shocks": {},
    },
}

for _aoi in AOIS.values():
    ring = _square_ring(_aoi["lat"], _aoi["lon"], _aoi["radius_km"])
    _aoi["polygon"] = ring
    _aoi["bbox"] = bbox_from_ring(ring)


def list_aois() -> list[dict[str, Any]]:
    return [
        {
            "aoi_id": a["aoi_id"],
            "name": a["name"],
            "country": a["country"],
            "biome": a["biome"],
            "lat": a["lat"],
            "lon": a["lon"],
            "radius_km": a["radius_km"],
            "area_km2": a["area_km2"],
            "default_focus_year": a["default_focus_year"],
            "default_focus_month": a["default_focus_month"],
            "peak_season": a["peak_season"],
            "expected_verdict": a["expected_verdict"],
            "description": a["description"],
            "polygon": a["polygon"],
            "bbox": a["bbox"],
        }
        for a in AOIS.values()
    ]


def _default_weights_for_lat(lat: float) -> list[float]:
    if lat >= 23.5:
        return [0.06, 0.08, 0.18, 0.35, 0.55, 0.85, 1.35, 1.65, 1.15, 0.45, 0.15, 0.07]
    if lat <= -23.5:
        return [1.35, 1.10, 0.45, 0.20, 0.12, 0.08, 0.07, 0.15, 0.35, 0.75, 1.25, 1.50]
    if lat >= 0.0:
        return [0.65, 1.25, 1.75, 1.20, 0.35, 0.10, 0.06, 0.06, 0.08, 0.14, 0.28, 0.48]
    return [0.08, 0.07, 0.12, 0.25, 0.65, 1.15, 1.55, 1.75, 1.30, 0.55, 0.18, 0.09]


def parse_custom_aoi(spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve preset AOI, custom lat/lon/radius, or GeoJSON Polygon/Feature into an AOI dict."""
    aoi_id = clean_str(spec.get("aoi_id"))
    if aoi_id and aoi_id in AOIS and not spec.get("geojson") and spec.get("custom_lat") is None:
        return dict(AOIS[aoi_id])

    geojson = spec.get("geojson")
    ring: Optional[list[list[float]]] = None
    name = clean_str(spec.get("name"))

    if geojson:
        if not isinstance(geojson, dict):
            raise ValueError("GeoJSON payload must be a JSON object")
        gtype = geojson.get("type")
        geom = geojson
        if gtype == "FeatureCollection":
            feats = geojson.get("features") or []
            if not feats:
                raise ValueError("GeoJSON FeatureCollection contains no features")
            geom = feats[0].get("geometry") or {}
            props = feats[0].get("properties") or {}
            name = name or clean_str(props.get("name"))
        elif gtype == "Feature":
            geom = geojson.get("geometry") or {}
            props = geojson.get("properties") or {}
            name = name or clean_str(props.get("name"))
        if geom.get("type") == "Polygon":
            coords = geom.get("coordinates") or []
            if not coords or len(coords[0]) < 4:
                raise ValueError("GeoJSON Polygon exterior ring must have at least 4 positions")
            ring = [[float(p[0]), float(p[1])] for p in coords[0]]
            if ring[0] != ring[-1]:
                ring.append(list(ring[0]))
        elif geom.get("type") == "Point":
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                raise ValueError("GeoJSON Point requires [lon, lat]")
            lon, lat = float(coords[0]), float(coords[1])
            radius_km = max(5.0, min(250.0, float(clean_float(spec.get("radius_km"), 50.0) or 50.0)))
            ring = _square_ring(lat, lon, radius_km)
        else:
            raise ValueError(f"Unsupported GeoJSON geometry type: {geom.get('type')!r}")

    if ring is not None:
        for lon_v, lat_v in ring:
            if not (-90.0 <= lat_v <= 90.0 and -180.0 <= lon_v <= 180.0):
                raise ValueError(f"GeoJSON coordinate out of Earth bounds: [{lon_v}, {lat_v}]")
        lat, lon = centroid_of_ring(ring)
        area_km2 = max(1.0, polygon_area_km2(ring))
        radius_km = round(math.sqrt(area_km2) * 0.5, 1)
    else:
        lat = clean_float(spec.get("lat", spec.get("custom_lat")))
        lon = clean_float(spec.get("lon", spec.get("custom_lon")))
        if lat is None or lon is None or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError("Valid latitude (-90..90) and longitude (-180..180) are required")
        radius_km = max(5.0, min(250.0, float(clean_float(spec.get("radius_km"), 60.0) or 60.0)))
        ring = _square_ring(lat, lon, radius_km)
        area_km2 = round((radius_km * 2.0) ** 2, 1)

    custom_id = f"CUSTOM-{abs(hash((round(lat, 3), round(lon, 3), round(area_km2, 1)))) % 10000:04d}"
    return {
        "aoi_id": custom_id,
        "name": name or f"Custom AOI ({lat:.2f}, {lon:.2f})",
        "country": "User Selected Region",
        "biome": "Regional Thermal Regime",
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "radius_km": radius_km,
        "area_km2": area_km2,
        "default_focus_year": int(clean_float(spec.get("focus_year"), 2026) or 2026),
        "default_focus_month": int(clean_float(spec.get("focus_month"), 8 if lat >= 0 else 1) or 8),
        "peak_season": "Latitude-derived climatology",
        "expected_verdict": "NOMINAL_REGIME",
        "description": f"User-defined area of interest centered at ({lat:.3f}, {lon:.3f}) covering {area_km2:,.1f} km².",
        "monthly_weights": _default_weights_for_lat(lat),
        "base_scale": max(4.0, min(16.0, area_km2 / 3500.0 + 3.5)),
        "viirs_small_fire_mult": 4.2,
        "night_prob": 0.32,
        "ag_share_bias": 0.35,
        "flare_count": 0,
        "trend_per_year": 0.004,
        "year_shocks": {},
        "polygon": ring,
        "bbox": bbox_from_ring(ring),
        "is_custom": True,
    }


def _seed_for(aoi: dict[str, Any]) -> int:
    digest = hashlib.sha256(f"{aoi['aoi_id']}:{aoi['lat']}:{aoi['lon']}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def generate_firms_records(
    aoi: dict[str, Any],
    year_start: int = 2000,
    year_end: int = 2026,
) -> list[dict[str, Any]]:
    """Generate deterministic, realistic raw FIRMS MODIS & VIIRS rows for the AOI."""
    rng = random.Random(_seed_for(aoi))
    ring = aoi["polygon"]
    bbox = aoi["bbox"]
    weights = aoi["monthly_weights"]
    base_scale = aoi["base_scale"]
    small_mult = aoi["viirs_small_fire_mult"]
    night_prob = aoi["night_prob"]
    ag_bias = aoi["ag_share_bias"]
    flare_count = int(aoi.get("flare_count", 0))
    trend = float(aoi.get("trend_per_year", 0.0))
    shocks = aoi.get("year_shocks", {})

    # Pre-generate stationary flare coordinates inside polygon if applicable
    flare_sites: list[tuple[float, float]] = []
    for _ in range(flare_count):
        for _attempt in range(50):
            fl_lat = rng.uniform(bbox["lat_min"] + 0.05, bbox["lat_max"] - 0.05)
            fl_lon = rng.uniform(bbox["lon_min"] + 0.05, bbox["lon_max"] - 0.05)
            if point_in_polygon(fl_lon, fl_lat, ring):
                flare_sites.append((round(fl_lat, 4), round(fl_lon, 4)))
                break

    # Pre-generate realistic spatial ignition hotspots inside polygon so cell clustering occurs naturally
    burn_clusters: list[tuple[float, float]] = []
    for _ in range(45):
        for _attempt in range(40):
            clat = rng.uniform(bbox["lat_min"], bbox["lat_max"])
            clon = rng.uniform(bbox["lon_min"], bbox["lon_max"])
            if point_in_polygon(clon, clat, ring):
                burn_clusters.append((round(clat, 4), round(clon, 4)))
                break
    if not burn_clusters:
        burn_clusters.append((aoi["lat"], aoi["lon"]))

    records: list[dict[str, Any]] = []
    span_lat = max(0.05, bbox["lat_max"] - bbox["lat_min"])
    span_lon = max(0.05, bbox["lon_max"] - bbox["lon_min"])

    for yr in range(max(2000, year_start), min(2026, year_end) + 1):
        # Natural interannual climate oscillation (ENSO-like deterministic cycle)
        enso = 1.0 + 0.14 * math.sin((yr - 2000) * 1.15 + (aoi["lon"] * 0.02))
        trend_mult = max(0.6, 1.0 + trend * (yr - 2000))
        yr_shocks = shocks.get(yr, {})
        max_month = 11 if yr == 2026 else 12

        for mo in range(1, max_month + 1):
            shock = yr_shocks.get(mo, 1.0)
            w = weights[mo - 1]
            # Expected true physical 1 km fire activity units before sensor split
            true_events = max(1, int(round(base_scale * w * enso * trend_mult * shock * rng.uniform(0.86, 1.14))))
            days_in_month = 28 if mo == 2 else (30 if mo in {4, 6, 9, 11} else 31)

            for ev_idx in range(true_events):
                day = ((ev_idx * 7 + rng.randint(0, 4)) % days_in_month) + 1
                acq_date = date(yr, mo, day).isoformat()
                cx, cy = burn_clusters[(ev_idx + mo * 3 + yr) % len(burn_clusters)]
                # Jitter within 0.015 deg (~1.6 km)
                ev_lat = max(bbox["lat_min"], min(bbox["lat_max"], cx + rng.uniform(-span_lat * 0.04, span_lat * 0.04)))
                ev_lon = max(bbox["lon_min"], min(bbox["lon_max"], cy + rng.uniform(-span_lon * 0.04, span_lon * 0.04)))
                if not point_in_polygon(ev_lon, ev_lat, ring):
                    ev_lat, ev_lon = cx, cy

                is_night = rng.random() < (night_prob * (1.25 if shock > 1.5 else 1.0))
                daynight = "N" if is_night else "D"
                is_ag = (not is_night) and (rng.random() < ag_bias) and (shock < 1.8)
                base_frp = rng.uniform(6.0, 21.0) if is_ag else rng.uniform(22.0, 95.0) * (1.35 if shock > 1.5 else 1.0)

                # Emit MODIS Terra (available 2000+) or MODIS Aqua (available mid-2002+)
                modis_emitted = False
                if yr == 2000 and mo < 11:
                    # Terra MODIS active from Nov 2000
                    pass
                else:
                    sat = "Terra" if (yr < 2002 or (yr == 2002 and mo < 7) or ev_idx % 2 == 0) else "Aqua"
                    # Small agricultural fires often fall below MODIS 1 km detection floor
                    if not is_ag or rng.random() > 0.35:
                        modis_emitted = True
                        scan_m = round(rng.uniform(1.0, 2.2), 2)
                        track_m = round(rng.uniform(1.0, 1.5), 2)
                        conf_m = rng.randint(55, 98) if base_frp > 22 else rng.randint(32, 78)
                        records.append({
                            "latitude": round(ev_lat, 5),
                            "longitude": round(ev_lon, 5),
                            "brightness": round(312.0 + min(80.0, base_frp * 0.55), 1),
                            "scan": scan_m,
                            "track": track_m,
                            "acq_date": acq_date,
                            "acq_time": "0215" if is_night else ("1030" if sat == "Terra" else "1335"),
                            "satellite": sat,
                            "instrument": "MODIS",
                            "confidence": conf_m,
                            "version": "6.1NRT",
                            "bright_t31": round(291.0 + rng.uniform(-3.0, 6.0), 1),
                            "frp": round(base_frp, 1),
                            "daynight": daynight,
                            "type": 0,
                        })

                # Emit VIIRS detections from 2012+ (S-NPP 2012+, NOAA-20 2018+, NOAA-21 2023+)
                if yr >= 2012:
                    # 375 m VIIRS detects more sub-pixel clusters (especially small agricultural fires)
                    n_sub = max(1, int(round((small_mult * 0.55) if is_ag else (small_mult * 0.42))))
                    sats_available = ["N"]
                    if yr >= 2018:
                        sats_available.append("N20")
                    if yr >= 2023:
                        sats_available.append("N21")
                    # Pick 1 or 2 afternoon train satellites to simulate real constellation co-detection
                    active_sats = sats_available[:1] if (ev_idx % 3 != 0 or len(sats_available) == 1) else sats_available[:2]
                    for v_sat in active_sats:
                        for sub in range(n_sub):
                            sub_lat = round(ev_lat + (sub - 0.5) * 0.0022, 5)
                            sub_lon = round(ev_lon + ((sub % 2) - 0.5) * 0.0022, 5)
                            conf_v = "h" if base_frp > 35 else ("n" if base_frp > 12 else "l")
                            records.append({
                                "latitude": sub_lat,
                                "longitude": sub_lon,
                                "bright_ti4": round(325.0 + min(42.0, base_frp * 0.42), 1),
                                "scan": round(rng.uniform(0.38, 0.62), 2),
                                "track": round(rng.uniform(0.37, 0.54), 2),
                                "acq_date": acq_date,
                                "acq_time": "0145" if is_night else ("1330" if v_sat == "N" else "1355"),
                                "satellite": v_sat,
                                "instrument": "VIIRS",
                                "confidence": conf_v,
                                "version": "2.0NRT",
                                "bright_ti5": round(290.5 + rng.uniform(-2.5, 5.0), 1),
                                "frp": round(max(1.8, base_frp / max(1.2, n_sub * 0.85)), 1),
                                "daynight": daynight,
                                "type": 0,
                            })
                elif not modis_emitted:
                    # Ensure pre-2012 MODIS record exists if event wasn't skipped
                    records.append({
                        "latitude": round(ev_lat, 5),
                        "longitude": round(ev_lon, 5),
                        "brightness": round(309.5 + min(40.0, base_frp * 0.5), 1),
                        "scan": 1.1,
                        "track": 1.0,
                        "acq_date": acq_date,
                        "acq_time": "0220" if is_night else "1330",
                        "satellite": "Terra" if yr < 2002 else "Aqua",
                        "instrument": "MODIS",
                        "confidence": rng.randint(40, 75),
                        "version": "6.1NRT",
                        "bright_t31": 292.0,
                        "frp": round(base_frp, 1),
                        "daynight": daynight,
                        "type": 0,
                    })

            # Emit persistent static industrial gas flares (if any in AOI, e.g. AOI-FLR)
            for fl_idx, (fl_lat, fl_lon) in enumerate(flare_sites):
                for pass_day in (5, 14, 23):
                    acq_date = date(yr, mo, min(pass_day, days_in_month)).isoformat()
                    records.append({
                        "latitude": fl_lat,
                        "longitude": fl_lon,
                        "brightness": 336.0,
                        "scan": 1.0,
                        "track": 1.0,
                        "acq_date": acq_date,
                        "acq_time": "0130",
                        "satellite": "Aqua" if yr >= 2003 else "Terra",
                        "instrument": "MODIS",
                        "confidence": 92,
                        "version": "6.1NRT",
                        "bright_t31": 294.0,
                        "frp": 38.0 + (fl_idx % 4) * 5.0,
                        "daynight": "N",
                        "type": 2,
                    })
                    if yr >= 2012:
                        for v_sat in (["N", "N20"] if yr >= 2018 else ["N"]):
                            records.append({
                                "latitude": round(fl_lat + 0.001, 5),
                                "longitude": round(fl_lon - 0.001, 5),
                                "bright_ti4": 352.0,
                                "scan": 0.40,
                                "track": 0.39,
                                "acq_date": acq_date,
                                "acq_time": "0140",
                                "satellite": v_sat,
                                "instrument": "VIIRS",
                                "confidence": "h",
                                "version": "2.0NRT",
                                "bright_ti5": 293.0,
                                "frp": 24.0,
                                "daynight": "N",
                                "type": 2,
                            })

    return records


def parse_uploaded_csv(csv_text: str, name: Optional[str] = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse an uploaded NASA FIRMS CSV (MODIS or VIIRS or combined) and derive its AOI bounds."""
    if not csv_text or not csv_text.strip():
        raise ValueError("Uploaded CSV content is empty")
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        raise ValueError("CSV header row is missing")
    rows: list[dict[str, Any]] = []
    lats: list[float] = []
    lons: list[float] = []
    years: list[int] = []
    months: list[int] = []
    for idx, row in enumerate(reader):
        if idx >= 25000:
            break
        lat = clean_float(row.get("latitude") or row.get("lat"))
        lon = clean_float(row.get("longitude") or row.get("lon"))
        acq = clean_str(row.get("acq_date"))
        if lat is None or lon is None or not acq:
            continue
        rows.append(dict(row))
        lats.append(lat)
        lons.append(lon)
        try:
            d = date.fromisoformat(acq[:10])
            years.append(d.year)
            months.append(d.month)
        except ValueError:
            continue

    if not rows:
        raise ValueError("No valid FIRMS hotspot rows found in uploaded CSV")

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    pad_lat = max(0.15, (lat_max - lat_min) * 0.1)
    pad_lon = max(0.15, (lon_max - lon_min) * 0.1)
    ring = [
        [round(lon_min - pad_lon, 5), round(lat_min - pad_lat, 5)],
        [round(lon_max + pad_lon, 5), round(lat_min - pad_lat, 5)],
        [round(lon_max + pad_lon, 5), round(lat_max + pad_lat, 5)],
        [round(lon_min - pad_lon, 5), round(lat_max + pad_lat, 5)],
        [round(lon_min - pad_lon, 5), round(lat_min - pad_lat, 5)],
    ]
    c_lat, c_lon = centroid_of_ring(ring)
    area_km2 = max(10.0, polygon_area_km2(ring))
    aoi = {
        "aoi_id": f"CSV-{abs(hash((len(rows), round(c_lat, 2), round(c_lon, 2)))) % 10000:04d}",
        "name": name or f"Uploaded FIRMS Archive ({len(rows)} rows)",
        "country": "Uploaded CSV",
        "biome": "User FIRMS Upload",
        "lat": c_lat,
        "lon": c_lon,
        "radius_km": round(math.sqrt(area_km2) * 0.5, 1),
        "area_km2": area_km2,
        "default_focus_year": max(years) if years else 2026,
        "default_focus_month": months[-1] if months else 8,
        "peak_season": "Derived from uploaded CSV",
        "expected_verdict": "NOMINAL_REGIME",
        "description": f"User-uploaded FIRMS dataset containing {len(rows)} raw hotspot detections.",
        "polygon": ring,
        "bbox": bbox_from_ring(ring),
        "is_uploaded_csv": True,
    }
    return rows, aoi

