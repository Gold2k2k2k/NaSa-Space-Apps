# FireTrace — follow the season, question the evidence

## Problem and intended impact

A land or forest manager comparing historical satellite hotspot counts can
mistake a sensor change for a change on the ground. MODIS and VIIRS observe
thermal activity with different sampling and resolution. A larger count does
not directly mean more physical fires, more burned forest or higher future risk.

FireTrace helps that manager identify recorded seasonal periods for closer
review, compare assumptions and carry a reproducible evidence snapshot to local
experts. It does not issue operational warnings. We have not yet tested it with
real land managers or measured changes in management outcomes.

## What we built

An original Python/FastAPI pipeline and a zero-build, offline dashboard connect
five views: Calendar, Sensor Bridge, Audit & Receipt, Schemas and Trap Bench.
The three-step workflow is **choose evidence → review periods → carry evidence**.
Every analysis retains its source, geometry, filters, model, queries and run ID.
Six exports include an audit ZIP and a receipt that can be checked offline.

Our real case clips 16,258 NASA FIRMS records to a Central Highlands study
rectangle in Vietnam: 4,143 MODIS and 12,115 S-NPP VIIRS rows. It includes MODIS
2001–2024 and VIIRS 2012–2024. This rectangle is not a verified administrative,
forest or protected-area boundary. The [manifest](../../app/data/central-highlands.manifest.json)
records all 37 NASA originals, hashes, versions, retrieval metadata and the exact
transformation. Generated presets remain separately labeled demonstrations.

## Method and creative contribution

We normalize confidence, time and source metadata, group observations into 1 km
sinusoidal cell windows, and compare family occupancy with a fitted multiplier.
The result, HHE, is a weighted index rather than a fire count. A separate matched
window fit scales VIIRS FRP; FRP stays sampled power in MW, not energy. Supplied
non-vegetation types can be excluded without claiming a verified fire cause.

For the real case, both factors are learned only from 2013–2020 and frozen for
assessment in 2021–2024. Windows are split before fitting at those boundaries.
The available same-month 2001–2020 reference remains descriptive. Changing the
display period, focus, audience or metric does not retune the model. Changing
confidence or the source-type guard refits only its declared training profile.

Our contribution is the connection between an inspectable sensor comparison,
explicit unknown coverage, immutable experiments and a portable manager brief.
Original code and reproducible fixtures make those claims inspectable without a
remote AI service, private database or live network connection.

## Evidence, including unfavorable results

At nominal-or-high confidence with the non-vegetation guard on, the case uses
κ = 0.18252710 and FRP factor = 1.75705295. Training has 73 positive monthly pairs
and 130 positive matched power windows. Held-out occupancy has 43 pairs,
R² = 0.841172, RMSE = 3.927599 index units and efficiency = 0.786767.

Held-out FRP has only 35 matched windows, R² = 0.101068, RMSE = 45.475956 MW and
efficiency = −5.058486. This poor power agreement limits the method; we do not
present it as successful radiative-power validation. Pair selection excludes
missing/nonpositive pairs and cannot establish complete sampling. Neither sensor
is independent ground truth. Exact results and exclusions are retained in the
[model report](results/model-evaluation.json).

The recorded reference suggests February, March and January as periods to
review, with unequal support considered explicitly. February 2024 is the initial
comparison because February has the largest defined reference median, not because
we searched held-out anomalies. It shows about 34.96 HHE against a 45.19 reference
median. It remains **UNVERIFIABLE** for a verified hazard conclusion: detection
archives establish records, not complete observation coverage or absence of fire.

## Relevance, limits and next step

FireTrace addresses the MODIS/VIIRS hotspot-calendar challenge with actual NASA
historical records, a selectable study extent, an auditable harmonization method
and evidence exports. Accessibility includes keyboard calendar navigation,
reduced motion, local fonts, alternative tables and phone layouts.

Next, validate against independent incidents, land cover and coverage products,
and observe land managers completing a review task. Research sensor-specific
sampling and FRP mismatch before making stronger physical claims. Modeled passes
are illustrative, not ephemeris predictions. No causal, burned-area, live-risk or
operational-readiness claim is made. See [sources](../../SOURCES.md),
[AI disclosure](../../AI-DISCLOSURE.md) and [license](../../LICENSE).
