"""Plain-language review facts derived from the same immutable snapshot."""
from __future__ import annotations


def build_manager_brief(run: dict) -> dict:
    calendar, aoi = run["calendar"], run["aoi"]
    focus = calendar["focus_comparison"]
    model = run["sensor_calibration_audit"]["calibration_model"]
    reference = [{"month": row["month"], "month_name": row["month_name"], "median": row["median"],
                  "samples": row["baseline_year_count"], "complete_samples": row["baseline_complete_year_count"]}
                 for row in calendar["climatology"] if row["median"] is not None]
    reference.sort(key=lambda row: (-row["median"], row["month"]))
    return {
        "run_id": run["run_id"],
        "question": "Which recorded seasonal periods deserve closer review before planning land or forest management?",
        "extent": {"name": aoi["name"], "bbox": aoi["bbox"], "area_km2": aoi["area_km2"],
                   "boundary_note": "Analysis extent only; not an administrative, protected-area or verified forest boundary."},
        "period": {"display": f"{calendar['year_start']}–{calendar['year_end']}", "focus": f"{focus['month_name']} {focus['year']}",
                   "reference": calendar["baseline_window"]},
        "source": {"kind": run["provenance"]["source_kind"], "case_id": run["provenance"].get("case_id"),
                   "subset_sha256": run["provenance"].get("subset_sha256"),
                   "manifest_sha256": run["provenance"].get("source_manifest_sha256"),
                   "retained_rows": run["_input_summary"]["total_rows"],
                   "origin_note": "Pinned NASA archive bytes with retrievable URLs and hashes; unsigned provenance." if run.get("source_manifest") else "Generated or user-provided inputs; source authentication not established."},
        "descriptive_periods": reference[:3],
        "comparison": {"status": run["verdict"], "metric": "raw retained detections" if calendar["mode"] == "raw" else "weighted occupancy index (HHE)",
                       "value": focus["value"], "historical_median": focus["hist_median"], "coverage": focus["coverage_status"],
                       "reference_status": "recorded_samples" if focus["hist_median"] is not None else "unavailable",
                       "model_id": model["model_id"], "training_years": model["policy"]["training_years"],
                       "evaluation_years": model["policy"]["evaluation_years"], "hypothetical": bool(run.get("counterfactual"))},
        "limitations": ["Unknown observation coverage prevents a verified hazard conclusion; missing months are not zero fire activity.",
                        "Recorded thermal patterns and FIRMS source types do not establish fire cause, forest loss, burned area or future risk.",
                        "The 2001–2020 reference describes available same-month samples, not a verified complete observational baseline.",
                        "Held-out sensor agreement assesses this model's consistency, not independent ground truth.",
                        "Satellite passes are approximate models; this historical study is not a live warning service."],
        "next_review_action": "Review these periods with local incident logs, land-cover boundaries and observation-coverage evidence; retain this run's receipt and audit ZIP for that review.",
    }
