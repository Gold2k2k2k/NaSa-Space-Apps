"""Coverage-aware monthly/dekadal summaries and descriptive demo statistics."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.stats import (empirical_percentile, ols_slope_per_decade, quantile,
                       season_phenology, theil_sen_per_decade)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _rounded(value):
    return round(value, 6) if value is not None else None


def _distribution(values):
    return {"median": quantile(values, .5), "mean": math.fsum(values) / len(values) if values else None,
            "q25": quantile(values, .25), "q75": quantile(values, .75),
            "p90": quantile(values, .9), "p95": quantile(values, .95),
            "min": min(values) if values else None, "max": max(values) if values else None}


def build_burning_calendar(harmonized_data: dict[str, Any], aoi: dict[str, Any], *,
                           year_start=2000, year_end=2026, baseline_start=2001,
                           baseline_end=2020, focus_year=2026, focus_month=9,
                           mode="harmonized") -> dict[str, Any]:
    if not 2000 <= year_start <= focus_year <= year_end <= 2026 or not 1 <= focus_month <= 12:
        raise ValueError("Calendar window or focus is invalid")
    if mode not in ("raw", "harmonized"):
        raise ValueError("Calendar mode must be raw or harmonized")
    use_raw = mode == "raw"
    events = harmonized_data["hotspots"]
    coverage = harmonized_data.get("observation_coverage", {})
    recorded = {tuple(m) for m in coverage.get("recorded_months", [(e["year"], e["month"]) for e in events])}
    complete = {tuple(m) for m in coverage.get("complete_months", aoi.get("complete_periods", []))}
    recorded_dekads = {tuple(d) for d in coverage.get("recorded_dekads", [(e["year"], e["dekad"]) for e in events])}
    observed = recorded | complete
    grouped = defaultdict(list)
    dekads = defaultdict(list)
    for event in events:
        if event["include_in_calendar"]:
            grouped[(event["year"], event["month"])].append(event)
            dekads[(event["year"], event["dekad"])].append(event)

    def total(items, key):
        return math.fsum(e[key] for e in items)
    def metric(items):
        return total(items, "raw_detections" if use_raw else "hhe")

    distributions, history_by_month, reference_history = [], {}, []
    for month in range(1, 13):
        years = [y for y in range(baseline_start, baseline_end + 1) if (y, month) in observed]
        values = [metric(grouped[(y, month)]) for y in years]
        history_by_month[month] = values
        reference_history.append({"month": month, "years": years, "values": values,
                                  "coverage_statuses": ["complete" if (y, month) in complete else "records_only" for y in years]})
        row = _distribution(values)
        row["iqr"] = row["q75"] - row["q25"] if values else None
        row["hhe_median"] = quantile([total(grouped[(y, month)], "hhe") for y in years], .5)
        distributions.append({"month": month, "month_name": MONTH_NAMES[month - 1],
                              "baseline_year_count": len(years),
                              "baseline_complete_year_count": sum((y, month) in complete for y in years),
                              **{key: _rounded(value) for key, value in row.items()}})

    def make_cell(year, month):
        key = year, month
        items = grouped[key]
        has_data = key in observed
        value = metric(items) if has_data else None
        hhe = total(items, "hhe") if has_data else None
        powers = [e["hfre_mw"] for e in items if e.get("hfre_mw") is not None]
        known_dn = [e for e in items if e["daynight"] in ("D", "N")]
        dn_total = metric(known_dn)
        night_share = metric([e for e in known_dn if e["daynight"] == "N"]) / dn_total if dn_total > 0 else None
        clim = distributions[month - 1]
        median, iqr = clim["median"], clim["iqr"]
        comparable = has_data and median is not None
        # Explicit heuristic floor, not an estimated probability distribution.
        scale = max(.7413 * iqr, .5, .18 * median) if median is not None else None
        anomaly = value - median if comparable else None
        z = anomaly / scale if comparable else None
        pct = anomaly / median * 100 if comparable and median != 0 else None
        band = ("missing" if not has_data else "unverifiable" if z is None else
                "critical" if z >= 2 and value > clim["p95"] else
                "elevated" if z >= 1 else "low" if z < -1 else "nominal")
        cell = {"aoi_id": aoi["aoi_id"], "year": year, "month": month,
                "month_name": MONTH_NAMES[month - 1], "is_observed": has_data,
                "is_complete": key in complete,
                "coverage_status": "complete" if key in complete else "records_only" if has_data else "missing",
                "value": _rounded(value), "hhe_total": _rounded(hhe),
                "raw_total": int(total(items, "raw_detections")) if has_data else None,
                "raw_modis": int(total(items, "raw_modis")) if has_data else None,
                "raw_viirs": int(total(items, "raw_viirs")) if has_data else None,
                "frp_total_mw": _rounded(math.fsum(powers)) if powers else None,
                "frp_measured_events": len(powers), "frp_missing_events": len(items) - len(powers),
                "night_share": _rounded(night_share),
                "hist_median_hhe": median, "hist_mean_hhe": clim["mean"],
                "hist_iqr_hhe": iqr, "hist_p90_hhe": clim["p90"], "hist_p95_hhe": clim["p95"],
                "anomaly_abs": _rounded(anomaly), "anomaly_pct": _rounded(pct),
                "z_robust": _rounded(z), "empirical_percentile": empirical_percentile(history_by_month[month], value) if has_data else None,
                "severity_band": band}
        return cell

    cells = [make_cell(year, month) for year in range(year_start, year_end + 1) for month in range(1, 13)]
    by_month = {(cell["year"], cell["month"]): cell for cell in cells}
    previous_key = (focus_year - 1, 12) if focus_month == 1 else (focus_year, focus_month - 1)
    previous_context = (by_month.get(previous_key) or make_cell(*previous_key)) if previous_key[0] >= 2000 else None

    annual = []
    hhe_points, raw_points = [], []
    for year in range(year_start, year_end + 1):
        available = [by_month[(year, m)] for m in range(1, 13) if by_month[(year, m)]["is_observed"]]
        full = all(by_month[(year, m)]["is_complete"] for m in range(1, 13))
        def annual_sum(key):
            values = [c[key] for c in available if c[key] is not None]
            return _rounded(math.fsum(values)) if values else None
        row = {"year": year, "is_complete": full, "observed_months": len(available),
               **{key: annual_sum(key) for key in ("value", "hhe_total", "raw_total", "raw_modis", "raw_viirs", "frp_total_mw")}}
        annual.append(row)
        if full:
            hhe_points.append((year, row["hhe_total"]))
            raw_points.append((year, row["raw_total"]))

    profile = []
    for dekad in range(1, 37):
        month = (dekad - 1) // 3 + 1
        def covered(year):
            return (year, month) in complete or (year, dekad) in recorded_dekads
        values = [metric(dekads[(y, dekad)]) for y in range(baseline_start, baseline_end + 1) if covered(y)]
        profile.append({"dekad": dekad, "month": month,
                        "label": f"{MONTH_NAMES[month - 1]} D{(dekad - 1) % 3 + 1}",
                        "focus_value": _rounded(metric(dekads[(focus_year, dekad)])) if covered(focus_year) else None,
                        "hist_median": _rounded(quantile(values, .5)),
                        "hist_p90": _rounded(quantile(values, .9)), "baseline_year_count": len(values)})
    phenology = season_phenology([p["hist_median"] for p in profile])
    valid_climate = [c for c in distributions if c["median"] is not None and c["median"] > 0]
    peak_months = [c["month"] for c in sorted(valid_climate, key=lambda c: (-c["median"], c["month"]))[:3]]
    focus_cell = by_month[(focus_year, focus_month)]
    history = [by_month[(y, focus_month)] for y in range(year_start, year_end + 1) if by_month[(y, focus_month)]["is_observed"]]
    rank = 1 + sum(c["value"] > focus_cell["value"] for c in history) if focus_cell["is_observed"] else None
    # Early-season context is the two months immediately before the cyclic onset.
    onset_month = (phenology["season_onset_dekad"] - 1) // 3 + 1 if phenology["season_defined"] else None
    prepeak = onset_month is not None and (onset_month - focus_month) % 12 in (1, 2)
    focus = {key: focus_cell[key] for key in ("year", "month", "month_name", "value", "hhe_total", "raw_total", "raw_modis", "raw_viirs",
              "frp_total_mw", "frp_measured_events", "frp_missing_events", "night_share", "anomaly_abs", "anomaly_pct",
              "z_robust", "empirical_percentile", "severity_band", "is_observed", "is_complete", "coverage_status")}
    focus.update({f"hist_{name}": distributions[focus_month - 1][name] for name in ("median", "mean", "iqr", "p90", "p95")})
    focus.update(rank_in_history=rank, history_years_count=len(history),
                 is_peak_season=focus_month in peak_months, is_pre_peak=prepeak)
    observed_cells = [c for c in cells if c["is_observed"]]
    peak_cell = max(observed_cells, key=lambda c: c["value"]) if observed_cells else focus_cell
    full_years = [r for r in annual if r["is_complete"]]
    peak_year = max(full_years, key=lambda r: r["value"]) if full_years else None
    points = raw_points if use_raw else hhe_points
    baseline = distributions[focus_month - 1]
    return {"mode": mode, "year_start": year_start, "year_end": year_end,
            "baseline_window": f"{baseline_start}-{baseline_end}",
            "baseline_year_count": baseline["baseline_year_count"],
            "baseline_complete_year_count": baseline["baseline_complete_year_count"],
            "focus_year": focus_year, "focus_month": focus_month,
            "max_cell_value": max((c["value"] for c in observed_cells), default=0),
            "max_hhe_value": max((c["hhe_total"] for c in observed_cells), default=0),
            "cells": cells, "previous_month_context": previous_context,
            "climatology": distributions, "reference_history": reference_history, "annual_series": annual,
            "dekadal_profile": profile, "phenology": phenology, "focus_comparison": focus,
            "coverage_note": "Recorded detections do not establish complete observation coverage or absence of fire.",
            "robust_scale_definition": "max(0.7413 * IQR, 0.5, 0.18 * median); demo heuristic",
            "summary_records": {"peak_months": peak_months, "peak_month_names": [MONTH_NAMES[m - 1] for m in peak_months],
                "peak_year": peak_year["year"] if peak_year else None,
                "peak_year_value": peak_year["value"] if peak_year else None,
                "peak_month_record": {key: peak_cell[key] for key in ("year", "month", "month_name", "value", "hhe_total")},
                "trend_slope_per_decade": ols_slope_per_decade(points),
                "theil_sen_slope_per_decade": theil_sen_per_decade(points),
                "harmonized_trend_slope_per_decade": ols_slope_per_decade(hhe_points),
                "raw_trend_slope_per_decade": ols_slope_per_decade(raw_points),
                "trend_complete_year_count": len(points)}}

