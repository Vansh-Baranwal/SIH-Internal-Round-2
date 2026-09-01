"""
Unit tests for the Lunar Landmark Network and database module.
Covers:
  - Landmark extraction/representation, spatial searching, and geolocalization queries
  - Haversine distance and bearing calculation on the Moon sphere
  - Landmark serialization and deserialization round-trips
  - Spatial coverage calculations (uniform grids vs. corner clusters vs. degenerate sets)
"""

from __future__ import annotations

import json
import math
import numpy as np
import pytest

from lunar_hazard_mapper.correspondence.metrics import _spatial_coverage
from lunar_hazard_mapper.landmarks import (
    Landmark,
    LandmarkDatabase,
    GeolocationResult,
    _bearing,
    _haversine_km,
)


# ===========================================================================
# 1. Landmark Data Model & Default Database Catalog
# ===========================================================================

def test_landmark_creation_and_attributes():
    """Landmark dataclass contains all required lunar feature attributes."""
    lm = Landmark(
        id="LM_TEST",
        name="Test Crater",
        lat=-89.0,
        lon=0.0,
        radius_km=15.5,
        depth_m=3200.0,
        confidence=0.95,
        tags=["southpole", "test"],
    )
    assert lm.id == "LM_TEST"
    assert lm.name == "Test Crater"
    assert lm.lat == -89.0
    assert lm.lon == 0.0
    assert lm.radius_km == 15.5
    assert lm.depth_m == 3200.0
    assert lm.confidence == 0.95
    assert lm.tags == ["southpole", "test"]


def test_default_database_contains_standard_craters():
    """Default LandmarkDatabase initializes with prominent lunar craters."""
    db = LandmarkDatabase()
    all_lms = db.all()
    assert len(all_lms) >= 10

    names = {lm.name for lm in all_lms}
    assert "Tycho" in names
    assert "Copernicus" in names
    assert "Shackleton" in names


# ===========================================================================
# 2. Haversine & Bearing Calculations (Lunar Spherical Coordinates)
# ===========================================================================

def test_haversine_km_same_point_is_zero():
    """Distance between identical coordinates is 0.0 km."""
    d = _haversine_km(10.0, 20.0, 10.0, 20.0)
    assert d == pytest.approx(0.0, abs=1e-6)


def test_haversine_km_known_lunar_arc():
    """1 degree along lunar equator corresponds to pi/180 * 1737.4 km."""
    R_moon = 1737.4
    expected_km = (math.pi / 180.0) * R_moon  # ~30.323 km
    actual_km = _haversine_km(0.0, 0.0, 0.0, 1.0)
    assert actual_km == pytest.approx(expected_km, rel=1e-4)


def test_bearing_cardinal_directions():
    """Bearing calculates forward azimuth (0=North, 90=East, 180=South, 270=West)."""
    # Moving due North along meridian: (0, 0) -> (10, 0)
    assert _bearing(0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0, abs=1e-4)

    # Moving due East along equator: (0, 0) -> (0, 10)
    assert _bearing(0.0, 0.0, 0.0, 10.0) == pytest.approx(90.0, abs=1e-4)

    # Moving due South along meridian: (10, 0) -> (0, 0)
    assert _bearing(10.0, 0.0, 0.0, 0.0) == pytest.approx(180.0, abs=1e-4)

    # Moving due West along equator: (0, 10) -> (0, 0)
    assert _bearing(0.0, 10.0, 0.0, 0.0) == pytest.approx(270.0, abs=1e-4)


# ===========================================================================
# 3. Database Search & Geolocate Queries
# ===========================================================================

def test_database_search_finds_nearest_landmarks():
    """Search near South Pole (-89.9, 0.0) identifies Shackleton as closest landmark."""
    db = LandmarkDatabase()
    results = db.search(lat=-89.9, lon=0.0, radius_km=200.0)

    assert len(results) >= 1
    closest = results[0]
    assert closest.landmark.name == "Shackleton"
    assert closest.distance_km == pytest.approx(0.0, abs=1.0)
    assert 0.0 <= closest.confidence <= 1.0


def test_database_search_with_tag_filtering():
    """Tag filtering restricts returned landmarks to matching subsets."""
    db = LandmarkDatabase()
    # Filter for "raycrater" tag (Tycho, Copernicus)
    results = db.search(lat=0.0, lon=0.0, radius_km=5000.0, tags=["raycrater"])

    assert len(results) >= 2
    for r in results:
        assert "raycrater" in r.landmark.tags


def test_database_geolocate_top_k():
    """geolocate respects top_k limit and returns results ordered by distance ascending."""
    db = LandmarkDatabase()
    hits = db.geolocate(lat=-85.0, lon=0.0, radius_km=3000.0, top_k=3)

    assert len(hits) <= 3
    distances = [h.distance_km for h in hits]
    assert distances == sorted(distances)


def test_database_search_empty_when_no_landmarks_in_radius():
    """Searching a remote coordinate with small radius returns an empty list without crash."""
    db = LandmarkDatabase()
    results = db.search(lat=0.0, lon=0.0, radius_km=5.0)
    assert len(results) == 0


def test_database_get_and_add():
    """Dynamic landmark registration via add() and lookup via get()."""
    db = LandmarkDatabase(landmarks=[])
    assert len(db.all()) == 0

    new_lm = Landmark("LM_CUSTOM", "Custom Basin", 12.0, 34.0, 50.0, 2000.0, 0.9)
    db.add(new_lm)

    assert db.get("LM_CUSTOM") == new_lm
    assert db.get("NONEXISTENT") is None
    assert len(db.all()) == 1


# ===========================================================================
# 4. Serialization & Round-Trip
# ===========================================================================

def test_database_to_json_and_from_json_round_trip():
    """to_json() serializes landmarks and from_json() reconstructs exact database."""
    original_db = LandmarkDatabase()
    json_str = original_db.to_json()

    # Valid JSON string
    parsed = json.loads(json_str)
    assert isinstance(parsed, list)
    assert len(parsed) == len(original_db.all())

    # Reconstruct database
    restored_db = LandmarkDatabase.from_json(json_str)
    assert len(restored_db.all()) == len(original_db.all())

    for orig_lm, rest_lm in zip(original_db.all(), restored_db.all()):
        assert orig_lm.id == rest_lm.id
        assert orig_lm.name == rest_lm.name
        assert orig_lm.lat == rest_lm.lat
        assert orig_lm.lon == rest_lm.lon
        assert orig_lm.radius_km == rest_lm.radius_km
        assert orig_lm.depth_m == rest_lm.depth_m
        assert orig_lm.confidence == rest_lm.confidence
        assert orig_lm.tags == rest_lm.tags


# ===========================================================================
# 5. Spatial Coverage Evaluation on Landmark & Coordinate Sets
# ===========================================================================

def test_spatial_coverage_uniform_grid():
    """Uniformly distributed point grid gives high spatial coverage (> 0.5)."""
    # 4 points spanning across a 1000x1000 domain
    grid_pts = np.array([
        [100.0, 100.0],
        [900.0, 100.0],
        [900.0, 900.0],
        [100.0, 900.0],
    ], dtype=np.float32)
    # Area covered = 800 * 800 = 640000 / 1000000 = 0.64
    cov = _spatial_coverage(grid_pts, (1000, 1000))
    assert cov == pytest.approx(0.64, abs=0.01)


def test_spatial_coverage_corner_cluster():
    """Points clustered in a single corner yield low coverage (< 0.25)."""
    corner_pts = np.array([
        [10.0, 10.0],
        [150.0, 10.0],
        [150.0, 150.0],
        [10.0, 150.0],
    ], dtype=np.float32)
    # Area covered = 140 * 140 = 19600 / 1000000 = ~0.0196
    cov = _spatial_coverage(corner_pts, (1000, 1000))
    assert cov < 0.25


def test_spatial_coverage_empty_or_collinear_returns_zero():
    """Empty, single, or collinear points return 0.0 coverage without error."""
    assert _spatial_coverage(np.zeros((0, 2)), (500, 500)) == 0.0
    assert _spatial_coverage(np.array([[50.0, 50.0]]), (500, 500)) == 0.0
    assert _spatial_coverage(np.array([[10.0, 10.0], [20.0, 20.0]]), (500, 500)) == 0.0
