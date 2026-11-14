# FireTrace team demonstration

FireTrace is a competition prototype about a real comparison problem: sensors
with different resolutions, observation times and processing streams should not
be summed as interchangeable fire counts. Its contribution is an inspectable
comparison workflow: explicit source/coverage, a defined occupancy index,
sensor-transition diagnostics and portable consistency evidence.

This document positions the team's accepted brief. It does not assert compliance
with every official competition criterion or an independently verified challenge
year/title. Confirm the team's selected challenge and submission rules on the
[NASA Space Apps site](https://www.spaceappschallenge.org/) before submission.

## Five-minute walkthrough

1. Start with [README setup](../README.md). Open Calendar and point to the
   **generated demo** source badge. Choose Mekong, March 2026. Compare its
   harmonized label with raw mode, then use Bridge to inspect 2012/2018 changes,
   calibration basis, RMSE and correlation separately. These are fixture results.
2. Return to Calendar. Use arrow keys to choose a month; show coverage, the
   same-month 2001–2020 reference, monthly/dekad profiles and complete-year trends.
   Explain that HHE is a weighted occupancy index, not burned area or fire count.
3. Open Audit. Set the focus metric to its historical median, show the scenario
   label and new run identity, then restore observations. Download the receipt
   and audit ZIP. Run `python verify.py receipt.json`; explain the unsigned scope.
4. Upload [the invented mixed-quality sample](../app/web/static/samples/generated-mixed-quality.csv).
   Show accepted/rejected counts and recorded-only coverage. Its short archive
   correctly remains UNVERIFIABLE instead of inventing a historical baseline.
5. Open Schemas, then Bench. Inspect a mapping and run the twelve generated cases.
   Show Basra with the non-vegetation guard; type 2 means other static-land source,
   not proof of industrial gas flaring. Show the stored schedule reference and
   approximate label before exporting ICS.

## Evidence and limits

Run `python smoke_test.py` and `python judge.py` for integration and seven demo
checks; the latter writes current measured fixture results to
`logs/judge/report.md`. Run the full suite and artifact checks from README for
numerical, geometry, immutable-state, verifier, export and real-HTTP browser QA.
The [visual audit](verification/visual-audit.md) describes desktop/mobile review.

Presets are invented, geographically named scenarios, not NASA observations.
User-supplied CSVs are not authenticated and do not establish complete coverage.
The bridge and source-pattern labels are demonstration heuristics without held-out
observational validation. Passes have no ephemerides, cloud or instrument-status
inputs. Verdicts are not emergency guidance. Accessibility has keyboard, contrast
and reduced-motion checks, but no claim of full WCAG or screen-reader certification.

Next scientific work requires curated real observations with coverage metadata,
held-out cross-sensor validation and independent ecological evidence. Operational
passes require propagated ephemerides and validated acquisition schedules. A
public multi-user deployment also requires persistent storage and access control.
See [methods and primary references](SCIENCE.md) and [receipt limits](RECEIPTS.md).
