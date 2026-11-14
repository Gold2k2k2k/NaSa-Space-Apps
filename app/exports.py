"""Complete, source-labeled CSV/GeoJSON and reference-bound RFC 5545 exports."""
from __future__ import annotations

import copy
import csv
import io
from datetime import datetime, timezone

from app.geo_passes import predict_passes


def _metadata(run):
    return {"run_id": run["run_id"], "aoi_name": run["aoi"]["name"],
            "source_kind": run.get("provenance", {}).get("source_kind", "unspecified"),
            "calculation_version": run.get("calculation_version", "legacy"),
            "reference_time": run.get("reference_time", ""),
            "scenario_kind": (run.get("counterfactual") or {}).get("kind", "")}


def _csv_safe(value):
    if isinstance(value, (list, tuple)):
        value = "|".join(map(str, value))
    if isinstance(value, str):
        value = "".join(char for char in value if (ord(char) >= 32 and ord(char) != 127) or char in "\t\r\n")
        if value.lstrip().startswith(("=", "+", "-", "@")):
            value = "'" + value
    return value


def _csv_text(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_safe(value) for key, value in row.items()})
    return buffer.getvalue()


def _hotspots(run, limit):
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("An explicit preview limit must be a nonnegative integer")
    if "_hotspots_all" not in run and limit is None:
        raise ValueError("Complete exports require retained hotspot evidence, not the map preview")
    all_rows = run.get("_hotspots_all", run.get("map_hotspots", []))
    selected = all_rows if limit is None else all_rows[:limit]
    return selected, {"export_scope": "complete" if limit is None else "preview",
                      "total_hotspots": len(all_rows), "returned_hotspots": len(selected)}


def export_hotspots_csv(run_data, limit=None):
    spots, scope = _hotspots(run_data, limit)
    metadata = {**_metadata(run_data), **scope}
    fields = list(metadata) + [
        "hotspot_id", "cell_id", "acq_date", "year", "month", "dekad", "lat", "lon",
        "daynight", "temporal_precision", "window_start_utc", "window_end_utc", "observation_dates",
        "sensor_family", "satellites", "mir_bt_k", "tir_bt_k", "confidence_class", "confidence_weight",
        "effective_area_km2", "raw_detections", "unique_observations", "duplicate_observation_rows",
        "raw_modis", "raw_viirs", "overpass_dedup_factor", "modis_satellite_factor", "viirs_satellite_factor",
        "hhe", "hfre_mw", "frp_is_missing", "fire_category", "source_type", "classification_basis",
        "is_persistent_inferred", "include_in_calendar"]
    return _csv_text(fields, ({**metadata, **spot} for spot in spots))


def export_calendar_csv(run_data):
    metadata = {**_metadata(run_data), "mode": run_data["calendar"]["mode"],
                "metric_unit": "raw detections" if run_data["calendar"]["mode"] == "raw" else "HHE index"}
    fields = list(metadata) + [
        "aoi_id", "year", "month", "month_name", "is_observed", "is_complete", "coverage_status",
        "value", "observed_value", "value_is_counterfactual", "hhe_total", "raw_total", "raw_modis",
        "raw_viirs", "frp_total_mw", "frp_measured_events", "frp_missing_events", "night_share",
        "hist_median_hhe", "hist_mean_hhe", "hist_iqr_hhe", "hist_p90_hhe", "hist_p95_hhe",
        "anomaly_abs", "anomaly_pct", "z_robust", "empirical_percentile", "severity_band"]
    return _csv_text(fields, ({**metadata, **cell} for cell in run_data["calendar"]["cells"]))


def export_hotspots_geojson(run_data, limit=None):
    spots, scope = _hotspots(run_data, limit)
    aoi = run_data["aoi"]
    features = [{"type": "Feature", "properties": {
        "feature_role": "AOI_BOUNDARY", "aoi_id": aoi["aoi_id"], "name": aoi["name"],
        "area_km2": aoi["area_km2"], "verdict": run_data["verdict"],
        "verdict_sha256": run_data["verdict_sha256"], **_metadata(run_data)},
        "geometry": copy.deepcopy(aoi["geometry"])}]
    for spot in spots:
        properties = {key: copy.deepcopy(value) for key, value in spot.items() if key not in ("lat", "lon")}
        features.append({"type": "Feature", "properties": {
            "feature_role": "HARMONIZED_HOTSPOT", **properties},
            "geometry": {"type": "Point", "coordinates": [spot["lon"], spot["lat"]]}})
    return {"type": "FeatureCollection", "firetrace": {**_metadata(run_data), **scope,
            "note": "Observed/harmonized points include excluded source types; include_in_calendar states their use. Map previews are separate."},
            "features": features}


def _ics_escape(text):
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(char for char in value if (ord(char) >= 32 and ord(char) != 127) or char == "\n")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_ics_line(line):
    parts, current, octets = [], "", 0
    for character in line:
        size = len(character.encode("utf-8"))
        if octets + size > 75:
            parts.append(current)
            current, octets = " ", 1
        current += character
        octets += size
    parts.append(current)
    return "\r\n".join(parts)


def export_calendar_ics(run_data):
    aoi, calendar = run_data["aoi"], run_data["calendar"]
    reference = datetime.fromisoformat(run_data["reference_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
    pass_data = run_data.get("passes") or predict_passes(aoi["lat"], aoi["lon"], days=5, start_dt=reference)
    if pass_data["reference_time"] != run_data["reference_time"]:
        raise ValueError("Stored pass reference disagrees with the analysis snapshot")
    stamp = reference.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FireTrace//Modeled demo opportunities//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:" + _ics_escape("FireTrace demo: " + aoi["name"])]
    for index, row in enumerate(pass_data["passes"]):
        begin = datetime.fromisoformat(row["utc_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(row["end_utc"].replace("Z", "+00:00"))
        description = (f"Approximate modeled opportunity, not an operational prediction. {pass_data['note']} "
                       f"Source: {_metadata(run_data)['source_kind']}; reference {run_data['reference_time']}.")
        lines.extend(["BEGIN:VEVENT", f"UID:modeled-pass-{row['norad']}-{index}-{run_data['run_id']}@firetrace",
                      f"DTSTAMP:{stamp}", f"DTSTART:{begin.strftime('%Y%m%dT%H%M%SZ')}",
                      f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
                      "SUMMARY:" + _ics_escape(f"MODELED {row['satellite']} {row['pass_type']} opportunity - {aoi['name']}"),
                      "DESCRIPTION:" + _ics_escape(description), "END:VEVENT"])
    for month in calendar["summary_records"]["peak_months"]:
        year = reference.year
        beginning = datetime(year, month, 1, tzinfo=timezone.utc)
        if beginning.date() < reference.date():
            year += 1
            beginning = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
        climate = calendar["climatology"][month - 1]
        description = (f"Historical seasonal window, not a forecast. Reference median {climate['median']}, "
                       f"P95 {climate['p95']}; mode {calendar['mode']}. Source {_metadata(run_data)['source_kind']}.")
        lines.extend(["BEGIN:VEVENT", f"UID:historical-month-{year}-{month:02d}-{run_data['run_id']}@firetrace",
                      f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{beginning.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                      "SUMMARY:" + _ics_escape(f"Historical seasonal window (not a forecast) - {aoi['name']}"),
                      "DESCRIPTION:" + _ics_escape(description), "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_ics_line(line) for line in lines) + "\r\n"

