"""FireTrace HTTP API: Harmonized MODIS & VIIRS Burning Activity Calendar & Verifier."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import pickle
import re
import tempfile
from typing import Any, Literal, Optional
import zlib

from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

from app.agents import PERSONAS, apply_what_if, run_investigation
from app.datasets import AOIS, MAX_CSV_BYTES, list_aois, parse_uploaded_csv
from app.http_limits import BodyLimits
from app.models import AnalysisRequest, WhatIfBody
from app.models import AnalysisOptions
from app.case_studies import list_case_studies, run_case_study
from app.run_store import RunStore, SnapshotConflict, SnapshotLimit
from app.exports import (
    export_calendar_csv,
    export_calendar_ics,
    export_hotspots_csv,
    export_hotspots_geojson,
)
from app.geo_passes import predict_passes
from app.receipt import build_receipt, package_zip
from app.rules import RULES_VERSION
from app.schema_mapping import get_manifesto

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
RUNS = RunStore()

COLOR_RAMPS = [
    {"id": "viridis", "name": "Viridis (Sequential)"},
    {"id": "cividis", "name": "Cividis (Sequential)"},
    {"id": "ylorrd", "name": "YlOrRd (Thermal Fire Sequential)"},
    {"id": "diverging", "name": "Diverging Anomaly (-Z / +Z)"},
]

BENCH_CASES: list[dict[str, Any]] = [
    {
        "id": "TC-01",
        "name": 'Generated Amazon anomaly (Sep 2026)',
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 9, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": 'Scripted activity exceeds its generated same-month reference; not observed drought evidence.',
    },
    {
        "id": "TC-02",
        "name": 'Generated Amazon near-reference month (May 2026)',
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 5, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": 'Scripted May metric stays near the generated reference.',
    },
    {
        "id": "TC-03",
        "name": 'Generated Mekong harmonized elevation (Mar 2026)',
        "request": {"aoi_id": "AOI-MEK", "focus_year": 2026, "focus_month": 3, "mode": "harmonized"},
        "expected_verdict": "ELEVATED_WATCH",
        "why": 'Pooled bridge reduces the scripted transition discontinuity; fixture remains elevated.',
    },
    {
        "id": "TC-04",
        "name": 'Generated Mekong raw-count trap (Mar 2026)',
        "request": {"aoi_id": "AOI-MEK", "focus_year": 2026, "focus_month": 3, "mode": "raw"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": 'Raw sensor counts produce a higher demo anomaly than the occupancy index.',
    },
    {
        "id": "TC-05",
        "name": 'Generated Sierra nighttime anomaly (Aug 2026)',
        "request": {"aoi_id": "AOI-CAL", "focus_year": 2026, "focus_month": 8, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": 'Generated high metric and nighttime detections; no crown-fire or continuous-burning inference.',
    },
    {
        "id": "TC-06",
        "name": 'Generated NSW historical peak (Dec 2019)',
        "request": {"aoi_id": "AOI-NSW", "focus_year": 2019, "focus_month": 12, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": 'Scripted December 2019 peak; not independent reconstruction of a historical event.',
    },
    {
        "id": "TC-07",
        "name": 'Generated NSW near-reference month (Jan 2026)',
        "request": {"aoi_id": "AOI-NSW", "focus_year": 2026, "focus_month": 1, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": 'Scripted January activity remains near the generated reference.',
    },
    {
        "id": "TC-08",
        "name": 'Generated Miombo seasonal regime (Jul 2026)',
        "request": {"aoi_id": "AOI-MIO", "focus_year": 2026, "focus_month": 7, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": 'Generated seasonal activity remains near its reference; no ecological-cause attribution.',
    },
    {
        "id": "TC-09",
        "name": 'Generated Basra static-land trap (Guard ON)',
        "request": {"aoi_id": "AOI-FLR", "focus_year": 2026, "focus_month": 8, "flare_guard": True},
        "expected_verdict": "UNVERIFIABLE",
        "why": 'Supplied non-vegetation types dominate the fixture; type 2 is not proof of gas flaring.',
    },
    {
        "id": "TC-10",
        "name": 'Generated Basra guard experiment (Guard OFF)',
        "request": {"aoi_id": "AOI-FLR", "focus_year": 2026, "focus_month": 8, "flare_guard": False},
        "expected_verdict": "NOMINAL_REGIME",
        "why": 'Including supplied non-vegetation detections changes the demonstration label.',
    },
    {
        "id": "TC-11",
        "name": 'Generated custom polygon (Congo setting)',
        "request": {
            "name": "Custom Congo Polygon",
            "geojson": {
                "type": "Polygon",
                "coordinates": [[[21.0, -2.0], [22.0, -2.0], [22.0, -1.0], [21.0, -1.0], [21.0, -2.0]]],
            },
            "focus_year": 2026,
            "focus_month": 7,
        },
        "expected_verdict": "NOMINAL_REGIME",
        "why": 'The complete custom polygon is used for generated data and retained through analysis.',
    },
    {
        "id": "TC-12",
        "name": 'Generated high-confidence sensitivity (AMZ)',
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 9, "confidence_min": "high"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": 'The scripted anomaly persists at the high-confidence filter; not ground-truth confirmation.',
    },
]

app = FastAPI(title="FireTrace", version="1.0.0")
app.add_middleware(BodyLimits)


@app.exception_handler(RequestValidationError)
async def request_validation_error(request, error):
    # Echo locations and reasons, not arbitrary non-finite/deep submitted values.
    detail = [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
              for item in error.errors()]
    return JSONResponse({"detail": detail}, status_code=422)


_RUN_ID_RE = re.compile(r"^ft-[0-9a-f]{24}$")


def _serverless_cache_dir() -> Optional[Path]:
    if os.environ.get("VERCEL") == "1" or os.environ.get("FIRETRACE_SERVERLESS") == "1":
        target = Path(tempfile.gettempdir()) / "firetrace-runs"
        target.mkdir(parents=True, exist_ok=True)
        return target
    return None


def _store_run(run_data: dict[str, Any]) -> None:
    try:
        RUNS.put(run_data)
    except SnapshotConflict as error:
        raise HTTPException(409, str(error)) from error
    except SnapshotLimit as error:
        raise HTTPException(413, str(error)) from error
    cache_dir = _serverless_cache_dir()
    run_id = run_data.get("run_id", "")
    if cache_dir is not None and _RUN_ID_RE.match(run_id):
        try:
            blob = zlib.compress(pickle.dumps(run_data, protocol=pickle.HIGHEST_PROTOCOL), level=1)
            (cache_dir / f"{run_id}.bin").write_bytes(blob)
        except OSError:
            pass


def _public_run(run_data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in run_data.items() if not k.startswith("_")}


def _get_run_or_404(run_id: str) -> dict[str, Any]:
    found = RUNS.get(run_id)
    if found is not None:
        return found
    cache_dir = _serverless_cache_dir()
    if cache_dir is not None and _RUN_ID_RE.match(run_id):
        cache_file = cache_dir / f"{run_id}.bin"
        if cache_file.is_file():
            try:
                restored = pickle.loads(zlib.decompress(cache_file.read_bytes()))
                RUNS.put(restored)
                return RUNS.get(run_id) or restored
            except Exception:
                pass
    raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found in memory")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "firetrace", "rules_version": RULES_VERSION}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/ui/setup")
def ui_setup() -> dict[str, Any]:
    return {
        "service": "FireTrace",
        "rules_version": RULES_VERSION,
        "default_aoi": "AOI-AMZ",
        "aois": list_aois(),
        "case_studies": list_case_studies(),
        "color_ramps": COLOR_RAMPS,
        "personas": [{"id": k, "label": v} for k, v in PERSONAS.items()],
        "year_min": 2000,
        "year_max": 2026,
        "bench_cases": [{"id": b["id"], "name": b["name"], "expected_verdict": b["expected_verdict"], "why": b["why"]} for b in BENCH_CASES],
    }


@app.get("/api/schema-mapping")
def schema_mapping() -> dict[str, Any]:
    return get_manifesto()


@app.get("/api/methods/{name}", include_in_schema=False)
def method_notes(name: Literal["science", "inputs", "receipts", "exports"]) -> FileResponse:
    return FileResponse(STATIC_DIR.parents[2] / "docs" / (name.upper() + ".md"), media_type="text/plain")


@app.post("/api/analyze")
@app.post("/run")
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    try:
        run_data = run_investigation(request.model_dump(exclude_unset=True))
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    _store_run(run_data)
    return _public_run(run_data)


@app.get("/api/case-studies")
def case_studies() -> list[dict]:
    return list_case_studies()


@app.post("/api/case-studies/{case_id}/analyze")
def analyze_case_study(case_id: str, request: AnalysisRequest) -> dict[str, Any]:
    if case_id not in {item["case_id"] for item in list_case_studies()}:
        raise HTTPException(404, "Unknown case study")
    options = request.model_dump(exclude_unset=True)
    if set(options) - AnalysisOptions.model_fields.keys():
        raise HTTPException(422, "Case studies accept analysis options only")
    try:
        run_data = run_case_study(case_id, options)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    _store_run(run_data)
    return _public_run(run_data)


@app.post("/api/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    focus_year: Optional[int] = Query(None, ge=2000, le=2026),
    focus_month: Optional[int] = Query(None, ge=1, le=12),
    mode: Literal["harmonized", "raw"] = Query("harmonized"),
    flare_guard: bool = Query(True),
    persona: Literal["responder", "scientist", "land_manager", "firefighter"] = Query("responder"),
    confidence_min: Literal["low", "nominal", "high"] = Query("low"),
) -> dict[str, Any]:
    raw_bytes = await file.read(MAX_CSV_BYTES + 1)
    await file.close()
    if len(raw_bytes) > MAX_CSV_BYTES:
        raise HTTPException(413, "Uploaded CSV exceeds the 10 MiB limit")
    try:
        csv_text = raw_bytes.decode("utf-8-sig")
        records, aoi = await run_in_threadpool(parse_uploaded_csv, csv_text, name=file.filename)
    except (UnicodeDecodeError, ValueError) as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    req = {
        "name": aoi["name"],
        "focus_year": focus_year if focus_year is not None else aoi["default_focus_year"],
        "focus_month": focus_month if focus_month is not None else aoi["default_focus_month"],
        "mode": mode,
        "flare_guard": flare_guard,
        "persona": persona,
        "confidence_min": confidence_min,
    }
    try:
        run_data = await run_in_threadpool(run_investigation, req, raw_records_override=records, source_aoi=aoi)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    await run_in_threadpool(_store_run, run_data)
    return _public_run(run_data)


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    return _public_run(_get_run_or_404(run_id))


@app.post("/runs/{run_id}/what_if")
def what_if(run_id: str, body: WhatIfBody) -> dict[str, Any]:
    existing = _get_run_or_404(run_id)
    try:
        updated = apply_what_if(existing, body.field, body.value)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    _store_run(updated)
    return _public_run(updated)


@app.get("/runs/{run_id}/receipt")
def get_receipt(run_id: str) -> dict[str, Any]:
    return build_receipt(_get_run_or_404(run_id))


@app.get("/runs/{run_id}/package")
def get_package(run_id: str) -> Response:
    run_data = _get_run_or_404(run_id)
    blob = package_zip(run_data)
    return Response(
        blob,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="firetrace-{run_id}.zip"'},
    )


@app.get("/api/export/{run_id}/hotspots.csv")
def download_hotspots_csv(run_id: str) -> Response:
    run_data = _get_run_or_404(run_id)
    csv_text = export_hotspots_csv(run_data)
    return Response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="firetrace-{run_id}-hotspots.csv"'},
    )


@app.get("/api/export/{run_id}/calendar.csv")
def download_calendar_csv(run_id: str) -> Response:
    run_data = _get_run_or_404(run_id)
    csv_text = export_calendar_csv(run_data)
    return Response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="firetrace-{run_id}-calendar.csv"'},
    )


@app.get("/api/export/{run_id}/hotspots.geojson")
def download_hotspots_geojson(run_id: str) -> JSONResponse:
    run_data = _get_run_or_404(run_id)
    return JSONResponse(
        export_hotspots_geojson(run_data),
        headers={"Content-Disposition": f'attachment; filename="firetrace-{run_id}-hotspots.geojson"'},
    )


@app.get("/api/export/{run_id}/calendar.ics")
def download_calendar_ics(run_id: str) -> Response:
    run_data = _get_run_or_404(run_id)
    ics_text = export_calendar_ics(run_data)
    return Response(
        ics_text,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="firetrace-{run_id}-watch.ics"'},
    )


@app.get("/api/passes")
def satellite_passes(
    run_id: Optional[str] = Query(None),
    aoi_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None, ge=-90, le=90, allow_inf_nan=False),
    lon: Optional[float] = Query(None, ge=-180, le=180, allow_inf_nan=False),
    days: int = Query(5, ge=1, le=16),
    reference_time: Optional[datetime] = Query(None),
) -> dict[str, Any]:
    if run_id is not None:
        if any(value is not None for value in (aoi_id, lat, lon, reference_time)) or days != 5:
            raise HTTPException(422, "A stored run supplies its own five-day schedule and reference")
        snapshot = _get_run_or_404(run_id)
        return {"run_id": run_id, "aoi_id": snapshot["aoi"]["aoi_id"], **snapshot["passes"]}
    if aoi_id is not None:
        if aoi_id not in AOIS:
            raise HTTPException(422, "Unknown preset AOI")
        if lat is not None or lon is not None:
            raise HTTPException(422, "Choose a preset or coordinates")
        lat_v, lon_v = AOIS[aoi_id]["lat"], AOIS[aoi_id]["lon"]
    elif lat is not None and lon is not None:
        lat_v, lon_v = lat, lon
    else:
        raise HTTPException(status_code=422, detail="Provide aoi_id or lat and lon")
    try:
        return {"aoi_id": aoi_id, **predict_passes(lat_v, lon_v, days=days, start_dt=reference_time)}
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err


@app.post("/api/bench")
def run_bench() -> dict[str, Any]:
    results = []
    passed = 0
    for case in BENCH_CASES:
        out = run_investigation(case["request"])
        ok = out["verdict"] == case["expected_verdict"]
        if ok:
            passed += 1
        results.append({
            "id": case["id"],
            "name": case["name"],
            "expected_verdict": case["expected_verdict"],
            "actual_verdict": out["verdict"],
            "pass": ok,
            "z_robust": out["calendar"]["focus_comparison"]["z_robust"],
            "bias_reduction_pct": out["sensor_calibration_audit"]["bias_reduction_pct"],
            "verdict_sha256": out["verdict_sha256"][:16],
            "why": case["why"],
        })
    return {
        "passed": passed,
        "total": len(BENCH_CASES),
        "all_pass": passed == len(BENCH_CASES),
        "results": results,
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

