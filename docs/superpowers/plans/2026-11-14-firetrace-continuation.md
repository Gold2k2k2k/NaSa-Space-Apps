# FireTrace Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all R1–R4 upgrades in the approved FireTrace continuation design.

**Architecture:** Preserve the FastAPI application and five zero-build web views.
Introduce shared canonical, geometry, and validation contracts before repairing
science and workflow state. Keep receipts, exports, and UI descriptions bound to
the same immutable analysis snapshot.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, HTML/CSS/JavaScript/SVG, unittest,
and Playwright with an installed Chrome/Edge browser.

**Spec:** [Approved continuation design](../specs/2026-11-14-firetrace-continuation-design.md)

## Global Constraints

- Preserve Python 3.11/FastAPI and zero-build HTML/CSS/JS/SVG.
- Preserve Burning Calendar, Sensor Bridge, Evaluator & Receipt, Schema Manifesto,
  and Trap Bench.
- Use original core logic. Do not copy existing projects' core implementation.
- Clearly label generated presets and approximate satellite estimates; accept
  real FIRMS CSV uploads; restrict claims to reproducible evidence.
- Prioritize scientific meaning and provenance, then reliability/accessibility,
  then visual polish.
- Support 375px and 1440px layouts, keyboard access, contrast, and reduced motion.
- Verify survey findings before marking them defects. Complete the full approved
  scope; no narrow green suite establishes completion.

## Review Focus

1. Missing or malformed receipt evidence, including altered displayed findings,
   must never verify as valid (Task 2).
2. Polygon holes, multiple features, poles, and antimeridian selections must retain
   their geometry or fail explicitly (Task 3).
3. Short, shuffled, malformed, and oversized CSV uploads must preserve data identity
   and must never manufacture observed-zero months (Tasks 3–5).
4. Consecutive counterfactuals and rapid UI selections must preserve the source
   geometry/data and show the latest state (Tasks 5 and 7).
5. Reference-time changes must be explicit, with reproducible fixed-run exports
   and honestly labeled standalone upcoming estimates (Task 6).

## Task 1: Reproducible runtime

**Files:** `requirements.txt`, `requirements-dev.txt`, `README.md`, `.env.example`,
`Dockerfile`; test environment `.venv/` (ignored).

**Interfaces:** Existing `python run.py`, `python smoke_test.py`,
`python judge.py`, and `python -m unittest discover -s tests -v` remain valid.

- [x] Reproduce current import failure and verify declared imports/dependencies.
- [x] Create a project virtual environment, declare missing multipart support,
  install a compatible complete runtime, and record tested versions.
- [x] Run the existing suites through that interpreter and record actual baseline
  failures; document the clean setup commands with the delivered dependencies.

## Task 2: Receipt integrity and deterministic packaging

**Files:** `verify.py`, `app/receipt.py`, `app/rules.py`,
`tests/test_receipt_integrity.py`.

**Interfaces:** `build_receipt(run_data: dict) -> dict`,
`check_receipt(receipt: dict) -> dict`, and `package_zip(run_data: dict) -> bytes`
remain the public seams. Receipt revisions are explicitly versioned.

- [x] Add failing tests: changing `verdict`, `deciding_rule`, `rules_version`, or
  findings must return `TAMPERED`; removing/duplicating required queries must
  fail; malformed CLI input must exit 2, never traceback.
- [x] Run `python -m unittest discover -s tests -p test_receipt_integrity.py -v`
  and confirm the specific failures against current code.
- [x] Bind full required evidence and decision fields, re-derive all rule context,
  and make archive serialization deterministic. Preserve/document v1 verification
  where feasible and generate a new version when the contract changes.
- [x] Add and run tests for every query/evidence relationship, JSON round-trip,
  fixed-run byte equality, and tampered CLI exit 1. Complete counterfactual
  generation and receipt validity together in Task 5, which owns that state.

## Task 3: Canonical geometry and input contracts

**Files:** `app/canonical.py`, new `app/geometry.py`, new `app/models.py`,
`app/datasets.py`, `app/schema_mapping.py`, `tests/test_inputs_geometry.py`.

**Interfaces:** `stable_id(prefix: str, payload: Any, length: int = 16) -> str`;
`parse_custom_aoi(spec: dict) -> dict` retains geometry and adds canonical source
metadata; `parse_uploaded_csv(csv_text: str, name: str | None = None) -> tuple`
keeps its existing return shape while returning ingestion/coverage metadata.

- [x] Add failing tests for month 0/13, nonfinite coordinates, reversed/outside year
  windows, boolean/string enum mistakes, invalid calendar dates, valid numeric
  zeroes, sensor aliases, empty/oversized CSVs, and stable content identity.
- [x] Add failing geometry tests for Point/Polygon/MultiPolygon/FeatureCollection,
  holes, self-intersection, empty/degenerate rings, excessive vertices, poles,
  antimeridian, and lossless round-tripping.
- [x] Implement shared strict validation and canonical geometry operations; bound
  input work and report rejected-row reasons without silent truncation.
- [x] Run `python -m unittest discover -s tests -p test_inputs_geometry.py -v`.
  Assert equivalent canonical inputs share identity, changed geometry/data does
  not, and invalid inputs produce controlled validation errors.

## Task 4: Defined science and coverage semantics

**Files:** `app/harmonize.py`, `app/calendar_engine.py`, `app/rules.py`,
`app/datasets.py`, `app/schema_mapping.py`, `tests/test_science_contracts.py`.

**Interfaces:** `harmonize_records(...) -> dict` and
`build_burning_calendar(...) -> dict` retain existing public outputs and add
explicit source/coverage, overlap agreement, percentile, robust trend, and season
summaries. `decide(evidence: dict) -> dict` remains deterministic.

- [x] Write independent small-fixture tests for sensor/time deduplication,
  row-order invariance, per-era calibration, thermal-source categories, missing
  coverage versus zero, and per-month baseline sufficiency.
- [x] Write failing rule tests for January context, Z-boundaries, actual pre-peak
  onset, missing focus observations, and short uploaded archives.
- [x] Define and implement the planned 2012/2018 diagnostics, RMSE/agreement,
  percentile, OLS/Theil–Sen trends, and onset/peak/cessation/duration; test known
  numeric examples and insufficient-data results independently.
- [x] Correct impossible fixture dates, misleading units, and unsupported
  operational claims; rerun six presets and twelve trap cases, documenting any
  changed expected results caused by legitimate scientific corrections.
- [x] Run `python -m unittest discover -s tests -p test_science_contracts.py -v`.

## Task 5: Immutable analysis and complete HTTP/CLI workflows

**Files:** `app/agents.py`, `app/api.py`, `run.py`, new `app/run_store.py`,
`tests/test_analysis_workflows.py`, `tests/test_http_boundaries.py`.

**Interfaces:** `run_investigation(request: dict, *, run_id=None,
raw_records_override=None) -> dict`; `apply_what_if(run_state: dict, field: str,
value: Any) -> dict`; bounded thread-safe run store with immutable snapshots.

- [x] Write failing tests for polygon/CSV preservation through every toggle,
  median-counterfactual receipt validity, distinct upload/state IDs, same-input
  cross-process equality, and wrong combined-CSV sensor query counts.
- [x] Repair state construction around canonical inputs and rebuild all derived
  evidence together. Preserve source records and return new content-bound states.
- [x] Write actual HTTP boundary tests: malformed JSON/query/what-if values return
  422, upload limits reject safely, run snapshots survive unrelated requests,
  exports match state, and expected not-found behavior is 404.
- [x] Exercise concurrent cache reads/writes and expanded CLI inputs. Run both
  targeted suites plus the existing complete API workflow.

## Task 6: Satellite references and all exports

**Files:** `app/geo_passes.py`, `app/exports.py`, `app/receipt.py`, `app/api.py`,
`examples/`, `output_examples/`, `tests/test_exports_passes.py`.

**Interfaces:** `predict_passes(lat, lon, *, days=5, start_dt=None) -> dict`;
all existing export functions consume the same immutable analysis snapshot.

- [x] Add failing reference-time, date-rollover, coordinate, declared-window,
  geometric-boundary, and deterministic archive tests.
- [x] Implement explicit snapshot references, documented approximate geometry,
  model labels, and preserved data lineage in CSV/GeoJSON/ICS/JSON/ZIP outputs.
- [x] Test units, geometry, escaping, ZIP member contents, fixed-run byte equality,
  valid receipts, and every download against the actual API. Regenerate examples.

## Task 7: Tokenized, accessible five-view application

**Files:** `app/web/static/index.html`, `app/web/static/app.css`,
`app/web/static/app.js`, focused `app/web/static/js/` modules as needed,
`design-tokens.json`, `DESIGN.md`, `design-preview.html`,
`tests/test_design_tokens.py`, `tests/test_browser_showcase.py`.

**Interfaces:** Preserve existing view routes and core workflows. Design tokens
are the shared JSON/CSS source of semantic color, typography, spacing, radii,
elevation, motion, and breakpoint decisions.

- [ ] Capture existing rendered baselines and failures at 375px and 1440px; record
  keyboard gaps and actual contrast failures without treating mocks as HTTP tests.
- [ ] Generate synchronized tokens, rationale, and dependency-free interactive
  preview with restrained teal/ember glass navigation/cards and crisp data wells.
- [ ] Repair responsive minimum sizing, primary navigation, keyboard heatmap,
  accessible charts/legends, contrast, reduced motion, blur fallback, loading and
  error feedback, CSV/polygon guidance, and safe export availability.
- [ ] Add request cancellation/versioning so delayed responses cannot overwrite
  the latest selection. Test failed requests on all five views.
- [ ] Run browser tests against the real server for presets, custom inputs,
  polygon and upload workflows, all toggles/ramps/roles, every download, receipt
  inspection, and trap bench; require no document overflow or unexpected errors.

## Task 8: Accurate documentation and judging walkthrough

**Files:** `README.md`, `.env.example`, `docs/ARCHITECTURE.md`,
`docs/MAPPING_MANIFESTO.md`, `docs/SUBMISSION.md`, `PROJECT-CONTEXT.md`,
`judge.py`, `smoke_test.py`, `tests/test_documentation.py`.

- [ ] Align setup, commands, routes, schemas, formulas, fixture metrics, modeling
  limits, and the distinction between demo claims and external validation.
- [ ] Add a reproducible short judging walkthrough and samples. Check relative
  links and referenced artifacts against the actual repository.
- [ ] Extend meaningful smoke/judge checks to cover corrected workflows rather
  than merely asserting that outputs are non-empty.
- [ ] Follow README commands in a fresh environment and run all documented suites.

## Task 9: Independent review and requirement-by-requirement completion audit

**Files:** review fixes as needed; final evidence in `docs/verification/`.

- [ ] Run the complete unit, HTTP, smoke, judge, verifier, determinism, and browser
  suites; record command, revision, environment, and outputs.
- [ ] Have independent Standards and Spec reviewers inspect the complete change
  from `a7b7ec9`, and an independent visual evaluator inspect every primary view.
- [ ] Resolve findings and rerun the checks affected by each fix.
- [ ] Map each approved design/recovered R1–R4 requirement and survey item to its
  implementation and authoritative evidence. Report unsupported environmental
  checks as unverified; do not claim complete until all required work is proved.

## Execution decision

The user explicitly approved implementing the full design. Execute natively in
this session because engine, receipt, coverage, and API contracts are tightly
coupled. Use fresh independent reviewers at meaningful gates and for completion.
The approval already authorizes implementation; no additional plan permission is
needed. Commit coherent verified milestones, keeping `.codegraph/` local.

## Plan self-review

All five scope sections map to Tasks 1–8; M5 maps to Task 9. The five Review Focus
conditions have explicit owners/tests. Existing public signatures remain the
integration seams; any revision must update dependent tasks and documentation.
