"""
Unit tests for the Counterfactual Sun Simulator module.
Tests cover DEM shadow raycasting, sun elevation edge cases, azimuth sweep rotations,
batch simulation, vector geometry, and base image illumination modulation.
All DEM and image data are synthesized dynamically with numpy.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from lunar_hazard_mapper.simulation import (
    SunSimResult,
    SunSimulator,
    simulate_sun,
)


def _create_synthetic_dem_hill(size: int = 64, peak_height_m: float = 100.0) -> np.ndarray:
    """Create a synthetic Gaussian hill DEM centered in the grid."""
    y, x = np.ogrid[:size, :size]
    cy, cx = size // 2, size // 2
    sigma = size / 6.0
    r_sq = (x - cx) ** 2 + (y - cy) ** 2
    dem = peak_height_m * np.exp(-r_sq / (2 * sigma ** 2)).astype(np.float32)
    return dem


def _azimuth_elevation_to_unit_vector(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Compute 3D sun direction unit vector from azimuth (clockwise from North) and elevation."""
    az_rad = math.radians(azimuth_deg)
    el_rad = math.radians(elevation_deg)
    # x: East, y: North, z: Up
    x = math.cos(el_rad) * math.sin(az_rad)
    y = math.cos(el_rad) * math.cos(az_rad)
    z = math.sin(el_rad)
    return np.array([x, y, z], dtype=np.float64)


# ===========================================================================
# 1. Sun Elevation Boundary Cases (Overhead, Flat DEM, Below Horizon)
# ===========================================================================

def test_sun_sim_flat_dem_overhead_sun_no_shadows():
    """Overhead sun (90 deg elevation) on a flat DEM has no shadows and uniform illumination."""
    dem = np.zeros((32, 32), dtype=np.float32)
    sim = SunSimulator()
    res = sim.simulate(dem, sun_azimuth_deg=0.0, sun_elevation_deg=90.0, pixel_scale_m=5.0)

    assert isinstance(res, SunSimResult)
    assert not res.shadow_mask.any()
    assert res.shadow_mask.shape == (32, 32)
    assert np.allclose(res.illumination_map, 1.0, atol=1e-3)


@pytest.mark.parametrize("elevation", [0.0, -10.0, -45.0])
def test_sun_sim_sun_at_or_below_horizon_full_shadow(elevation: float):
    """When sun elevation <= 0 deg, the entire terrain is in 100% shadow."""
    dem = _create_synthetic_dem_hill(size=32, peak_height_m=50.0)
    sim = SunSimulator()
    res = sim.simulate(dem, sun_azimuth_deg=45.0, sun_elevation_deg=elevation)

    assert res.shadow_mask.all()
    assert np.allclose(res.illumination_map, 0.0)


# ===========================================================================
# 2. Azimuth Directionality & Shadow Rotation
# ===========================================================================

def test_sun_sim_east_sun_casts_shadow_west():
    """Sun from East (azimuth=90 deg) casts shadow on the Western (left) side of a hill."""
    dem = _create_synthetic_dem_hill(size=64, peak_height_m=100.0)
    sim = SunSimulator()
    # Low sun from East
    res = sim.simulate(dem, sun_azimuth_deg=90.0, sun_elevation_deg=15.0, pixel_scale_m=5.0)

    cx = 32
    # Shadow mask on left half vs right half
    west_shadow_count = res.shadow_mask[:, :cx].sum()
    east_shadow_count = res.shadow_mask[:, cx:].sum()

    assert west_shadow_count > east_shadow_count
    assert west_shadow_count > 0


def test_sun_sim_south_sun_casts_shadow_north():
    """Sun from South (azimuth=180 deg) casts shadow on the Northern (top) side of a hill."""
    dem = _create_synthetic_dem_hill(size=64, peak_height_m=100.0)
    sim = SunSimulator()
    # Low sun from South
    res = sim.simulate(dem, sun_azimuth_deg=180.0, sun_elevation_deg=15.0, pixel_scale_m=5.0)

    cy = 32
    # In matrix coords: y < cy is top (North), y >= cy is bottom (South)
    north_shadow_count = res.shadow_mask[:cy, :].sum()
    south_shadow_count = res.shadow_mask[cy:, :].sum()

    assert north_shadow_count > south_shadow_count
    assert north_shadow_count > 0


def test_sun_sim_azimuth_sweep_rotates_shadow_centroid():
    """Shadow centroid rotates as sun azimuth completes a circular sweep around a central hill."""
    dem = _create_synthetic_dem_hill(size=64, peak_height_m=80.0)
    sim = SunSimulator()
    angles = [0.0, 90.0, 180.0, 270.0]
    centroids = []

    for az in angles:
        res = sim.simulate(dem, sun_azimuth_deg=az, sun_elevation_deg=20.0, pixel_scale_m=5.0)
        assert res.shadow_mask.any()
        y_indices, x_indices = np.where(res.shadow_mask)
        mean_y, mean_x = float(np.mean(y_indices)), float(np.mean(x_indices))
        centroids.append((mean_x, mean_y))

    # Sun from North (az=0) -> shadow south (mean_y > 32)
    assert centroids[0][1] > 32.0
    # Sun from East (az=90) -> shadow west (mean_x < 32)
    assert centroids[1][0] < 32.0
    # Sun from South (az=180) -> shadow north (mean_y < 32)
    assert centroids[2][1] < 32.0
    # Sun from West (az=270) -> shadow east (mean_x > 32)
    assert centroids[3][0] > 32.0


# ===========================================================================
# 3. Vector Geometry & Unit Length Validation
# ===========================================================================

@pytest.mark.parametrize("az,el", [
    (0.0, 45.0),
    (90.0, 30.0),
    (180.0, 60.0),
    (270.0, 10.0),
    (135.0, 75.0),
])
def test_azimuth_elevation_to_unit_vector_length(az: float, el: float):
    """Calculated 3D sun direction vectors must always have unit length."""
    v = _azimuth_elevation_to_unit_vector(az, el)
    norm = np.linalg.norm(v)
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_azimuth_antipodal_symmetry():
    """Azimuth 180 deg vector is opposite along horizontal axis compared to 0 deg."""
    v_north = _azimuth_elevation_to_unit_vector(0.0, 45.0)
    v_south = _azimuth_elevation_to_unit_vector(180.0, 45.0)

    # y (North) component is negated
    assert v_south[1] == pytest.approx(-v_north[1], abs=1e-6)
    # z (Up) elevation component remains identical
    assert v_south[2] == pytest.approx(v_north[2], abs=1e-6)


# ===========================================================================
# 4. Batch Simulation & Base Image Illumination Rendering
# ===========================================================================

def test_sun_sim_batch_simulation_returns_correct_count_and_results():
    """simulate_batch processes multiple angles and produces valid individual results."""
    dem = _create_synthetic_dem_hill(size=32, peak_height_m=50.0)
    sim = SunSimulator()
    angles = [(0.0, 30.0), (90.0, 30.0), (180.0, 30.0)]

    results = sim.simulate_batch(dem, angles, pixel_scale_m=5.0)
    assert len(results) == 3
    for i, res in enumerate(results):
        assert isinstance(res, SunSimResult)
        assert res.sun_azimuth_deg == angles[i][0]
        assert res.sun_elevation_deg == angles[i][1]
        assert res.illumination_map.shape == (32, 32)


def test_sun_sim_with_base_image_applies_illumination_and_shadow():
    """When base_image is supplied, synthetic_image darkens shadowed regions while preserving dimensions."""
    dem = _create_synthetic_dem_hill(size=64, peak_height_m=100.0)
    base_img = np.full((64, 64), 200, dtype=np.uint8)

    res = simulate_sun(dem, sun_azimuth_deg=90.0, sun_elevation_deg=15.0, base_image=base_img)

    assert res.synthetic_image is not None
    assert res.synthetic_image.shape == base_img.shape
    assert res.synthetic_image.dtype == np.uint8

    # Shadowed pixels must be significantly darker than unshadowed illuminated pixels
    shadowed_vals = res.synthetic_image[res.shadow_mask]
    assert len(shadowed_vals) > 0
    assert shadowed_vals.mean() < 50.0  # Ambient shadow darkening
