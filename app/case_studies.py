"""Whitelisted, integrity-pinned NASA archive case; no network at runtime."""
from __future__ import annotations

import copy
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


_CASE_STUDY_CACHE: dict[tuple[str, str], tuple[list[dict], dict]] = {}


def load_case_study(case_id: str) -> tuple[list[dict], dict]:
    if case_id != CASE_ID:
        raise ValueError("Unknown case study")
    cache_key = (case_id, str(DATA_DIR))
    cached = _CASE_STUDY_CACHE.get(cache_key)
    if cached is not None:
        records, aoi = cached
        return [dict(r) for r in records], copy.deepcopy(aoi)
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
    from app.agents import _raw_record_sort_key
    records.sort(key=_raw_record_sort_key)
    aoi = parse_custom_aoi({"name": "Central Highlands study rectangle · Vietnam", "focus_year": 2024,
                            "geometry": {"type": "Polygon", "coordinates": [[[107.8, 12.5], [108.5, 12.5], [108.5, 13.1], [107.8, 13.1], [107.8, 12.5]]]}})
    aoi.update(country="Vietnam", biome="Mixed land cover; forest boundary not established",
               description=manifest["extent_note"], source_kind="nasa_firms_archive", case_id=CASE_ID,
               source_manifest=manifest, source_manifest_sha256=MANIFEST_SHA256,
               subset_sha256=subset["sha256"], calibration_policy=manifest["calibration_policy"],
               complete_periods=[], default_focus_year=2024, default_focus_month=2,
               selection_notes=[manifest["extent_note"], manifest["coverage"]])
    _CASE_STUDY_CACHE[cache_key] = (records, aoi)
    try:
        from app.observations import get_normalized_row_and_canon
        from app.evidence import summarize_inputs
        from app.agents import _get_raw_row_canon
        for r in records:
            get_normalized_row_and_canon(r)
            _get_raw_row_canon(r)
        summarize_inputs(records)
    except Exception:
        pass
    return [dict(r) for r in records], copy.deepcopy(aoi)


def run_case_study(case_id: str, options: dict | None = None) -> dict:
    """Run pinned records with analysis options and an optional snapshot reference."""
    from app.agents import run_investigation
    from app.models import AnalysisOptions
    records, aoi = load_case_study(case_id)
    options = {} if options is None else options.copy()
    if set(options) - (AnalysisOptions.model_fields.keys() | {"reference_time"}):
        raise ValueError("Case studies accept analysis options and reference_time only")
    request = {"year_start": 2001, "year_end": 2024, "focus_year": 2024,
               "focus_month": options.get("focus_month", aoi.get("default_focus_month", 2)),
               "confidence_min": "nominal", "persona": "land_manager",
               "mode": "harmonized", "flare_guard": True, **options}
    # A narrowed display without an explicit focus follows its final year.
    if "focus_year" not in options:
        request["focus_year"] = min(max(2024, request["year_start"]), request["year_end"])
    run = run_investigation(request, raw_records_override=records, source_aoi=aoi)
    if "focus_month" not in options:
        defined = [r for r in run["calendar"]["climatology"] if r["median"] is not None]
        month = max(defined, key=lambda r: r["median"])["month"] if defined else 1
        if month != request["focus_month"]:
            request["focus_month"] = month
            run = run_investigation(request, raw_records_override=records, source_aoi=aoi)
    return run


try:
    load_case_study(CASE_ID)
except Exception:
    pass

