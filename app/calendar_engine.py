"""Burning Activity Calendar Engine (2000-2026 Monthly & Dekadal Matrix + Climatology).

Computes non-parametric historical baselines (median, Q25, Q75, IQR, P90, P95) over
2001-2020, robust Z-scores, multi-decadal trend slopes, and side-by-side harmonized
vs. unharmonized raw sensor views.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def _severity_band(z_robust: float, value: float, median: float, p95: float) -> str:
    if value <= 0.01 and median <= 0.01:
        return "low"
    if value > p95 and z_robust >= 2.0:
        return "extreme"
    if z_robust >= 1.5 or value > p95:
        return "high"
    if z_robust >= 0.75:
        return "elevated"
    if z_robust <= -0.75:
        return "low"
    return "normal"


def _ols_slope_per_decade(points: list[tuple[int, float]]) -> float:
    if len(points) < 4:
        return 0.0
    xs = [float(x) for x, _y in points]
    ys = [float(y) for _x, y in points]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 1e-12:
        return 0.0
    return round((num / den) * 10.0, 2)


def build_burning_calendar(
    harmonized_data: dict[str, Any],
    aoi: dict[str, Any],
    *,
    year_start: int = 2000,
    year_end: int = 2026,
    baseline_start: int = 2001,
    baseline_end: int = 2020,
    focus_year: int = 2026,
    focus_month: int = 9,
    mode: str = "harmonized",
) -> dict[str, Any]:
    """Build the full burning calendar matrix, seasonal climatology, and focus-month comparison."""
    hotspots = harmonized_data["hotspots"]
    use_raw = mode == "raw"

    # Aggregate included hotspot events by (year, month) and (year, dekad)
    ym_agg: dict[tuple[int, int], dict[str, Any]] = defaultdict(lambda: {
        "hhe": 0.0, "raw": 0, "raw_modis": 0, "raw_viirs": 0,
        "frp": 0.0, "night_hhe": 0.0, "wildfire": 0.0, "ag": 0.0,
        "events": 0,
    })
    dekad_hist: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))

    observed_years: set[int] = set()
    for ev in hotspots:
        if not ev["include_in_calendar"]:
            continue
        yr, mo = ev["year"], ev["month"]
        observed_years.add(yr)
        b = ym_agg[(yr, mo)]
        b["hhe"] += ev["hhe"]
        b["raw"] += ev["raw_detections"]
        b["raw_modis"] += ev["raw_modis"]
        b["raw_viirs"] += ev["raw_viirs"]
        b["frp"] += ev["hfre_mw"]
        b["events"] += 1
        metric_val = float(ev["raw_detections"]) if use_raw else float(ev["hhe"])
        if ev["daynight"] == "N":
            b["night_hhe"] += metric_val
        if ev["fire_category"] == "AGRICULTURAL_BURN":
            b["ag"] += metric_val
        elif ev["fire_category"] == "WILDFIRE":
            b["wildfire"] += metric_val
        dekad_hist[ev["dekad"]][yr] += metric_val

    # Clamp effective year window cleanly
    eff_start = max(2000, min(year_start, year_end))
    eff_end = min(2026, max(year_start, year_end))

    # Build 2001-2020 monthly baseline distributions
    # Fallback to all years excluding focus_year if dataset doesn't span 2001-2020 (e.g., short uploaded CSV)
    baseline_years_available = sorted(
        y for y in observed_years if baseline_start <= y <= baseline_end
    )
    if len(baseline_years_available) < 3:
        baseline_years_available = sorted(y for y in observed_years if y != focus_year) or sorted(observed_years)

    climatology: list[dict[str, Any]] = []
    clim_by_month: dict[int, dict[str, Any]] = {}
    for mo in range(1, 13):
        vals = []
        hhe_vals = []
        for y in baseline_years_available:
            b = ym_agg.get((y, mo))
            v = float(b["raw"] if use_raw else b["hhe"]) if b else 0.0
            vals.append(v)
            hhe_vals.append(float(b["hhe"]) if b else 0.0)
        vals_sorted = sorted(vals)
        med = _quantile(vals_sorted, 0.5)
        mean_v = sum(vals_sorted) / len(vals_sorted) if vals_sorted else 0.0
        q25 = _quantile(vals_sorted, 0.25)
        q75 = _quantile(vals_sorted, 0.75)
        iqr = max(0.0, q75 - q25)
        p90 = _quantile(vals_sorted, 0.90)
        p95 = _quantile(vals_sorted, 0.95)
        row_c = {
            "month": mo,
            "month_name": MONTH_NAMES[mo - 1],
            "median": round(med, 2),
            "mean": round(mean_v, 2),
            "q25": round(q25, 2),
            "q75": round(q75, 2),
            "iqr": round(iqr, 2),
            "p90": round(p90, 2),
            "p95": round(p95, 2),
            "min": round(vals_sorted[0], 2) if vals_sorted else 0.0,
            "max": round(vals_sorted[-1], 2) if vals_sorted else 0.0,
            "hhe_median": round(_quantile(sorted(hhe_vals), 0.5), 2),
        }
        climatology.append(row_c)
        clim_by_month[mo] = row_c

    # Build calendar cells across [eff_start..eff_end] x [1..12]
    cells: list[dict[str, Any]] = []
    cells_by_ym: dict[tuple[int, int], dict[str, Any]] = {}
    max_metric_val = 0.0
    max_hhe_val = 0.0

    for yr in range(eff_start, eff_end + 1):
        for mo in range(1, 13):
            is_observed = not (yr == 2026 and mo == 12)
            b = ym_agg.get((yr, mo))
            hhe_total = round(b["hhe"], 2) if (b and is_observed) else 0.0
            raw_total = int(b["raw"]) if (b and is_observed) else 0
            raw_modis = int(b["raw_modis"]) if (b and is_observed) else 0
            raw_viirs = int(b["raw_viirs"]) if (b and is_observed) else 0
            frp_total = round(b["frp"], 1) if (b and is_observed) else 0.0
            metric = float(raw_total) if use_raw else float(hhe_total)
            denom_metric = max(1e-6, metric)
            night_share = round(b["night_hhe"] / denom_metric, 4) if (b and metric > 0 and is_observed) else 0.0

            clim = clim_by_month[mo]
            hist_med = clim["median"]
            hist_iqr = clim["iqr"]
            sigma_rob = max(0.7413 * hist_iqr, max(0.5, 0.18 * hist_med))
            anom_abs = round(metric - hist_med, 2) if is_observed else 0.0
            anom_pct = round(((metric - hist_med) / max(1.0, hist_med)) * 100.0, 1) if is_observed else 0.0
            z_rob = round((metric - hist_med) / sigma_rob, 2) if is_observed else 0.0
            band = _severity_band(z_rob, metric, hist_med, clim["p95"]) if is_observed else "pending"

            if is_observed:
                max_metric_val = max(max_metric_val, metric)
                max_hhe_val = max(max_hhe_val, hhe_total)

            cell = {
                "aoi_id": aoi["aoi_id"],
                "year": yr,
                "month": mo,
                "month_name": MONTH_NAMES[mo - 1],
                "is_observed": is_observed,
                "value": round(metric, 2),
                "hhe_total": hhe_total,
                "raw_total": raw_total,
                "raw_modis": raw_modis,
                "raw_viirs": raw_viirs,
                "frp_total_mw": frp_total,
                "night_share": night_share,
                "hist_median_hhe": hist_med,
                "hist_mean_hhe": clim["mean"],
                "hist_iqr_hhe": hist_iqr,
                "hist_p90_hhe": clim["p90"],
                "hist_p95_hhe": clim["p95"],
                "anomaly_abs": anom_abs,
                "anomaly_pct": anom_pct,
                "z_robust": z_rob,
                "severity_band": band,
            }
            cells.append(cell)
            cells_by_ym[(yr, mo)] = cell

    # Build annual series across eff_start..eff_end
    annual_series: list[dict[str, Any]] = []
    trend_pts_hhe: list[tuple[int, float]] = []
    trend_pts_raw: list[tuple[int, float]] = []
    for yr in range(eff_start, eff_end + 1):
        yr_cells = [cells_by_ym[(yr, m)] for m in range(1, 13) if cells_by_ym[(yr, m)]["is_observed"]]
        hhe_yr = round(sum(c["hhe_total"] for c in yr_cells), 2)
        raw_yr = sum(c["raw_total"] for c in yr_cells)
        modis_yr = sum(c["raw_modis"] for c in yr_cells)
        viirs_yr = sum(c["raw_viirs"] for c in yr_cells)
        frp_yr = round(sum(c["frp_total_mw"] for c in yr_cells), 1)
        val_yr = float(raw_yr) if use_raw else hhe_yr
        annual_series.append({
            "year": yr,
            "value": round(val_yr, 2),
            "hhe_total": hhe_yr,
            "raw_total": raw_yr,
            "raw_modis": modis_yr,
            "raw_viirs": viirs_yr,
            "frp_total_mw": frp_yr,
        })
        if yr < 2026:
            trend_pts_hhe.append((yr, hhe_yr))
            trend_pts_raw.append((yr, float(raw_yr)))

    # 36-dekad seasonal profile for focus_year vs baseline
    dekadal_profile: list[dict[str, Any]] = []
    for dk in range(1, 37):
        base_dk_vals = sorted(dekad_hist[dk].get(y, 0.0) for y in baseline_years_available)
        dk_med = round(_quantile(base_dk_vals, 0.5), 2)
        dk_p90 = round(_quantile(base_dk_vals, 0.9), 2)
        dk_focus = round(dekad_hist[dk].get(focus_year, 0.0), 2)
        dekadal_profile.append({
            "dekad": dk,
            "month": ((dk - 1) // 3) + 1,
            "label": f"{MONTH_NAMES[(dk - 1) // 3]} D{((dk - 1) % 3) + 1}",
            "focus_value": dk_focus,
            "hist_median": dk_med,
            "hist_p90": dk_p90,
        })

    # Focus-month comparison & records
    eff_focus_year = min(2026, max(eff_start, focus_year))
    eff_focus_month = min(11 if eff_focus_year == 2026 else 12, max(1, focus_month))
    focus_cell = cells_by_ym[(eff_focus_year, eff_focus_month)]

    same_month_history = sorted(
        (cells_by_ym[(y, eff_focus_month)] for y in range(eff_start, eff_end + 1) if cells_by_ym[(y, eff_focus_month)]["is_observed"]),
        key=lambda c: c["value"],
        reverse=True,
    )
    rank_in_history = next(
        (idx + 1 for idx, c in enumerate(same_month_history) if c["year"] == eff_focus_year),
        len(same_month_history),
    )

    peak_months_sorted = sorted(climatology, key=lambda c: c["median"], reverse=True)
    peak_months = [c["month"] for c in peak_months_sorted[:3]]
    peak_year_row = max(annual_series, key=lambda r: r["value"]) if annual_series else {"year": eff_focus_year, "value": 0}
    observed_cells = [c for c in cells if c["is_observed"]]
    peak_cell = max(observed_cells, key=lambda c: c["value"]) if observed_cells else focus_cell

    return {
        "mode": "raw" if use_raw else "harmonized",
        "year_start": eff_start,
        "year_end": eff_end,
        "baseline_window": f"{baseline_years_available[0]}-{baseline_years_available[-1]}" if baseline_years_available else "none",
        "baseline_year_count": len(baseline_years_available),
        "focus_year": eff_focus_year,
        "focus_month": eff_focus_month,
        "max_cell_value": round(max_metric_val, 2),
        "max_hhe_value": round(max_hhe_val, 2),
        "cells": cells,
        "climatology": climatology,
        "annual_series": annual_series,
        "dekadal_profile": dekadal_profile,
        "focus_comparison": {
            "year": eff_focus_year,
            "month": eff_focus_month,
            "month_name": MONTH_NAMES[eff_focus_month - 1],
            "value": focus_cell["value"],
            "hhe_total": focus_cell["hhe_total"],
            "raw_total": focus_cell["raw_total"],
            "raw_modis": focus_cell["raw_modis"],
            "raw_viirs": focus_cell["raw_viirs"],
            "frp_total_mw": focus_cell["frp_total_mw"],
            "night_share": focus_cell["night_share"],
            "hist_median": focus_cell["hist_median_hhe"],
            "hist_mean": focus_cell["hist_mean_hhe"],
            "hist_iqr": focus_cell["hist_iqr_hhe"],
            "hist_p90": focus_cell["hist_p90_hhe"],
            "hist_p95": focus_cell["hist_p95_hhe"],
            "anomaly_abs": focus_cell["anomaly_abs"],
            "anomaly_pct": focus_cell["anomaly_pct"],
            "z_robust": focus_cell["z_robust"],
            "severity_band": focus_cell["severity_band"],
            "rank_in_history": rank_in_history,
            "history_years_count": len(same_month_history),
            "is_peak_season": eff_focus_month in peak_months,
        },
        "summary_records": {
            "peak_months": peak_months,
            "peak_month_names": [MONTH_NAMES[m - 1] for m in peak_months],
            "peak_year": peak_year_row["year"],
            "peak_year_value": peak_year_row["value"],
            "peak_month_record": {
                "year": peak_cell["year"],
                "month": peak_cell["month"],
                "month_name": peak_cell["month_name"],
                "value": peak_cell["value"],
                "hhe_total": peak_cell["hhe_total"],
            },
            "trend_slope_per_decade": _ols_slope_per_decade(trend_pts_raw if use_raw else trend_pts_hhe),
            "harmonized_trend_slope_per_decade": _ols_slope_per_decade(trend_pts_hhe),
            "raw_trend_slope_per_decade": _ols_slope_per_decade(trend_pts_raw),
        },
    }

