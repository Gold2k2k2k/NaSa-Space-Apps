"""Rebuild the pinned NASA subset. Network use requires --download explicitly."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
CASE_ID = "central-highlands"
BBOX = [107.8, 12.5, 108.5, 13.1]


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_case(cache_dir: Path, *, download: bool = False, check: bool = False) -> dict:
    manifest_path = DATA / f"{CASE_ID}.manifest.json"
    pinned = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    research = json.loads((cache_dir / "research-manifest.json").read_text(encoding="utf-8")) if not pinned else None
    sources = pinned["source_files"] if pinned else [
        {k: v for k, v in item.items() if k != "candidate_monthly_counts"} for item in research["files"]]
    expected = {(family, year) for family, start in [("modis", 2001), ("viirs-snpp", 2012)] for year in range(start, 2025)}
    if {(s["family"], s["year"]) for s in sources} != expected or len(sources) != 37:
        raise ValueError("Expected the pinned 37-file NASA snapshot")
    rows, fields, versions = [], set(), set()
    for source in sources:
        expected_url = f"https://firms.modaps.eosdis.nasa.gov/data/country/{source['family']}/{source['year']}/{source['filename']}"
        if source["url"] != expected_url or Path(source["filename"]).name != source["filename"]:
            raise ValueError("Unexpected source identity")
        path = cache_dir / source["filename"]
        if download:
            request = urllib.request.Request(source["url"], headers={"User-Agent": "FireTrace-reproducible-case/1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read(30_000_001)
            if digest(payload) != source["sha256"] or len(payload) != source["bytes"]:
                raise ValueError(f"NASA source changed: {source['filename']}; refusing to replace pinned snapshot")
            cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        payload = path.read_bytes()
        if len(payload) != source["bytes"] or digest(payload) != source["sha256"]:
            raise ValueError(f"Source integrity failure: {path.name}")
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        fields.update(reader.fieldnames)
        for row in reader:
            if BBOX[0] <= float(row["longitude"]) <= BBOX[2] and BBOX[1] <= float(row["latitude"]) <= BBOX[3]:
                rows.append(row)
                versions.add((row["instrument"], row.get("version", "")))
    fields = sorted(fields)
    rows = [{field: row.get(field, "") for field in fields} for row in rows]
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = buffer.getvalue().encode("utf-8")
    manifest = {
        "case_id": CASE_ID, "title": "Central Highlands thermal activity study", "country": "Vietnam",
        "bbox": BBOX, "extent_note": "Study rectangle; not an administrative, protected-area or forest boundary.",
        "source_kind": "nasa_firms_archive", "catalog_url": "https://firms.modaps.eosdis.nasa.gov/data/country/yearly_summary_files.txt",
        "catalog_sha256": pinned["catalog_sha256"] if pinned else research["catalog_sha256"],
        "source_files": sources, "versions": [list(item) for item in sorted(versions)],
        "transform": "Inclusive longitude/latitude rectangle clip; retain original values and union fields (absent fields empty); canonical JSON row sort; UTF-8 CSV with LF. No fabricated detections or completeness.",
        "coverage": "Detection records only. File availability does not establish complete observations. Missing months remain unknown.",
        "calibration_policy": {"name": "central-highlands-2013-2020-v1", "training_years": [2013, 2020], "evaluation_years": [2021, 2024]},
        "subset": {"filename": f"{CASE_ID}.csv", "sha256": digest(csv_bytes), "bytes": len(csv_bytes), "rows": len(rows),
                   "modis_rows": sum(r["instrument"] == "MODIS" for r in rows), "viirs_rows": sum(r["instrument"] == "VIIRS" for r in rows),
                   "date_min": min(r["acq_date"] for r in rows), "date_max": max(r["acq_date"] for r in rows), "fields": fields},
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if check:
        if manifest_path.read_bytes() != manifest_bytes or (DATA / f"{CASE_ID}.csv").read_bytes() != csv_bytes:
            raise ValueError("Bundled subset differs from deterministic rebuild")
    else:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / f"{CASE_ID}.csv").write_bytes(csv_bytes)
        manifest_path.write_bytes(manifest_bytes)
    return {"case_id": CASE_ID, "rows": len(rows), "sha256": digest(csv_bytes), "manifest_sha256": digest(manifest_bytes), "checked": check}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_case(args.cache_dir, download=args.download, check=args.check), indent=2))
