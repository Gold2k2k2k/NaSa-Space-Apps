"""Original, deterministic cell-occupancy harmonization for the demo.

HHE is a weighted index, not a fire count or a calibrated probability. The
empirical bridge compares supplied observations; it cannot validate their truth.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.observations import (normalize_observations, observation_windows,
                              persistent_cells, summarize_window)
from app.stats import calibration_agreement

DEFAULT_KAPPA = 0.58
DEFAULT_FRP_RATIO = 1.0


def _sum_months(events, key):
    values = defaultdict(list)
    for event in events:
        if event["include_in_calendar"]:
            values[(event["year"], event["month"])].append(event[key])
    return {month: math.fsum(numbers) for month, numbers in values.items()}


def _transition_audit(by_year, covered, transition):
    before = list(range(transition - 3, transition))
    after = list(range(transition, transition + 3))
    years = before + after
    result = {"transition_year": transition, "pre_years": before, "post_years": after,
              "raw_step_pct": None, "harmonized_step_pct": None,
              "bias_reduction_pct": None, "status": "insufficient_complete_years"}
    if not all(all((year, month) in covered for month in range(1, 13)) for year in years):
        return result
    def average(group, key):
        return math.fsum(by_year.get(year, {}).get(key, 0) for year in group) / len(group)
    raw_before, harm_before = average(before, "raw_total"), average(before, "hhe_total")
    if raw_before <= 0 or harm_before <= 0:
        result["status"] = "undefined_zero_reference"
        return result
    raw = (average(after, "raw_total") / raw_before - 1) * 100
    harm = (average(after, "hhe_total") / harm_before - 1) * 100
    result.update(raw_step_pct=round(raw, 6), harmonized_step_pct=round(harm, 6),
                  status="descriptive_before_after_comparison")
    if abs(raw) > 1e-9:
        result["bias_reduction_pct"] = round((1 - abs(harm) / abs(raw)) * 100, 6)
    else:
        result["status"] = "undefined_reduction_when_raw_change_is_zero"
    return result


def harmonize_records(raw_records: list[dict[str, Any]], aoi: dict[str, Any], *,
                      exclude_static_flares: bool = True,
                      confidence_min: str = "low") -> dict[str, Any]:
    rows, quality, coverage = normalize_observations(raw_records, aoi, confidence_min)
    inferred, known_static = persistent_cells(rows)
    windows = observation_windows(rows)
    events = [summarize_window(window, inferred, aoi.get("geometry")) for window in windows]
    for event in events:
        # Persistence alone does not establish a non-vegetation source or cause.
        event["include_in_calendar"] = not (exclude_static_flares and event["source_type"] != 0)

    monthly_modis = _sum_months(events, "modis_w")
    monthly_viirs = _sum_months(events, "viirs_w")
    overlap = sorted(month for month in monthly_modis.keys() & monthly_viirs.keys()
                     if (2012, 2) <= month <= (2024, 12)
                     and monthly_modis[month] > 0 and monthly_viirs[month] > 0)
    calibrated = len(overlap) >= 3
    kappa = (math.fsum(monthly_modis[m] for m in overlap) /
             math.fsum(monthly_viirs[m] for m in overlap)) if calibrated else DEFAULT_KAPPA
    agreement = calibration_agreement([monthly_modis[m] for m in overlap],
                                      [kappa * monthly_viirs[m] for m in overlap])
    eras = []
    for start, end in ((2012, 2017), (2018, 2023), (2024, 2024)):
        months = [m for m in overlap if start <= m[0] <= end]
        ratio = (math.fsum(monthly_modis[m] for m in months) /
                 math.fsum(monthly_viirs[m] for m in months)) if len(months) >= 3 else None
        eras.append({"years": f"{start}-{end}", "overlap_months": len(months),
                     "empirical_kappa": round(ratio, 8) if ratio is not None else None,
                     "applied": False, "purpose": "diagnostic comparison with the pooled bridge",
                     "agreement_at_pooled_kappa": calibration_agreement(
                         [monthly_modis[m] for m in months], [kappa * monthly_viirs[m] for m in months])})
    matched_frp = [e for e in events if e["include_in_calendar"]
                   and (2012, 2) <= (e["year"], e["month"]) <= (2024, 12)
                   and e["modis_frp_mw"] is not None and e["modis_frp_mw"] > 0
                   and e["viirs_frp_mw"] is not None and e["viirs_frp_mw"] > 0]
    frp_ratio = (math.fsum(e["modis_frp_mw"] for e in matched_frp) /
                 math.fsum(e["viirs_frp_mw"] for e in matched_frp)) if len(matched_frp) >= 3 else DEFAULT_FRP_RATIO

    for event in events:
        month = event["year"], event["month"]
        blend = 0.5 if monthly_modis.get(month, 0) > 0 and monthly_viirs.get(month, 0) > 0 else 1.0
        event["hhe"] = round(blend * (event["modis_w"] + kappa * event["viirs_w"]), 8) if event["include_in_calendar"] else 0.0
        powers = ([event["modis_frp_mw"]] if event["modis_frp_mw"] is not None else [])
        if event["viirs_frp_mw"] is not None:
            powers.append(frp_ratio * event["viirs_frp_mw"])
        event["frp_is_missing"] = not powers
        event["hfre_mw"] = round(math.fsum(powers) / len(powers), 6) if powers else None

    grouped = defaultdict(list)
    for event in events:
        grouped[event["year"]].append(event)
    by_year = {}
    for year, values in sorted(grouped.items()):
        included = [e for e in values if e["include_in_calendar"]]
        powers = [e["hfre_mw"] for e in included if e["hfre_mw"] is not None]
        by_year[year] = {
            "year": year, "raw_modis": sum(e["raw_modis"] for e in included),
            "raw_viirs": sum(e["raw_viirs"] for e in included),
            "raw_total": sum(e["raw_detections"] for e in included),
            "raw_flares": sum(e["raw_detections"] for e in values if e["source_type"] != 0),
            "hhe_total": round(math.fsum(e["hhe"] for e in included), 6),
            "frp_total_mw": round(math.fsum(powers), 6) if powers else None,
            "cell_events": len(included),
        }
    covered = {tuple(month) for month in coverage["complete_months"]}
    transitions = [_transition_audit(by_year, covered, year) for year in (2012, 2018)]
    categories = defaultdict(int)
    for event in events:
        categories[event["fire_category"]] += event["raw_detections"]
    non_vegetation = sum(e["raw_detections"] for e in events if e["source_type"] != 0)
    raw_modis = sum(e["raw_modis"] for e in events if e["include_in_calendar"] and (e["year"], e["month"]) in overlap)
    raw_viirs = sum(e["raw_viirs"] for e in events if e["include_in_calendar"] and (e["year"], e["month"]) in overlap)
    denominator = len(rows)
    audit = {
        "aoi_id": aoi["aoi_id"],
        "method_version": "occupancy-windows-v2",
        "overlap_years": f"{overlap[0][0]}-{overlap[-1][0]}" if overlap else "none",
        "overlap_months_count": len(overlap), "calibration_valid": calibrated,
        "calibration_basis": "empirical_monthly_sum_ratio" if calibrated else "assumed_demo_kappa_insufficient_overlap",
        "raw_viirs_to_modis_ratio": round(raw_viirs / raw_modis, 6) if raw_modis else None,
        "calibrated_kappa": round(kappa, 8), "frp_conversion_ratio": round(frp_ratio, 8),
        "frp_calibration_basis": "matched_window_sum_ratio" if len(matched_frp) >= 3 else "assumed_identity_insufficient_pairs",
        "matched_frp_windows": len(matched_frp),
        "era_diagnostics": eras,
        "bridge_r2": agreement["r2"], "bridge_efficiency": agreement["efficiency"],
        "bridge_rmse": agreement["rmse"], "bridge_mean_bias": agreement["mean_bias"],
        "overpass_duplicates_removed": len(rows) - len(events),
        "exact_or_revised_duplicate_rows": sum(e["duplicate_observation_rows"] for e in events),
        "raw_step_jump_2012_pct": transitions[0]["raw_step_pct"],
        "harmonized_step_diff_2012_pct": transitions[0]["harmonized_step_pct"],
        "bias_reduction_pct": transitions[0]["bias_reduction_pct"],
        "transition_audits": transitions,
        "total_raw_detections": denominator,
        "total_harmonized_events": sum(e["include_in_calendar"] for e in events),
        "static_flare_detections": non_vegetation,
        "flare_contamination_share": round(non_vegetation / denominator, 6) if denominator else 0,
        "non_vegetation_share": round(non_vegetation / denominator, 6) if denominator else 0,
        # Compatibility keys describe patterns, never independently established causes.
        "wildfire_share": round(categories["VEGETATION_THERMAL"] / denominator, 6) if denominator else 0,
        "agricultural_share": round(categories["LOW_FRP_DAYTIME"] / denominator, 6) if denominator else 0,
        "category_counts": dict(sorted(categories.items())),
        "classification_limit": "FIRMS types and thermal patterns do not establish wildfire, agricultural burning, or industrial cause.",
        "skipped_invalid_rows": quality["invalid_rows"], "quality": quality,
        "exclude_static_flares": exclude_static_flares,
        "window_minutes": 60, "target_grid_metres": 1000,
    }
    return {"hotspots": events, "annual_sensor_breakdown": list(by_year.values()),
            "sensor_calibration_audit": audit, "persistent_flare_cells": sorted(known_static),
            "persistent_inferred_cells": sorted(inferred), "observation_coverage": coverage,
            "quality": quality}

