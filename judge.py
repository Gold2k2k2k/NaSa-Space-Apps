"""One-Command Judge Verification Suite for FireTrace.

    python judge.py

Runs 7 generated-demo integration checks offline, writes logs/judge/report.md,
and prints PASS/FAIL. These checks do not establish real-world scientific accuracy.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

from app.agents import apply_what_if, run_investigation
from app.exports import (
    export_calendar_csv,
    export_calendar_ics,
    export_hotspots_csv,
    export_hotspots_geojson,
)
from app.receipt import build_receipt, package_zip
from verify import check_receipt

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "logs" / "judge"


def check_seal_determinism() -> tuple[bool, str]:
    r1 = run_investigation({"aoi_id": "AOI-AMZ"})
    r2 = run_investigation({"aoi_id": "AOI-AMZ"})
    ok = (
        r1["verdict"] == "CRITICAL_ANOMALY"
        and r1["run_id"] == r2["run_id"]
        and r1["verdict_sha256"] == r2["verdict_sha256"]
        and build_receipt(r1) == build_receipt(r2)
        and package_zip(r1) == package_zip(r2)
    )
    return ok, f"AOI-AMZ run twice -> {r1['verdict']}, identical seal {r1['verdict_sha256'][:16]}..."


def check_step_jump_removal() -> tuple[bool, str]:
    r = run_investigation({"aoi_id": "AOI-MEK"})
    audit = r["sensor_calibration_audit"]
    ok = (
        audit["raw_step_jump_2012_pct"] > 100.0
        and audit["bias_reduction_pct"] > 0.0
        and audit["calibration_valid"]
        and audit["bridge_rmse"] >= 0.0
        and audit["bridge_efficiency"] is not None
        and {row["transition_year"] for row in audit["transition_audits"]} == {2012, 2018}
    )
    return ok, (
        f"AOI-MEK 2012 jump {audit['raw_step_jump_2012_pct']:+.1f}% -> "
        f"{audit['harmonized_step_diff_2012_pct']:+.1f}% ({audit['bias_reduction_pct']:.1f}% bias reduction, "
        f"R²={audit['bridge_r2']:.3f})"
    )


def check_overpass_deduplication() -> tuple[bool, str]:
    r = run_investigation({"aoi_id": "AOI-AMZ"})
    audit = r["sensor_calibration_audit"]
    ok = audit["overpass_duplicates_removed"] > 500 and audit["total_harmonized_events"] < audit["total_raw_detections"]
    return ok, (
        f"Collapsed {audit['total_raw_detections']:,} raw detections into {audit['total_harmonized_events']:,} "
        f"1 km cell-window events ({audit['overpass_duplicates_removed']:,} row-to-window reduction; not verified same-fire duplicates)"
    )


def check_flare_trap() -> tuple[bool, str]:
    guarded = run_investigation({"aoi_id": "AOI-FLR", "flare_guard": True})
    unguarded = apply_what_if(guarded, "flare_guard", False)
    ok = guarded["verdict"] == "UNVERIFIABLE" and unguarded["verdict"] == "NOMINAL_REGIME"
    return ok, (
        f"Generated AOI-FLR ({guarded['sensor_calibration_audit']['non_vegetation_share']:.1%} supplied non-vegetation types): "
        f"guard ON -> {guarded['verdict']}; guard OFF -> {unguarded['verdict']}"
    )


def check_receipt_and_tamper() -> tuple[bool, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_out = run_investigation({"aoi_id": "AOI-AMZ"})
    receipt = build_receipt(run_out)
    real_path = OUT_DIR / "receipt.json"
    forged_path = OUT_DIR / "receipt_forged.json"
    real_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    forged = copy.deepcopy(receipt)
    forged["calendar_summary"]["focus_comparison"]["value"] = 0.5
    forged_path.write_text(json.dumps(forged, indent=2), encoding="utf-8")

    p_real = subprocess.run([sys.executable, str(ROOT / "verify.py"), str(real_path)], capture_output=True, text=True)
    p_forg = subprocess.run([sys.executable, str(ROOT / "verify.py"), str(forged_path)], capture_output=True, text=True)
    ok = p_real.returncode == 0 and p_forg.returncode == 1 and "TAMPERED" in (p_forg.stdout + p_forg.stderr)
    return ok, f"verify.py real=exit {p_real.returncode}, forged=exit {p_forg.returncode} ({p_forg.stdout.strip()})"


def check_what_if_mode_flip() -> tuple[bool, str]:
    harm = run_investigation({"aoi_id": "AOI-MEK", "mode": "harmonized"})
    original = copy.deepcopy(harm)
    raw = apply_what_if(harm, "mode", "raw")
    median = apply_what_if(harm, "focus_to_median", True)
    ok = (harm["verdict"] == "ELEVATED_WATCH" and raw["verdict"] == "CRITICAL_ANOMALY"
          and harm == original and raw["run_id"] != harm["run_id"]
          and median["_raw_records"] == harm["_raw_records"]
          and median["calendar"]["focus_comparison"]["z_robust"] == 0
          and check_receipt(build_receipt(median))["status"] == "VALID")
    return ok, f"AOI-MEK Harmonized -> {harm['verdict']} (Z={harm['calendar']['focus_comparison']['z_robust']:+.2f}); Raw -> {raw['verdict']} (Z={raw['calendar']['focus_comparison']['z_robust']:+.2f})"


def check_exports() -> tuple[bool, str]:
    r = run_investigation({"aoi_id": "AOI-CAL"})
    h_csv = export_hotspots_csv(r)
    c_csv = export_calendar_csv(r)
    gj = export_hotspots_geojson(r)
    ics = export_calendar_ics(r)
    ok = (
        len(list(csv.DictReader(io.StringIO(h_csv)))) == len(r["_hotspots_all"])
        and len(list(csv.DictReader(io.StringIO(c_csv)))) == len(r["calendar"]["cells"])
        and gj.get("type") == "FeatureCollection"
        and len(gj.get("features", [])) == len(r["_hotspots_all"]) + 1
        and gj["features"][0]["geometry"] == r["aoi"]["geometry"]
        and "BEGIN:VCALENDAR" in ics
        and ics.count("BEGIN:VEVENT") == len(r["passes"]["passes"]) + len(r["calendar"]["summary_records"]["peak_months"])
    )
    return ok, (
        f"Hotspots CSV ({len(h_csv.splitlines())} lines), Calendar CSV ({len(c_csv.splitlines())} lines), "
        f"GeoJSON ({len(gj['features'])} features), ICS ({ics.count('BEGIN:VEVENT')} events)"
    )


CHECKS = [
    ("1. Deterministic Verdict Seal", check_seal_determinism),
    ("2. Generated Sensor-Transition Diagnostics", check_step_jump_removal),
    ("3. Cell-Window Occupancy Aggregation", check_overpass_deduplication),
    ("4. Supplied Non-Vegetation Guard", check_flare_trap),
    ("5. Offline Receipt & Tamper Detection", check_receipt_and_tamper),
    ("6. Immutable Mode and Median Experiments", check_what_if_mode_flip),
    ("7. CSV / GeoJSON / iCalendar Exports", check_exports),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# FireTrace generated-demo verification\n",
             "Fixture integration checks; not external scientific validation.\n"]
    all_ok = True
    for label, fn in CHECKS:
        ok, detail = fn()
        all_ok &= ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}: {detail}")
        lines.append(f"- **{status}** {label}: {detail}")

    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

