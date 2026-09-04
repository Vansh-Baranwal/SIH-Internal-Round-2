"""Focused M4-12.2 transport tests; no real lunar data is asserted or created."""

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m3_terrain.synthetic import create_synthetic_terrain
from lunar_hazard_mapper.m4_terrain import DemDataProvider, TerrainFoundation


def test_foundation_grid_preserves_dem_coordinates_elevation_and_nodata():
    dem = create_synthetic_terrain(kind="flat", size=4, pixel_size_m=2.0)
    dem.elevation[1, 1] = dem.nodata
    dem.elevation[2, 2] = np.nan
    foundation = TerrainFoundation(DemDataProvider(dem, source="m4_12_2_test"))
    grid = foundation.grid()

    assert grid["x"][0, 1] > grid["x"][0, 0]  # local East
    assert grid["y"][1, 0] < grid["y"][0, 0]  # local North-up raster
    assert grid["z"][0, 0] == dem.elevation[0, 0]  # local Up / metres
    assert not grid["valid_mask"][1, 1]
    assert not grid["valid_mask"][2, 2]


def test_dem_viewer_route_uses_foundation_not_glb_or_synthetic_frontend_import():
    api_source = (PROJECT_ROOT / "src" / "lunar_hazard_mapper" / "api" / "main.py").read_text(encoding="utf-8")
    terrain_source = (PROJECT_ROOT / "web" / "src" / "components" / "Terrain.tsx").read_text(encoding="utf-8")

    assert '"/api/terrain/dem"' in api_source
    assert "TerrainFoundation(SyntheticTerrainProvider())" in api_source
    assert "SyntheticTerrainProvider" not in terrain_source
    assert "moon_surface.glb" not in terrain_source
    assert "validMask" in terrain_source
    assert "positions.push(x[row][column], z[row][column], y[row][column])" in terrain_source
    assert "kind: 'invalid'" in terrain_source
    assert "isDemTerrainPayload" in terrain_source


def test_synthetic_provenance_is_in_the_viewer_payload():
    foundation = TerrainFoundation(DemDataProvider(create_synthetic_terrain(size=4)))
    metadata = foundation.metadata()
    assert metadata["data_status"] == "synthetic"
    assert metadata["display_label"] == "SYNTHETIC DEVELOPMENT DATA"
