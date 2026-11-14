"""Bounded 2-D AOI geometry with explicit longitude-wrap semantics.

Edges follow the shortest longitude interval. Areas use a spherical-Earth
approximation; point/radius inputs select an approximate rectangular footprint,
split at the dateline and clipped at the poles rather than inventing coordinates.
"""
from __future__ import annotations

import math
from typing import Any

from app.canonical import canonical_json

MAX_VERTICES = 2000
EARTH_RADIUS_KM = 6371.0088
EPSILON = 1e-10


def wrap_longitude(lon: float) -> float:
    value = (lon + 180.0) % 360.0 - 180.0
    return 0.0 if value == 0 else value


def finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _coordinate(point: Any) -> list[float]:
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        raise ValueError("Each position must contain exactly [longitude, latitude]")
    lon, lat = finite_number(point[0], "longitude"), finite_number(point[1], "latitude")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("Geometry coordinates must be inside Earth bounds")
    return [wrap_longitude(lon), lat]


def unwrap_ring(ring: list[list[float]]) -> list[list[float]]:
    result = [list(ring[0])]
    for lon, lat in ring[1:]:
        previous = result[-1][0]
        lon += 360 * round((previous - lon) / 360)
        result.append([lon, lat])
    if abs(result[-1][0] - result[0][0]) > EPSILON:
        raise ValueError("A ring winding around a pole must be split into bounded polygons")
    return result


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p) -> bool:
    return (abs(_cross(a, b, p)) <= EPSILON
            and min(a[0], b[0]) - EPSILON <= p[0] <= max(a[0], b[0]) + EPSILON
            and min(a[1], b[1]) - EPSILON <= p[1] <= max(a[1], b[1]) + EPSILON)


def _intersects(a, b, c, d) -> bool:
    if (max(a[0], b[0]) < min(c[0], d[0]) - EPSILON
            or max(c[0], d[0]) < min(a[0], b[0]) - EPSILON
            or max(a[1], b[1]) < min(c[1], d[1]) - EPSILON
            or max(c[1], d[1]) < min(a[1], b[1]) - EPSILON):
        return False
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if ((ab_c > EPSILON and ab_d < -EPSILON) or (ab_d > EPSILON and ab_c < -EPSILON)) and (
            (cd_a > EPSILON and cd_b < -EPSILON) or (cd_b > EPSILON and cd_a < -EPSILON)):
        return True
    return any(_on_segment(x, y, point) for x, y, point in ((a, b, c), (a, b, d), (c, d, a), (c, d, b)))


def _signed_area(ring) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2


def validate_polygon_ring(value: Any, *, hole: bool = False) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or not 3 <= len(value) <= MAX_VERTICES:
        raise ValueError(f"A polygon ring needs 3–{MAX_VERTICES} positions")
    ring = [_coordinate(point) for point in value]
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(ring) > MAX_VERTICES or len(set(map(tuple, ring[:-1]))) < 3:
        raise ValueError("Polygon ring has too few distinct vertices or exceeds the vertex limit")
    unwrapped = unwrap_ring(ring)
    size = len(unwrapped) - 1
    for i in range(size):
        if unwrapped[i] == unwrapped[i + 1]:
            raise ValueError("Polygon ring contains a zero-length edge")
        for j in range(i + 1, size):
            if j == i + 1 or (i == 0 and j == size - 1):
                continue
            if _intersects(unwrapped[i], unwrapped[i + 1], unwrapped[j], unwrapped[j + 1]):
                raise ValueError("Polygon ring self-intersects or touches itself")
    area = _signed_area(unwrapped)
    if abs(area) <= EPSILON:
        raise ValueError("Polygon ring must enclose a non-zero area")
    if (area < 0) != hole:
        ring = list(reversed(ring))
    vertices = ring[:-1]
    start = min(range(len(vertices)), key=lambda i: tuple(vertices[i]))
    vertices = vertices[start:] + vertices[:start]
    return vertices + [list(vertices[0])]


def point_in_polygon(lon: float, lat: float, ring: list[list[float]], *, boundary: bool = True) -> bool:
    points = unwrap_ring(ring)
    anchor = sum(p[0] for p in points[:-1]) / (len(points) - 1)
    lon += 360 * round((anchor - lon) / 360)
    point = [lon, lat]
    inside = False
    for a, b in zip(points, points[1:]):
        if _on_segment(a, b, point):
            return boundary
        if (a[1] > lat) != (b[1] > lat):
            crossing = a[0] + (lat - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if lon < crossing:
                inside = not inside
    return inside


def _aligned_rings(first, second):
    a, b = unwrap_ring(first), unwrap_ring(second)
    shift = 360 * round((sum(p[0] for p in a[:-1]) / (len(a) - 1)
                         - sum(p[0] for p in b[:-1]) / (len(b) - 1)) / 360)
    return a, [[lon + shift, lat] for lon, lat in b]


def _rings_intersect(first, second) -> bool:
    a, b = _aligned_rings(first, second)
    return any(_intersects(p, q, r, s) for p, q in zip(a, a[1:]) for r, s in zip(b, b[1:]))


def _rings_cross(first, second) -> bool:
    a, b = _aligned_rings(first, second)
    for p, q in zip(a, a[1:]):
        for r, s in zip(b, b[1:]):
            if _cross(p, q, r) * _cross(p, q, s) < -EPSILON ** 2 and _cross(r, s, p) * _cross(r, s, q) < -EPSILON ** 2:
                return True
    return False


def _validate_polygon(value: Any) -> list[list[list[float]]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("Polygon coordinates must contain an exterior ring")
    exterior = validate_polygon_ring(value[0])
    holes = [validate_polygon_ring(ring, hole=True) for ring in value[1:]]
    for i, hole in enumerate(holes):
        if not all(point_in_polygon(*p, exterior, boundary=False) for p in hole[:-1]) or _rings_intersect(exterior, hole):
            raise ValueError("Polygon holes must be strictly inside their exterior ring")
        for other in holes[:i]:
            if (_rings_intersect(hole, other) or point_in_polygon(*hole[0], other)
                    or point_in_polygon(*other[0], hole)):
                raise ValueError("Polygon holes must not overlap or nest")
    return [exterior, *sorted(holes, key=canonical_json)]


def box_geometry(west: float, east: float, south: float, north: float) -> dict[str, Any]:
    south, north = max(-90, south), min(90, north)
    if east - west >= 360:
        west, east = -180.0, 180.0
    while west < -180:
        west, east = west + 360, east + 360
    while west >= 180:
        west, east = west - 360, east - 360
    polygons = []
    left = west
    while left < east - EPSILON:
        right = min(east, left + 90, 180 if left < 180 else 360)
        offset = 360 if left >= 180 else 0
        a, b = left - offset, right - offset
        polygons.append([[[a, south], [b, south], [b, north], [a, north], [a, south]]])
        left = right
    if not polygons:
        raise ValueError("Bounding region must have positive longitude extent")
    return {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1 else {
        "type": "MultiPolygon", "coordinates": polygons}


def bounding_geometry(points: list[list[float]]) -> dict[str, Any]:
    positions = [_coordinate(point) for point in points]
    longitudes = sorted({p[0] for p in positions})
    gaps = [(longitudes[(i + 1) % len(longitudes)] + (360 if i == len(longitudes) - 1 else 0) - lon, i)
            for i, lon in enumerate(longitudes)]
    _, gap = max(gaps)
    west = longitudes[(gap + 1) % len(longitudes)]
    east = longitudes[gap]
    if east < west:
        east += 360
    south, north = min(p[1] for p in positions), max(p[1] for p in positions)
    pad_lon, pad_lat = max(0.15, (east - west) * 0.1), max(0.15, (north - south) * 0.1)
    return normalize_geometry(box_geometry(west - pad_lon, east + pad_lon, south - pad_lat, north + pad_lat))


def point_geometry(lon: float, lat: float, radius_km: float) -> dict[str, Any]:
    lon, lat = _coordinate([lon, lat])
    radius = finite_number(radius_km, "radius_km")
    if not 5 <= radius <= 250:
        raise ValueError("radius_km must be between 5 and 250")
    dlat = radius / 111.32
    dlon = radius / (111.32 * max(0.15, math.cos(math.radians(lat))))
    return box_geometry(lon - dlon, lon + dlon, lat - dlat, lat + dlat)


def normalize_geometry(value: Any, *, radius_km: float = 60) -> dict[str, Any]:
    polygons = []
    remaining = MAX_VERTICES

    def extract(item):
        nonlocal remaining
        if not isinstance(item, dict):
            raise ValueError("GeoJSON must be an object")
        kind = item.get("type")
        if kind == "Feature":
            geometry = item.get("geometry")
            if not isinstance(geometry, dict) or geometry.get("type") not in {"Point", "Polygon", "MultiPolygon"}:
                raise ValueError("Feature geometry must be a supported geometry object")
            extract(geometry)
        elif kind == "FeatureCollection":
            features = item.get("features")
            if not isinstance(features, list) or not features or len(features) > MAX_VERTICES // 3:
                raise ValueError("FeatureCollection must contain a bounded non-empty features array")
            for feature in features:
                if not isinstance(feature, dict) or feature.get("type") != "Feature":
                    raise ValueError("FeatureCollection entries must be Features")
                extract(feature)
        elif kind == "Point":
            lon, lat = _coordinate(item.get("coordinates"))
            extract(point_geometry(lon, lat, radius_km))
        elif kind in {"Polygon", "MultiPolygon"}:
            coords = item.get("coordinates")
            shapes = [coords] if kind == "Polygon" else coords
            if not isinstance(shapes, (list, tuple)) or not shapes:
                raise ValueError("Geometry coordinates cannot be empty")
            for shape in shapes:
                if not isinstance(shape, (list, tuple)):
                    raise ValueError("Polygon coordinates must contain rings")
                count = sum(len(ring) if isinstance(ring, (list, tuple)) else MAX_VERTICES + 1 for ring in shape)
                remaining -= count
                if remaining < 0:
                    raise ValueError(f"Geometry exceeds the {MAX_VERTICES}-position limit")
                polygon = _validate_polygon(shape)
                remaining -= sum(len(ring) for ring in polygon) - count
                if remaining < 0:
                    raise ValueError(f"Normalized geometry exceeds the {MAX_VERTICES}-position limit")
                polygons.append(polygon)
        else:
            raise ValueError(f"Unsupported GeoJSON geometry type: {kind!r}")

    extract(value)
    polygons = list({canonical_json(polygon): polygon for polygon in polygons}.values())
    polygons.sort(key=canonical_json)
    # Overlapping components require a union operation, not addition of areas.
    # Reject that unsupported ambiguity explicitly instead of double-counting.
    for i, polygon in enumerate(polygons):
        for other in polygons[:i]:
            if (any(_polygon_contains(*p, other, boundary=False) for p in polygon[0][:-1])
                    or any(_polygon_contains(*p, polygon, boundary=False) for p in other[0][:-1])
                    or any(_rings_cross(first, second) for first in polygon for second in other)):
                raise ValueError("Overlapping polygon components must be merged before analysis")
    return {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1 else {
        "type": "MultiPolygon", "coordinates": polygons}


def geometry_polygons(geometry):
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


def geometry_contains(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    return any(_polygon_contains(lon, lat, p) for p in geometry_polygons(geometry))


def _polygon_contains(lon, lat, polygon, *, boundary=True) -> bool:
    return point_in_polygon(lon, lat, polygon[0], boundary=boundary) and not any(
        point_in_polygon(lon, lat, hole) for hole in polygon[1:])


def bbox_from_ring(ring) -> dict[str, float]:
    points = unwrap_ring(ring)
    west, east = min(p[0] for p in points), max(p[0] for p in points)
    shift = -360 * math.floor((west + 180) / 360)
    return {"lon_min": west + shift, "lon_max": east + shift,
            "lat_min": min(p[1] for p in points), "lat_max": max(p[1] for p in points)}


def geometry_bbox(geometry) -> dict[str, float]:
    boxes = [bbox_from_ring(p[0]) for p in geometry_polygons(geometry)]
    candidates = []
    for anchor_box in boxes:
        anchor = (anchor_box["lon_min"] + anchor_box["lon_max"]) / 2
        shifted = []
        for box in boxes:
            center = (box["lon_min"] + box["lon_max"]) / 2
            shift = 360 * round((anchor - center) / 360)
            shifted.append((box["lon_min"] + shift, box["lon_max"] + shift))
        candidates.append((min(p[0] for p in shifted), max(p[1] for p in shifted)))
    west, east = min(candidates, key=lambda pair: pair[1] - pair[0])
    shift = -360 * math.floor((west + 180) / 360)
    return {"lon_min": west + shift, "lon_max": east + shift,
            "lat_min": min(b["lat_min"] for b in boxes), "lat_max": max(b["lat_max"] for b in boxes)}


def polygon_area_km2(ring) -> float:
    points = unwrap_ring(ring)
    total = sum(math.radians(b[0] - a[0]) * (math.sin(math.radians(a[1])) + math.sin(math.radians(b[1])))
                for a, b in zip(points, points[1:]))
    return abs(total) * EARTH_RADIUS_KM ** 2 / 2


def geometry_area_km2(geometry) -> float:
    return sum(polygon_area_km2(p[0]) - sum(polygon_area_km2(hole) for hole in p[1:])
               for p in geometry_polygons(geometry))


def centroid_of_ring(ring) -> tuple[float, float]:
    points = unwrap_ring(ring)
    twice_area = 2 * _signed_area(points)
    if abs(twice_area) < EPSILON:
        raise ValueError("Cannot find a centroid for a zero-area ring")
    cx = sum((a[0] + b[0]) * (a[0] * b[1] - b[0] * a[1]) for a, b in zip(points, points[1:])) / (3 * twice_area)
    cy = sum((a[1] + b[1]) * (a[0] * b[1] - b[0] * a[1]) for a, b in zip(points, points[1:])) / (3 * twice_area)
    return cy, wrap_longitude(cx)


def geometry_centroid(geometry) -> tuple[float, float]:
    box = geometry_bbox(geometry)
    anchor = (box["lon_min"] + box["lon_max"]) / 2
    latitude = longitude = total = 0.0
    for polygon in geometry_polygons(geometry):
        for index, ring in enumerate(polygon):
            weight = polygon_area_km2(ring) * (1 if index == 0 else -1)
            lat, lon = centroid_of_ring(ring)
            lon += 360 * round((anchor - lon) / 360)
            latitude += lat * weight
            longitude += lon * weight
            total += weight
    if total <= 1e-6:
        raise ValueError("AOI must enclose at least one square metre")
    return latitude / total, wrap_longitude(longitude / total)


def interior_point(geometry) -> tuple[float, float]:
    lat, lon = geometry_centroid(geometry)
    if geometry_contains(lon, lat, geometry):
        return lat, lon
    for polygon in sorted(geometry_polygons(geometry), key=lambda p: -polygon_area_km2(p[0])):
        outer = unwrap_ring(polygon[0])
        rings = [outer] + [_aligned_rings(polygon[0], hole)[1] for hole in polygon[1:]]
        levels = sorted({p[1] for ring in rings for p in ring})
        for low, high in zip(levels, levels[1:]):
            y = (low + high) / 2
            crossings = sorted(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                               for ring in rings for a, b in zip(ring, ring[1:]) if (a[1] > y) != (b[1] > y))
            for left, right in zip(crossings[::2], crossings[1::2]):
                x = wrap_longitude((left + right) / 2)
                if geometry_contains(x, y, geometry):
                    return y, x
    raise ValueError("Could not find an interior sampling point for this AOI")
