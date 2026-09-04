"""Coordinate, CRS, and footprint-polygon utilities owned by Member 1 (M1).

This module replaces the earlier stub. It is deliberately independent of any
specific sensor: axis-aligned rasters (TMC/OHRC GeoTIFFs) build their footprint
straight from ``bounds``, while non-rectangular / non-georeferenced products
(IIRS pushbroom swaths) build it from an explicit list of corner points parsed
out of their PDS4 label. Both paths converge on the same GeoJSON polygon shape
so downstream code (catalogue.py, overlap.py) never needs to know which sensor
produced a given record.
"""

from __future__ import annotations

from typing import Any

from rasterio.crs import CRS
from shapely.geometry import Polygon, box, mapping
from shapely.ops import transform as shapely_transform
import pyproj


# All comparisons happen in this frame, NOT Earth WGS84. Chandrayaan-2 TMC,
# OHRC, and IIRS products are all archived against the Moon 2000 geographic
# frame, and PROJ correctly refuses to transform between Moon and Earth
# ellipsoids (they are different celestial bodies) -- so WGS84 must never be
# used as the common comparison CRS for this project's data.
MOON_2000_GEOGRAPHIC = (
    'GEOGCRS["Moon 2000",DATUM["D_Moon_2000",'
    'ELLIPSOID["Moon_2000_IAU_IAG",1737400,0,LENGTHUNIT["metre",1]]],'
    'PRIMEM["Reference Meridian",0],'
    'CS[ellipsoidal,2],AXIS["geodetic latitude (Lat)",north],'
    'AXIS["geodetic longitude (Lon)",east],ANGLEUNIT["degree",0.0174532925199433]]'
)


def bounds_to_polygon(bounds: dict[str, float]) -> Polygon:
    """Build an axis-aligned shapely polygon from a west/south/east/north dict."""
    return box(bounds["west"], bounds["south"], bounds["east"], bounds["north"])


def corners_to_polygon(corners: list[tuple[float, float]]) -> Polygon:
    """Build a (possibly non-rectangular) polygon from an ordered list of (lon, lat) corners.

    Pushbroom-scan products like IIRS have a swath footprint that is a rotated
    quadrilateral, not an axis-aligned box, so their real spatial extent must
    come from actual corner points rather than a min/max bounding box.
    """
    if len(corners) < 3:
        raise ValueError(f"need at least 3 corner points to build a footprint polygon, got {len(corners)}")
    polygon = Polygon(corners)
    if not polygon.is_valid:
        # Corners are occasionally listed in a crossed (bowtie) order in raw
        # labels; the convex hull recovers the intended footprint in that case.
        polygon = polygon.convex_hull
    return polygon


def polygon_to_bounds(polygon: Polygon) -> dict[str, float]:
    """Return the west/south/east/north envelope of a polygon (for legacy bbox code paths)."""
    west, south, east, north = polygon.bounds
    return {"west": west, "south": south, "east": east, "north": north}


def reproject_polygon(polygon: Polygon, src_crs: Any, dst_crs: Any = None) -> Polygon:
    """Reproject a polygon between CRSs, resolving lunar frames via a synthetic authority.

    ``dst_crs=None`` (the default) means "compare in the shared Moon 2000
    geographic frame", which is correct for this project's data -- never pass
    Earth WGS84 here.
    """
    src = _resolve_crs(src_crs)
    dst = _resolve_crs(dst_crs)
    if src == dst:
        return polygon
    transformer = pyproj.Transformer.from_crs(src.to_wkt(), dst.to_wkt(), always_xy=True)
    return shapely_transform(lambda x, y, z=None: transformer.transform(x, y), polygon)


def _resolve_crs(value: Any) -> CRS:
    """Best-effort CRS resolution that tolerates missing/garbled lunar CRS strings."""
    if isinstance(value, CRS):
        return value
    if value is None:
        return CRS.from_wkt(MOON_2000_GEOGRAPHIC)
    try:
        return CRS.from_user_input(value)
    except Exception:
        return CRS.from_wkt(MOON_2000_GEOGRAPHIC)


def footprint_geojson(record: dict[str, Any]) -> dict[str, Any]:
    """Return a GeoJSON Feature for a record's footprint, in the record's native CRS.

    Accepts either an axis-aligned ``record["bounds"]`` (TMC/OHRC) or an explicit
    ``record["corners"]`` list of (lon, lat) pairs (IIRS and other swath products).
    """
    if record.get("corners"):
        polygon = corners_to_polygon(record["corners"])
    elif record.get("bounds"):
        polygon = bounds_to_polygon(record["bounds"])
    else:
        raise ValueError("record has neither 'bounds' nor 'corners' to build a footprint from")
    return {
        "type": "Feature",
        "properties": {"file_path": record.get("file_path"), "crs": record.get("crs")},
        "geometry": mapping(polygon),
    }


def real_intersection_fraction(
    record_a: dict[str, Any],
    record_b: dict[str, Any],
    *,
    relative_to: str = "a",
) -> float:
    """Return the true polygon-intersection fraction between two records' footprints.

    Unlike a bounding-box check, this handles rotated/non-rectangular footprints
    (IIRS swaths) correctly and reprojects both footprints into a common
    geographic frame before intersecting, per Section 4 of the dataset strategy
    ("Do NOT assume broad coordinate bounding boxes imply useful optical overlap").
    """
    poly_a = _footprint_polygon(record_a)
    poly_b = _footprint_polygon(record_b)
    poly_a = reproject_polygon(poly_a, record_a.get("crs"))
    poly_b = reproject_polygon(poly_b, record_b.get("crs"))
    if not poly_a.is_valid or not poly_b.is_valid or poly_a.area == 0 or poly_b.area == 0:
        return 0.0
    intersection = poly_a.intersection(poly_b)
    if intersection.is_empty:
        return 0.0
    denominator = poly_a.area if relative_to == "a" else poly_b.area
    return float(intersection.area / denominator) if denominator else 0.0


def _footprint_polygon(record: dict[str, Any]) -> Polygon:
    if record.get("corners"):
        return corners_to_polygon(record["corners"])
    return bounds_to_polygon(record["bounds"])