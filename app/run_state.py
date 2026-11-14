"""Content identity and explicit hypothetical calendar metrics."""
from __future__ import annotations

import math
from pathlib import Path

from app.canonical import sha256_of
from app.stats import empirical_percentile, ols_slope_per_decade, theil_sen_per_decade

DEMO_REFERENCE = "2026-11-14T00:00:00Z"
CALCULATION_VERSION = "firetrace-demo-v2"


def calculation_digest():
    root = Path(__file__).resolve().parent
    names = ("agents.py", "calendar_engine.py", "canonical.py", "datasets.py", "evidence.py",
             "geo_passes.py", "geometry.py", "harmonize.py", "models.py", "observations.py",
             "rules.py", "run_state.py", "satellites.py", "schema_mapping.py", "stats.py")
    return sha256_of({name: (root / name).read_text(encoding="utf-8-sig") for name in names})


def content_run_id(aoi, options, inputs, source_digest, reference, scenario, lineage, calculation):
    payload = {"aoi": aoi, "options": options, "input_summary": inputs,
               "source_records_sha256": source_digest, "reference_time": reference,
               "scenario": scenario, "lineage": lineage, "calculation_sha256": calculation}
    return "ft-" + sha256_of(payload)[:24]


def apply_calendar_scenario(calendar):
    """Hold reference/observations fixed and model the focus metric at its median.

    This does not rewrite satellite records, raw counts, HHE or FRP. Only the
    explicitly hypothetical metric and summaries derived from that metric change.
    """
    focus = calendar["focus_comparison"]
    old, target = focus["value"], focus["hist_median"]
    if old is None or target is None:
        raise ValueError("A median scenario requires an observed focus period and reference median")
    year, month = focus["year"], focus["month"]
    history = [c["value"] for c in calendar["cells"] if c["month"] == month
               and 2001 <= c["year"] <= 2020 and c["is_observed"]]
    percentile = empirical_percentile(history, target)
    for cell in calendar["cells"]:
        if (cell["year"], cell["month"]) == (year, month):
            cell.update(observed_value=old, value=target, value_is_counterfactual=True,
                        anomaly_abs=0.0, anomaly_pct=0.0 if target != 0 else None,
                        z_robust=0.0, empirical_percentile=percentile, severity_band="nominal")
            focus.update({key: cell[key] for key in ("observed_value", "value", "value_is_counterfactual",
                          "anomaly_abs", "anomaly_pct", "z_robust", "empirical_percentile", "severity_band")})
    observed = [c for c in calendar["cells"] if c["is_observed"]]
    focus["rank_in_history"] = 1 + sum(c["value"] > target for c in observed if c["month"] == month)
    for row in calendar["annual_series"]:
        if row["year"] == year:
            row["observed_value"] = row["value"]
            row["value"] = round(math.fsum(c["value"] for c in observed if c["year"] == year), 6)
            row["value_is_counterfactual"] = True
    for row in calendar["dekadal_profile"]:
        if row["month"] == month:
            row["observed_focus_value"] = row["focus_value"]
            row["focus_value"] = round(row["focus_value"] * target / old, 6) if old > 0 and row["focus_value"] is not None else None
            row["value_is_counterfactual"] = True
    records = calendar["summary_records"]
    complete = [r for r in calendar["annual_series"] if r["is_complete"]]
    points = [(r["year"], r["value"]) for r in complete]
    records["trend_slope_per_decade"] = ols_slope_per_decade(points)
    records["theil_sen_slope_per_decade"] = theil_sen_per_decade(points)
    peak_year = max(complete, key=lambda r: r["value"]) if complete else None
    records["peak_year"] = peak_year["year"] if peak_year else None
    records["peak_year_value"] = peak_year["value"] if peak_year else None
    peak = max(observed, key=lambda c: c["value"])
    records["peak_month_record"] = {key: peak[key] for key in ("year", "month", "month_name", "value", "hhe_total")}
    calendar["max_cell_value"] = max(c["value"] for c in observed)
    calendar["counterfactual"] = {"kind": "focus_metric_to_median", "mode": calendar["mode"],
        "year": year, "month": month, "observed_value": old, "modeled_value": target,
        "baseline_held_fixed": True, "observations_unchanged": True,
        "note": "Hypothetical focus metric; observed raw counts, HHE, FRP and source records are unchanged. Annual metric totals and trends reflect the scenario."}
    return calendar
