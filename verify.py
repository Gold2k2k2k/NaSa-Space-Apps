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
from app.evidence import expected_query_rows
from app.receipt import LEGACY_RECEIPT_VERSION, RECEIPT_VERSION, rules_sha256
from app.rules import decide
from app.rules import RULES_VERSION
from app import legacy_rules

MAX_RECEIPT_BYTES = 20 * 1024 * 1024


def check_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Check an unsigned receipt's structure, complete evidence, and decision."""
    if not isinstance(receipt, dict):
        raise ValueError("Receipt must be a JSON object")
    for field in ("aoi", "options", "calendar_summary", "sensor_calibration_audit"):
        if not isinstance(receipt.get(field), dict):
            raise ValueError(f"Receipt {field} must be an object")
    if not isinstance(receipt.get("queries"), list):
        raise ValueError("Receipt queries must be an array")
    # Reject non-JSON values and non-finite numbers anywhere, including ignored
    # extensions. In particular, Python's JSON decoder otherwise accepts NaN.
    sha256_of(receipt)
    version = receipt.get("receipt_version")
    if version not in (RECEIPT_VERSION, LEGACY_RECEIPT_VERSION):
        raise ValueError(f"Unsupported receipt version: {version!r}")
    problems: list[str] = []
    rules_version = receipt.get("rules_version")
    decision_function = decide
    expected_rules_hash = rules_sha256()
    if rules_version == legacy_rules.RULES_VERSION:
        decision_function = legacy_rules.decide
        expected_rules_hash = sha256_of(Path(legacy_rules.__file__).read_text(encoding="utf-8"))
    elif rules_version != RULES_VERSION:
        problems.append("unsupported or changed rules_version")
    if receipt.get("rules_sha256") != expected_rules_hash:
        problems.append("rules_sha256 mismatch: versioned rules source differs from the receipt")
    if version == RECEIPT_VERSION:
        payload = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        if sha256_of(payload) != receipt.get("receipt_sha256"):
            problems.append("receipt_sha256 mismatch: receipt contents changed")

    queries = {}
    for q in receipt["queries"]:
        if not isinstance(q, dict) or not isinstance(q.get("query_id"), str):
            raise ValueError("Each query must be an object with a query_id")
        rows = q.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Query {q['query_id']} rows must be objects in an array")
        if q["query_id"] in queries:
            problems.append(f"duplicate query {q['query_id']}")
        queries[q["query_id"]] = q
        if type(q.get("row_count")) is not int or q["row_count"] != len(rows):
            problems.append(f"query {q['query_id']} row_count does not match rows")
        if len(rows) != 1:
            problems.append(f"query {q['query_id']} requires exactly one evidence row")
        if sha256_of(q.get("rows")) != q.get("sha256"):
            problems.append(f"query {q.get('query_id')} row hash tampered")
    if set(queries) != {f"Q{i}" for i in range(9)}:
        problems.append("exactly the nine required queries Q0-Q8 must be present")
    if problems:
        return {"status": "TAMPERED", "problems": problems, "verdict": None,
                "seal": None, "queries_checked": len(queries)}

    cal_summary = receipt["calendar_summary"]
    fc = cal_summary["focus_comparison"]
    if not isinstance(fc, dict):
        raise ValueError("focus_comparison must be an object")
    if version == RECEIPT_VERSION:
        calendar = receipt["calendar"]
        inputs = receipt["input_summary"]
        if not isinstance(calendar, dict) or not isinstance(calendar.get("cells"), list):
            raise ValueError("v2 calendar must include its cells array")
        if not isinstance(inputs, dict):
            raise ValueError("v2 input_summary must be an object")
        for key in ("total_rows", "valid_rows", "invalid_rows", "modis_rows", "viirs_rows"):
            if type(inputs.get(key)) is not int or inputs[key] < 0:
                raise ValueError(f"input_summary.{key} must be a non-negative integer")
        if (inputs["modis_rows"] + inputs["viirs_rows"] != inputs["valid_rows"]
                or inputs["valid_rows"] + inputs["invalid_rows"] != inputs["total_rows"]):
            problems.append("input_summary sensor/validation counts are inconsistent")
        persistent_count = receipt["persistent_cells_count"]
        if type(persistent_count) is not int or persistent_count < 0:
            raise ValueError("persistent_cells_count must be a non-negative integer")
        for key, value in cal_summary.items():
            if key != "cells_sha256" and sha256_of(calendar.get(key)) != sha256_of(value):
                problems.append(f"calendar_summary.{key} disagrees with full calendar evidence")
        if sha256_of(calendar["cells"]) != cal_summary.get("cells_sha256"):
            problems.append("calendar cells_sha256 mismatch")
    else:
        # v1 did not carry full cells or independent source counts. Check every
        # available relationship, and identify that narrower scope in the result.
        calendar = {**cal_summary, "cells": []}
        inputs = {"modis_rows": queries["Q1"]["rows"][0]["raw_detections"],
                  "viirs_rows": queries["Q2"]["rows"][0]["raw_detections"]}
        persistent_count = queries["Q5"]["rows"][0]["persistent_cells_count"]

    expected = expected_query_rows(receipt["aoi"], calendar,
                                   receipt["sensor_calibration_audit"], inputs,
                                   persistent_count)
    for query_id, row in expected.items():
        if sha256_of(queries[query_id]["rows"]) != sha256_of([row]):
            problems.append(f"{query_id} disagrees with its receipt evidence")
    evidence = {
        "aoi": receipt["aoi"],
        "calendar": calendar,
        "sensor_calibration_audit": receipt["sensor_calibration_audit"],
        "options": receipt["options"],
    }
    recomputed = decision_function(evidence)
    for field in ("rules_version", "verdict", "deciding_rule", "findings", "verdict_sha256"):
        if sha256_of(recomputed[field]) != sha256_of(receipt.get(field)):
            problems.append(f"{field} disagrees with the re-derived decision")

    return {
        "status": "TAMPERED" if problems else "VALID",
        "problems": problems,
        "verdict": recomputed["verdict"],
        "seal": recomputed["verdict_sha256"],
        "queries_checked": len(receipt.get("queries", [])),
        "verification_scope": "full v2 evidence" if version == RECEIPT_VERSION else "legacy v1 limited evidence",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python verify.py <receipt.json>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        with path.open("rb") as stream:
            contents = stream.read(MAX_RECEIPT_BYTES + 1)
        if len(contents) > MAX_RECEIPT_BYTES:
            raise ValueError("Receipt exceeds the 20 MiB input limit")
        receipt = json.loads(contents.decode("utf-8-sig"))
    except (OSError, ValueError, RecursionError) as err:
        print(f"UNREADABLE: {err}")
        return 2
    try:
        res = check_receipt(receipt)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, RecursionError) as err:
        print(f"UNREADABLE: missing or malformed receipt field ({err})")
        return 2

    if res["status"] == "VALID":
        print(f"VALID: {res['verdict']} re-derived offline from {res['queries_checked']} queries (seal {res['seal'][:16]}...)")
        return 0
    print(f"TAMPERED: {'; '.join(res['problems'])}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

