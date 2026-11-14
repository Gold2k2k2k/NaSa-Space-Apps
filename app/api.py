"""FireTrace HTTP API: Harmonized MODIS & VIIRS Burning Activity Calendar & Verifier."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

from app.agents import PERSONAS, apply_what_if, run_investigation
from app.datasets import AOIS, MAX_CSV_BYTES, list_aois, parse_uploaded_csv
from app.http_limits import BodyLimits
from app.models import AnalysisRequest, WhatIfBody
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
    {"id": "viridis", "name": "Viridis (Perceptual, Colorblind-Safe)"},
    {"id": "cividis", "name": "Cividis (Deuteranopia / Protanopia Safe)"},
    {"id": "ylorrd", "name": "YlOrRd (Thermal Fire Sequential)"},
    {"id": "diverging", "name": "Okabe-Ito Diverging Anomaly (-Z / +Z)"},
]

BENCH_CASES: list[dict[str, Any]] = [
    {
        "id": "TC-01",
        "name": "Amazon Arc Drought Surge (Sep 2026)",
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 9, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": "Extreme dry-season burning exceeds 2001–2020 P95 with Z_robust >= 2.0.",
    },
    {
        "id": "TC-02",
        "name": "Amazon Baseline Month Counterfactual (May 2026)",
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 5, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": "Early dry-season May 2026 remains within normal historical bounds.",
    },
    {
        "id": "TC-03",
        "name": "Mekong Crop Burning — Harmonized (Mar 2026)",
        "request": {"aoi_id": "AOI-MEK", "focus_year": 2026, "focus_month": 3, "mode": "harmonized"},
        "expected_verdict": "ELEVATED_WATCH",
        "why": "Harmonization removes 2012 VIIRS small-fire cliff, isolating true moderate elevation.",
    },
    {
        "id": "TC-04",
        "name": "Mekong Trap — Unharmonized Raw Counts (Mar 2026)",
        "request": {"aoi_id": "AOI-MEK", "focus_year": 2026, "focus_month": 3, "mode": "raw"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": "Without harmonization, 2012+ VIIRS 375 m counts falsely inflate Z_robust past P95.",
    },
    {
        "id": "TC-05",
        "name": "Sierra Nevada Nighttime Crown Fire (Aug 2026)",
        "request": {"aoi_id": "AOI-CAL", "focus_year": 2026, "focus_month": 8, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": "Severe nighttime FRP persistence + extreme HHE surge trigger Rule 2.",
    },
    {
        "id": "TC-06",
        "name": "NSW Black Summer Historical Peak (Dec 2019)",
        "request": {"aoi_id": "AOI-NSW", "focus_year": 2019, "focus_month": 12, "mode": "harmonized"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": "Historical calendar correctly flags December 2019 Black Summer catastrophe.",
    },
    {
        "id": "TC-07",
        "name": "NSW Blue Mountains Current Season (Jan 2026)",
        "request": {"aoi_id": "AOI-NSW", "focus_year": 2026, "focus_month": 1, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": "Southern Hemisphere summer Jan 2026 tracks near historical median.",
    },
    {
        "id": "TC-08",
        "name": "Miombo Ecological Savanna Regime (Jul 2026)",
        "request": {"aoi_id": "AOI-MIO", "focus_year": 2026, "focus_month": 7, "mode": "harmonized"},
        "expected_verdict": "NOMINAL_REGIME",
        "why": "Periodic ecological savanna fire season stays within historical IQR.",
    },
    {
        "id": "TC-09",
        "name": "Basra Industrial Gas Flare Trap (Guard ON)",
        "request": {"aoi_id": "AOI-FLR", "focus_year": 2026, "focus_month": 8, "flare_guard": True},
        "expected_verdict": "UNVERIFIABLE",
        "why": ">75% persistent type=2 gas flares mask vegetation fire inference (Rule 1).",
    },
    {
        "id": "TC-10",
        "name": "Basra Trap Counterfactual (Guard OFF)",
        "request": {"aoi_id": "AOI-FLR", "focus_year": 2026, "focus_month": 8, "flare_guard": False},
        "expected_verdict": "NOMINAL_REGIME",
        "why": "Disabling static-flare filtering hides the industrial contamination.",
    },
    {
        "id": "TC-11",
        "name": "Custom Drawn Polygon AOI (Congo Basin)",
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
        "why": "Arbitrary GeoJSON polygon runs the identical pipeline cleanly.",
    },
    {
        "id": "TC-12",
        "name": "High-Confidence Filter Sensitivity (AOI-AMZ)",
        "request": {"aoi_id": "AOI-AMZ", "focus_year": 2026, "focus_month": 9, "confidence_min": "high"},
        "expected_verdict": "CRITICAL_ANOMALY",
        "why": "Restricting to high-confidence detections still confirms Sep 2026 anomaly.",
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


def _store_run(run_data: dict[str, Any]) -> None:
    try:
        RUNS.put(run_data)
    except SnapshotConflict as error:
        raise HTTPException(409, str(error)) from error
    except SnapshotLimit as error:
        raise HTTPException(413, str(error)) from error


def _public_run(run_data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in run_data.items() if not k.startswith("_")}


def _get_run_or_404(run_id: str) -> dict[str, Any]:
    found = RUNS.get(run_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found in memory")
    return found


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
        "color_ramps": COLOR_RAMPS,
        "personas": [{"id": k, "label": v} for k, v in PERSONAS.items()],
        "year_min": 2000,
        "year_max": 2026,
        "bench_cases": [{"id": b["id"], "name": b["name"], "expected_verdict": b["expected_verdict"], "why": b["why"]} for b in BENCH_CASES],
    }


@app.get("/api/schema-mapping")
def schema_mapping() -> dict[str, Any]:
    return get_manifesto()


@app.post("/api/analyze")
@app.post("/run")
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    try:
        run_data = run_investigation(request.model_dump(exclude_unset=True))
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
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
    aoi_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    days: int = Query(5, ge=1, le=16),
) -> dict[str, Any]:
    if aoi_id and aoi_id in AOIS:
        lat_v, lon_v = AOIS[aoi_id]["lat"], AOIS[aoi_id]["lon"]
    elif lat is not None and lon is not None:
        lat_v, lon_v = lat, lon
    else:
        raise HTTPException(status_code=422, detail="Provide aoi_id or lat and lon")
    try:
        return {"aoi_id": aoi_id, **predict_passes(lat_v, lon_v, days=days)}
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

