"""Offline Cryptographic Verifier for FireTrace Verdict Receipts.

    python verify.py receipt.json

Exit codes:
  0  VALID      - every query hash, rules hash, and verdict seal re-derives cleanly
  1  TAMPERED   - one or more hashes or rule re-derivations do not match
  2  UNREADABLE - invalid or missing receipt file
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.canonical import sha256_of
from app.receipt import RECEIPT_VERSION, rules_sha256
from app.rules import decide


def check_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        problems.append(f"unexpected receipt_version {receipt.get('receipt_version')!r}")

    if receipt.get("rules_sha256") != rules_sha256():
        problems.append("rules_sha256 mismatch: app/rules.py differs from the receipt")

    for q in receipt.get("queries", []):
        if sha256_of(q.get("rows")) != q.get("sha256"):
            problems.append(f"query {q.get('query_id')} row hash tampered")

    # Cross-check Q6 focus values against calendar_summary.focus_comparison
    cal_summary = receipt.get("calendar_summary", {})
    fc = cal_summary.get("focus_comparison", {})
    q6 = next((q for q in receipt.get("queries", []) if q.get("query_id") == "Q6"), None)
    if q6 and q6.get("rows"):
        q6_row = q6["rows"][0]
        if round(float(q6_row.get("focus_value", -1)), 2) != round(float(fc.get("value", -2)), 2):
            problems.append("Q6 focus_value disagrees with calendar_summary.focus_comparison.value")

    evidence = {
        "aoi": receipt["aoi"],
        "calendar": {
            "mode": cal_summary["mode"],
            "year_start": cal_summary["year_start"],
            "year_end": cal_summary["year_end"],
            "baseline_window": cal_summary["baseline_window"],
            "baseline_year_count": cal_summary["baseline_year_count"],
            "focus_comparison": fc,
            "summary_records": cal_summary["summary_records"],
            "climatology": cal_summary["climatology"],
            "annual_series": cal_summary["annual_series"],
            "cells": [],
        },
        "sensor_calibration_audit": receipt["sensor_calibration_audit"],
        "options": receipt["options"],
    }
    recomputed = decide(evidence)
    if recomputed["verdict_sha256"] != receipt.get("verdict_sha256"):
        problems.append(
            f"verdict seal tampered: rules re-derive {recomputed['verdict']} "
            f"({recomputed['verdict_sha256'][:12]}...), receipt claims {receipt.get('verdict')} "
            f"({str(receipt.get('verdict_sha256'))[:12]}...)"
        )

    return {
        "status": "TAMPERED" if problems else "VALID",
        "problems": problems,
        "verdict": recomputed["verdict"],
        "seal": recomputed["verdict_sha256"],
        "queries_checked": len(receipt.get("queries", [])),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python verify.py <receipt.json>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        print(f"UNREADABLE: {err}")
        return 2
    try:
        res = check_receipt(receipt)
    except (KeyError, TypeError, ValueError) as err:
        print(f"UNREADABLE: missing or malformed receipt field ({err})")
        return 2

    if res["status"] == "VALID":
        print(f"VALID: {res['verdict']} re-derived offline from {res['queries_checked']} queries (seal {res['seal'][:16]}...)")
        return 0
    print(f"TAMPERED: {'; '.join(res['problems'])}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

