"""Cryptographic Verdict Receipt Builder & Audit Package ZIP Archive."""
from __future__ import annotations

import io
import copy
import json
import zipfile
import hashlib
from pathlib import Path
from typing import Any

from app.canonical import sha256_of
from app.exports import (
    export_calendar_csv,
    export_calendar_ics,
    export_hotspots_csv,
    export_hotspots_geojson,
)

RECEIPT_VERSION = "firetrace-receipt-v2"
LEGACY_RECEIPT_VERSION = "firetrace-receipt-v1"
RULES_PATH = Path(__file__).resolve().parent / "rules.py"
DOCS_MANIFESTO = Path(__file__).resolve().parent.parent / "docs" / "MAPPING_MANIFESTO.md"


def rules_sha256() -> str:
    return sha256_of(RULES_PATH.read_text(encoding="utf-8"))


def build_receipt(run_data: dict[str, Any]) -> dict[str, Any]:
    """Construct a self-contained offline-verifiable receipt from a finished run."""
    queries = []
    for q in run_data["queries"]:
        queries.append({
            "query_id": q["query_id"],
            "title": q["title"],
            "row_count": len(q["rows"]),
            "rows": q["rows"],
            "sha256": sha256_of(q["rows"]),
        })

    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "run_id": run_data["run_id"],
        "rules_version": run_data["rules_version"],
        "rules_sha256": rules_sha256(),
        "aoi": run_data["aoi"],
        "options": run_data["options"],
        "calendar_summary": {
            "mode": run_data["calendar"]["mode"],
            "year_start": run_data["calendar"]["year_start"],
            "year_end": run_data["calendar"]["year_end"],
            "baseline_window": run_data["calendar"]["baseline_window"],
            "baseline_year_count": run_data["calendar"]["baseline_year_count"],
            "focus_comparison": run_data["calendar"]["focus_comparison"],
            "summary_records": run_data["calendar"]["summary_records"],
            "climatology": run_data["calendar"]["climatology"],
            "annual_series": run_data["calendar"]["annual_series"],
            "cells_sha256": sha256_of(run_data["calendar"]["cells"]),
        },
        "sensor_calibration_audit": run_data["sensor_calibration_audit"],
        "queries": queries,
        "verdict": run_data["verdict"],
        "deciding_rule": run_data["deciding_rule"],
        "findings": run_data["findings"],
        "verdict_sha256": run_data["verdict_sha256"],
        "calendar": run_data["calendar"],
        "input_summary": run_data["_input_summary"],
        "persistent_cells_count": run_data["_persistent_cells_count"],
        "verification_scope": "Unsigned reproducibility and internal evidence consistency; not source authentication.",
    }
    receipt = copy.deepcopy(receipt)
    for key in ("reference_time", "calculation_version", "calculation_sha256", "provenance",
                "ingestion", "lineage", "counterfactual", "passes"):
        if key in run_data:
            receipt[key] = copy.deepcopy(run_data[key])
    receipt["receipt_sha256"] = sha256_of(receipt)
    return receipt


def package_zip(run_data: dict[str, Any]) -> bytes:
    """Create an in-memory ZIP audit bundle containing all evidence and downloadable exports."""
    receipt = build_receipt(run_data)
    buf = io.BytesIO()
    public_evidence = {k: v for k, v in run_data.items() if not k.startswith("_")}
    members = {
        "evidence.json": json.dumps(public_evidence, ensure_ascii=False, indent=2),
        "receipt.json": json.dumps(receipt, ensure_ascii=False, indent=2),
        "hotspots_harmonized.csv": export_hotspots_csv(run_data),
        "burning_calendar.csv": export_calendar_csv(run_data),
        "hotspots.geojson": json.dumps(export_hotspots_geojson(run_data), ensure_ascii=False, indent=2),
        "fire_watch.ics": export_calendar_ics(run_data),
        "source_records.json": json.dumps(run_data["_raw_records"], ensure_ascii=False, indent=2),
        "analysis_inputs.json": json.dumps({"aoi": run_data["_aoi_full"], "options": run_data["options"],
            "reference_time": run_data["reference_time"], "scenario": run_data.get("_scenario", False),
            "lineage": run_data.get("lineage"), "expected_run_id": run_data["run_id"]}, ensure_ascii=False, indent=2),
        "README-AUDIT.txt": (
            "FireTrace unsigned demonstration evidence\n\n"
            "Verify without third-party dependencies: python -S -B verify.py receipt.json\n"
            "Hashes prove internal consistency, not NASA origin, authorship or scientific truth.\n"
            "source_records.json contains retained accepted input rows, not original CSV bytes.\n"
            "analysis_inputs.json preserves full AOI/options/reference/scenario/lineage.\n"
            "The bundled app sources permit replay with the project's declared runtime dependencies.\n"
            "HHE is an index; FRP is sampled power, not energy. Passes are approximate models.\n"
            "manifest.sha256.json records raw-file SHA-256 values for every other member.\n"
        ),
    }
    project_root = Path(__file__).resolve().parent.parent
    members["verify.py"] = (project_root / "verify.py").read_text(encoding="utf-8-sig")
    for source in sorted((project_root / "app").glob("*.py")):
        members[f"app/{source.name}"] = source.read_text(encoding="utf-8-sig")
    for name in ("SCIENCE.md", "INPUTS.md", "RECEIPTS.md"):
        members[f"docs/{name}"] = (project_root / "docs" / name).read_text(encoding="utf-8-sig")
    if DOCS_MANIFESTO.is_file():
        members["MAPPING_MANIFESTO.md"] = DOCS_MANIFESTO.read_text(encoding="utf-8")
    members["manifest.sha256.json"] = json.dumps({name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in sorted(members.items())}, indent=2)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, contents in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, contents.encode("utf-8"),
                        compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()

