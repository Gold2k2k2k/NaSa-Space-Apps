# Analysis inputs and geometry

Analysis years are 2000–2026 and focus months are 1–12. Explicit focus years must
be inside the selected year window. When no focus is supplied, its default follows
the selected window. Modes, audience roles, confidence filters, and booleans are
validated instead of silently changing an invalid value into a default.

Supported GeoJSON inputs are Point, Polygon, MultiPolygon, Feature, and
FeatureCollection. Every component and interior hole is retained. Coordinates
are finite two-dimensional `[longitude, latitude]` positions within Earth bounds.
Rings are closed, oriented, and rotated into a canonical representation; identity
binds the complete geometry rather than its centroid and rounded area alone.

The normalized geometry has a **2,000-position total limit**. Degenerate,
self-intersecting, or self-touching rings and invalid holes are rejected.
Overlapping component interiors must be merged before submission; they are
rejected rather than counted twice. A separate island inside a hole is valid.
Nested Features are not valid geometry objects. Unsupported geometry types and
dimensionalities produce validation errors.

Longitude edges use the shortest interval across the antimeridian. Internal
display/sampling bounds may therefore extend beyond 180 degrees, while GeoJSON
positions and generated detections remain in `[-180, 180]`. Rings winding around
a pole must be split into bounded polygons.

The existing latitude/longitude/radius workflow selects an **approximate
rectangular footprint**, not an exact geodesic circle. Its north/south half-span
is derived from kilometres; its longitude span uses a latitude correction. The
footprint is split at the dateline and clipped at the poles. The actual submitted
geometry determines area and membership. Areas use a spherical-Earth
approximation with mean radius 6,371.0088 km, rather than ellipsoidal survey
measurements. These modeling limits matter near the poles and for large regions.

CSV uploads are limited to **10 MiB and 25,000 rows**. Oversized archives are
rejected with instructions to split them. Headers are trimmed and normalized,
including a UTF-8 BOM; duplicate or empty headers and malformed quoting are
rejected. Each row is normalized and checked before acceptance. Invalid rows do
not affect AOI bounds or the default focus date. A mixed-validity upload returns
accepted/rejected counts and a bounded set of rejection examples; an entirely
invalid upload is rejected.

Uploaded geometry bounds follow the smallest longitude interval containing its
detections and include padding. The focus month/year follows the latest complete
date, even if rows are unsorted. Normalized content identities are independent of
row order. Instrument and satellite values determine sensor counts, including
J1/NOAA-20 and J2/NOAA-21 aliases. Invalid supplied instruments, satellites,
confidence ranges, acquisition times, footprints, radiative power, and source-type
codes are rejected. Valid zero coordinates and zero FRP remain zero.

An accepted hotspot-only CSV does not by itself prove complete observation
coverage, wildfire cause, burned area, or an absence of fire in missing months.
