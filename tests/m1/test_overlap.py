"""Tests for the real-data-footprint overlap verification (m1_data.overlap).

Directly regression-tests the false-positive bug found during M2 real-data
testing: bounding-box intersection alone does not guarantee real pixel
overlap between two tiles.
"""
from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from lunar_hazard_mapper.m1_data.overlap import (
    check_real_data_at_region,
    verify_real_overlap,
)
from lunar_hazard_mapper.m1_data.coordinates import real_intersection_fraction


@pytest.fixture
def tmc_like_tile(tmp_path):
    """A tile whose bounding box is [0,10]x[0,10] but whose real (non-zero)
    data only occupies the left 40% of columns -- reproduces the exact
    rotated-swath-in-empty-rectangle pattern found in real TMC ortho tiles."""
    data = np.zeros((1000, 1000), dtype=np.uint8)
    data[:, :400] = 100
    path = tmp_path / "tmc_like.tif"
    transform = from_origin(0, 10, 0.01, 0.01)
    with rasterio.open(path, "w", driver="GTiff", height=1000, width=1000,
                        count=1, dtype="uint8", crs="EPSG:4326",
                        transform=transform, nodata=0) as dst:
        dst.write(data, 1)
    return str(path)


@pytest.fixture
def small_tile_factory(tmp_path):
    def _make(name: str, west: float, north: float, size_deg: float = 1.0, value: int = 150):
        path = tmp_path / name
        data = np.full((200, 200), value, dtype=np.uint8)
        transform = from_origin(west, north, size_deg / 200, size_deg / 200)
        with rasterio.open(path, "w", driver="GTiff", height=200, width=200,
                            count=1, dtype="uint8", crs="EPSG:4326",
                            transform=transform, nodata=0) as dst:
            dst.write(data, 1)
        return str(path)
    return _make


def test_real_data_detected_in_populated_region(tmc_like_tile):
    result = check_real_data_at_region(tmc_like_tile, (1, 7, 2, 8), None)
    assert result["has_real_data"] is True
    assert result["valid_fraction"] == 1.0


def test_no_real_data_in_empty_corner(tmc_like_tile):
    result = check_real_data_at_region(tmc_like_tile, (6, 7, 7, 8), None)
    assert result["has_real_data"] is False
    assert result["valid_fraction"] == 0.0


def test_region_entirely_outside_raster_does_not_crash(tmc_like_tile):
    """Regression test for the WindowError crash bug found during review."""
    result = check_real_data_at_region(tmc_like_tile, (100, 100, 101, 101), None)
    assert result["has_real_data"] is False
    assert "reason" in result


def test_bbox_overlap_but_no_real_data_is_correctly_rejected(tmc_like_tile, small_tile_factory):
    """THE core regression test: reproduces the exact bug found testing real
    Chandrayaan-2 TMC/OHRC data -- bounding boxes intersect, but the LR
    tile's actual pixel data does not reach that location. Must be rejected,
    not silently treated as a valid pair."""
    hr_path = small_tile_factory("ohrc_empty_zone.tif", west=7, north=6, size_deg=1.0)
    lr_record = {"file_path": tmc_like_tile, "bounds": {"west": 0, "south": 0, "east": 10, "north": 10}, "crs": None}
    hr_record = {"file_path": hr_path, "bounds": {"west": 7, "south": 5, "east": 8, "north": 6}, "crs": None}

    result = verify_real_overlap(lr_record, hr_record)
    assert result["verified"] is False
    assert result["a_check"]["has_real_data"] is False
    assert result["b_check"]["has_real_data"] is True


def test_bbox_overlap_with_real_data_is_correctly_accepted(tmc_like_tile, small_tile_factory):
    """True-positive companion to the test above: when the LR tile DOES have
    real data at the intersection, the pair should be verified."""
    hr_path = small_tile_factory("ohrc_real_zone.tif", west=1, north=8, size_deg=1.0)
    lr_record = {"file_path": tmc_like_tile, "bounds": {"west": 0, "south": 0, "east": 10, "north": 10}, "crs": None}
    hr_record = {"file_path": hr_path, "bounds": {"west": 1, "south": 7, "east": 2, "north": 8}, "crs": None}

    result = verify_real_overlap(lr_record, hr_record)
    assert result["verified"] is True


def test_real_iirs_swath_polygon_overlaps_confirmed_tmc_roi():
    """Uses the ACTUAL corner coordinates from a real, already-downloaded
    Chandrayaan-2 IIRS label (ch2_iir_nri_20200203T1845559180_d_img_m65),
    confirming via real polygon geometry -- not eyeballing a map -- that this
    file genuinely overlaps the confirmed real TMC/OHRC ROI from the M2
    real-data testing (lon ~25.0-25.4, lat ~-13.9 to -13.5)."""
    iirs_corners = [(25.176954, -30.375724), (24.556687, -30.374377),
                     (24.626887, -0.52665), (25.154838, -0.527657)]
    iirs_record = {"corners": iirs_corners, "crs": None}
    tmc_record = {"bounds": {"west": 25.0, "south": -13.9, "east": 25.4, "north": -13.5}, "crs": None}

    fraction = real_intersection_fraction(tmc_record, iirs_record, relative_to="a")
    assert fraction > 0.05, f"expected meaningful real overlap, got fraction={fraction}"