# FireTrace project context

## Purpose

FireTrace is a NASA Space Apps competition showcase for comparing MODIS and
VIIRS thermal-anomaly detections through a harmonized burning-activity calendar.
It explains sensor-transition bias, seasonal comparisons, counterfactuals, and
reproducible evidence to judges and people exploring Earth-observation data.

## Stack

Python 3.11, FastAPI, and a zero-build HTML/CSS/JavaScript/SVG web application.
The five primary views are Burning Calendar, Sensor Bridge, Evaluator & Receipt,
Schema Manifesto, and Trap Bench.

## Current phase

The user approved a second judging-evidence design on November 15, 2026 for
land/forest managers, with an internal 23:00 Vietnam deadline. It adds an actual
FIRMS study rectangle, fixed training/held-out assessment, guided manager brief
and a local judging/source packet. See [approved design](docs/superpowers/specs/2026-11-15-judging-evidence-design.md)
and [current evidence](docs/judging/evidence.md). The earlier baseline below is
historical; current verification is recorded separately in that judging packet.

The approved continuation is complete on `codex/firetrace-upgrade`. Validated
inputs, scientific/coverage semantics, immutable workflows, receipts/exports,
modeled passes and the tokenized five-view dashboard are implemented. The fresh
Python 3.11 environment passed 144 tests, judge 7/7, smoke 3/3 and bench 12/12.
Independent Standards/Spec findings are closed; the rendered visual audit scored
88/100. [Completion evidence](docs/verification/completion.md) records results,
all 76 recovered survey dispositions and practical verification limits.
Antigravity supplied the recovered planning/surveys; implementation continued here.

## Constraints

- Preserve the current stack and five-view application.
- Keep a reliable offline demonstration with clearly labeled generated presets
  and approximate satellite-pass estimates. Accept real FIRMS CSV uploads.
- Keep NASA case archive availability distinct from complete observation coverage;
  fit both factors only on 2013–2020 and report 2021–2024 results without retuning.
- Prepare local source/evidence only. Publication, repository visibility and
  deployment are separate owner-authorized steps.
- Use original core logic. External documentation may inform implementation;
  existing projects are not a source of copied core code.
- Prioritize scientific meaning and provenance, then reliability and
  accessibility, then visual polish.
- Evolve the dark scientific dashboard with restrained teal/ember glass surfaces,
  crisp chart surfaces, responsive layouts, keyboard access, and reduced motion.
- Reproduce survey findings against current code before treating them as defects.

## Definition of done

The recovered upgrade requirements R1–R4 are implemented and verified. Setup
works from the documented commands; input validation, geometry, CSV workflows,
calendars, counterfactuals, receipts, and exports have meaningful regression
coverage. All five views and primary interactions work at desktop and mobile
widths. A tokenized design system, rationale, and interactive preview exist.
Documentation accurately separates demonstrated software behavior from externally
validated science. Independent review and rendered evidence support completion.

The continuation design is in
[docs/superpowers/specs/2026-11-14-firetrace-continuation-design.md](docs/superpowers/specs/2026-11-14-firetrace-continuation-design.md).
