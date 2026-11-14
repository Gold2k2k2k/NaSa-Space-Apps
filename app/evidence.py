"""Shared source counts and independently checkable query/evidence contracts."""
from __future__ import annotations

from typing import Any

from app.canonical import canonical_json, sha256_of
from app.schema_mapping import normalize_hotspot_row

QUERY_TITLES = (
    "AOI Geometry & Spatial Bounds",
    "MODIS Collection 6.1 Ingestion (Terra & Aqua)",
    "VIIRS 375 m Ingestion (S-NPP, NOAA-20, NOAA-21)",
    "1 km Spatial Clustering & Cell-Day Deduplication",
    "Radiative Power (FRP) & Diurnal Persistence",
    "Persistent Thermal Source Audit",
    "Baseline Climatology & Focus Month Anomaly",
    "Seasonal Peak & Out-of-Season Check",
    "Multi-Decadal Trend & 2012 Continuity Bridge",
)


def summarize_inputs(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Count sensors from normalized values, never from combined-CSV headers."""
    normalized = []
    invalid = 0
    for raw in raw_records:
        try:
            normalized.append(normalize_hotspot_row(raw))
        except ValueError:
            invalid += 1
    normalized.sort(key=canonical_json)
    return {
        "total_rows": len(raw_records),
        "valid_rows": len(normalized),
        "invalid_rows": invalid,
        "modis_rows": sum(r["instrument"] == "MODIS" for r in normalized),
        "viirs_rows": sum(r["instrument"] == "VIIRS" for r in normalized),
        "normalized_rows_sha256": sha256_of(normalized),
    }


def expected_query_rows(
    aoi: dict[str, Any], calendar: dict[str, Any], audit: dict[str, Any],
    inputs: dict[str, Any], persistent_cells_count: int,
) -> dict[str, dict[str, Any]]:
    """Define every field that a receipt query must corroborate in its evidence."""
    focus = calendar["focus_comparison"]
    records = calendar["summary_records"]
    return {
        "Q0": {"aoi_id": aoi["aoi_id"], "lat": aoi["lat"], "lon": aoi["lon"],
               "area_km2": aoi["area_km2"]},
        "Q1": {"instrument": "MODIS", "raw_detections": inputs["modis_rows"],
               "years": f"{calendar['year_start']}-{calendar['year_end']}"},
        "Q2": {"instrument": "VIIRS", "raw_detections": inputs["viirs_rows"],
               "overlap_years": audit["overlap_years"]},
        # Clustering precedes flare exclusion. The included calendar-event count
        # is a different statistic from all raw cell-pass clusters.
        "Q3": {"harmonized_cell_events": audit["total_raw_detections"] - audit["overpass_duplicates_removed"],
               "overpass_duplicates_removed": audit["overpass_duplicates_removed"],
               "calibrated_kappa": audit["calibrated_kappa"]},
        "Q4": {"focus_frp_mw": focus["frp_total_mw"],
               "focus_night_share": focus["night_share"],
               "wildfire_share": audit["wildfire_share"],
               "agricultural_share": audit["agricultural_share"]},
        "Q5": {"static_flare_detections": audit["static_flare_detections"],
               "flare_contamination_share": audit["flare_contamination_share"],
               "persistent_cells_count": persistent_cells_count},
        "Q6": {"focus_year": focus["year"], "focus_month": focus["month"],
               "focus_value": focus["value"], "hist_median": focus["hist_median"],
               "hist_p95": focus["hist_p95"], "z_robust": focus["z_robust"],
               "anomaly_pct": focus["anomaly_pct"]},
        "Q7": {"peak_months": records["peak_months"],
               "is_peak_season": focus["is_peak_season"],
               "rank_in_history": focus["rank_in_history"],
               **({"previous_month_context": calendar["previous_month_context"]} if "previous_month_context" in calendar else {})},
        "Q8": {"trend_slope_per_decade": records["trend_slope_per_decade"],
               "raw_step_jump_2012_pct": audit["raw_step_jump_2012_pct"],
               "harmonized_step_diff_2012_pct": audit["harmonized_step_diff_2012_pct"],
               "bias_reduction_pct": audit["bias_reduction_pct"],
               "bridge_r2": audit["bridge_r2"]},
    }
