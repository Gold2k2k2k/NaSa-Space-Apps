# FireTrace demonstration methods

These methods describe the code, not an externally validated fire-monitoring
service. Presets are reproducible **generated-demo-v2** fixtures. A FIRMS-shaped
CSV upload supplies detections; it does not establish complete observation
coverage, absence of fire, fire cause, burned area, or source authenticity.

## Observations and target cells

Coordinates use the MODIS sinusoidal sphere radius 6,371,007.181 m, with
`x = R * longitude_radians * cos(latitude)` and `y = R * latitude_radians`.
`G1K_y_x` bins are exactly 1,000 m in that projection. They are a target grid,
**not native MODIS tile pixels**. Point assignment does not implement footprint
intersection or bow-tie correction. Scan × track area is retained as metadata;
neither it nor point density establishes burned area. Missing scan/track
dimensions use nominal 1 km MODIS or 0.375 km VIIRS defaults. Individual missing
flags, quality counts and event `footprint_basis` distinguish these defaults
from supplied dimensions. They are metadata, not measured footprint areas.

Confidence classes have explicit heuristic weights: low 0.45, nominal 0.8, high
1.0, unknown 0. Missing confidence is excluded at the lowest supported filter.
These weights are not probabilities. Missing FRP and brightness temperatures
remain missing, distinct from a measured FRP of zero. Missing acquisition time
and day/night remain unknown rather than becoming a fabricated afternoon pass.

Within a target cell, source type and day/night class, timestamped observations
form anchored 60-minute windows, including across UTC midnight. The first
observation anchors the window, preventing chains from joining arbitrarily
distant passes. Date-only rows retain separate satellite/instrument groups.
Morning and afternoon passes remain separate. Duplicate observation identities
prefer standard processing over NRT/RT/URT, then confidence and measured FRP,
with a canonical tie-break. Supplied processing labels are not authenticated.

Each satellite contributes mean confidence occupancy for the cell; satellite
means within each instrument family are averaged. Repeated rows, additional
subpixels in one cell, or coincident satellites do not add occupancy. FRP sums
distinct observed pixel powers within a satellite/window and averages satellite
totals within a family. This is a simplification: coincident points are not
independently verified to represent the same physical fire.

## Bridge and diagnostics

For supplied positive overlap months in February 2012–December 2024:

`kappa = sum(MODIS monthly occupancy) / sum(VIIRS monthly occupancy)`.

At least three overlap months are required. Otherwise 0.58 is a labeled demo
assumption, and a harmonized verdict using VIIRS is UNVERIFIABLE. In a month
with both families, `HHE = 0.5 * (M + kappa * V)`; a single-family month uses
`M + kappa * V`. Event contributions sum to that monthly index. HHE is weighted
cell occupancy, not a count of fires or an ecological probability.

Era diagnostics (2012–2017, 2018–2023, and 2024) report their own descriptive
ratios alongside agreement at the **pooled** multiplier. They do not silently
change the applied multiplier. Correlation R² is distinct from agreement:
efficiency is `1 - sum((M - kappa*V)^2) / sum((M - mean(M))^2)`. RMSE and mean
bias retain index units. Constant or empty series have undefined metrics where
appropriate. These in-sample quantities do not validate the bridge externally.

FRP uses a sum ratio from at least three positive matched MODIS/VIIRS windows;
otherwise the conversion is an explicit identity assumption. Monthly/annual
FRP is **summed observed power in MW across observations**, not energy, a
simultaneous regional power measurement, or burned area. Missing contributions
are counted and never imputed as 12 MW.

2012 and 2018 diagnostics compare the three complete calendar years before
and after the transition. Missing years or zero reference totals produce null
results. Reduction is `100 * (1 - abs(harmonized change) / abs(raw change))`;
it can be negative and is undefined when the raw change is zero. This comparison
cannot distinguish physical changes from sensor changes.

## Source types and calendar coverage

Supplied FIRMS type 0 means presumed vegetation, 1 volcanic, 2 other static-land,
and 3 offshore thermal detection. The guard excludes types 1–3 from the calendar
and retains them in evidence/exports. It does not call every type an industrial
flare. Repeated occupancy over multiple years is a separate persistence flag;
it neither establishes cause nor automatically excludes type-0 records.
Low-FRP daytime patterns are descriptive and do not establish agricultural burns.

Months are `missing`, `records_only`, or `complete`. An absent month becomes
zero only inside declared complete coverage. Generated fixtures declare their
simulated November 2000–November 2026 period; uploads do not acquire that claim.
Recorded-only totals remain visible but cannot produce a verified regime
comparison. Reference distributions use available same-month values within
2001–2020, never a fallback to recent/focus data. Rule 1 requires a complete
focus period and at least five complete reference-month periods.

Quantiles use linear interpolation. Empirical percentile uses the midrank
`100 * (number below + 0.5 * number equal) / n`. The robust anomaly scale is the
explicit demo heuristic `max(0.7413 * IQR, 0.5, 0.18 * median)`. Percent change
is undefined for a zero reference median. Night share uses unrounded activity
among observations with known day/night labels and is undefined without them.

Annual OLS and Theil–Sen trends use complete years only, in index units per
decade. Partial totals remain labeled partial. The 36-dekad profile supports a
shortest cyclic window containing 90% of positive baseline activity, including
seasons spanning December/January. Missing or flat profiles leave the season
undefined. The onset, peak, cessation and duration are descriptive summaries.

Rules version `2026-11-15.3` preserves the preceding-month context even when it
falls outside the selected display window. That separate context is bound into
Q7 and the receipt; the displayed/exported matrix keeps exactly the requested
years. It fixes January's preceding December year, limits
early-onset findings to the two months before the cyclic onset, and treats
high Z as elevated even when P95 is not exceeded. Nighttime activity does not
establish crown fire or continuous burning. All verdict names are demo labels.
Frozen `.1` rules exist solely to verify earlier receipts with their original
hash, scope and limitations; they are not used for new analyses.

## Counterfactual snapshots

Every analysis has a content-derived ID binding geometry, retained source rows,
options, calculation source digest, reference time and lineage. Changing a
parameter creates a new snapshot. A focus-to-median experiment is explicitly a
hypothetical **metric**: reference climatology and observed raw counts, HHE, FRP
and source records stay fixed. The modeled cell value, annual metric sum/trend,
rank, focus dekad profile and query evidence are rebuilt together. Where a
zero observed total prevents a defined dekad allocation, that modeled profile
is missing. A scenario is neither an observed detection archive nor new evidence.

The snapshot reference defaults to the fixed demo instant 2026-11-14T00:00:00Z
and can be supplied explicitly with a UTC offset. Trace timestamps identify that
reference, not execution time. Run/receipt/package equality is reproducible
across processes for the same canonical inputs, code, reference and documentation.
The local cache copies snapshots on both sides, rejects ID collisions, and
evicts least recently used entries above 16 snapshots or 64 MiB of serialized
content. Cache eviction or a server restart makes a run unavailable; save its
receipt and audit ZIP for durable evidence.

## Fixture dates and primary references

The generator removes pre-November-2000 MODIS records, preserves small-fire
omission on both sides of 2012, includes NOAA-21, and converts nominal local
solar times to UTC. These times are synthetic, not orbital ephemerides.
Fixture mission starts follow the FIRMS availability examples: MODIS
2000-11-01, S-NPP 2012-01-20, NOAA-20 2018-04-01, NOAA-21 2024-01-17. S-NPP
fixture delivery stops at 2026-11-02 15:40 UTC, following NOAA's final update
rather than the earlier 13:00 notice. This corrects impossible inputs
without claiming the fixtures reproduce any real event. The six demo regimes
and twelve trap scenarios remain passing after these corrections.

Sources checked November 14, 2026:

- [NASA FIRMS VIIRS fields and source types](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html)
- [NASA FIRMS MODIS fields](https://firms.modaps.eosdis.nasa.gov/descriptions/FIRMS_MODIS_Firehotspots.html)
- [FIRMS API availability examples](https://firms.modaps.eosdis.nasa.gov/content/academy/data_api/firms_api_use.html)
- [FIRMS active-fire products and limitations](https://firms.modaps.eosdis.nasa.gov/content/active_fire/)
- [USGS/LP DAAC sinusoidal projection documentation](https://lpdaac.usgs.gov/documents/2124/VNP64_User_Guide_v1.1.pdf)
- [NOAA constellation spacing](https://www.nesdis.noaa.gov/news/noaa-21-operational)
- [NOAA final S-NPP delivery cessation update](https://www.nesdis.noaa.gov/news/update-4-cessation-of-suomi-national-polar-orbiting-partnership-s-npp-data-users-november-02-2026-1540-utc-and-decommissioning-issued-november-2-2026-1800-utc)

The core algorithms are original project code. These references supply product
semantics and physical/model definitions, not copied implementations.
