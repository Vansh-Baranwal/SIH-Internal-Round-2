"""Phase 12 data-source replaceability test.

The alternate input is a REAL-DATA-SHAPED TEST FIXTURE only. These checks
prove contract/path compatibility, not compatibility with actual lunar data
and not scientific validation.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (  # noqa: E402
    DemDataProvider,
    SyntheticTerrainProvider,
    TerrainFoundation,
)
from tests.m4.fixtures.real_data_shaped import make_real_data_shaped_dem  # noqa: E402


def _viewer_payload(foundation):
    """Serialize exactly the provider/foundation data used by the API boundary."""
    grid = foundation.grid()
    return {
        "metadata": foundation.metadata(),
        "grid": {
            "width": grid["width"],
            "height": grid["height"],
            "pixel_size_m": grid["pixel_size_m"],
            "x": grid["x"].tolist(),
            "y": grid["y"].tolist(),
            "z": grid["z"].tolist(),
            "valid_mask": grid["valid_mask"].tolist(),
            "coordinate_convention": grid["coordinate_convention"],
        },
    }


def _assert_viewer_payload(payload):
    grid = payload["grid"]
    height, width = grid["height"], grid["width"]
    assert width >= 2 and height >= 2
    for key in ("x", "y", "z", "valid_mask"):
        assert len(grid[key]) == height
        assert all(len(row) == width for row in grid[key])
    assert payload["metadata"]["coordinate_convention"] == {
        "x": "local_east_meters",
        "y": "local_north_meters",
        "z": "local_up_meters",
    }


def test_synthetic_and_real_data_shaped_fixture_share_viewer_path():
    fixtures = [
        TerrainFoundation(SyntheticTerrainProvider(kind="combined", size=16, pixel_size_m=5.0)),
        TerrainFoundation(DemDataProvider(make_real_data_shaped_dem(), source="real_data_shaped_test")),
    ]

    payloads = [_viewer_payload(foundation) for foundation in fixtures]
    for payload in payloads:
        _assert_viewer_payload(payload)
        json.dumps(payload)  # API-facing representation is JSON serializable.

    synthetic, alternate = payloads
    assert (synthetic["grid"]["width"], synthetic["grid"]["height"]) == (16, 16)
    assert (alternate["grid"]["width"], alternate["grid"]["height"]) == (7, 5)
    assert alternate["metadata"]["bounds"] == {
        "min_x": 120.0,
        "min_y": 42.5,
        "max_x": 172.5,
        "max_y": 80.0,
        "width_m": 52.5,
        "height_m": 37.5,
    }
    assert alternate["grid"]["x"][0][0] == 123.75
    assert alternate["grid"]["y"][0][0] == 76.25
    assert alternate["grid"]["z"][0][0] == 12.0
    assert alternate["grid"]["valid_mask"][1][2] is False
    assert alternate["grid"]["valid_mask"][3][5] is False
    assert alternate["metadata"]["provenance"]["source"] == "real_data_shaped_test"


def test_viewer_geometry_code_is_contract_based_not_synthetic_based():
    terrain_source = (PROJECT_ROOT / "web" / "src" / "components" / "Terrain.tsx").read_text(encoding="utf-8")
    coordinates_source = (PROJECT_ROOT / "web" / "src" / "spatial" / "coordinates.ts").read_text(encoding="utf-8")
    assert "SyntheticTerrainProvider" not in terrain_source
    assert "create_synthetic_terrain" not in terrain_source
    assert "terrainGridToThreeVector" in terrain_source
    assert "width - 1" in terrain_source and "height - 1" in terrain_source
    assert "validMask" in terrain_source
    assert "East -> X" in terrain_source and "North -> Z" in terrain_source and "Up -> Y" in terrain_source
    assert "terrainGridToThreeVector" in coordinates_source


def test_phase12_layer_contracts_keep_generic_coordinates_and_metadata():
    source_files = {
        "tmc": "src/lunar_hazard_mapper/m4_terrain/tmc_camera.py",
        "ohrc": "src/lunar_hazard_mapper/m4_terrain/ohrc_camera.py",
        "iirs": "src/lunar_hazard_mapper/m4_terrain/iirs_footprint.py",
        "landmarks": "src/lunar_hazard_mapper/m4_terrain/landmark_provider.py",
        "hazards": "src/lunar_hazard_mapper/m4_terrain/hazard_overlay.py",
        "spectral": "src/lunar_hazard_mapper/m4_terrain/spectral_overlay.py",
        "water_ice": "src/lunar_hazard_mapper/m4_terrain/water_ice_overlay.py",
    }
    for source_path in source_files.values():
        source = (PROJECT_ROOT / source_path).read_text(encoding="utf-8")
        assert "coordinate_convention" in source
        assert "provenance" in source
        assert "class Synthetic" in source
        assert "Provider" in source
    sun_source = (PROJECT_ROOT / "src/lunar_hazard_mapper/m4_terrain/sun_control.py").read_text(encoding="utf-8")
    assert "SunScenarioModel" in sun_source
    assert "counterfactual" in sun_source
    assert "provenance" in sun_source
