"""Five-Agent Explainable Pipeline: Extractor -> Planner -> Investigator -> Evaluator -> Writer.

Each investigation emits a deterministic trace (JSONL-compatible events), executes
scientific refutation checks in the Evaluator, calls app/rules.py for the immutable
verdict, and computes live counterfactual What-If flips.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.calendar_engine import MONTH_NAMES, build_burning_calendar
from app.canonical import sha256_of
from app.datasets import generate_firms_records, parse_custom_aoi
from app.evidence import QUERY_TITLES, expected_query_rows, summarize_inputs
from app.harmonize import harmonize_records
from app.models import counterfactual_options, validate_options
from app.rules import decide
from app.run_state import (CALCULATION_VERSION, DEMO_REFERENCE, apply_calendar_scenario,
                           calculation_digest, content_run_id)
from app.canonical import canonical_json
from app.geo_passes import predict_passes

PERSONAS = {
    "responder": "Early Warning & Emergency Responder",
    "scientist": "Earth Observation Scientist",
    "land_manager": "Land & Ecosystem Manager",
    "firefighter": "Wildfire Operations & Dispatch",
}


def _now_iso() -> str:
    return DEMO_REFERENCE


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
        "timestamp": DEMO_REFERENCE,
        "timestamp_semantics": "snapshot_reference_not_execution_time",
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


def _fmt(value, pattern=".2f"):
    return format(value, pattern) if value is not None else "not available"


def _evaluate_refutations(harmonized, calendar, raw_calendar):
    """Report bounded diagnostic evidence without claiming external validation."""
    audit = harmonized["sensor_calibration_audit"]
    reduction = audit["bias_reduction_pct"]
    raw_jump = audit["raw_step_jump_2012_pct"]
    status = ("NOT_ASSESSED" if reduction is None else
              "MITIGATED" if reduction >= 70 else "WARN")
    return [
        {"id": "R1_SENSOR_SWITCH_ILLUSION", "title": "2012 / 2018 transition diagnostics",
         "hypothesis_tested": "Compare complete three-year windows before and after each transition.",
         "status": status,
         "evidence": f"2012 raw change {_fmt(raw_jump)}%; harmonized change {_fmt(audit['harmonized_step_diff_2012_pct'])}%; change reduction {_fmt(reduction)}%. This descriptive comparison cannot separate sensor and physical change. See both transition audits.",
         "raw_z_focus": raw_calendar["focus_comparison"]["z_robust"],
         "harmonized_z_focus": calendar["focus_comparison"]["z_robust"]},
        {"id": "R2_AFTERNOON_TRAIN_DOUBLE_COUNT", "title": "Cell occupancy and timestamp windows",
         "hypothesis_tested": "Avoid raising occupancy for repeated rows, subpixels, and coincident satellites.",
         "status": "MITIGATED" if audit["overpass_duplicates_removed"] else "PASS",
         "evidence": f"{audit['total_raw_detections']} selected rows form {len(harmonized['hotspots'])} cell windows. Sources are averaged within each family in anchored 60-minute windows; morning and afternoon passes remain separate. Missing times retain date-only source groups. This is a heuristic, not event ground truth."},
        {"id": "R3_OFF_NADIR_PIXEL_GROWTH", "title": "Target grid and footprint limitations",
         "hypothesis_tested": "Prevent raw subpixel density from being interpreted as burning extent.",
         "status": "LIMITATION",
         "evidence": "Occupancy uses a 1,000 m sinusoidal target grid, distinct from the native MODIS tile grid. Scan/track metadata are retained. No polygon footprint intersection, bow-tie correction, or burned-area estimate is claimed."},
        {"id": "R4_STATIC_INDUSTRIAL_FLARE_TRAP", "title": "Supplied source types and persistence flags",
         "hypothesis_tested": "Separate vegetation-type records from supplied volcanic, other static-land, and offshore source types.",
         "status": "FLAGGED" if audit["non_vegetation_share"] > .5 else "MITIGATED" if audit["non_vegetation_share"] else "PASS",
         "evidence": f"{audit['static_flare_detections']} rows have supplied non-vegetation types ({audit['non_vegetation_share']:.1%}). Guard enabled: {audit['exclude_static_flares']}. Persistence-only flags are retained without establishing an industrial cause or automatically excluding vegetation records."},
    ]


def _persona_briefing(persona, aoi, calendar, decision, audit):
    focus, records = calendar["focus_comparison"], calendar["summary_records"]
    p_key = persona if persona in PERSONAS else "responder"
    unit = "raw detections" if calendar["mode"] == "raw" else "HHE index"
    headline = (f"{decision['verdict'].replace('_', ' ')}: {focus['month_name']} {focus['year']} "
                f"{_fmt(focus['value'], '.1f')} {unit}; reference median {_fmt(focus['hist_median'], '.1f')}.")
    common = "Demonstration analysis; confirm source coverage and independent evidence before interpreting fire conditions."
    details = {
        "responder": [f"Focus coverage: {focus['coverage_status']}. Reference months: {calendar['baseline_year_count']}; complete reference months: {calendar['baseline_complete_year_count']}.", common],
        "scientist": [f"Bridge kappa={_fmt(audit['calibrated_kappa'], '.3f')} ({audit['calibration_basis']}); correlation R²={_fmt(audit['bridge_r2'], '.3f')}, agreement efficiency={_fmt(audit['bridge_efficiency'], '.3f')}.",
                      f"Complete-year Theil-Sen slope={_fmt(records['theil_sen_slope_per_decade'])}/decade; Z={_fmt(focus['z_robust'])}. Correlation is not validation."],
        "land_manager": [f"Supplied non-vegetation source share: {audit['non_vegetation_share']:.1%}. Thermal patterns alone cannot attribute agricultural burning or wildfire.",
                         f"Summed observed FRP: {_fmt(focus['frp_total_mw'], '.1f')} MW across observations; this is power sampled repeatedly, not energy or burned area."],
        "firefighter": [f"Night share among records with known day/night labels: {_fmt(focus['night_share'], '.2f')}. This does not establish crown fire, intensity, or continuous burning.",
                        "Pass schedules are approximate modeled opportunities. Use official observation products and local operational channels for decisions."],
    }
    return {"persona": p_key, "persona_label": PERSONAS[p_key], "headline": headline,
            "actions": details[p_key], "limitation": common}


def _compute_what_ifs(
    harmonized: dict[str, Any],
    aoi: dict[str, Any],
    options: dict[str, Any],
    base_decision: dict[str, Any],
    raw_records: list[dict[str, Any]],
    calendars: dict[str, dict[str, Any]],
    scenario: bool = False,
) -> dict[str, Any]:
    """Evaluate key counterfactual experiments so the user can test what flips the verdict."""
    mode = options.get("mode", "harmonized")
    alt_mode = "raw" if mode == "harmonized" else "harmonized"
    current_calendar = calendars[mode]
    alt_cal = calendars[alt_mode]
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
        if scenario and alt_cal_flare["focus_comparison"]["hist_median"] is not None:
            apply_calendar_scenario(alt_cal_flare)
        alt_flare_dec = decide({
            "aoi": aoi,
            "calendar": alt_cal_flare,
            "sensor_calibration_audit": alt_harm_flare["sensor_calibration_audit"],
            "options": {**options, "flare_guard": alt_flare_guard},
        })
    else:
        alt_flare_dec = base_decision

    # Counterfactual 3: normalize focus month to historical median
    med_cal = copy.deepcopy(current_calendar)
    median_available = all(med_cal["focus_comparison"][key] is not None for key in ("value", "hist_median"))
    if median_available and not scenario:
        apply_calendar_scenario(med_cal)
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
            "z_before": current_calendar["focus_comparison"]["z_robust"],
            "z_after": alt_cal["focus_comparison"]["z_robust"],
        },
        {
            "id": "toggle_flare_guard",
            "label": f"{'Enable' if alt_flare_guard else 'Disable'} supplied non-vegetation source guard",
            "field": "flare_guard",
            "value": alt_flare_guard,
            "verdict_before": base_decision["verdict"],
            "verdict_after": alt_flare_dec["verdict"],
            "flips_verdict": alt_flare_dec["verdict"] != base_decision["verdict"],
        },
        {
            "id": "reset_focus_to_median",
            "label": "Model focus metric at the historical median (observations unchanged)",
            "field": "focus_to_median",
            "value": True,
            "available": median_available,
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
    source_aoi: Optional[dict[str, Any]] = None,
    scenario: bool = False,
    lineage: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Execute the full 5-agent investigation and return the complete structured output."""
    aoi = copy.deepcopy(source_aoi) if source_aoi is not None else parse_custom_aoi(request)
    # Internal preset shock maps use integer years; snapshots are strict JSON.
    aoi = json.loads(json.dumps(aoi, allow_nan=False))
    options = validate_options(request, aoi)
    aoi["source_kind"] = aoi.get("source_kind", "uploaded_csv" if aoi.get("is_uploaded_csv") else "generated_demo" if raw_records_override is None else "provided_records")
    aoi["complete_periods"] = ([(y, m) for y in range(2000, 2027) for m in range(1, 13)
                              if (2000, 11) <= (y, m) <= (2026, 11)]
                              if aoi["source_kind"] == "generated_demo" else aoi.get("complete_periods", []))
    year_start, year_end = options["year_start"], options["year_end"]
    focus_year, focus_month = options["focus_year"], options["focus_month"]
    mode, flare_guard = options["mode"], options["flare_guard"]
    confidence_min, persona = options["confidence_min"], options["persona"]

    reference = request.get("reference_time", DEMO_REFERENCE)
    try:
        stamp = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("reference_time must include a UTC offset")
        reference = stamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("reference_time must be an ISO timestamp with a UTC offset") from error
    if not 2000 <= stamp.year <= 2100:
        raise ValueError("Modeled reference years must be between 2000 and 2100")
    if raw_records_override is not None and (not isinstance(raw_records_override, list) or (len(raw_records_override) > 25000 and aoi["source_kind"] != "generated_demo")):
        raise ValueError("Provided records must be an array of at most 25,000 rows")
    raw_records = copy.deepcopy(raw_records_override) if raw_records_override is not None else generate_firms_records(aoi, year_start=2000, year_end=2026)
    raw_records.sort(key=canonical_json)
    input_summary = summarize_inputs(raw_records)
    source_digest = sha256_of(sorted(raw_records, key=canonical_json))
    calculation = calculation_digest()
    derived_id = content_run_id(aoi, options, input_summary, source_digest, reference, scenario, lineage, calculation)
    if run_id is not None and run_id != derived_id:
        raise ValueError("run_id is content-derived and cannot be overridden")
    run_id = derived_id

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
    if scenario:
        apply_calendar_scenario(calendar_harm)
        apply_calendar_scenario(calendar_raw)
    active_calendar = calendar_raw if mode == "raw" else calendar_harm
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
    what_if = _compute_what_ifs(harmonized, aoi, options, decision, raw_records,
                                 {"harmonized": calendar_harm, "raw": calendar_raw}, scenario)
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
    for step_record in trace:
        step_record["timestamp"] = reference

    return {
        "run_id": run_id,
        "status": "success",
        "reference_time": reference,
        "passes": predict_passes(aoi["lat"], aoi["lon"], days=5, start_dt=stamp),
        "calculation_version": CALCULATION_VERSION,
        "calculation_sha256": calculation,
        "provenance": {"source_kind": aoi["source_kind"], "source_records_sha256": source_digest,
                       "fixture_version": "generated-demo-v2" if aoi["source_kind"] == "generated_demo" else None,
                       "coverage_claim": "simulated_complete_periods" if aoi["source_kind"] == "generated_demo" else "records_only",
                       "source_authentication": "not established"},
        "ingestion": copy.deepcopy(aoi.get("ingestion")),
        "lineage": copy.deepcopy(lineage),
        "counterfactual": copy.deepcopy(active_calendar.get("counterfactual")),
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
            "geometry": aoi["geometry"],
            "geojson": aoi["geometry"],
            "selection_model": aoi.get("selection_model", "preset_box"),
            "selection_notes": aoi.get("selection_notes", []),
            "source_kind": aoi["source_kind"],
            "complete_periods": aoi["complete_periods"],
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
        "_raw_records": raw_records,
        "_aoi_full": aoi,
        "_scenario": scenario,
        "_input_summary": input_summary,
        "_persistent_cells_count": len(harmonized["persistent_flare_cells"]),
    }


def apply_what_if(run_state: dict[str, Any], field: str, value: Any) -> dict[str, Any]:
    """Construct a new content-bound snapshot; the parent is never mutated."""
    options = counterfactual_options(run_state["options"], field, value)
    scenario = value if field == "focus_to_median" else run_state.get("_scenario", False)
    lineage = {"parent_run_id": run_state["run_id"], "field": field, "value": copy.deepcopy(value),
               "verdict_before": run_state["verdict"]}
    request = {**options, "reference_time": run_state["reference_time"]}
    updated = run_investigation(request, source_aoi=run_state["_aoi_full"],
                                raw_records_override=run_state["_raw_records"],
                                scenario=scenario, lineage=lineage)
    updated["what_if_applied"] = {**lineage, "verdict_after": updated["verdict"]}
    return updated
