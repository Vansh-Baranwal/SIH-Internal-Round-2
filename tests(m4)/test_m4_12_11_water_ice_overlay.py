"""Focused M4-12.11 water-ice overlay contract tests."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (  # noqa: E402
    SyntheticWaterIceProvider,
    WaterIceDataStatus,
    WaterIceItem,
    WaterIceModel,
    WaterIceOverlayModel,
    WaterIceProvider,
)


def test_synthetic_water_ice_is_explicit_and_spatially_serializable():
    model = SyntheticWaterIceProvider().load_water_ice()
    payload = model.payload()
    assert isinstance(model, WaterIceModel)
    assert isinstance(model, WaterIceOverlayModel)
    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT WATER-ICE OVERLAY"
    assert "not a real lunar water-ice observation" in payload["items"][0]["provenance"]["note"]
    assert payload["coordinate_convention"] == {"x": "local_east_meters", "y": "local_up_meters", "z": "local_north_meters"}
    assert len(payload["items"]) == 3


def test_provider_contract_is_replaceable_and_no_measurements_are_required():
    class IndependentProvider(WaterIceProvider):
        def load_water_ice(self, foundation=None):
            return WaterIceOverlayModel(
                items=[WaterIceItem("TEST", "Development marker", (1.0, 2.0, 3.0))],
                data_status=WaterIceDataStatus.SYNTHETIC,
                provenance={"source": "test"},
            )

    model = IndependentProvider().load_water_ice()
    assert model.items[0].position_m == (1.0, 2.0, 3.0)
    assert "abundance" not in model.payload()["items"][0]


def test_invalid_water_ice_item_parameters_raise_value_error():
    with pytest.raises(ValueError, match="water_ice_id cannot be empty"):
        WaterIceItem("", "Invalid", (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="boundary_vertices_m must have at least 3 vertices"):
        WaterIceItem("INV", "Invalid", (0.0, 0.0, 0.0), [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])


def test_overlay_does_not_depend_on_synthetic_provider_class():
    source = (ROOT / "web" / "src" / "components" / "WaterIceOverlay.tsx").read_text(encoding="utf-8")
    assert "SyntheticWaterIceProvider" not in source
    assert "fetchWaterIceOverlay" in source
    assert "water-ice-region-fill" in source
    assert "Water-ice metadata is malformed" in source


def test_overlay_preserves_per_vertex_elevation_in_fill_geometry():
    source = (ROOT / "web" / "src" / "components" / "WaterIceOverlay.tsx").read_text(encoding="utf-8")
    assert "vertex.x, vertex.y + 0.45, vertex.z" in source
    assert "new THREE.Float32BufferAttribute(positions, 3)" in source
    assert "ShapeGeometry" not in source
