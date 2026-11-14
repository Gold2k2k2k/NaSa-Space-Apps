# FireTrace continuation design

Status: approved by the user on November 14, 2026. Implementation follows the
linked continuation plan.

## Intent and agreed direction

Complete the interrupted FireTrace upgrade described by the recovered
Antigravity brief: R1 engineering correctness, R2 scientific and product showcase
capabilities, R3 a cohesive web-adapted glass design system, and R4 automated
verification and accurate submission documentation.

The user confirmed the review baseline `a7b7ec9` plus a full current-app audit;
scientific meaning and provenance before reliability/accessibility and polish;
a transparent offline demo with real FIRMS CSV support; preservation of the
five-view dashboard; and restrained dark teal/ember glass styling with crisp data
surfaces, mobile layouts, keyboard access, and reduced-motion support.

The morning surveys and five milestones are a starting inventory. Survey
findings are hypotheses until reproduced; their proposed architecture is not
evidence that features already exist. All recovered R1–R4 acceptance criteria
remain in scope.

## Approaches considered

1. **Continue the current stack as a transparent, reliable demonstration.**
   Preserve Python 3.11/FastAPI and zero-build HTML/CSS/JS/SVG, repair the full
   workflow, add the planned scientific summaries with explicit assumptions,
   and deliver the design system and verification evidence. This is the approach
   selected by the user. It preserves the existing investment and offline judging
   workflow while making the limits of the evidence visible.
2. **Build an operational live-data service.** Add ongoing archive acquisition,
   coverage metadata, external validation, and orbital ephemeris ingestion. This
   requires data and operational work beyond the recovered demo brief. The user
   selected the offline demonstration instead.

## Scope and contracts

### 1. Reproducible environment and canonical identity

- Document a clean Python 3.11 virtual-environment setup, declare every runtime
  dependency including multipart uploads, and remove misleading environment
  settings. Keep the standalone receipt verifier usable offline.
- Canonical identifiers bind normalized geometry, input data, analysis options,
  and calculation/dataset versions. Distinct uploads and counterfactual states
  receive distinct immutable run identities. Equal canonical inputs reproduce
  results across processes; input row ordering does not change an analysis.
- Archive member ordering, timestamps, and serialization are deterministic for a
  fixed run. Cache operations preserve immutable snapshots and are bounded and
  safe under concurrent API requests.

### 2. Validated spatial and CSV inputs

- Use shared, explicit validation contracts for CLI, engine, API, and
  counterfactual inputs: finite coordinates, supported geometries, valid dates,
  year windows, months, confidence levels, modes, and audience roles.
- Preserve submitted geometry through every counterfactual and export. Support
  the spatial forms in the recovered plan, including Polygon, MultiPolygon,
  Point, Feature, and FeatureCollection, without silently discarding holes or
  additional features. Reject invalid or unsupported geometry with a clear error.
- Check bounds, closure, vertex limits, non-zero area, and self-intersections;
  handle polar and antimeridian cases explicitly. No silent replacement of a
  drawn polygon with a bounding square.
- Bound CSV bytes and rows, validate each row before deriving an AOI, and report
  accepted/rejected row counts with useful reasons. Do not silently truncate an
  oversized file. Preserve valid zeros and recognize documented sensor aliases.
- Include convenient sample uploads with their provenance labeled. Generated
  sample data must never be described as an authentic NASA observation.

### 3. Scientific demonstration and calendar semantics

- Clearly identify generated preset data, uploaded data, calculation versions,
  source limitations, and coverage assumptions in the UI, receipts, and exports.
  The existing 89%–99% reductions and correlation statistics describe fixture
  results until independent observational evidence establishes broader validity.
- Audit the current harmonization: common spatial grid, temporal/constellation
  deduplication, confidence and footprint weights, overlap calibration, and
  persistent thermal-source handling. Verify the intended sensor-era behavior
  and add 2012/2018 transition diagnostics, overlap RMSE, and a defined agreement
  metric alongside correlation. Name the units and assumptions explicitly.
- Preserve the six benchmark regimes and twelve trap scenarios as reproducible
  demonstrations. Correct impossible sensor dates and document any fixture or
  expected-result changes required by a validated correction.
- Distinguish missing coverage, recorded detections, and a measured zero. A
  hotspot-only upload cannot establish that an absent month had zero fire.
  Compute baseline sufficiency for the comparison actually being made; a
  short archive must not acquire a fictional 20-year baseline.
- Complete the planned calendar summaries: monthly and 36-dekad views, quantiles,
  empirical percentile, OLS and Theil–Sen trends, and defined season
  onset/peak/cessation/duration. Report insufficient data and partial periods.
- Audit verdict boundaries, January previous-month context, and season-onset
  logic. Describe category and operational-looking conclusions as demonstration
  heuristics where no ground-truth validation exists. FRP in MW is power, not
  energy or burned area.
- Preserve exact AOI, source records, and options across raw/harmonized,
  flare-guard, focus-period, confidence, persona, and median counterfactuals.
  Rebuild consistent evidence, summaries, query tables, and receipts together.

### 4. Satellite estimates, receipts, and exports

- Retain the original approximate overpass capability, improve its documented
  geometry where substantiated, and explicitly label it as an illustrative
  sun-synchronous model without orbital ephemerides or operational guarantees.
- Make the time reference an explicit snapshot input. Standalone requests for
  upcoming estimates use the requested/current reference; repeatable run exports
  use the stored run reference. Show the reference and modeling limits to users.
- Verify every required query, row hash, evidence relationship, verdict,
  deciding rule, and finding. Include the previous-month context needed to
  re-derive all rule paths. Reject changed, missing, duplicated, or malformed
  required evidence without an unhandled exception. Regenerate reference receipts
  after intentional format/rule changes and document compatibility.
- Hashes provide reproducibility and internal consistency, not proof that NASA
  supplied an input or that an author could not regenerate an entire receipt.
- Keep all six download workflows: hotspot CSV, calendar CSV, GeoJSON, iCalendar,
  receipt JSON, and audit ZIP. Their data, geometry, units, identity, and reference
  time must agree with the displayed run.

### 5. Design system and five-view web application

- Deliver `design-tokens.json`, CSS custom properties, `DESIGN.md`, and a
  self-contained interactive `design-preview.html`. Tokens cover semantic colors,
  typography, spacing, radii, shadows, surface elevation, motion, and breakpoints.
- Evolve the existing dark scientific identity with teal signal and ember thermal
  accents. Use glass for navigation and selected instrument surfaces. Scientific
  charts, heatmaps, tables, and receipt text remain crisp, legible data wells.
  Avoid nested blur and effects on every component.
- Preserve Burning Calendar, Sensor Bridge, Evaluator & Receipt, Schema Manifesto,
  and Trap Bench. Improve hierarchy, units, legends, mobile navigation, loading,
  empty/error states, polygon feedback, upload feedback, and export availability.
- Use contrast calculations in linearized sRGB, purposeful focus styles, usable
  touch targets, keyboard calendar navigation, accessible SVG descriptions/data
  alternatives, and status announcements. Include the additional ramps planned
  in the morning design where they improve access.
- Prevent stale asynchronous results from replacing newer selections. Handle
  failures in every workflow and keep errors visible on every view.
- Support 375px and 1440px layouts without document-level horizontal overflow;
  deliberate data-table scrolling stays inside its container. Respect reduced
  motion and provide an opaque fallback when backdrop blur is unavailable.

## Implementation order

1. **M1 — foundation and science:** environment, canonical identity, geometry,
   input/schema validation, calibration, calendar/rules, and receipt foundations.
2. **M2 — complete workflows:** lossless engine state, API/cache, CLI, satellite
   reference handling, sample uploads, all exports, and regenerated examples.
3. **M3 — design and accessibility:** tokens, preview/rationale, five-view UI,
   scientific visualization clarity, responsive and keyboard interactions.
4. **M4 — verification and docs:** expand the relevant test layers and align
   README, architecture, schema mapping, submission notes, and demo instructions.
5. **M5 — independent completion audit:** review implementation against every
   recovered requirement and survey item, run complete suites, inspect rendered
   views, repair findings, and record evidence and remaining limitations.

Regression tests accompany the defect they protect, rather than waiting for M4.
No speculative architecture or arbitrary test-count target substitutes for
verified behavior.

## Completion evidence

| Requirement | Evidence required |
| --- | --- |
| Clean setup | Fresh virtual environment follows README commands and starts the actual FastAPI application; Docker build/run when Docker is available, otherwise explicitly unverified |
| Correct inputs and geometry | Engine and HTTP boundary tests, malformed-input cases, spatial edge cases, lossless counterfactual/export comparisons |
| Reproducibility | Separate-process tests with differing hash seeds, reordered uploads, stable canonical identity, and byte-identical fixed-run archives |
| Scientific behavior | Independent small fixtures for calibration, coverage, baselines, trend/phenology definitions, rule boundaries, flare and sensor-era traps; clearly limited claims |
| Receipts | Valid normal and counterfactual receipts, complete evidence checks, a meaningful tamper matrix, malformed-input CLI exit-code checks |
| Full workflows | Unit and actual HTTP integration suites, smoke test, judge suite, standalone verifier, and non-empty valid exports |
| Web application | Browser tests against the real server across all five views and primary controls, zero uncaught JS errors or unexpected failed requests, 375px/1440px overflow checks, keyboard/contrast/motion checks |
| Visual quality | Screenshots of each primary view and an independent evaluator passing token consistency, glass hierarchy/contrast, interaction feedback, and visualization clarity |
| Design artifacts | Tokens/CSS synchronization check, rationale, interactive dependency-free preview, and a ten-dimension visual audit with cited evidence |
| Submission readiness | Accurate commands/routes/formulas/claims, working relative links, regenerated examples, and a reproducible judging walkthrough |

The full goal is complete only after all requirements are implemented and the
evidence supports them. A passing synthetic judge suite alone is insufficient.

## Builder decisions and limits

Internal module boundaries and small refactorings may change as needed to make
these contracts reliable. Keep public workflows recognizable and version
intentional receipt or scientific-output changes. An unsupported environmental
check must be reported as unverified, not marked passing. No deployment or remote
publication is part of this design.
