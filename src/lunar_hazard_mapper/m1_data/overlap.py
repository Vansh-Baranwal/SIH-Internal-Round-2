"""Real (pixel-level) overlap verification owned by Member 1 (M1).

catalogue.py's find_overlapping_hr_tiles() and coordinates.py's
real_intersection_fraction() both operate on *claimed* footprints (a bounding
box, or a polygon built from label corner coordinates). Neither actually looks
at the pixels. A tile's real data can still be a smaller, oddly-shaped, or
rotated region inside that claimed footprint (common with orbit gaps,
nodata borders, and pushbroom swaths) -- two footprints can overlap on paper
while their *real* image content does not overlap at all.

This module is the final gate before a pair is trusted: it reads a small
window at the claimed intersection region from both sources and checks that
each side actually has non-nodata pixel data there.
"""

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
    Builds a real pixel<->lonlat affine transform for products (like OHRC)
    that open with an identity transform (no map projection baked into the
    file itself) but DO have known real corner coordinates from their PDS4
    label.

    corners must be in (upper_left, upper_right, lower_right, lower_left)
    order -- the same perimeter-walk order parse_iirs_corners() returns,
    confirmed shared by both IIRS and OHRC labels.
    """
    pixel_corners = [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]
    gcps = [
        GroundControlPoint(row=row, col=col, x=lon, y=lat)
        for (lon, lat), (col, row) in zip(corners, pixel_corners)
    ]
    return from_gcps(gcps)


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

    ``region_bounds``/``region_crs`` describe the claimed overlap region, which
    may be in a different CRS than the file being checked -- it is reprojected
    onto the file's own CRS before windowing.

    ``transform_override``: for products that open with an identity transform
    (no real georeferencing in the file itself, e.g. OHRC via the PDS4 XML
    driver) but DO have a real pixel<->lonlat mapping derivable from known
    corner coordinates (see transform_from_corners above), pass that here.
    Without it, region_bounds (real lon/lat, e.g. ~25.1, -13.0) would be
    misinterpreted as raw pixel coordinates against the identity transform --
    landing the window near pixel (25, 13) in a 12000x90148 image instead of
    the real data region.
    """
    file_path = Path(file_path)
    try:
        with rasterio.open(file_path) as dataset:
            effective_transform = transform_override if transform_override is not None else dataset.transform
            if dataset.crs is not None and region_crs is not None:
                west, south, east, north = transform_bounds(region_crs, dataset.crs, *region_bounds)
            else:
                west, south, east, north = region_bounds
            try:
                window = from_bounds(west, south, east, north, transform=effective_transform)
            except WindowError:
                return {"has_real_data": False, "valid_fraction": 0.0, "reason": "region falls outside file extent"}
            # window.intersection() raises WindowError (not an empty window)
            # when there's zero overlap with the raster extent -- this
            # crashed the whole check for query regions entirely outside a
            # file, instead of correctly reporting "no data here".
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
    (corners known, but no real georeferencing in the file -- currently
    OHRC). Returns None for records that should just use their own
    dataset.transform (TMC, anything with a real CRS)."""
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
    """Verify that two records genuinely overlap in real pixel data, not just claimed footprint.

    Two-stage check:
      1. Real polygon intersection (handles rotated IIRS/OHRC swaths
         correctly, unlike a bounding-box check) must clear
         ``min_polygon_overlap_fraction``.
      2. Both sides must have actual non-nodata pixel data inside that
         intersection region -- this is the check a bbox/polygon test alone
         cannot make, since a nodata border or orbit gap can sit inside an
         otherwise-overlapping footprint.
    """
    # real_intersection_fraction's default relative_to="a" hardcodes which
    # footprint is the denominator. For this project's actual use case (a
    # small OHRC/IIRS tile fully contained within a much larger TMC tile),
    # the fraction relative to the LARGE tile is always tiny (e.g. 0.01 for
    # a 1deg box fully inside a 10deg box) even when the small tile's
    # footprint is 100% covered -- this would systematically reject
    # genuinely good pairs, not just bad ones. The correct denominator for
    # "does this pair actually share useful ground" is the SMALLER
    # footprint's area, i.e. "what fraction of the smaller tile is covered".
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
    """Rough planar bounding-box area, used only to decide which footprint
    is smaller for real_intersection_fraction's denominator -- does not need
    to be precise (a full polygon area would double-compute what
    real_intersection_fraction already does internally), just needs to
    correctly rank TMC (large) vs OHRC/IIRS (small) tiles by size."""
    bounds = record.get("bounds") or _corners_bounds(record)
    return (bounds["east"] - bounds["west"]) * (bounds["north"] - bounds["south"])