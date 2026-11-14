"""Deterministic Fire Regime Verdict Rules (pure code, zero network, zero model calls).

Ordered Rules:
  Rule 1 -> UNVERIFIABLE     (invalid geometry, insufficient baseline <5 yrs, or >50% static flare contamination)
  Rule 2 -> CRITICAL_ANOMALY (extreme burning surge > P95 & Z_robust >= 2.0, out-of-season ignition, or night FRP surge)
  Rule 3 -> ELEVATED_WATCH   (above-median activity 1.0 <= Z_robust < 2.0, regime intensification, or early season onset)
  Rule 4 -> NOMINAL_REGIME   (activity tracking within 2001-2020 historical baseline bounds)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.canonical import sha256_of

RULES_VERSION = "2026-11-14.1"
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
                f"{audit['total_raw_detections']}) originate from stationary industrial flares (FIRMS type=2 / "
                f">=8 mo/yr persistence). Vegetation wildfire inference is masked."
            ),
            (f"audit:flares:{aoi['aoi_id']}", "query:Q5"),
        ))

    # If Rule 1 fires, return UNVERIFIABLE immediately (matching GreenTrace's rule-1 safeguard)
    if findings:
        return _finalize(findings, focus, calendar, audit)

    z_rob = float(focus["z_robust"])
    val = float(focus["value"])
    p95 = float(focus["hist_p95"])
    p90 = float(focus["hist_p90"])
    med = float(focus["hist_median"])
    night_share = float(focus.get("night_share", 0.0))

    # Rule 2: CRITICAL_ANOMALY checks
    if val > p95 and z_rob >= 2.0:
        findings.append(Finding(
            2, CRITICAL_ANOMALY, "extreme_burning_surge",
            (
                f"{focus['month_name']} {focus['year']} recorded {val:.1f} "
                f"{'raw detections' if calendar['mode'] == 'raw' else 'HHE'}, exceeding the 2001–2020 "
                f"95th percentile ({p95:.1f}) with Z_robust = {z_rob:+.2f} "
                f"({focus['anomaly_pct']:+.1f}% vs median {med:.1f})."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6"),
        ))

    # Out-of-season ignition: normally quiet month (< 25% of peak month median) surges past P95 & Z >= 2.2
    peak_med = max((c["median"] for c in climatology), default=1.0)
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
    if night_share >= 0.45 and z_rob >= 1.8 and val > p90:
        findings.append(Finding(
            2, CRITICAL_ANOMALY, "nighttime_crown_fire_surge",
            (
                f"Nocturnal burning share reached {night_share:.1%} ({focus['frp_total_mw']:.0f} MW FRP) during "
                f"{focus['month_name']} {focus['year']}, indicating sustained high-intensity wildfire."
            ),
            (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q4"),
        ))

    # Rule 3: ELEVATED_WATCH checks
    if not any(f.verdict == CRITICAL_ANOMALY for f in findings):
        if 1.0 <= z_rob < 2.0 or (val > p90 and z_rob >= 0.85):
            findings.append(Finding(
                3, ELEVATED_WATCH, "above_median_activity",
                (
                    f"{focus['month_name']} {focus['year']} activity ({val:.1f}) sits above the historical "
                    f"interquartile envelope (median {med:.1f}, Z_robust = {z_rob:+.2f}, {focus['anomaly_pct']:+.1f}%)."
                ),
                (f"cell:{focus['year']}-{focus['month']:02d}", "query:Q6"),
            ))

        annual_vals = [r["value"] for r in calendar["annual_series"] if r["year"] < 2026]
        mean_annual = sum(annual_vals) / max(1, len(annual_vals))
        rel_slope_pct = (records["trend_slope_per_decade"] / max(1.0, mean_annual)) * 100.0
        if rel_slope_pct >= 22.0 and z_rob >= 0.5:
            findings.append(Finding(
                3, ELEVATED_WATCH, "regime_intensification",
                (
                    f"Multi-decadal burning trend rises {rel_slope_pct:+.1f}% per decade "
                    f"({records['trend_slope_per_decade']:+.1f}/decade), indicating structural regime intensification."
                ),
                ("series:annual", "query:Q8"),
            ))

        # Early season onset check: preceding month elevated while focus month is pre-peak
        prev_mo = 12 if focus["month"] == 1 else focus["month"] - 1
        prev_cell = next(
            (c for c in calendar["cells"] if c["year"] == focus["year"] and c["month"] == prev_mo and c["is_observed"]),
            None,
        )
        if prev_cell and prev_cell["z_robust"] >= 1.25 and z_rob >= 0.6 and not focus["is_peak_season"]:
            findings.append(Finding(
                3, ELEVATED_WATCH, "early_season_onset",
                (
                    f"Pre-peak month {focus['month_name']} following elevated {prev_cell['month_name']} "
                    f"(Z = {prev_cell['z_robust']:+.2f}) signals an early fire-season onset."
                ),
                (f"cell:{focus['year']}-{prev_mo:02d}", "query:Q7"),
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
        "focus_value": round(float(focus["value"]), 4),
        "focus_hist_median": round(float(focus["hist_median"]), 4),
        "focus_z_robust": round(float(focus["z_robust"]), 4),
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

