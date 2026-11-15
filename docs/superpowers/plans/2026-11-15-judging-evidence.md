# Judging Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver the approved real-FIRMS judging package and land-manager workflow before 23:00 Asia/Saigon on November 15, 2026.

**Architecture:** Preserve the current stack and immutable pipeline. Bundle one verified NASA subset with provenance; give it a fixed training policy and a matching held-out assessment. Extend the existing five-view application with case selection, a guided review and a manager brief.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, standard-library data scripts, local HTML/CSS/JS/SVG, unittest and Playwright.

**Spec:** `docs/superpowers/specs/2026-11-15-judging-evidence-design.md`, approved by the user in Q7 on November 15, 2026.

## Global Constraints

- Preserve Python 3.11/FastAPI, zero-build assets, five existing views and all six downloads; no new runtime dependency.
- Use original core code and the actual 37-file FIRMS snapshot already downloaded.
- Primary study rectangle: `[107.8, 12.5, 108.5, 13.1]`; 16,258 rows (4,143 MODIS, 12,115 VIIRS), 2001–2024.
- Keep 2001–2020 descriptive reference; real-case training 2013–2020, held-out 2021–2024.
- Archive availability does not establish observation completeness; preserve missing/records-only and UNVERIFIABLE conclusions.
- Fit both occupancy and FRP factors per source/filter profile using training data only. Focus/display/persona/mode/median changes preserve factors.
- Do not manufacture validation, user testing, scores, fire causes or predictions. Rubric 2025 is a dated reference; exact 2026 guide remains unverified.
- Local commits and release-ready materials only; publishing, visibility changes, deployment and actual submission require separate authorization.

## Review Focus

1. Broad or repeatedly wrapped longitude bounds must terminate and retain all valid points (Task 1).
2. Arrays/objects in nested GeoJSON `type` must produce controlled 422 responses (Task 1).
3. Median percentile must use the fixed reference even outside the display, including asymmetric ties and empty references (Task 1).
4. Windows crossing the training/evaluation boundary and held-out FRP changes must not contaminate either fitted factor (Task 3).
5. Switching case/generated/upload sources during slow requests, scenarios or filter changes must preserve the latest intended source and its exact model/provenance (Tasks 4–6).

## File Map

- `app/geometry.py`, `app/calendar_engine.py`, `app/run_state.py`: three reproduced repairs and retained reference history.
- `scripts/build_firms_case.py`, `app/data/central-highlands.csv`, `app/data/central-highlands.manifest.json`: deterministic research-cache/network rebuild and bundled subset.
- `app/case_studies.py`: whitelist metadata, integrity checks, typed-source loading and case execution defaults.
- `app/calibration.py`, `app/harmonize.py`: training policy, fitted factors, temporal separation and descriptive held-out agreement.
- `app/agents.py`, `app/api.py`, `run.py`, `app/receipt.py`, `verify.py`: bind and expose the case, policy, evaluation and sources.
- `app/manager_brief.py`, existing web HTML/CSS/JS modules: structured brief and accessible three-step workflow.
- `docs/judging/`, `SOURCES.md`, `AI-DISCLOSURE.md`, `LICENSE`, `scripts/package_submission.py`: concise presentation, credits and reproducible local handoff package.
- Focused `tests/test_judging_*.py` plus existing regression suites: independent contracts and actual HTTP/browser proof.

## Task 1: Repair the three confirmed defects

**Files:** Modify `app/geometry.py`, `app/calendar_engine.py`, `app/run_state.py`; create `tests/test_judging_regressions.py`.

**Interfaces:** Preserve `box_geometry(...)`, `normalize_geometry(...)` and `apply_calendar_scenario(calendar)`. Add `calendar.reference_history`, a twelve-item list of `{month, years, values, coverage_statuses}` using all available same-month values in the fixed reference interval, independent of displayed years.

- [x] Write independent tests: bound `box_geometry(166,454,-1,1)` using a subprocess timeout; CSV at `-170,-50,70` retains all rows; nested array/object GeoJSON types return 422; compare full/narrow AMZ median percentile and an asymmetric tied distribution `[1,2,2,2,3,3,4]` (midrank `100*2.5/7`, not 50); empty reference remains unavailable.
- [x] Run `python -m unittest discover -s tests -p test_judging_regressions.py -v`; observe the expected failures without letting a hanging process remain live.
- [x] Make longitude subdivisions advance at each periodic boundary; validate string geometry types before hashing; retain fixed reference values and use them for scenarios without changing observations.
- [x] Run the new tests and existing geometry, scientific, workflow and receipt suites; require PASS.
- [x] Commit `fix: close remaining geometry and scenario review defects`.

## Task 2: Bundle a reproducible real NASA case

**Files:** Create `scripts/build_firms_case.py`, `app/case_studies.py`, `app/data/central-highlands.csv`, `app/data/central-highlands.manifest.json`, `tests/test_judging_case_data.py`.

**Interfaces:** `build_case(cache_dir: Path, *, download: bool = False, check: bool = False) -> dict`; `list_case_studies() -> list[dict]`; `load_case_study(case_id: str) -> tuple[list[dict], dict]`. ID is exactly `central-highlands`; unknown IDs raise `ValueError`, never form file paths.

- [x] Write tests for source/subset hashes, exact 37 URLs, exact count/sensor totals, declared rectangle, canonical row order, data corruption, unknown/path-like IDs and absence of invented completeness.
- [x] Observe RED before implementing data builder/loader.
- [x] Build from the existing ignored research cache. Preserve original FIRMS fields in a union CSV schema; sort canonical raw rows. Manifest records raw-file hashes/bytes/retrieval metadata, versions, transform and subset identity. `--check` is offline and compares bundled outputs; `--download` explicitly fetches originals and rejects changed expected input identities.
- [x] The loader returns full normalized geometry plus source kind `nasa_firms_archive`, manifest, subset hash and policy. It returns fresh data copies and verifies bundled bytes on load. No module import requires the research cache or network.
- [x] Run the focused suite and rebuild `--check`; require byte equality and PASS. Commit the dataset milestone.

## Task 3: Freeze and assess the actual case model

**Files:** Create `app/calibration.py`, `tests/test_judging_calibration.py`; modify `app/harmonize.py`, `app/run_state.py`, relevant schema declarations/docs.

**Interfaces:** `resolve_calibration_policy(aoi: dict) -> dict`; `calibration_period(year: int, month: int, policy: dict) -> str`; `build_model_evaluation(events: list[dict], monthly_modis: dict, monthly_viirs: dict, policy: dict, model: dict) -> dict`. `harmonize_records(...)` keeps its public signature and reads an internal validated AOI policy. Its audit adds `calibration_model` and `model_evaluation`.

- [x] Write fixtures with known occupancy/FRP factors; changing only 2021–2024 rows leaves fitted factors/training identity unchanged. Test cross-midnight/year-boundary windows, filter/guard refits within training only, no factor changes for display/focus/persona/mode/scenario, sparse/constant/undefined metrics and defaults for existing generated regimes.
- [x] Observe RED, then separate case observation windows at policy partitions before fitting to prevent cross-boundary leakage. Both monthly occupancy and matched-window FRP fit use only 2013–2020. Store training identity/options/counts/basis and the applied factors.
- [x] Evaluate the identical factors on 2021–2024; return fit/held-out counts, exclusions, correlation, RMSE, mean bias and efficiency, with power metrics separate from occupancy. Keep undefined/fallback results explicit; do not optimize using held-out output.
- [x] Run focused and existing science/benchmark tests; require PASS without changing expected qualitative labels to hide failures. Commit the model milestone.

## Task 4: Complete API/CLI, receipt and audit integration

**Files:** Modify `app/agents.py`, `app/api.py`, `run.py`, `app/receipt.py`, `verify.py`, `app/run_state.py`; extend `app/case_studies.py`; create `tests/test_judging_workflows.py`.

**Interfaces:** `run_case_study(case_id: str, options: dict | None = None) -> dict`; `POST /api/case-studies/{case_id}/analyze` accepts only existing analysis options, using the strict request model plus option-only validation; `GET /api/case-studies` lists metadata. CLI adds `--case-study central-highlands` alongside mutually exclusive input selectors. `ui/setup` advertises case metadata.

- [x] Write tests for case defaults/unknown IDs, rejected geometry/extra fields on case routes, HTTP/CLI loading and source preservation through all six experiment types.
- [x] Observe RED, then load the actual subset with full AOI/manifest/policy and use the existing engine. Defaults: 2001–2024, focus 2024, nominal confidence, guard on, land manager, harmonized. Choose initial focus by largest historical reference median, earliest-month tie; a labeled January navigation fallback is allowed if no median exists.
- [x] Bind manifest, calibration/evaluation and source identities in snapshots/receipts; include matching manifest/report in audit ZIP. Add independent verifier relationships for these fields and retain documented legacy scope; new implementation files join calculation identity.
- [x] Verify filters refit only their training profiles, other experiments preserve factors, raw records never become generated, snapshots remain immutable, and all six downloads agree. Test malformed/tampered case metadata and extracted dependency-free verification.
- [x] Run focused API/CLI/receipt/export suites and commit the integrated workflow.

## Task 5: Guided review and manager brief

**Files:** Create `app/manager_brief.py`, `tests/test_judging_brief.py`; modify existing HTML/CSS/JS modules and browser suite.

**Interfaces:** `build_manager_brief(run: dict) -> dict` produces question, extent/time, source, descriptive periods, comparison, limitations, next-review action and run identity. It is included in public run evidence and rendered within the five views.

- [x] Write tests proving records-only data cannot yield a claimed verified hazard, missing medians are explicit, source/model facts match the snapshot, and non-vegetation types do not become forest-fire causes.
- [x] Observe RED and implement the brief with original plain English copy; relevant static text can be shared by UI and evidence rather than duplicated logic.
- [x] Add a separate actual-data entry and three-step guidance: choose evidence, review periods, retain evidence. Preserve generated choices and all controls. Expose training/held-out support and limitations progressively; show source badges and accessible brief/download links.
- [x] Extend actual-server browser tests at 375/1440 px for case loading, navigation, filters/personas/mode/scenario, source switching/races, errors and all six downloads. Require no unexpected exceptions/requests, overflow or keyboard regressions.
- [x] Commit the usable workflow.

## Task 6: Judging packet, release-ready handoff and final review

**Files:** Create `docs/judging/README.md`, `docs/judging/submission.md`, `docs/judging/slides.md`, `docs/judging/team-notes-vi.md`, `docs/judging/evidence.md`, `SOURCES.md`, `AI-DISCLOSURE.md`, `LICENSE`, `scripts/package_submission.py`, `tests/test_judging_packet.py`; update README, scientific/schema docs, PROJECT-CONTEXT and current examples.

**Interfaces:** `package_submission(output: Path) -> dict` creates a deterministic local ZIP of the tracked source/evidence with raw-file manifest, excluding VCS/config credentials/research caches. Publishing is not part of this function.

- [x] Prepare concise English submission/slide outline and Vietnamese team notes. Clearly distinguish 2025 reference rubric from unverified current guide; cover all five criteria and actual measured evidence/limitations.
- [x] Record actual held-out results, including negative/undefined outcomes; data/source/tool/AI credits and proposed Apache-2.0 license. Verify actual dependency/font licensing references. Do not claim real-user testing or public accessibility that was not established.
- [x] Test packet contents, repeat byte equality, source/evidence manifests, local links, all required narrative sections and exclusions; create/review the local handoff ZIP.
- [x] Regenerate schemas/design/examples where affected. Run the complete unit/HTTP/browser suite, judge, smoke, all current receipt verifiers, determinism checks and artifact checks. Save authoritative outputs and screenshots with revision/environment.
- [x] Apply fresh independent Standards/Spec review to the entire goal delta from `b9a8815`, fix demonstrated defects, and rerun affected checks. Review rendered actual-case flow independently where available.
- [x] Map every spec requirement and each judging criterion to actual proof; report remaining external limits. Commit completion evidence and confirm clean worktree. Do not publish or deploy.

## Execution and self-review

The user approved both planning and implementation in Q7. Continue natively in
this existing isolated feature branch, preserving the prior execution method;
use fresh independent final review. No second approval of the same scope is needed.
The six tasks cover the whole approved design, the five review-focus conditions
have explicit tests, and public interfaces/defaults are named above. Whole-branch
tests and the criterion evidence report are completion gates, not substitutes
for the real-data and scientific claims they must cover.
