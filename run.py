"""Run the local demo server or analyze a preset, geometry, point or CSV."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.agents import PERSONAS, run_investigation
from app.datasets import AOIS, MAX_CSV_BYTES, parse_uploaded_csv
from app.receipt import build_receipt, package_zip
from app.case_studies import run_case_study


def _read_input(path, limit):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Input exceeds the {limit}-byte limit")
    return data.decode("utf-8-sig")


def main(argv: list[str]) -> int:
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="FireTrace: transparent offline fire-regime demonstration")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--aoi", choices=sorted(AOIS), help="Analyze a generated preset")
    selection.add_argument("--case-study", choices=["central-highlands"], help="Analyze the pinned actual NASA FIRMS case")
    selection.add_argument("--csv", help="Analyze uploaded FIRMS-shaped detections")
    selection.add_argument("--geojson", help="Generate a demo inside a GeoJSON file")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--radius-km", type=float, default=60)
    parser.add_argument("--name", help="Display name for a custom selection or upload")
    parser.add_argument("--year", type=int, help="Focus year (2000-2026)")
    parser.add_argument("--month", type=int, help="Focus month (1-12)")
    parser.add_argument("--year-start", type=int)
    parser.add_argument("--year-end", type=int)
    parser.add_argument("--mode", choices=["harmonized", "raw"], default="harmonized")
    parser.add_argument("--confidence-min", choices=["low", "nominal", "high"])
    parser.add_argument("--persona", choices=sorted(PERSONAS))
    parser.add_argument("--no-flare-guard", action="store_true", help="Include supplied non-vegetation types")
    parser.add_argument("--reference-time", help="Explicit ISO snapshot/pass reference with UTC offset")
    parser.add_argument("--output", help="Write public analysis JSON to this path")
    parser.add_argument("--receipt", help="Write the offline-verifiable receipt")
    parser.add_argument("--package", help="Write the complete audit ZIP")
    parser.add_argument("--port", type=int, default=os.environ.get("PORT", "8000"))
    args = parser.parse_args(argv)
    point = args.lat is not None or args.lon is not None
    selected = args.aoi or args.case_study or args.csv or args.geojson or point
    if point and (args.lat is None or args.lon is None):
        parser.error("--lat and --lon must be supplied together")
    if point and (args.aoi or args.case_study or args.csv or args.geojson):
        parser.error("Choose a point or one of --aoi, --csv, --geojson")
    if not selected:
        if any(value is not None for value in (args.year, args.month, args.year_start, args.year_end,
                                               args.output, args.receipt, args.package, args.reference_time, args.name)):
            parser.error("Analysis options require an AOI, CSV, GeoJSON, or point selection")
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        import uvicorn
        uvicorn.run("app.api:app", host="0.0.0.0", port=args.port)
        return 0

    request = {"mode": args.mode, "flare_guard": not args.no_flare_guard}
    if args.confidence_min is not None:
        request["confidence_min"] = args.confidence_min
    if args.persona is not None:
        request["persona"] = args.persona
    for argument, key in (("year", "focus_year"), ("month", "focus_month"),
                          ("year_start", "year_start"), ("year_end", "year_end"),
                          ("reference_time", "reference_time"), ("name", "name")):
        value = getattr(args, argument)
        if value is not None:
            request[key] = value
    records = source_aoi = None
    try:
        if args.case_study:
            output = run_case_study(args.case_study, request)
        elif args.aoi:
            request["aoi_id"] = args.aoi
        elif args.csv:
            records, source_aoi = parse_uploaded_csv(_read_input(args.csv, MAX_CSV_BYTES), name=args.name or Path(args.csv).name)
        elif args.geojson:
            request["geojson"] = json.loads(_read_input(args.geojson, 256 * 1024))
            request["radius_km"] = args.radius_km
        else:
            request.update(lat=args.lat, lon=args.lon, radius_km=args.radius_km)
        if not args.case_study:
            output = run_investigation(request, raw_records_override=records, source_aoi=source_aoi)
        public = {key: value for key, value in output.items() if not key.startswith("_")}
        text = json.dumps(public, ensure_ascii=False, allow_nan=False, indent=2)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        if args.receipt:
            Path(args.receipt).write_text(json.dumps(build_receipt(output), ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        if args.package:
            Path(args.package).write_bytes(package_zip(output))
    except (OSError, ValueError, RecursionError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

