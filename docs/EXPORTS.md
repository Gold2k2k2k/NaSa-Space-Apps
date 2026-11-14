# Exports and modeled observation opportunities

All six downloads consume the same immutable run. Save the audit ZIP before
restarting the server or allowing its bounded cache to evict the run.

| Download | Contents |
| --- | --- |
| Hotspots CSV | Every retained cell-window event, including excluded source types; inclusion, missing measurements, confidence, source and timing fields |
| Calendar CSV | Active metric and mode, observed counts/HHE, coverage, nullable reference statistics, percentile and scenario labels |
| GeoJSON | Complete AOI geometry, holes and components, plus every retained event and its inclusion flag |
| iCalendar | Every modeled opportunity in the stored five-day window and the next full historical peak-month windows |
| Receipt JSON | Full calendar, queries, decision, metadata, source/reference/code identities and modeled schedule |
| Audit ZIP | All exports, retained accepted rows, full inputs, matching app/verifier sources, method documentation and a file-hash manifest |

Hotspot downloads are complete by default. Optional Python `limit=` requests
are labeled previews; map rendering samples are separate. Missing CSV values
are empty fields, distinct from numeric zero. CSV text fields beginning with
spreadsheet formula characters receive an apostrophe. GeoJSON retains the full
geometry and includes an export-scope foreign member. ICS normalizes and escapes
newlines/controls and folds UTF-8 content lines at 75 octets. All-day month events
end on the next month's first day, exclusively, including leap-year February.
Line folding and text escaping follow [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.1).

## Schedule model and references

Run-bound schedules use the stored reference time; counterfactuals preserve it.
`GET /api/passes?run_id=...` returns that same five-day schedule. Standalone
`/api/passes?lat=...&lon=...&days=...` uses current UTC unless an explicit
timezone-aware `reference_time` is supplied. References are supported from
2000–2100 and windows from 1–16 days. Every returned start lies in the half-open
reference window; counts describe all returned rows, without silent truncation.

These are **approximate modeled opportunities**, using nominal solar times,
a schematic date/track phase, declared swath widths and a spherical Earth.
They are not propagated satellite positions. Viewing elevation and ground
zenith are complements; the sensor off-nadir angle is a separate quantity.
The geometry uses radius 6,371.0088 km and satellite altitude, rather than the
flat-Earth `atan(distance / altitude)` shortcut. Day/night labels indicate
nominal model branches, not computed illumination at polar locations.

NOAA-21 precedes NOAA-20 by a schematic 50 minutes, with historical S-NPP between
them. Nominal local times do not establish actual current orbit phase. Known
FIRMS product-start dates are applied. S-NPP is excluded after November 2, 2026
15:40 UTC, following [NOAA's final delivery-cessation update](https://www.nesdis.noaa.gov/news/update-4-cessation-of-suomi-national-polar-orbiting-partnership-s-npp-data-users-november-02-2026-1540-utc-and-decommissioning-issued-november-2-2026-1800-utc).
The model supplies no ephemerides, cloud conditions, actual instrument scheduling,
or operational accuracy. Historical peak-month events are labeled **not a
forecast**. See [methods and primary references](SCIENCE.md).

The bundled synthetic upload samples are in `app/web/static/samples/`; their
README states their invented provenance. The three current reference receipts
come from `examples/*.json`; regenerate all five sample artifacts with
`python scripts/generate_examples.py`, or add `--check` to detect stale output.
Earlier v1 reference receipts remain in `tests/fixtures/legacy_receipts/` solely
to test the narrower historical verification contract.
