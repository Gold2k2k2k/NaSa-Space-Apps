"""Regenerate the three reference receipts and clearly synthetic upload samples."""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents import run_investigation
from app.receipt import build_receipt
from app.case_studies import run_case_study


def upload_samples():
    fields = ["latitude", "longitude", "acq_date", "acq_time", "instrument", "satellite",
              "confidence", "brightness", "bright_t31", "bright_ti4", "bright_ti5",
              "scan", "track", "frp", "daynight", "type", "version", "fixture_version"]
    rows = []
    for index in range(12):
        viirs = index % 2 == 1
        rows.append({"latitude": 10 + index * .002, "longitude": 105 + index * .002,
            "acq_date": f"2026-08-{10 + index // 4:02d}",
            "acq_time": "" if index == 11 else "0655" if viirs else "0330",
            "instrument": "VIIRS" if viirs else "MODIS", "satellite": "N20" if viirs else "T",
            "confidence": "n" if viirs else 55,
            "brightness": "" if viirs else 335, "bright_t31": "" if viirs else 292,
            "bright_ti4": 340 if viirs else "", "bright_ti5": 290 if viirs else "",
            "scan": .4 if viirs else 1, "track": .4 if viirs else 1,
            "frp": "" if index == 10 else 0 if index == 9 else 20 + index,
            "daynight": "D", "type": index - 8 if index in (9, 10, 11) else 0,
            "version": "2.0NRT" if viirs else "6.1NRT", "fixture_version": "synthetic-upload-demo-v2"})
    def encode(values):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)
        return stream.getvalue()
    invalid = [{**rows[0], "acq_date": "2026-02-30"}, {**rows[1], "latitude": "invalid"}]
    return {"generated-firms-demo.csv": encode(rows),
            "generated-mixed-quality.csv": encode(rows[:3] + invalid)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale artifacts without writing")
    arguments = parser.parse_args()
    expected = {}
    for source in sorted((ROOT / "examples").glob("*.json")):
        request = json.loads(source.read_text(encoding="utf-8-sig"))
        state = run_investigation(request)
        expected[ROOT / "output_examples" / (source.stem + "_receipt.json")] = json.dumps(
            build_receipt(state), ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    for name, contents in upload_samples().items():
        expected[ROOT / "app" / "web" / "static" / "samples" / name] = contents
    case = run_case_study("central-highlands")
    case_outputs = {
        ROOT / "output_examples" / "central_highlands_receipt.json": build_receipt(case),
        ROOT / "output_examples" / "central_highlands_evidence.json": {k: v for k, v in case.items() if not k.startswith("_")},
        ROOT / "docs" / "judging" / "results" / "model-evaluation.json": case["sensor_calibration_audit"]["model_evaluation"],
        ROOT / "docs" / "judging" / "results" / "manager-brief.json": case["manager_brief"],
    }
    expected.update({path: json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n" for path, value in case_outputs.items()})
    stale = []
    for path, contents in expected.items():
        if arguments.check:
            if not path.is_file() or path.read_bytes() != contents.encode("utf-8"):
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents.encode("utf-8"))
            print(f"Generated {path.relative_to(ROOT)}")
    for path in stale:
        print(f"Stale reference: {path}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
