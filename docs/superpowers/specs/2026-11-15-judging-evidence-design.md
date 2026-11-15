# FireTrace: judging evidence and forest-manager workflow

Status: approved by the user in Q7 on November 15, 2026, after builder review.
Date: November 15, 2026. Target: ready before **23:00 Asia/Saigon** today.
Starting implementation revision: `e3c1670` on `codex/firetrace-upgrade`.

## Intent and decisions

Improve FireTrace against the Space Apps judging criteria by making a useful,
traceable scientific demonstration for **forest and land managers**. The core
question is: which periods in a selected area have recorded recurring or unusual
thermal detections, and what evidence and limitations should inform further review?

The user selected approach A below and requested evaluation/design approval before
product changes. The user specifically requested real FIRMS data. A Vietnam study
extent is proposed below from verified data availability; it is a design proposal,
not a claim that the user supplied an administrative boundary.

Keep Python 3.11/FastAPI, the zero-build browser application, five existing views,
original core algorithms, offline demonstration and all six current downloads.
Deployment, repository-visibility changes, external posting, and actual competition
submission are outside this implementation approval.

## Authoritative sources and their limits

- The [current 2026 challenge](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/)
  calls for a harmonized MODIS/VIIRS historical burning-activity calendar for a
  selected area, supporting examination of patterns, unusual conditions and
  critical periods. Its indexed official summary was verified; direct fetch fails.
- The requested [current judging guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)
  returns 502/timeouts. Exact 2026 scoring, weights, demo limits and award eligibility
  remain unverified.
- The user explicitly accepted the dated official
  [2025 rubric](https://spaceapps-v2-staging.s3.amazonaws.com/media/documents/Final_Space_Apps_2025_Judging_Guidelines_for_web.pdf)
  as a limited reference. It identifies Impact, Creativity, Validity, Relevance and
  Presentation and uses a holistic 1–5 judgment. Do not invent a weighted score,
  NASA rating or probability of winning. Its demo-format rules are not asserted
  as current 2026 rules.
- The [2026 terms](https://www.spaceappschallenge.org/legal/) require accessible/
  open original work and citations/licensing for third-party resources. The
  repository currently remains private and has no root license. Prepare a
  release-ready source/evidence package and explicit credits; publishing requires
  a separate concrete action by an authorized owner.

## Current gaps and criterion-to-evidence mapping

This is our qualitative assessment, not an official score.

| Criterion | Existing strength | Important gap | Proposed improvement and proof |
| --- | --- | --- | --- |
| Impact | Calendar, AOI controls and audience lenses | No demonstrated land-manager task or real case in bundled data | One real study extent; three-step review flow; manager brief identifying relevant periods, evidence and uncertainty |
| Creativity | Sensor comparison, scenarios and portable receipts | Technical controls alone do not explain the contribution | Connect a selected month to raw/harmonized evidence and an inspectable assumption change; explain this combination without claiming it is globally unprecedented |
| Validity | Defined methods, missingness and regression suites | Three confirmed defects; no held-out observational method assessment | Repair defects; freeze a calibration policy before evaluating later observations; report sample sizes, errors and limitations, including unfavorable results |
| Relevance | MODIS/VIIRS-shaped pipeline and full geometry | Bundled presets and upload examples are invented | Integrate actual NASA FIRMS archive rows with URLs, versions, retrieval times and hashes into the main workflow and exports |
| Presentation | Five coherent accessible views | Judges must currently infer the user story from technical panels | Guided entry, plain-language brief, concise English submission narrative and slide outline with traceable screenshots/evidence |

## Approaches considered

**A — A bounded judging demonstration, selected by the user.** Repair known
defects, integrate one real offline NASA case, provide evidence for a limited
scientific comparison and guide one land-manager task through the existing UI.
This concentrates effort before 23:00 while exposing what has not been validated.

**B — A deeper methods-research package.** Prioritize broader spatial validation,
alternative harmonization policies and more extensive independent ecological
assessment. This could provide stronger research evidence, but data curation,
external interpretation and evaluation make its completion uncertain tonight.

## Real data: verified research and proposed product snapshot

The research download has completed from NASA's public
[annual-country catalog](https://firms.modaps.eosdis.nasa.gov/data/country/yearly_summary_files.txt):

| Source | Years | Files |
| --- | --- | --- |
| MODIS Collection 6.1 Vietnam archive | 2001–2024 | 24 |
| S-NPP VIIRS Vietnam archive | 2012–2024 | 13 |

All **37 files**, **105,748,823 bytes**, have been downloaded, checked against
catalog sizes, parsed as CSV and hashed. The national files contain **1,339,562
rows**. No credentials or MAP_KEY were used. They currently reside only in the
ignored research cache `.superpowers/spaceapps-judging-2026-11-15/firms-research/`.

Proposed primary extent is a **Central Highlands study rectangle**:
`[107.8, 12.5, 108.5, 13.1]` in west/south/east/north order. It is not a province,
protected-area or forest boundary. Clipping yields **16,258 accepted rows**:
4,143 MODIS and 12,115 VIIRS. All pass the existing row normalizer; none have its
missing-measurement flags. Supplied types are 16,172 vegetation-type, 85 other
static-land and one offshore-type row; retain original classifications, including
unexpected supplied types, rather than editing them to fit the story.

The full source routes are catalog-derived, for example
[MODIS 2001](https://firms.modaps.eosdis.nasa.gov/data/country/modis/2001/modis_2001_Vietnam.csv),
[MODIS 2024](https://firms.modaps.eosdis.nasa.gov/data/country/modis/2024/modis_2024_Vietnam.csv),
[S-NPP 2012](https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2012/viirs-snpp_2012_Vietnam.csv)
and [S-NPP 2024](https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2024/viirs-snpp_2024_Vietnam.csv).

After approval, create a compact bundled AOI CSV and public provenance manifest,
plus an original standard-library rebuild script. Keep the 101 MiB national
research cache out of Git. The manifest records all 37 original URLs, byte sizes,
SHA-256 values, collection/version information, retrieval times, clipping extent,
transform version, accepted/rejected counts and the bundled subset hash. Rebuilding
from the same frozen inputs reproduces the subset. Upstream changes are reported
explicitly rather than silently accepted as the same snapshot.

## Scientific contract

### Reported detections and observation coverage

An annual archive file does not establish complete observation coverage. Keep
archive availability, recorded detections and unknown observability distinct.
Do not populate `complete_periods` simply because annual files were retrieved.
An empty month does not establish no fire. Real-case comparisons remain
`records_only`/missing and **UNVERIFIABLE where the existing coverage requirements
are unmet**. The brief explains this as an evidence limit rather than hiding it.

Keep the current engine's descriptive reference behavior explicit: a same-month
distribution may use available **recorded** reference values, labeled with its
records-only coverage, contributing-year count and exclusions. Reference months
without recorded data remain missing, not zero. A descriptive median, profile or
percentile is therefore available when samples exist; it does not establish a
verified fire anomaly. When no reference values exist, these comparisons and the
median experiment remain unavailable. "Full reference history" means all available
values in the declared interval, not a claim of complete physical observation.

The real case supports historical review of **reported thermal detections**.
It does not establish wildfire cause, forest-only activity, burned area, physical
fire counts, an operational warning, or an ecological risk forecast. Keep HHE as
an explicitly modeled occupancy index and FRP as observed power, not energy.

### Reference and held-out assessment

Retain the selected **2001–2020 same-month reference**. S-NPP does not exist in
2001–2011, and January 2012 is partial; do not fabricate those observations.
Use **2013–2020** as the real case's declared calibration interval, fixed before
the new evaluation. Evaluate **2021–2024** separately with that frozen multiplier.
The main case analysis and evaluation must use the same frozen model; a separate
better-performing variant cannot be presented as validation of the displayed one.
Existing generated presets retain their documented default calibration behavior.

Freeze both occupancy **kappa** and the independently fitted **FRP conversion
ratio** for each canonical source/filter profile. They are estimated only from
2013–2020: occupancy uses supported positive matched months, FRP uses supported
positive matched windows. Changing confidence or the source guard refits that
profile using the same training interval, never held-out observations. Changing
focus, display years, audience, metric mode or the hypothetical median preserves
its numerical factors. Held-out metrics use exactly those profile factors.
Store interval, filter options, training-input identity, fitted/assumed basis and
sample counts with the model. Existing insufficient-data fallbacks remain visibly
assumed; a weak fit is not repaired using later observations. Sensitivity results
from other user-selected profiles are exploratory, not new independent validation.

Report matched-month counts, exclusions, squared correlation, RMSE, mean bias
and efficiency separately for fit and held-out periods. Undefined or weak metrics
remain visible. Do not tune the AOI, cutoff, confidence filter or multiplier to
improve the held-out result. This is temporal out-of-sample agreement between
sensor records, **not independent validation of physical fire occurrence**.
Absent independent ecological evidence or actual user testing, explicitly retain
those as validation gaps. No fabricated testimonials or user-benefit measurements.

## Required reliability repairs

1. **Longitude subdivision:** every bounding-box split advances across all wraps;
   the three-row `-170, -50, 70` CSV terminates. Preserve legal dateline/polar and
   adjacent-component behavior; reject unsupported extents with controlled errors.
2. **GeoJSON dispatch:** non-string `type` values, including nested Feature values,
   produce controlled validation errors rather than unhashable-type HTTP 500s.
3. **Median scenarios:** empirical percentiles use retained full reference
   history (all available samples in the fixed reference interval, with coverage
   labels) rather than the visible matrix. Display-window changes preserve the
   same reference distribution and scenario percentile. Ties use the documented
   empirical midrank; a median scenario must not simply hard-code percentile 50.

Add independent reproductions before repairs and retain regression coverage.

## Product integration

### Case loading and immutable state

Provide a clearly separate real-case entry alongside generated demonstrations.
Load a whitelist-defined bundled dataset and its full geometry/provenance;
subsequent mode, guard, confidence, period, persona and median experiments preserve
those inputs. Arbitrary geometry edits remain explicitly generated demonstrations
unless new observations are supplied. No path can relabel generated data as NASA.

The real case defaults to 2001–2024 and a clearly historical 2024 comparison;
the initial focus month is chosen from the historical reference profile, not by
maximizing a held-out anomaly. Proposed defaults are nominal-or-high confidence,
source guard on, harmonized mode and land-manager audience. Select the largest
defined historical reference median as the initial month; break ties by earliest
month, with January as a labeled navigation fallback if all are undefined.
Collection dates are distinct from analysis/pass
reference times. Mission-start and partial-period limits remain visible.

Bind the subset hash, source manifest identity, geometry, frozen calibration
policy, options and scenario lineage into the run identity and receipts. Include
the real-case manifest and relevant validation report in the audit package. Preserve
complete exports and exact source retention within existing size limits. Regenerate
current examples after intentional source/format changes and document compatibility.

### Manager's three-step flow

1. **Choose evidence:** enter the real study case, inspect place/years, sources and
   the difference between actual archive data and generated examples.
2. **Review periods:** inspect the seasonal profile and selected historical month,
   compare raw and harmonized views, and see a concise explanation of changed
   assumptions, missingness and sample support.
3. **Carry the evidence:** open a manager brief summarizing the question, study
   extent, relevant recorded periods, source/model limitations and next review
   step; retain its run identity and the existing receipt/audit download links.

Implement this within the existing five views using progressive disclosure.
Preserve keyboard access, reduced motion, dynamic-ramp contrast, mobile layout,
source badges, error visibility and latest-request-wins behavior. A new framework,
basemap dependency, live ingestion service or AI chat is unnecessary for this scope.

## Presentation and release-ready evidence

Prepare concise English submission text and an English slide outline with a
Vietnamese team explanation. Seven slides is a conservative proposed format, not
a verified 2026 requirement. The narrative follows a manager's problem, why raw
sensor counts differ, one real case, what the method does, evidence, limitations
and the next validation step. Separate the internal walkthrough from any official
demo length limit, which remains to be checked against the actual current guide.

Prepare data/method/tool citations, dependency/font credits, a proposed Apache-2.0
root license consistent with the published default, and honest AI-assistance/data
generation disclosures. The licensed public-ready source snapshot contains no
credentials or private research cache. Verify its links and offline instructions.
Actual publishing or submission is a separate owner-approved action; the private
repository's current accessibility is not described as submission-ready.

## Acceptance and completion evidence

- All three reported defects have targeted before/after reproductions; malformed
  HTTP geometry returns 422 and broad-longitude ingestion terminates within a
  documented bounded test interval without silently dropping rows.
- The curated case has exactly reproducible row selection, a valid manifest and
  traceable NASA originals. Every bundled row lies within the declared rectangle.
- No archive-only period becomes complete observation coverage. Missing evidence
  produces the documented limited conclusion; source types and zeros are preserved.
- The frozen calibration and held-out report use disjoint declared years and the
  same model as the displayed case; unfavorable and undefined results are reported.
- Real-case provenance, geometry, reference and calibration survive every supported
  experiment and all six downloads. Fresh and counterfactual receipts verify.
- A narrow/full display-window comparison preserves the median scenario's reference
  percentile, including an asymmetric tied-value independent fixture.
- Actual HTTP/browser checks cover the real-case guided flow, source transitions,
  errors, keyboard use, all downloads and 375/1440 px layouts. Existing workflows
  and required suites pass; test counts are measured, not used as scientific proof.
- Submission narrative, slide outline, limitations, source/AI credits and a
  release-ready source/evidence snapshot exist and have resolvable local links.
- A criterion-by-criterion evidence report states what was demonstrated and what
  remains unverified, including the inaccessible current judging guide, independent
  field validation, actual land-manager testing and external publication.

## Delivery order and scope control

After written-design approval: repair the three defects; build the curated case
and frozen model/evidence; integrate the guided review/brief; prepare the judging
packet and release-ready materials; run targeted then full verification and final
review. Preserve the final period before 23:00 for validation and team handoff.
Use the existing downloaded research snapshot; no live-data dependency is needed.

If evidence is weak, preserve and explain the weak result rather than broadening
the claim. If work overruns, report unfinished acceptance items and their impact;
do not declare the selected scope complete merely because the deadline approaches.

## Builder discretion

The builder may choose focused module boundaries, whitelist route details, exact
brief placement and concise wording within these contracts. The geographic extent,
data/model policy, scientific limitations, delivery scope and deadline are visible
parts of this proposal for the user's approval. Do not silently replace the real
case with generated data or drop the held-out comparison to make the demo appear
more successful.
