# FireTrace

A transparent NASA Space Apps team demonstration for comparing MODIS and VIIRS
thermal detections through a burning-activity calendar. Python 3.11, FastAPI and
zero-build HTML/CSS/JavaScript; all dashboard assets are local.

**Presets and custom-region data are generated fixtures.** Upload a FIRMS CSV to
explore supplied observations. Hotspot-only uploads do not establish complete
coverage, fire causes or burned area. HHE is a demo occupancy index; summed FRP
is observed power in MW, not energy. Satellite opportunities are approximate
models without orbital ephemerides. Verdicts are demonstration labels.

**An actual NASA FIRMS case is bundled:** 16,258 records for a declared Central
Highlands study rectangle, Vietnam (2001–2024). Choose **Explore NASA FIRMS case**
for the guided manager review, fixed 2013–2020 calibration and 2021–2024 assessment.
Unknown coverage remains **UNVERIFIABLE**. The power comparison has poor held-out
agreement; see the [judging evidence and limits](docs/judging/evidence.md).
[Judging packet](docs/judging/README.md) · [Data/source credits](SOURCES.md) ·
[AI disclosure](AI-DISCLOSURE.md) · [Apache-2.0 license](LICENSE).

[Methods](docs/SCIENCE.md) · [Inputs](docs/INPUTS.md) · [Exports](docs/EXPORTS.md) ·
[Receipts](docs/RECEIPTS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Schema reference](docs/MAPPING_MANIFESTO.md) · [Judge walkthrough](docs/SUBMISSION.md) ·
[Design](DESIGN.md) · [Interactive design preview](design-preview.html)

## Start locally

Install Python 3.11. In Windows PowerShell, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Open [localhost:8000](http://localhost:8000). `PORT` (or `--port`) changes the port.
No API key or automatic network ingestion is implemented. The server binds all
interfaces for local demos; it has no authentication, persistent storage or
multi-user isolation. Run it on a trusted machine/network.

On macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r
requirements.txt`, then `.venv/bin/python run.py`. Dependency installation needs
network access or a populated package cache; analysis runs offline afterward.
Docker configuration is supplied, but a container build requires separate
verification on a Docker-enabled machine.

## Explore the five views

- **Calendar:** six generated regimes, full monthly and 36-dekad summaries,
  complete-year trends, explicit missing coverage, keyboard cell selection,
  four color ramps and four audience lenses. Draw, paste GeoJSON, enter a
  point/radius rectangle, or upload detections. Geometry changes generate demo
  data; changing analysis options preserves the current supplied source.
- **Bridge:** raw versus harmonized sensor series, pooled calibration assumptions,
  per-era agreement and 2012/2018 transition diagnostics. Correlation is separate
  from agreement; neither is external validation.
- **Audit:** Q0–Q8 evidence, deterministic rule decision, immutable experiments,
  median metric scenario, receipt inspection and all six downloads.
- **Schemas:** three source groups and four logical evidence views, generated from
  the same declarations as the API.
- **Bench:** twelve qualitative generated trap cases. Passing them demonstrates
  software behavior on fixtures, not prediction accuracy on real events.

Default generated regimes: AMZ/CAL `CRITICAL_ANOMALY`, MEK `ELEVATED_WATCH`,
NSW/MIO `NOMINAL_REGIME`, FLR `UNVERIFIABLE`. Their geographic names are fixture
settings, not claims about observed historical events. Quantities are calculated
at runtime rather than advertised as fixed real-world performance.

Sample uploads: [invented combined FIRMS CSV](app/web/static/samples/generated-firms-demo.csv),
[mixed-quality CSV](app/web/static/samples/generated-mixed-quality.csv),
[provenance](app/web/static/samples/README.md).

## Reproduce without the browser

The commands below assume the environment's Python is activated, or substitute
its full executable path. CLI errors exit 2 with a controlled message.

```powershell
python run.py --aoi AOI-MEK --year 2026 --month 3 --output logs/mekong.json --receipt logs/receipt.json --package logs/audit.zip
python verify.py logs/receipt.json
python run.py --csv app/web/static/samples/generated-firms-demo.csv --output logs/upload.json
python run.py --case-study central-highlands --output logs/case.json --receipt logs/case-receipt.json --package logs/case-audit.zip
python run.py --lat 10 --lon 106 --radius-km 25 --year 2026 --month 7 --mode raw --output logs/custom.json
python run.py --help
```

`--geojson FILE`, confidence/persona/guard, selected years and an explicit
`--reference-time` are also supported. Snapshot references default to
`2026-11-14T00:00:00Z`; standalone pass requests default to current UTC.
The three [example JSON files](examples/) are request bodies for `POST
/api/analyze`, not a separate CLI input format. Their corresponding current
receipts are in [output_examples](output_examples/); the generation check below
replays those requests and compares the saved receipts.

Receipts are **unsigned internal consistency records**. The verifier re-derives
rules `.3`, query relationships and decision fields; hashes do not authenticate
NASA observations. Exit 0 means `VALID`, 1 `TAMPERED`, 2 `UNREADABLE`. Extracting an
audit ZIP and running `python -S -B verify.py receipt.json` needs only Python's
standard library. V1 receipts have a documented narrower verification scope.

## Verify the implementation

Install development dependencies and either Chrome or Playwright Chromium:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pip check
python -m unittest discover -s tests -v
python smoke_test.py
python judge.py
python scripts/build_design.py --check
python scripts/build_schema_docs.py --check
python scripts/generate_examples.py --check
python scripts/package_submission.py --output logs/firetrace-submission.zip
python verify.py output_examples/01_amazon_critical_receipt.json
```

The browser suite launches an actual local HTTP server, uses installed Chrome
when available and falls back to bundled Chromium. It covers all five views at
375/1440 px, keyboard controls, actual contrast, workflows, failures, races,
uploads and downloads. Browser installation is a one-time network step.
`judge.py` writes seven reproducible demo checks to `logs/judge/report.md`.
Tests use small independent numerical examples as well as fixtures. A passed
suite is not scientific ground-truth or assistive-technology certification.
Regenerate intentionally changed artifacts with the corresponding script without
`--check`. [Visual audit](docs/verification/visual-audit.md) records rendered QA.

## HTTP interface

Interactive typed contracts are at `/docs` after starting the server.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health`, `/ui/setup` | Health and dashboard configuration |
| POST | `/api/analyze` (alias `/run`) | New validated analysis |
| POST | `/api/upload-csv` | Multipart `file`; filename supplies label; accepted/rejected diagnostics |
| GET | `/runs/{run_id}` | Immutable public snapshot |
| POST | `/runs/{run_id}/what_if` | `{field, value}` experiment; returns a new snapshot |
| GET | `/runs/{run_id}/receipt`, `/runs/{run_id}/package` | Receipt JSON and full audit ZIP |
| GET | `/api/export/{run_id}/hotspots.csv`, `/api/export/{run_id}/calendar.csv` | Complete event/month exports |
| GET | `/api/export/{run_id}/hotspots.geojson`, `/api/export/{run_id}/calendar.ics` | Full geometry/events and modeled windows |
| GET | `/api/passes` | Stored `run_id` schedule, or `lat`, `lon`, `days` and optional `reference_time` |
| GET | `/api/schema-mapping` | Source and target declarations |
| GET | `/api/methods/{name}` | `science`, `inputs`, `receipts`, `exports` method notes |
| POST | `/api/bench` | Twelve generated regression cases |

JSON bodies are bounded to 256 KiB; CSVs to 10 MiB/25,000 rows; normalized geometry
to 2,000 positions. Invalid input returns 422, missing/evicted runs 404, capacity
413 and content-ID collisions 409. The copied, locked LRU cache holds up to 16
runs or 64 MiB. Save the audit ZIP before eviction/restart; this prototype has no
persistent run database.

Core algorithms are original project code. NASA/NOAA product documentation and
other primary references are cited in the methods. Bundled font licenses remain
alongside the assets. See [project context](PROJECT-CONTEXT.md) for the agreed
scope and completion criteria.
