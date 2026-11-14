"""Cryptographic Verdict Receipt Builder & Audit Package ZIP Archive."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from app.canonical import sha256_of
from app.exports import (
    export_calendar_csv,
    export_calendar_ics,
    export_hotspots_csv,
    export_hotspots_geojson,
)

RECEIPT_VERSION = "firetrace-receipt-v1"
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

    return {
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
    }


def package_zip(run_data: dict[str, Any]) -> bytes:
    """Create an in-memory ZIP audit bundle containing all evidence and downloadable exports."""
    receipt = build_receipt(run_data)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        public_evidence = {k: v for k, v in run_data.items() if not k.startswith("_")}
        zf.writestr("evidence.json", json.dumps(public_evidence, ensure_ascii=False, indent=2))
        zf.writestr("receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2))
        zf.writestr("hotspots_harmonized.csv", export_hotspots_csv(run_data))
        zf.writestr("burning_calendar.csv", export_calendar_csv(run_data))
        zf.writestr("hotspots.geojson", json.dumps(export_hotspots_geojson(run_data), ensure_ascii=False, indent=2))
        zf.writestr("fire_watch.ics", export_calendar_ics(run_data))
        if DOCS_MANIFESTO.is_file():
            zf.writestr("MAPPING_MANIFESTO.md", DOCS_MANIFESTO.read_text(encoding="utf-8"))
    return buf.getvalue()

