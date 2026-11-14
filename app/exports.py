"""Downloadable CSV, GeoJSON, and RFC 5545 iCalendar (.ics) Exporters for FireTrace."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from app.geo_passes import predict_passes


def export_hotspots_csv(run_data: dict[str, Any], limit: int = 5000) -> str:
    """Export harmonized active fire hotspots with raw and harmonized provenance columns."""
    buf = io.StringIO()
    fields = [
        "hotspot_id", "cell_id", "acq_date", "year", "month", "dekad",
        "lat", "lon", "daynight", "sensor_family", "satellites",
        "mir_bt_k", "tir_bt_k", "confidence_class", "confidence_weight",
        "effective_area_km2", "raw_detections", "raw_modis", "raw_viirs",
        "overpass_dedup_factor", "hhe", "hfre_mw", "fire_category",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    rows = run_data.get("_hotspots_all") or run_data.get("map_hotspots") or []
    # Prioritize focus year/month first if truncated, or keep chronological
    for row in rows[:limit]:
        out = dict(row)
        if isinstance(out.get("satellites"), list):
            out["satellites"] = "|".join(out["satellites"])
        writer.writerow(out)
    return buf.getvalue()


def export_calendar_csv(run_data: dict[str, Any]) -> str:
    """Export the 2000-2026 monthly burning calendar matrix with historical medians and anomalies."""
    buf = io.StringIO()
    fields = [
        "aoi_id", "year", "month", "month_name", "is_observed",
        "hhe_total", "raw_total", "raw_modis", "raw_viirs", "frp_total_mw", "night_share",
        "hist_median_hhe", "hist_mean_hhe", "hist_iqr_hhe", "hist_p90_hhe", "hist_p95_hhe",
        "anomaly_abs", "anomaly_pct", "z_robust", "severity_band",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for cell in run_data["calendar"]["cells"]:
        writer.writerow(cell)
    return buf.getvalue()


def export_hotspots_geojson(run_data: dict[str, Any], limit: int = 600) -> dict[str, Any]:
    """Export the AOI polygon and harmonized hotspot points as a GeoJSON FeatureCollection."""
    aoi = run_data["aoi"]
    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "properties": {
                "feature_role": "AOI_BOUNDARY",
                "aoi_id": aoi["aoi_id"],
                "name": aoi["name"],
                "area_km2": aoi["area_km2"],
                "verdict": run_data["verdict"],
                "verdict_sha256": run_data["verdict_sha256"],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [aoi["polygon"]],
            },
        }
    ]
    spots = run_data.get("map_hotspots") or run_data.get("_hotspots_all", [])[:limit]
    for h in spots[:limit]:
        features.append({
            "type": "Feature",
            "properties": {
                "feature_role": "HARMONIZED_HOTSPOT",
                "hotspot_id": h["hotspot_id"],
                "cell_id": h["cell_id"],
                "acq_date": h["acq_date"],
                "daynight": h["daynight"],
                "sensor_family": h["sensor_family"],
                "hhe": h["hhe"],
                "hfre_mw": h["hfre_mw"],
                "raw_detections": h["raw_detections"],
                "fire_category": h["fire_category"],
                "confidence_class": h["confidence_class"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [h["lon"], h["lat"]],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def export_calendar_ics(run_data: dict[str, Any]) -> str:
    """Export an RFC 5545 iCalendar (.ics) scheduling MODIS/VIIRS passes and peak fire watch windows."""
    aoi = run_data["aoi"]
    cal = run_data["calendar"]
    peaks = cal["summary_records"]["peak_months"]
    pass_data = predict_passes(aoi["lat"], aoi["lon"], days=5)
    now_stamp = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FireTrace//NASA Space Apps 2026//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_escape('FireTrace Watch: ' + aoi['name'])}",
    ]

    for idx, p in enumerate(pass_data["passes"][:10]):
        dt_start = datetime.strptime(p["utc_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        dt_end = datetime.strptime(p["end_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        desc = (
            f"{p['satellite']} ({p['instrument']} {p['resolution_m']}m) {p['pass_type']} overpass. "
            f"Max elevation {p['max_elevation_deg']} deg, zenith {p['viewing_zenith_deg']} deg, "
            f"verdict {run_data['verdict']}."
        )
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:pass-{p['norad']}-{idx}-{run_data['run_id']}@firetrace",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{_ics_escape(p['satellite'] + ' ' + p['instrument'] + ' pass (' + p['pass_type'] + ') - ' + aoi['aoi_id'])}",
            f"DESCRIPTION:{_ics_escape(desc)}",
            "END:VEVENT",
        ])

    # Schedule upcoming critical peak-season readiness windows for 2027
    for mo in peaks:
        start_d = datetime(2027, mo, 1, tzinfo=timezone.utc)
        end_d = start_d + timedelta(days=27)
        clim = next(c for c in cal["climatology"] if c["month"] == mo)
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:peak-window-2027-{mo:02d}-{run_data['run_id']}@firetrace",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{start_d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end_d.strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_escape('Critical Fire Window (' + clim['month_name'] + ') - ' + aoi['name'])}",
            f"DESCRIPTION:{_ics_escape('Historical median ' + str(clim['median']) + ' HHE, P95 ' + str(clim['p95']) + ' HHE. Verdict: ' + run_data['verdict'])}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

