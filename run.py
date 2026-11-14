"""FireTrace CLI & Web Server Entry Point.

    python run.py                         # starts HTTP API + web UI on 0.0.0.0:$PORT (default 8000)
    python run.py --aoi AOI-AMZ           # runs one investigation, prints JSON to stdout
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from app.agents import run_investigation


def main(argv: list[str]) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="FireTrace: Harmonized MODIS & VIIRS Burning Calendar")
    parser.add_argument("--aoi", help="Run a single preset AOI (e.g. AOI-AMZ) and print JSON output")
    parser.add_argument("--year", type=int, help="Focus year (2000-2026)")
    parser.add_argument("--month", type=int, help="Focus month (1-12)")
    parser.add_argument("--mode", choices=["harmonized", "raw"], default="harmonized")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args(argv)

    if args.aoi:
        req = {"aoi_id": args.aoi, "mode": args.mode}
        if args.year:
            req["focus_year"] = args.year
        if args.month:
            req["focus_month"] = args.month
        out = run_investigation(req)
        public = {k: v for k, v in out.items() if not k.startswith("_")}
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return 0

    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

