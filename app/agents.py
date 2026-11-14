"""Five-Agent Explainable Pipeline: Extractor -> Planner -> Investigator -> Evaluator -> Writer.

Each investigation emits a deterministic trace (JSONL-compatible events), executes
scientific refutation checks in the Evaluator, calls app/rules.py for the immutable
verdict, and computes live counterfactual What-If flips.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Optional

from app.calendar_engine import MONTH_NAMES, build_burning_calendar
from app.canonical import sha256_of
from app.datasets import generate_firms_records, parse_custom_aoi
from app.evidence import QUERY_TITLES, expected_query_rows, summarize_inputs
from app.harmonize import harmonize_records
from app.rules import decide

PERSONAS = {
    "responder": "Early Warning & Emergency Responder",
    "scientist": "Earth Observation Scientist",
    "land_manager": "Land & Ecosystem Manager",
    "firefighter": "Wildfire Operations & Dispatch",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _trace_line(
    run_id: str,
    agent_name: str,
    action: str,
    input_summary: str,
    output_summary: str,
    *,
    confidence: float = 1.0,
    status: str = "success",
    rows: int = 0,
) -> dict[str, Any]:
    return {
        "timestamp": _now_iso(),
        "run_id": run_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "confidence": round(confidence, 3),
        "status": status,
        "rows": int(rows),
    }


def _build_query_tables(
    aoi: dict[str, Any],
    raw_records: list[dict[str, Any]],
    harmonized: dict[str, Any],
    calendar: dict[str, Any],
    input_summary: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    rows = expected_query_rows(
        aoi, calendar, harmonized["sensor_calibration_audit"],
        input_summary if input_summary is not None else summarize_inputs(raw_records),
        len(harmonized["persistent_flare_cells"]),
    )
    queries = [{"query_id": f"Q{i}", "title": title, "rows": [rows[f"Q{i}"]]}
               for i, title in enumerate(QUERY_TITLES)]
    for q in queries:
        q["row_count"] = len(q["rows"])
        q["sha256"] = sha256_of(q["rows"])
    return queries


def _evaluate_refutations(
    harmonized: dict[str, Any],
    calendar: dict[str, Any],
    raw_calendar: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run the Evaluator's four adversarial scientific checks."""
    audit = harmonized["sensor_calibration_audit"]
    hotspots = harmonized["hotspots"]
    avg_area = round(
        sum(h["effective_area_km2"] for h in hotspots) / max(1, len(hotspots)),
        3,
    )
    raw_jump = audit["raw_step_jump_2012_pct"]
    harm_diff = audit["harmonized_step_diff_2012_pct"]
    bias_red = audit["bias_reduction_pct"]

    r1_triggered = abs(raw_jump) >= 50.0
    r1_status = "MITIGATED" if (r1_triggered and bias_red >= 70.0) else ("PASS" if not r1_triggered else "WARN")

    dups = audit["overpass_duplicates_removed"]
    r2_status = "MITIGATED" if dups > 0 else "PASS"

    flare_share = audit["flare_contamination_share"]
    r4_status = "FLAGGED" if flare_share > 0.50 else ("MITIGATED" if flare_share > 0.0 else "PASS")

    return [
        {
            "id": "R1_SENSOR_SWITCH_ILLUSION",
            "title": "2012 / 2018 VIIRS Sensor-Switch Discontinuity Test",
            "hypothesis_tested": "Post-2012 increase in fire counts is an artifact of 375 m VIIRS sensitivity rather than physical burning.",
            "status": r1_status,
            "evidence": (
                f"Raw unharmonized counts exhibit a {raw_jump:+.1f}% discontinuity after 2012 (raw/MODIS ratio = "
                f"{audit['raw_viirs_to_modis_ratio']:.2f}x). Applying 1 km clustering and overlap bridge "
                f"kappa={audit['calibrated_kappa']:.3f} (R²={audit['bridge_r2']:.3f}) reduces step bias to "
                f"{harm_diff:+.1f}% ({bias_red:.1f}% bias reduction)."
            ),
            "raw_z_focus": raw_calendar["focus_comparison"]["z_robust"],
            "harmonized_z_focus": calendar["focus_comparison"]["z_robust"],
        },
        {
            "id": "R2_AFTERNOON_TRAIN_DOUBLE_COUNT",
            "title": "Afternoon Constellation Overpass Deduplication Test",
            "hypothesis_tested": "Co-orbiting afternoon satellites (Aqua, S-NPP, NOAA-20, NOAA-21) double-count the same fire event.",
            "status": r2_status,
            "evidence": (
                f"Collapsed {dups:,} redundant sub-pixel and co-orbital afternoon-train detections into "
                f"{audit['total_harmonized_events']:,} unique 1 km spatiotemporal burning events."
            ),
        },
        {
            "id": "R3_OFF_NADIR_PIXEL_GROWTH",
            "title": "Off-Nadir Bow-Tie Pixel Geometry Audit",
            "hypothesis_tested": "High scan-angle detections inflate apparent burning extent across sensor swaths.",
            "status": "MITIGATED",
            "evidence": (
                f"Normalized scan×track footprint area (mean {avg_area:.3f} km²) onto equal-area 1 km "
                f"sinusoidal cells (G1K_*) rather than weighting raw point density."
            ),
        },
        {
            "id": "R4_STATIC_INDUSTRIAL_FLARE_TRAP",
            "title": "Static Industrial Gas Flare & Volcano Contamination Test",
            "hypothesis_tested": "Persistent stationary thermal emitters (FIRMS type=2 or >=8 mo/yr) mask vegetation fire regimes.",
            "status": r4_status,
            "evidence": (
                f"Detected {audit['static_flare_detections']:,} stationary industrial detections "
                f"({flare_share:.1%} of total raw records across {len(harmonized['persistent_flare_cells'])} persistent cells). "
                + ("Dominates >50% of signal: vegetation regime marked UNVERIFIABLE." if flare_share > 0.50
                   else "Isolated from vegetation burning calendar.")
            ),
        },
    ]


def _persona_briefing(
    persona: str,
    aoi: dict[str, Any],
    calendar: dict[str, Any],
    decision: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    focus = calendar["focus_comparison"]
    records = calendar["summary_records"]
    verdict = decision["verdict"]
    peaks = ", ".join(records["peak_month_names"])
    p_key = persona if persona in PERSONAS else "responder"

    if p_key == "responder":
        headline = (
            f"{verdict.replace('_', ' ')}: {focus['month_name']} {focus['year']} stands at "
            f"{focus['anomaly_pct']:+.1f}% vs 2001–2020 median ({focus['value']:.1f} vs {focus['hist_median']:.1f} HHE)."
        )
        actions = [
            f"Critical historical season windows: {peaks}. Peak single year on record: {records['peak_year']}.",
            (
                "Escalate regional suppression readiness and monitor upcoming Terra/Aqua/VIIRS overpasses."
                if verdict == "CRITICAL_ANOMALY"
                else "Maintain watch-level briefing and track 10-day dekadal trajectory."
                if verdict == "ELEVATED_WATCH"
                else "Investigate ground verification before interpreting thermal anomalies as vegetation wildfire."
                if verdict == "UNVERIFIABLE"
                else "Activity aligns with historical seasonal baseline; maintain routine monitoring."
            ),
        ]
    elif p_key == "scientist":
        headline = (
            f"Sensor bridge kappa={audit['calibrated_kappa']:.3f} (R²={audit['bridge_r2']:.3f}) reduced 2012 "
            f"step bias by {audit['bias_reduction_pct']:.1f}% ({audit['raw_step_jump_2012_pct']:+.1f}% -> "
            f"{audit['harmonized_step_diff_2012_pct']:+.1f}%)."
        )
        actions = [
            f"Multi-decadal slope: {records['harmonized_trend_slope_per_decade']:+.2f} HHE/decade vs raw {records['raw_trend_slope_per_decade']:+.2f}/decade.",
            f"Focus period Z_robust = {focus['z_robust']:+.2f}, rank #{focus['rank_in_history']} of {focus['history_years_count']} years.",
        ]
    elif p_key == "land_manager":
        headline = (
            f"Attribution: {audit['wildfire_share']:.0%} wildfire, {audit['agricultural_share']:.0%} agricultural "
            f"crop-residue burns, {audit['flare_contamination_share']:.0%} static flares."
        )
        actions = [
            f"Peak management window for prescribed burn & permit enforcement: {peaks}.",
            f"Total harmonized radiative energy in {focus['month_name']} {focus['year']}: {focus['frp_total_mw']:,.0f} MW.",
        ]
    else:  # firefighter
        headline = (
            f"Nocturnal persistence {focus['night_share']:.0%} in {focus['month_name']} {focus['year']} "
            f"({focus['frp_total_mw']:,.0f} MW FRP) — {'active multi-night burn conditions' if focus['night_share'] >= 0.40 else 'predominantly diurnal burn cycle'}."
        )
        actions = [
            f"Check Passes & .ics schedule for next daylight/nighttime MODIS and VIIRS overpasses over {aoi['name']}.",
            "Download GeoJSON cell coordinates for tactical GIS overlay.",
        ]

    return {
        "persona": p_key,
        "persona_label": PERSONAS[p_key],
        "headline": headline,
        "actions": actions,
    }


def _compute_what_ifs(
    harmonized: dict[str, Any],
    aoi: dict[str, Any],
    options: dict[str, Any],
    base_decision: dict[str, Any],
    raw_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate key counterfactual experiments so the user can test what flips the verdict."""
    mode = options.get("mode", "harmonized")
    alt_mode = "raw" if mode == "harmonized" else "harmonized"
    alt_cal = build_burning_calendar(
        harmonized,
        aoi,
        year_start=options["year_start"],
        year_end=options["year_end"],
        focus_year=options["focus_year"],
        focus_month=options["focus_month"],
        mode=alt_mode,
    )
    alt_mode_dec = decide({"aoi": aoi, "calendar": alt_cal, "sensor_calibration_audit": harmonized["sensor_calibration_audit"], "options": options})

    # Counterfactual 2: toggle flare_guard (only needs re-harmonizing when flares exist in the AOI)
    alt_flare_guard = not bool(options.get("flare_guard", True))
    if harmonized["sensor_calibration_audit"]["static_flare_detections"] > 0:
        alt_harm_flare = harmonize_records(
            raw_records, aoi,
            exclude_static_flares=alt_flare_guard,
            confidence_min=options.get("confidence_min", "low"),
        )
        alt_cal_flare = build_burning_calendar(
            alt_harm_flare, aoi,
            year_start=options["year_start"],
            year_end=options["year_end"],
            focus_year=options["focus_year"],
            focus_month=options["focus_month"],
            mode=mode,
        )
        alt_flare_dec = decide({
            "aoi": aoi,
            "calendar": alt_cal_flare,
            "sensor_calibration_audit": alt_harm_flare["sensor_calibration_audit"],
            "options": {**options, "flare_guard": alt_flare_guard},
        })
    else:
        alt_flare_dec = base_decision

    # Counterfactual 3: normalize focus month to historical median
    med_cal = copy.deepcopy(build_burning_calendar(
        harmonized, aoi,
        year_start=options["year_start"],
        year_end=options["year_end"],
        focus_year=options["focus_year"],
        focus_month=options["focus_month"],
        mode=mode,
    ))
    med_focus = med_cal["focus_comparison"]
    med_focus["value"] = med_focus["hist_median"]
    med_focus["anomaly_abs"] = 0.0
    med_focus["anomaly_pct"] = 0.0
    med_focus["z_robust"] = 0.0
    med_focus["night_share"] = min(0.25, med_focus["night_share"])
    med_dec = decide({
        "aoi": aoi,
        "calendar": med_cal,
        "sensor_calibration_audit": harmonized["sensor_calibration_audit"],
        "options": options,
    })

    experiments = [
        {
            "id": "toggle_sensor_mode",
            "label": f"Switch to {'raw unharmonized detections' if alt_mode == 'raw' else 'harmonized HHE'}",
            "field": "mode",
            "value": alt_mode,
            "verdict_before": base_decision["verdict"],
            "verdict_after": alt_mode_dec["verdict"],
            "flips_verdict": alt_mode_dec["verdict"] != base_decision["verdict"],
            "z_before": round(float(med_cal["focus_comparison"]["z_robust"] if False else alt_cal["focus_comparison"]["z_robust"]), 2),
        },
        {
            "id": "toggle_flare_guard",
            "label": f"{'Enable' if alt_flare_guard else 'Disable'} static industrial flare guard",
            "field": "flare_guard",
            "value": alt_flare_guard,
            "verdict_before": base_decision["verdict"],
            "verdict_after": alt_flare_dec["verdict"],
            "flips_verdict": alt_flare_dec["verdict"] != base_decision["verdict"],
        },
        {
            "id": "reset_focus_to_median",
            "label": "Normalize focus month activity to 2001–2020 historical median",
            "field": "focus_to_median",
            "value": True,
            "verdict_before": base_decision["verdict"],
            "verdict_after": med_dec["verdict"],
            "flips_verdict": med_dec["verdict"] != base_decision["verdict"],
        },
    ]
    return {
        "experiments": experiments,
        "first_flip": next((e for e in experiments if e["flips_verdict"]), None),
    }


def run_investigation(
    request: dict[str, Any],
    *,
    run_id: Optional[str] = None,
    raw_records_override: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Execute the full 5-agent investigation and return the complete structured output."""
    aoi = parse_custom_aoi(request)
    year_start = int(request.get("year_start", 2000))
    year_end = int(request.get("year_end", 2026))
    focus_year = int(request.get("focus_year", aoi.get("default_focus_year", 2026)))
    focus_month = int(request.get("focus_month", aoi.get("default_focus_month", 8)))
    mode = "raw" if request.get("mode") == "raw" else "harmonized"
    flare_guard = bool(request.get("flare_guard", True))
    confidence_min = str(request.get("confidence_min", "low")).lower()
    persona = str(request.get("persona", "responder")).lower()

    options = {
        "year_start": year_start,
        "year_end": year_end,
        "focus_year": focus_year,
        "focus_month": focus_month,
        "mode": mode,
        "flare_guard": flare_guard,
        "confidence_min": confidence_min,
        "persona": persona,
    }

    if not run_id:
        seed_id = sha256_of({"aoi": aoi["aoi_id"], "options": options})[:10]
        run_id = f"ft-{seed_id}"

    trace: list[dict[str, Any]] = []

    # 1. Extractor
    trace.append(_trace_line(
        run_id, "Extractor", "parse_aoi_and_schemas",
        f"aoi={aoi['aoi_id']} ({aoi['lat']}, {aoi['lon']}) window={year_start}..{year_end}",
        f"Resolved 3 FIRMS source schemas -> 4 target schema definitions; focus={MONTH_NAMES[focus_month - 1]} {focus_year}",
        rows=1,
    ))

    # 2. Planner
    trace.append(_trace_line(
        run_id, "Planner", "plan_harmonization_queries",
        f"mode={mode}, flare_guard={flare_guard}, confidence_min={confidence_min}",
        "Planned queries Q0-Q8 across MODIS C6.1, VIIRS S-NPP, VIIRS NOAA-20/21, and 2001-2020 baseline",
        rows=9,
    ))

    # 3. Investigator
    raw_records = raw_records_override if raw_records_override is not None else generate_firms_records(aoi, year_start=2000, year_end=2026)
    harmonized = harmonize_records(
        raw_records,
        aoi,
        exclude_static_flares=flare_guard,
        confidence_min=confidence_min,
    )
    calendar_harm = build_burning_calendar(
        harmonized, aoi,
        year_start=year_start, year_end=year_end,
        focus_year=focus_year, focus_month=focus_month,
        mode="harmonized",
    )
    calendar_raw = build_burning_calendar(
        harmonized, aoi,
        year_start=year_start, year_end=year_end,
        focus_year=focus_year, focus_month=focus_month,
        mode="raw",
    )
    active_calendar = calendar_raw if mode == "raw" else calendar_harm
    input_summary = summarize_inputs(raw_records)
    queries = _build_query_tables(aoi, raw_records, harmonized, active_calendar, input_summary)

    trace.append(_trace_line(
        run_id, "Investigator", "execute_harmonize_and_calendar",
        f"raw_records={len(raw_records)}",
        (
            f"Clustered into {len(harmonized['hotspots'])} 1 km cell-pass events; "
            f"kappa={harmonized['sensor_calibration_audit']['calibrated_kappa']:.3f}; "
            f"deduped={harmonized['sensor_calibration_audit']['overpass_duplicates_removed']} co-detections"
        ),
        rows=len(harmonized["hotspots"]),
    ))

    # 4. Evaluator
    refutations = _evaluate_refutations(harmonized, calendar_harm, calendar_raw)
    trace.append(_trace_line(
        run_id, "Evaluator", "run_adversarial_refutations",
        "4 refutation tests (R1 sensor switch, R2 overpass double-count, R3 bow-tie, R4 static flares)",
        ", ".join(f"{r['id'].split('_')[0]}:{r['status']}" for r in refutations),
        rows=len(refutations),
    ))

    # 5. Writer (calls deterministic app/rules.py)
    evidence = {
        "aoi": aoi,
        "calendar": active_calendar,
        "sensor_calibration_audit": harmonized["sensor_calibration_audit"],
        "options": options,
    }
    decision = decide(evidence)
    what_if = _compute_what_ifs(harmonized, aoi, options, decision, raw_records)
    briefing = _persona_briefing(persona, aoi, active_calendar, decision, harmonized["sensor_calibration_audit"])

    trace.append(_trace_line(
        run_id, "Writer", "apply_deterministic_rules",
        f"rules_version={decision['rules_version']}",
        f"verdict={decision['verdict']} (rule {decision['deciding_rule']}), seal={decision['verdict_sha256'][:12]}...",
        rows=len(decision["findings"]),
    ))

    # Build a spatial preview sample of up to 450 representative hotspots for fast map rendering
    hotspots = harmonized["hotspots"]
    focus_spots = [h for h in hotspots if h["year"] == active_calendar["focus_year"] and h["month"] == active_calendar["focus_month"]]
    other_spots = [h for h in hotspots if not (h["year"] == active_calendar["focus_year"] and h["month"] == active_calendar["focus_month"])]
    step = max(1, len(other_spots) // 250)
    map_hotspots = (focus_spots[:220] + other_spots[::step][:230])[:450]

    return {
        "run_id": run_id,
        "status": "success",
        "aoi": {
            "aoi_id": aoi["aoi_id"],
            "name": aoi["name"],
            "country": aoi["country"],
            "biome": aoi["biome"],
            "lat": aoi["lat"],
            "lon": aoi["lon"],
            "radius_km": aoi["radius_km"],
            "area_km2": aoi["area_km2"],
            "peak_season": aoi.get("peak_season", ""),
            "description": aoi.get("description", ""),
            "polygon": aoi["polygon"],
            "bbox": aoi["bbox"],
        },
        "options": options,
        "verdict": decision["verdict"],
        "deciding_rule": decision["deciding_rule"],
        "rules_version": decision["rules_version"],
        "verdict_sha256": decision["verdict_sha256"],
        "findings": decision["findings"],
        "briefing": briefing,
        "calendar": active_calendar,
        "calendar_harmonized_summary": calendar_harm["focus_comparison"],
        "calendar_raw_summary": calendar_raw["focus_comparison"],
        "annual_sensor_breakdown": harmonized["annual_sensor_breakdown"],
        "sensor_calibration_audit": harmonized["sensor_calibration_audit"],
        "refutations": refutations,
        "what_if": what_if,
        "queries": queries,
        "trace": trace,
        "map_hotspots": map_hotspots,
        "_hotspots_all": hotspots,
        "_raw_records_count": len(raw_records),
        "_raw_records": raw_records_override,
        "_input_summary": input_summary,
        "_persistent_cells_count": len(harmonized["persistent_flare_cells"]),
    }


def apply_what_if(
    run_state: dict[str, Any],
    field: str,
    value: Any,
) -> dict[str, Any]:
    """Re-run the pipeline cleanly with a single counterfactual parameter updated."""
    opts = dict(run_state["options"])
    if field == "mode":
        opts["mode"] = "raw" if str(value) == "raw" else "harmonized"
    elif field == "flare_guard":
        opts["flare_guard"] = bool(value)
    elif field == "focus_year":
        opts["focus_year"] = int(value)
    elif field == "focus_month":
        opts["focus_month"] = int(value)
    elif field == "focus_period":
        opts["focus_year"] = int(value[0])
        opts["focus_month"] = int(value[1])
    elif field == "confidence_min":
        opts["confidence_min"] = str(value).lower()
    elif field == "persona":
        opts["persona"] = str(value).lower()
    elif field == "focus_to_median":
        updated = copy.deepcopy(run_state)
        cal = updated["calendar"]
        fc = cal["focus_comparison"]
        fc["value"] = fc["hist_median"]
        fc["anomaly_abs"] = 0.0
        fc["anomaly_pct"] = 0.0
        fc["z_robust"] = 0.0
        fc["night_share"] = min(0.25, fc["night_share"])
        dec = decide({
            "aoi": updated["aoi"],
            "calendar": cal,
            "sensor_calibration_audit": updated["sensor_calibration_audit"],
            "options": opts,
        })
        updated["verdict"] = dec["verdict"]
        updated["deciding_rule"] = dec["deciding_rule"]
        updated["verdict_sha256"] = dec["verdict_sha256"]
        updated["findings"] = dec["findings"]
        updated["briefing"] = _persona_briefing(opts["persona"], updated["aoi"], cal, dec, updated["sensor_calibration_audit"])
        updated["what_if_applied"] = {"field": field, "value": value, "verdict_before": run_state["verdict"], "verdict_after": dec["verdict"]}
        return updated
    else:
        raise ValueError(f"Unsupported what_if field: {field!r}")

    req = {**run_state["aoi"], **opts}
    new_run = run_investigation(
        req,
        run_id=run_state["run_id"],
        raw_records_override=run_state.get("_raw_records"),
    )
    new_run["what_if_applied"] = {
        "field": field,
        "value": value,
        "verdict_before": run_state["verdict"],
        "verdict_after": new_run["verdict"],
    }
    return new_run

