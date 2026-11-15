"""Explicit temporal policies and descriptive assessment of the applied model."""
from __future__ import annotations

from app.stats import calibration_agreement


def resolve_calibration_policy(aoi: dict) -> dict:
    policy = aoi.get("calibration_policy")
    if policy is None:
        return {"name": "pooled-demo-2012-2024", "training_years": [2012, 2024],
                "training_start_month": 2, "evaluation_years": None, "held_out": False}
    expected = {"name": "central-highlands-2013-2020-v1", "training_years": [2013, 2020], "evaluation_years": [2021, 2024]}
    if policy != expected:
        raise ValueError("Unsupported calibration policy")
    return {**expected, "training_start_month": 1, "held_out": True}


def calibration_period(year: int, month: int, policy: dict) -> str:
    start, end = policy["training_years"]
    if (start, policy["training_start_month"]) <= (year, month) <= (end, 12):
        return "training"
    evaluation = policy["evaluation_years"]
    if evaluation and evaluation[0] <= year <= evaluation[1]:
        return "held_out"
    return "outside"


def build_model_evaluation(events: list[dict], monthly_modis: dict, monthly_viirs: dict,
                           policy: dict, model: dict) -> dict:
    def assess(period):
        months = sorted(m for m in monthly_modis.keys() | monthly_viirs.keys()
                        if calibration_period(*m, policy) == period)
        pairs = [m for m in months if monthly_modis.get(m, 0) > 0 and monthly_viirs.get(m, 0) > 0]
        windows = [e for e in events if calibration_period(e["year"], e["month"], policy) == period]
        included = [e for e in windows if e["include_in_calendar"]]
        powers = [e for e in included if e["modis_frp_mw"] is not None and e["modis_frp_mw"] > 0
                  and e["viirs_frp_mw"] is not None and e["viirs_frp_mw"] > 0]
        return {"occupancy": {"pairs": len(pairs), "unpaired_recorded_months": len(months) - len(pairs),
                              "agreement": calibration_agreement([monthly_modis[m] for m in pairs], [model["kappa"] * monthly_viirs[m] for m in pairs])},
                "power": {"pairs": len(powers), "unpaired_or_nonpositive_windows": len(included) - len(powers),
                          "agreement": calibration_agreement([e["modis_frp_mw"] for e in powers], [model["frp_ratio"] * e["viirs_frp_mw"] for e in powers])},
                "excluded_source_type_windows": len(windows) - len(included)}
    return {"policy": policy, "model_id": model["model_id"], "applied_kappa": model["kappa"],
            "applied_frp_ratio": model["frp_ratio"], "training": assess("training"), "held_out": assess("held_out"),
            "status": "descriptive_held_out_sensor_agreement" if policy["held_out"] else "in_sample_only_no_held_out_period",
            "limitations": ["Agreement between sensors is not independent ground truth or burned-area validation.",
                            "Only positive paired observations enter agreement; omitted and missing observations are not zeros.",
                            "Occupancy is a weighted cell index. FRP is instantaneous MW, not energy or burned area."]}
