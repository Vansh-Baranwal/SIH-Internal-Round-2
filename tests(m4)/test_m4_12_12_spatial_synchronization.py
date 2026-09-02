"""Focused M4-12.12 local-frame synchronization tests."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (  # noqa: E402
    LOCAL_UNITS,
    TERRAIN_GRID_CONVENTION,
    VIEW_COORDINATE_CONVENTION,
    SyntheticHazardProvider,
    SyntheticIirsProvider,
    SyntheticLandmarkProvider,
    SyntheticOhrcCameraProvider,
    SyntheticSpectralProvider,
    SyntheticTmcCameraProvider,
    SyntheticTerrainProvider,
    SyntheticWaterIceProvider,
    TerrainFoundation,
    terrain_grid_to_viewer,
    viewer_position,
)


def test_shared_frame_preserves_phase_12_axes_and_units():
    assert VIEW_COORDINATE_CONVENTION == {"x": "local_east_meters", "y": "local_up_meters", "z": "local_north_meters"}
    assert TERRAIN_GRID_CONVENTION == {"x": "local_east_meters", "y": "local_north_meters", "z": "local_up_meters"}
    assert LOCAL_UNITS == "metres"
    assert terrain_grid_to_viewer(10, 20, 30) == (10.0, 30.0, 20.0)
    assert viewer_position({"x": 10, "y": 30, "z": 20}) == (10.0, 30.0, 20.0)


def test_all_visualization_contracts_publish_the_same_viewer_convention():
    foundation = TerrainFoundation(SyntheticTerrainProvider(size=32))
    payloads = [
        SyntheticTmcCameraProvider().load_camera().payload(),
        SyntheticOhrcCameraProvider().load_camera().payload(),
        SyntheticIirsProvider().load_footprint().payload(),
        SyntheticLandmarkProvider().load_landmarks(foundation).payload(),
        SyntheticHazardProvider().load_hazards(foundation).payload(),
        SyntheticSpectralProvider().load_spectral(foundation).payload(),
        SyntheticWaterIceProvider().load_water_ice(foundation).payload(),
    ]
    for payload in payloads:
        assert payload["coordinate_convention"] == VIEW_COORDINATE_CONVENTION


def test_invalid_or_nonfinite_viewer_coordinates_are_rejected():
    with pytest.raises(ValueError):
        viewer_position({"x": 0, "y": 0, "z": float("nan")})


def test_frontend_uses_shared_dem_boundary_conversion():
    terrain = (ROOT / "web" / "src" / "components" / "Terrain.tsx").read_text(encoding="utf-8")
    water_ice = (ROOT / "web" / "src" / "components" / "WaterIceOverlay.tsx").read_text(encoding="utf-8")
    utility = (ROOT / "web" / "src" / "spatial" / "coordinates.ts").read_text(encoding="utf-8")
    assert "terrainGridToThreeVector" in terrain
    assert "toThreeVector" in water_ice
    assert "East, Up, North" in utility
