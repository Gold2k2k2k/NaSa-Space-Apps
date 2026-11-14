"""Deterministic Fire Regime Verdict Rules (pure code, zero network, zero model calls).

Ordered Rules:
  Rule 1 -> UNVERIFIABLE     (missing/partial coverage, insufficient baseline or bridge, invalid geometry, source contamination)
  Rule 2 -> CRITICAL_ANOMALY (demo thresholds for high, out-of-season, or nighttime activity)
  Rule 3 -> ELEVATED_WATCH   (above-reference activity, robust trend, or pre-onset activity)
  Rule 4 -> NOMINAL_REGIME   (activity tracking within 2001-2020 historical baseline bounds)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.canonical import sha256_of

RULES_VERSION = "2026-11-14.2"
VERDICTS = ("CRITICAL_ANOMALY", "ELEVATED_WATCH", "NOMINAL_REGIME", "UNVERIFIABLE")
CRITICAL_ANOMALY, ELEVATED_WATCH, NOMINAL_REGIME, UNVERIFIABLE = VERDICTS


@dataclass(frozen=True)
class Finding:
    rule: int
    verdict: str
    code: str
    detail: str
    refs: tuple[str, ...]


def decide(evidence: dict[str, Any]) -> dict[str, Any]:
    """Compute the deterministic fire regime verdict and verdict_sha256 from evidence."""
    aoi = evidence["aoi"]
    calendar = evidence["calendar"]
    audit = evidence["sensor_calibration_audit"]
    options = evidence.get("options", {})
    flare_guard = bool(options.get("flare_guard", True))

    focus = calendar["focus_comparison"]
    records = calendar["summary_records"]
    climatology = calendar["climatology"]
    findings: list[Finding] = []

    if not focus.get("is_observed", True) or any(focus.get(key) is None for key in ("value", "hist_median", "hist_p90", "hist_p95", "z_robust")):
        findings.append(Finding(1, UNVERIFIABLE, "missing_comparison_evidence",
            "The focus period or its reference distribution is missing; absence of records is not zero activity.",
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6")))
    if not focus.get("is_complete", True) or calendar.get("baseline_complete_year_count", 20) < 5:
        findings.append(Finding(1, UNVERIFIABLE, "incomplete_observation_coverage",
            "Complete focus-month and at least five reference-month observation periods have not been established.",
            ("query:Q1", "query:Q6")))
    if calendar["mode"] == "harmonized" and focus.get("raw_viirs", 0) and not audit.get("calibration_valid", True):
        findings.append(Finding(1, UNVERIFIABLE, "assumed_sensor_bridge",
            "VIIRS contributes to this comparison, but fewer than three overlap months support the bridge; its multiplier is an explicit demo assumption.",
            ("query:Q2",)))

    lat = aoi.get("lat")
    lon = aoi.get("lon")
    if lat is None or lon is None or not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0):
        findings.append(Finding(
            1, UNVERIFIABLE, "invalid_aoi_geometry",
            f"AOI coordinates ({lat}, {lon}) lie outside valid Earth bounds.",
            (f"aoi:{aoi.get('aoi_id', 'unknown')}",),
        ))

    if calendar["baseline_year_count"] < 5:
        findings.append(Finding(
            1, UNVERIFIABLE, "insufficient_baseline_years",
            f"Only {calendar['baseline_year_count']} baseline years available (requires at least 5 years).",
            (f"calendar:baseline:{calendar['baseline_window']}",),
        ))

    flare_share = float(audit.get("flare_contamination_share", 0.0))
    if flare_guard and flare_share > 0.50:
        findings.append(Finding(
            1, UNVERIFIABLE, "static_flare_contamination",
            (
                f"{flare_share:.1%} of raw thermal detections ({audit['static_flare_detections']} of "
                f"{audit['total_raw_detections']}) have supplied volcanic, other static-land, or offshore "
                f"source types. Their dominance limits a vegetation-regime comparison; this is not independent source attribution."
            ),
            (f"audit:flares:{aoi['aoi_id']}", "query:Q5"),
        ))

    # Missing evidence takes priority over demonstration anomaly thresholds.
    if findings:
        return _finalize(findings, focus, calendar, audit)

    z_rob = float(focus["z_robust"])
    val = float(focus["value"])
    p95 = float(focus["hist_p95"])
    p90 = float(focus["hist_p90"])
    med = float(focus["hist_median"])
    night_share = focus.get("night_share")

    # Rule 2: CRITICAL_ANOMALY checks
    if val > p95 and z_rob >= 2.0:
        findings.append(Finding(
            2, CRITICAL_ANOMALY, "extreme_burning_surge",
            (
                f"{focus['month_name']} {focus['year']} recorded {val:.1f} "
                f"{'raw detections' if calendar['mode'] == 'raw' else 'HHE'}, exceeding the 2001–2020 "
                f"95th percentile ({p95:.1f}) with Z_robust = {z_rob:+.2f} "
                f"(reference median {med:.1f}). This is a descriptive demo threshold."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6"),
        ))

    # Out-of-season ignition: normally quiet month (< 25% of peak month median) surges past P95 & Z >= 2.2
    peak_med = max((c["median"] for c in climatology if c["median"] is not None), default=0)
    if med < 0.25 * peak_med and val > p95 and z_rob >= 2.2:
        findings.append(Finding(
            2, CRITICAL_ANOMALY, "out_of_season_ignition",
            (
                f"Off-peak month {focus['month_name']} {focus['year']} erupted to {val:.1f} against a "
                f"normally quiescent median of {med:.1f} (peak season median {peak_med:.1f})."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q7"),
        ))

    # Severe nighttime crown-fire persistence
    if night_share is not None and night_share >= 0.45 and z_rob >= 1.8 and val > p90:
        findings.append(Finding(
            2, CRITICAL_ANOMALY, "nighttime_activity_surge",
            (
                f"Nighttime share of activity with known day/night labels reached {night_share:.1%} during "
                f"{focus['month_name']} {focus['year']}. Satellite detections alone do not establish crown fire or fire cause."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q4"),
        ))

    # Rule 3: ELEVATED_WATCH checks
    if not any(f.verdict == CRITICAL_ANOMALY for f in findings):
        if z_rob >= 1.0 or (val > p90 and z_rob >= 0.85):
            findings.append(Finding(
                3, ELEVATED_WATCH, "above_median_activity",
                (
                    f"{focus['month_name']} {focus['year']} activity ({val:.1f}) sits above the historical "
                    f"reference (median {med:.1f}, Z_robust = {z_rob:+.2f})."
                ),
                (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6"),
            ))

        annual_vals = [r["value"] for r in calendar["annual_series"] if r.get("is_complete", False) and r["value"] is not None]
        mean_annual = sum(annual_vals) / max(1, len(annual_vals))
        slope = records.get("theil_sen_slope_per_decade", records.get("trend_slope_per_decade"))
        rel_slope_pct = slope / mean_annual * 100 if slope is not None and mean_annual > 0 else None
        if rel_slope_pct is not None and rel_slope_pct >= 22.0 and z_rob >= 0.5:
            findings.append(Finding(
                3, ELEVATED_WATCH, "regime_intensification",
                (
                    f"Multi-decadal burning trend rises {rel_slope_pct:+.1f}% per decade "
                    f"(Theil-Sen {slope:+.1f}/decade) across complete years; this does not establish a cause."
                ),
                ("series:annual", "query:Q8"),
            ))

        # Early season onset check: preceding month elevated while focus month is pre-peak
        prev_mo = 12 if focus["month"] == 1 else focus["month"] - 1
        prev_year = focus["year"] - 1 if focus["month"] == 1 else focus["year"]
        prev_cell = next(
            (c for c in calendar["cells"] if c["year"] == prev_year and c["month"] == prev_mo and c["is_observed"]),
            None,
        )
        if prev_cell and prev_cell["z_robust"] is not None and prev_cell["z_robust"] >= 1.25 and z_rob >= 0.6 and focus.get("is_pre_peak", False):
            findings.append(Finding(
                3, ELEVATED_WATCH, "early_season_onset",
                (
                    f"Pre-peak month {focus['month_name']} following elevated {prev_cell['month_name']} "
                    f"(Z = {prev_cell['z_robust']:+.2f}) signals an early fire-season onset."
                ),
                (f"cell:{prev_year}-{prev_mo:02d}", "query:Q7"),
            ))

    # Rule 4: NOMINAL_REGIME fallback
    if not findings:
        findings.append(Finding(
            4, NOMINAL_REGIME, "within_historical_regime",
            (
                f"{focus['month_name']} {focus['year']} activity ({val:.1f}) remains consistent with the "
                f"2001–2020 historical seasonal median ({med:.1f}, Z_robust = {z_rob:+.2f})."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6"),
        ))

    return _finalize(findings, focus, calendar, audit)


def _finalize(
    findings: list[Finding],
    focus: dict[str, Any],
    calendar: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    findings_sorted = sorted(findings, key=lambda f: (f.rule, f.code, f.refs))
    verdicts_present = {f.verdict for f in findings_sorted}
    if UNVERIFIABLE in verdicts_present:
        overall = UNVERIFIABLE
    elif CRITICAL_ANOMALY in verdicts_present:
        overall = CRITICAL_ANOMALY
    elif ELEVATED_WATCH in verdicts_present:
        overall = ELEVATED_WATCH
    else:
        overall = NOMINAL_REGIME

    deciding_rule = min(f.rule for f in findings_sorted if f.verdict == overall)
    seal_payload = {
        "rules_version": RULES_VERSION,
        "verdict": overall,
        "deciding_rule": deciding_rule,
        "mode": calendar["mode"],
        "focus_year": focus["year"],
        "focus_month": focus["month"],
        "focus_value": round(float(focus["value"]), 4) if focus["value"] is not None else None,
        "focus_hist_median": round(float(focus["hist_median"]), 4) if focus["hist_median"] is not None else None,
        "focus_z_robust": round(float(focus["z_robust"]), 4) if focus["z_robust"] is not None else None,
        "calibrated_kappa": round(float(audit["calibrated_kappa"]), 4),
        "flare_contamination_share": round(float(audit["flare_contamination_share"]), 4),
        "findings": [
            {"rule": f.rule, "verdict": f.verdict, "code": f.code, "refs": list(f.refs)}
            for f in findings_sorted
        ],
    }
    return {
        "verdict": overall,
        "deciding_rule": deciding_rule,
        "rules_version": RULES_VERSION,
        "findings": [f.__dict__ for f in findings_sorted],
        "verdict_sha256": sha256_of(seal_payload),
    }

