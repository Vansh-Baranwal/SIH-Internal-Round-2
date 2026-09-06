"""Real (pixel-level) overlap verification owned by Member 1 (M1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.control import GroundControlPoint
from rasterio.errors import RasterioIOError
from rasterio.transform import from_gcps
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds, WindowError

from .coordinates import real_intersection_fraction


def transform_from_corners(corners: list[tuple[float, float]], width: int, height: int):
    """
    Builds a real pixel<->lonlat affine transform for products (like OHRC
    and IIRS) that open with an identity transform (no map projection baked
    into the file itself) but DO have known real corner coordinates from
    their PDS4 label.

    corners must be in (upper_left, upper_right, lower_right, lower_left)
    order -- the same perimeter-walk order parse_iirs_corners() returns.
    """
    pixel_corners = [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]
    gcps = [
        GroundControlPoint(row=row, col=col, x=lon, y=lat)
        for (lon, lat), (col, row) in zip(corners, pixel_corners)
    ]
    return from_gcps(gcps)


def _window_from_bounds_general(transform, west, south, east, north, raster_width, raster_height):
    """
    Replacement for rasterio.windows.from_bounds() for use with a rotated/
    corner-derived transform (see transform_from_corners above).

    from_bounds() assumes the transform is close to axis-aligned (near-zero
    rotation) -- it inverts just two opposite corners (west,north) and
    (east,south) and treats the result as an axis-aligned pixel window.
    For a transform with real rotation -- confirmed present in IIRS's
    ~900km pole-to-equator swath (the footprint's longitude span visibly
    shifts between the swath's north and south ends -- it is NOT an
    axis-aligned rectangle in lon/lat), unlike OHRC's much shorter ~22km
    swath, which is close enough to axis-aligned that from_bounds() worked
    fine there -- that assumption is wrong and can compute a window that
    lands partly or entirely outside the real raster, even though the
    requested lon/lat region genuinely does overlap real data. This was
    confirmed: IIRS's real polygon overlap with TMC was 0.987 (genuine),
    but the naive from_bounds() window still reported "falls outside file
    extent".

    Fix: invert ALL FOUR corners of the requested region individually, then
    take the min/max row/col across all four -- this correctly bounds a
    rotated region with an axis-aligned pixel window regardless of how much
    rotation is present in the transform.
    """
    inv = ~transform
    corners_world = [(west, north), (east, north), (east, south), (west, south)]
    cols, rows = [], []
    for x, y in corners_world:
        col, row = inv * (x, y)
        cols.append(col)
        rows.append(row)

    col_min, col_max = max(0, min(cols)), min(raster_width, max(cols))
    row_min, row_max = max(0, min(rows)), min(raster_height, max(rows))

    width = col_max - col_min
    height = row_max - row_min
    if width <= 0 or height <= 0:
        return None
    return rasterio.windows.Window(col_min, row_min, width, height)


def _bounds_tuple(bounds: dict[str, float]) -> tuple[float, float, float, float]:
    return bounds["west"], bounds["south"], bounds["east"], bounds["north"]


def check_real_data_at_region(
    file_path: Path,
    region_bounds: tuple[float, float, float, float],
    region_crs: Any,
    *,
    min_valid_fraction: float = 0.5,
    transform_override: Any = None,
) -> dict[str, Any]:
    """Check whether a raster has real (non-nodata) pixel data inside a target region.

    ``transform_override``: for products that open with an identity transform
    but DO have a real pixel<->lonlat mapping derivable from known corner
    coordinates (OHRC, IIRS), pass that here. When set, windowing uses
    ``_window_from_bounds_general`` (rotation-safe) instead of the standard
    ``from_bounds`` (which assumes near-zero rotation and is only safe for a
    dataset's own native, typically near-axis-aligned transform).
    """
    file_path = Path(file_path)
    try:
        with rasterio.open(file_path) as dataset:
            effective_transform = transform_override if transform_override is not None else dataset.transform
            if dataset.crs is not None and region_crs is not None:
                west, south, east, north = transform_bounds(region_crs, dataset.crs, *region_bounds)
            else:
                west, south, east, north = region_bounds

            if transform_override is not None:
                window = _window_from_bounds_general(
                    effective_transform, west, south, east, north, dataset.width, dataset.height
                )
                if window is None:
                    return {"has_real_data": False, "valid_fraction": 0.0,
                             "reason": "region does not overlap this file's raster extent at all (rotation-safe check)"}
            else:
                try:
                    window = from_bounds(west, south, east, north, transform=effective_transform)
                except WindowError:
                    return {"has_real_data": False, "valid_fraction": 0.0, "reason": "region falls outside file extent"}
                try:
                    window = window.intersection(rasterio.windows.Window(0, 0, dataset.width, dataset.height))
                except WindowError:
                    return {"has_real_data": False, "valid_fraction": 0.0,
                             "reason": "region does not overlap this file's raster extent at all"}
                if window.width <= 0 or window.height <= 0:
                    return {"has_real_data": False, "valid_fraction": 0.0, "reason": "zero-size window after clipping to raster extent"}

            mask = dataset.read_masks(1, window=window)
            valid_fraction = float((mask != 0).mean()) if mask.size else 0.0
            return {
                "has_real_data": valid_fraction >= min_valid_fraction,
                "valid_fraction": valid_fraction,
                "window_shape": [int(window.height), int(window.width)],
            }
    except (RasterioIOError, OSError) as error:
        return {"has_real_data": False, "valid_fraction": 0.0, "reason": f"could not open {file_path.name}: {error}"}


def _transform_for(record: dict[str, Any]):
    """Build a corner-derived transform override for records that need one
    (corners known, but no real georeferencing in the file -- OHRC, IIRS).
    Returns None for records that should use their own dataset.transform."""
    if record.get("corners") and record.get("width") and record.get("height"):
        return transform_from_corners(record["corners"], record["width"], record["height"])
    return None


def verify_real_overlap(
    record_a: dict[str, Any],
    record_b: dict[str, Any],
    *,
    min_polygon_overlap_fraction: float = 0.05,
    min_valid_pixel_fraction: float = 0.5,
) -> dict[str, Any]:
    """Verify that two records genuinely overlap in real pixel data, not just claimed footprint."""
    area_a = _footprint_area(record_a)
    area_b = _footprint_area(record_b)
    relative_to = "a" if area_a <= area_b else "b"
    polygon_fraction = real_intersection_fraction(record_a, record_b, relative_to=relative_to)
    if polygon_fraction < min_polygon_overlap_fraction:
        return {
            "verified": False,
            "reason": f"claimed footprints do not meaningfully overlap (fraction={polygon_fraction:.4f})",
            "polygon_overlap_fraction": polygon_fraction,
        }

    a_bounds = record_a.get("bounds") or _corners_bounds(record_a)
    b_bounds = record_b.get("bounds") or _corners_bounds(record_b)
    west = max(a_bounds["west"], b_bounds["west"])
    south = max(a_bounds["south"], b_bounds["south"])
    east = min(a_bounds["east"], b_bounds["east"])
    north = min(a_bounds["north"], b_bounds["north"])
    intersection_bounds = (west, south, east, north)

    a_check = check_real_data_at_region(
        record_a["file_path"], intersection_bounds, record_a.get("crs"),
        min_valid_fraction=min_valid_pixel_fraction, transform_override=_transform_for(record_a),
    )
    b_check = check_real_data_at_region(
        record_b["file_path"], intersection_bounds, record_b.get("crs"),
        min_valid_fraction=min_valid_pixel_fraction, transform_override=_transform_for(record_b),
    )

    verified = bool(a_check["has_real_data"] and b_check["has_real_data"])
    return {
        "verified": verified,
        "reason": "verified real pixel overlap" if verified
        else "claimed footprints intersect but real pixel data does not (false-positive avoided)",
        "polygon_overlap_fraction": polygon_fraction,
        "bbox_intersection": list(intersection_bounds),
        "a_check": a_check,
        "b_check": b_check,
    }


def _corners_bounds(record: dict[str, Any]) -> dict[str, float]:
    lons = [c[0] for c in record["corners"]]
    lats = [c[1] for c in record["corners"]]
    return {"west": min(lons), "south": min(lats), "east": max(lons), "north": max(lats)}


def _footprint_area(record: dict[str, Any]) -> float:
    bounds = record.get("bounds") or _corners_bounds(record)
    return (bounds["east"] - bounds["west"]) * (bounds["north"] - bounds["south"])