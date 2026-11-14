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

Resuming the interrupted November 14, 2026 upgrade. Antigravity produced surveys
and a milestone plan; the repository still contains the initial application and
documentation commits. Implementation and verification of the upgrade remain.

## Constraints

- Preserve the current stack and five-view application.
- Keep a reliable offline demonstration with clearly labeled generated presets
  and approximate satellite-pass estimates. Accept real FIRMS CSV uploads.
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
