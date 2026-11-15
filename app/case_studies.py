"""Whitelisted, integrity-pinned NASA archive case; no network at runtime."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from app.datasets import parse_custom_aoi

DATA_DIR = Path(__file__).resolve().parent / "data"
CASE_ID = "central-highlands"
MANIFEST_SHA256 = "48037a8052e187a20a879788a749d77261136f2f8407c006018deaa45f341bf8"


def list_case_studies() -> list[dict]:
    return [{"case_id": CASE_ID, "name": "Central Highlands · actual NASA FIRMS",
             "description": "Vietnam study rectangle, MODIS 2001–2024 and S-NPP VIIRS 2012–2024. Records-only coverage.",
             "source_kind": "nasa_firms_archive", "bbox": [107.8, 12.5, 108.5, 13.1], "rows": 16258,
             "year_start": 2001, "year_end": 2024}]


def load_case_study(case_id: str) -> tuple[list[dict], dict]:
    if case_id != CASE_ID:
        raise ValueError("Unknown case study")
    manifest_bytes = (DATA_DIR / "central-highlands.manifest.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Case manifest integrity failure")
    manifest = json.loads(manifest_bytes)
    payload = (DATA_DIR / "central-highlands.csv").read_bytes()
    subset = manifest["subset"]
    if len(payload) != subset["bytes"] or hashlib.sha256(payload).hexdigest() != subset["sha256"]:
        raise ValueError("Case data integrity failure")
    records = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    if len(records) != subset["rows"]:
        raise ValueError("Case row integrity failure")
    aoi = parse_custom_aoi({"name": "Central Highlands study rectangle · Vietnam", "focus_year": 2024,
                            "geometry": {"type": "Polygon", "coordinates": [[[107.8, 12.5], [108.5, 12.5], [108.5, 13.1], [107.8, 13.1], [107.8, 12.5]]]}})
    aoi.update(country="Vietnam", biome="Mixed land cover; forest boundary not established",
               description=manifest["extent_note"], source_kind="nasa_firms_archive", case_id=CASE_ID,
               source_manifest=manifest, source_manifest_sha256=MANIFEST_SHA256,
               subset_sha256=subset["sha256"], calibration_policy=manifest["calibration_policy"],
               complete_periods=[], default_focus_year=2024,
               selection_notes=[manifest["extent_note"], manifest["coverage"]])
    return records, aoi
