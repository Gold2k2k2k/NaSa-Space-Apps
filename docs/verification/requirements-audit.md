# Approved requirements and recovered-survey disposition

Status: complete. Reviewed implementation revision: `1458086`. Full fresh suite **144/144**, judge **7/7**, smoke **3/3**, bench **12/12**; all findings independently closed.

The recovered Antigravity work completed planning/surveys, then stopped on quota/billing failures. Its claims were hypotheses. The inventory has **76 rows: 26 backend issues, 10 UI issues, 26 documentation issues, and 14 feature descriptions**. Group prefixes below disambiguate repeated F IDs. Source handoffs: `teamwork_explorer_survey_1/handoff.md`, `teamwork_explorer_survey_2/handoff.md`, `teamwork_spec_miner_survey_3/handoff.md` in the recovered local teamwork workspace.

The approved [continuation design](../superpowers/specs/2026-11-14-firetrace-continuation-design.md) governs deliberate scientific/modeling corrections. Survey suggestions are not extra requirements when they contradict that design (for example, inferred industrial causes, physical burned area, real orbit propagation or a pytest dependency).

## R1–R4 acceptance mapping

| Requirement | Delivered implementation | Authoritative verification |
| --- | --- | --- |
| R1 engineering | Canonical full inputs/identity, bounded validation, immutable cache, original extracted modules, complete verifier relationships | Input/geometry, workflow, HTTP, cache, CLI and receipt suites; cross-process receipt/ZIP equality; independent reviews |
| R2 scientific/product | Defined occupancy/coverage, pooled and per-era diagnostics, reference statistics/trends/phenology, retained input experiments, all exports, explicitly modeled schedules | Independent numerical cases, six generated regimes, twelve generated traps, real-HTTP browser workflows; not external observational validation |
| R3 visual/accessibility | Five views, shared tokens/preview, restrained glass, crisp plots, responsive44pxcontrols, roving keyboard, text/table alternatives, contrast and motion fallbacks | All5views375/1440, four actual ramp contrasts, keyboard/reducedmotion tests; independent rendered audit88/100; no complete AT/WCAG certification |
| R4 verification/docs | Expanded unit/integration/browser/smoke/judge/verifier, synchronized generated artifacts, fresh setup and judging walkthrough | Final verification report; doc links and schema contracts; independent Spec review; Docker unavailable |

## Every recovered survey row

All paths in the implementation column are repository relative. Test filenames are under `tests/`; each named suite contains purpose-built regression cases. Quantitative fixture changes follow corrected methods, without retuning the algorithm to benchmark labels.

| Survey item | Disposition | Implementation | Verification |
| --- | --- | --- | --- |
| backend:BUG-01 | Full geometry and sources survive all experiments | app/agents.py; app/run_state.py | test_analysis_workflows.py; test_browser_showcase.py |
| backend:BUG-02 | V2 embeds full calendar; verifier rederives all rule context; v1 frozen with narrower scope | app/receipt.py; verify.py | test_receipt_integrity.py |
| backend:BUG-03 | Median is explicit new metric scenario; queries/calendar/receipt rebuilt; observed input unchanged | app/run_state.py; app/agents.py | test_analysis_workflows.py; test_browser_showcase.py |
| backend:BUG-04 | Bounded streamed multipart envelope and file read | app/http_limits.py; app/api.py | test_http_boundaries.py |
| backend:BUG-05 | Typed strict analysis/what-if contracts and controlled errors | app/models.py; app/api.py | test_http_boundaries.py; test_inputs_geometry.py |
| backend:BUG-06 | SHA-256 canonical geometry/data/options/code/reference identity; immutable collision checks | app/canonical.py; app/run_state.py; app/run_store.py | test_analysis_workflows.py; test_inputs_geometry.py; test_run_store.py |
| backend:BUG-07 | Previous December uses previous year; onset restricted to two pre-onset months | app/rules.py; app/calendar_engine.py | test_science_contracts.py |
| backend:BUG-08 | Before/after metrics computed from correct active/alternate calendars; removed dead branch | app/agents.py | test_analysis_workflows.py |
| backend:BUG-09 | All nine required queries/counts/hashes and evidence/decision relationships verified; unsigned scope explicit | app/evidence.py; verify.py | test_receipt_integrity.py |
| backend:BUG-10 | Strict bounded full geometry with holes/components; invalid rings rejected, observations remain in AOI | app/geometry.py; app/datasets.py | test_inputs_geometry.py; test_science_contracts.py |
| backend:BUG-11 | Dateline/polar bounds and geometry identity; CSV focus follows latest valid row | app/geometry.py; app/datasets.py | test_inputs_geometry.py |
| backend:BUG-12 | Fixed reference trace and sorted ZIP epoch/permissions/compression; byte equality | app/agents.py; app/receipt.py | test_receipt_integrity.py; test_analysis_workflows.py |
| backend:BUG-13 | Source-preserving option form uses retained snapshot; no accidental preset-to-custom conversion | app/web/static/app.js | test_browser_showcase.py |
| backend:BUG-14 | Missing/records_only/complete coverage; explicit focus preserved, December CSV not discarded | app/calendar_engine.py | test_science_contracts.py; test_inputs_geometry.py |
| backend:BUG-15 | Known D/N share computed from unrounded contributions and bounded by its denominator | app/calendar_engine.py | test_science_contracts.py |
| backend:BUG-16 | Unique observation revisions, satellite family mean occupancy; R2 separate from efficiency/RMSE. Monthly half-blend is an explicit index convention, not physical equivalence | app/observations.py; app/harmonize.py; docs/SCIENCE.md | test_science_contracts.py |
| backend:BUG-17 | Removed forced pre-2012 MODIS detection; availability and omission applied consistently | app/datasets.py; app/satellites.py | test_science_contracts.py |
| backend:BUG-18 | Spherical viewing geometry, bounded schematic nominal solar phase; footprint metadata/defaults explicit. No ephemeris or bow-tie correction claimed | app/geo_passes.py; app/satellites.py; docs/EXPORTS.md | test_exports_passes.py; test_science_contracts.py |
| backend:BUG-19 | CSV formula neutralization and RFC5545 control normalization/UTF8 folding | app/exports.py | test_exports_passes.py |
| backend:BUG-20 | Complete retained events by default, explicit inclusion/missing flags; labeled optional previews only | app/exports.py | test_exports_passes.py; test_browser_showcase.py |
| backend:BUG-21 | Copy-in/out locked bounded LRU and new content IDs for experiments | app/run_store.py; app/run_state.py | test_run_store.py; test_analysis_workflows.py |
| backend:BUG-22 | No invented FRP/temperature; valid zero preserved; missing flags exported | app/schema_mapping.py; app/observations.py | test_science_contracts.py; test_inputs_geometry.py |
| backend:BUG-23 | Multi-year persistence is only a descriptive flag; supplied types distinct; shared overlap docs2012-2024 | app/observations.py; app/harmonize.py; app/schema_manifest.py | test_science_contracts.py; test_documentation.py |
| backend:BUG-24 | Frontend split into focused modules; geometry/stats/observations/evidence/state/store extracted. Remaining cohesive algorithm functions retained; survey line ceilings were advisory, not repo rules | app/web/static/js/; app/geometry.py; app/stats.py; app/observations.py | full regression suite; independent Standards review |
| backend:BUG-25 | Pinned minimal runtime plus dev browser dependency; stdlib unittest, multipart declared; fresh venv installed | requirements.txt; requirements-dev.txt; README.md | fresh install and pip check; full suite; smoke_test.py |
| backend:BUG-26 | Unknown preset gets explicit validation error; GET snapshot documented | app/api.py; README.md | test_http_boundaries.py; test_documentation.py |
| ui:F-01 | Contained scrolling and min-width rules; no document overflow375/1440 | app/web/static/app.css | test_browser_showcase.py; visual-audit.md |
| ui:F-02 | Median is explicit new metric scenario; queries/calendar/receipt rebuilt; observed input unchanged | app/run_state.py; app/agents.py | test_analysis_workflows.py; test_browser_showcase.py |
| ui:F-03 | Source-preserving option form uses retained snapshot; no accidental preset-to-custom conversion | app/web/static/app.js | test_browser_showcase.py |
| ui:F-04 | Full geometry and sources survive all experiments | app/agents.py; app/run_state.py | test_analysis_workflows.py; test_browser_showcase.py |
| ui:F-05 | Caught request errors, global live alert/retry on all views and readable validation details | app/web/static/app.js; app/web/static/index.html | test_browser_showcase.py |
| ui:F-06 | AbortController plus revision guard; immutable server snapshots; stored schedule | app/web/static/app.js; app/run_store.py | test_browser_showcase.py; test_run_store.py |
| ui:F-07 | Linear-sRGB foreground choice and token contrast; all four actual cell ramps >=4.5:1 | app/web/static/js/theme.js; design-tokens.json | test_design_tokens.py; test_browser_showcase.py |
| ui:F-08 | Native44px roving calendar buttons, text/table alternatives, live regions, keyboard Escape, GeoJSON drawing alternative | app/web/static/js/charts.js; app/web/static/index.html; app/web/static/app.js | test_browser_showcase.py; visual-audit.md (no AT certification) |
| ui:F-09 | Shared ramp tokens; meaningful legends/units and chart text alternatives; no disconnected profile ramp | app/web/static/js/charts.js; app/web/static/js/theme.js | test_browser_showcase.py; visual-audit.md |
| ui:F-10 | One-file drop zone with picker alternative, disabled pre-run exports, relational client/server validation, modular JS and multipart packaging | app/web/static/app.js; app/web/static/index.html; requirements.txt | test_browser_showcase.py test_35; test_http_boundaries.py; fresh setup |
| docs:D-01 | Pinned minimal runtime plus dev browser dependency; stdlib unittest, multipart declared; fresh venv installed | requirements.txt; requirements-dev.txt; README.md | fresh install and pip check; full suite; smoke_test.py |
| docs:D-02 | Pinned minimal runtime plus dev browser dependency; stdlib unittest, multipart declared; fresh venv installed | requirements.txt; requirements-dev.txt; README.md | fresh install and pip check; full suite; smoke_test.py |
| docs:D-03 | Pinned minimal runtime plus dev browser dependency; stdlib unittest, multipart declared; fresh venv installed | requirements.txt; requirements-dev.txt; README.md | fresh install and pip check; full suite; smoke_test.py |
| docs:D-04 | Removed unimplemented live-mode/API-key settings; PORT only | .env.example; README.md | documentation review; fresh startup |
| docs:D-05 | Two invented CSVs served locally with provenance and mixed-quality example | app/web/static/samples/; scripts/generate_examples.py | test_browser_showcase.py; generate_examples.py --check |
| docs:D-06 | JSON request examples and current receipts documented; supported explicit CLI flags instead of unimplemented --input alias | README.md; examples/; output_examples/; run.py | test_cli.py; generate_examples.py --check; verify.py all3 |
| docs:D-07 | Unknown preset gets explicit validation error; GET snapshot documented | app/api.py; README.md | test_http_boundaries.py; test_documentation.py |
| docs:D-08 | CLI supports CSV/GeoJSON/point/window/confidence/persona/guard/reference/output/receipt/package and strict zero validation | run.py; README.md | test_cli.py |
| docs:D-09 | All nine required queries/counts/hashes and evidence/decision relationships verified; unsigned scope explicit | app/evidence.py; verify.py | test_receipt_integrity.py |
| docs:D-10 | V2 embeds full calendar; verifier rederives all rule context; v1 frozen with narrower scope | app/receipt.py; verify.py | test_receipt_integrity.py |
| docs:D-11 | Median is explicit new metric scenario; queries/calendar/receipt rebuilt; observed input unchanged | app/run_state.py; app/agents.py | test_analysis_workflows.py; test_browser_showcase.py |
| docs:D-12 | Full geometry and sources survive all experiments | app/agents.py; app/run_state.py | test_analysis_workflows.py; test_browser_showcase.py |
| docs:D-13 | Known D/N share computed from unrounded contributions and bounded by its denominator | app/calendar_engine.py | test_science_contracts.py |
| docs:D-14 | Removed hardcoded historical percentage claims; descriptions explicitly generated, values calculated at runtime | app/datasets.py; README.md | test_documentation.py; judge.py |
| docs:D-15 | Removed probability-as-observation and crown-fire claims; measured known D/N share shown | README.md; app/datasets.py; docs/SCIENCE.md | test_science_contracts.py; judge.py |
| docs:D-16 | Unique observation revisions, satellite family mean occupancy; R2 separate from efficiency/RMSE. Monthly half-blend is an explicit index convention, not physical equivalence | app/observations.py; app/harmonize.py; docs/SCIENCE.md | test_science_contracts.py |
| docs:D-17 | Multi-year persistence is only a descriptive flag; supplied types distinct; shared overlap docs2012-2024 | app/observations.py; app/harmonize.py; app/schema_manifest.py | test_science_contracts.py; test_documentation.py |
| docs:D-18 | Removed forced pre-2012 MODIS detection; availability and omission applied consistently | app/datasets.py; app/satellites.py | test_science_contracts.py |
| docs:D-19 | Unique observation revisions, satellite family mean occupancy; R2 separate from efficiency/RMSE. Monthly half-blend is an explicit index convention, not physical equivalence | app/observations.py; app/harmonize.py; docs/SCIENCE.md | test_science_contracts.py |
| docs:D-20 | Full robust scale includes .18*median; separate OLS/Theil-Sen on complete years only | app/stats.py; app/calendar_engine.py; app/schema_manifest.py | test_science_contracts.py; test_documentation.py |
| docs:D-21 | High-Z gap closed; no unsupported crown-fire/continuous-burning inference | app/rules.py | test_science_contracts.py |
| docs:D-22 | Linear-sRGB foreground choice and token contrast; all four actual cell ramps >=4.5:1 | app/web/static/js/theme.js; design-tokens.json | test_design_tokens.py; test_browser_showcase.py |
| docs:D-23 | Typed strict analysis/what-if contracts and controlled errors | app/models.py; app/api.py | test_http_boundaries.py; test_inputs_geometry.py |
| docs:D-24 | Sensor query counts use normalized sensor values, not CSV header presence | app/evidence.py | test_analysis_workflows.py; test_receipt_integrity.py |
| docs:D-25 | Before/after metrics computed from correct active/alternate calendars; removed dead branch | app/agents.py | test_analysis_workflows.py |
| docs:D-26 | Thermal types 1/2/3 distinct; persistence not industrial cause; no fixed persistent-cell count claim | app/observations.py; docs/SCIENCE.md; app/datasets.py | test_science_contracts.py; test_documentation.py |
| docs:F-01 | No invented FRP/temperature; valid zero preserved; missing flags exported | app/schema_mapping.py; app/observations.py | test_science_contracts.py; test_inputs_geometry.py |
| docs:F-02 | Shared source/target declarations with generated document and semantic API view | app/schema_manifest.py; scripts/build_schema_docs.py | test_documentation.py; test_browser_showcase.py |
| docs:F-03 | Six deterministic geographically named generated regimes retained, impossible dates removed and unsupported causal labels corrected | app/datasets.py | test_firetrace.py; test_science_contracts.py; judge.py |
| docs:F-04 | Strict bounded full geometry with holes/components; invalid rings rejected, observations remain in AOI | app/geometry.py; app/datasets.py | test_inputs_geometry.py; test_science_contracts.py |
| docs:F-05 | Bounded mixed-sensor CSV with rejection diagnostics/aliases/latest focus and source-preserving UI options | app/datasets.py; app/api.py | test_inputs_geometry.py; test_http_boundaries.py; test_browser_showcase.py |
| docs:F-06 | Unique observation revisions, satellite family mean occupancy; R2 separate from efficiency/RMSE. Monthly half-blend is an explicit index convention, not physical equivalence | app/observations.py; app/harmonize.py; docs/SCIENCE.md | test_science_contracts.py |
| docs:F-07 | Monthly2000-2026 and36-dekad profiles, same-month reference, empirical percentile, complete-year OLS/Theil-Sen and cyclic90% season; explicit coverage | app/calendar_engine.py; app/stats.py | test_science_contracts.py; test_browser_showcase.py |
| docs:F-08 | All nine required queries/counts/hashes and evidence/decision relationships verified; unsigned scope explicit | app/evidence.py; verify.py | test_receipt_integrity.py |
| docs:F-09 | Five ordinary deterministic stages, Q0-Q8, four bounded diagnostics, four audience lenses, immutable what-if scenarios | app/agents.py; app/evidence.py | test_analysis_workflows.py; test_browser_showcase.py |
| docs:F-10 | Spherical viewing geometry, bounded schematic nominal solar phase; footprint metadata/defaults explicit. No ephemeris or bow-tie correction claimed | app/geo_passes.py; app/satellites.py; docs/EXPORTS.md | test_exports_passes.py; test_science_contracts.py |
| docs:F-11 | Complete retained events by default, explicit inclusion/missing flags; labeled optional previews only | app/exports.py | test_exports_passes.py; test_browser_showcase.py |
| docs:F-12 | V2 consistency verifier, v1 narrower scope, seven demo checks, smoke and12fixture bench | verify.py; judge.py; smoke_test.py; app/api.py | test_receipt_integrity.py; judge7/7; smoke3/3; bench12/12 |
| docs:F-13 | Semantic JSON/CSS tokens, generated interactive preview, restrained glass and opaque charts, reduced motion/transparency/forced color fallbacks | design-tokens.json; DESIGN.md; design-preview.html; app/web/static/ | test_design_tokens.py; test_browser_showcase.py; independent visual audit88/100 |
| docs:F-14 | Documented clean Python3.11 setup, accurate schema/routes/CLI/limitations and short judging walkthrough; sample paths intentionally served from static directory | README.md; docs/; requirements*.txt; .env.example; Dockerfile | fresh install, full tests, artifact checks; Docker build unverified (tool unavailable) |
