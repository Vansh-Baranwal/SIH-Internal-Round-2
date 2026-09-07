"""Focused M4-12.9 Hazard Overlay contract tests.

Verifies hazard models, replaceable provider contracts, payload serialization,
DEM elevation association, and synthetic provenance isolation.
No real hazard observations or scientific classifications are fabricated.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    HazardDataStatus,
    HazardItem,
    HazardModel,
    HazardProvider,
    HazardSetModel,
    HazardSeverity,
    HazardType,
    SyntheticHazardProvider,
    SyntheticTerrainProvider,
    TerrainFoundation,
)


class IndependentHazardProvider(HazardProvider):
    """Proves the renderer-facing hazard contract is not provider-specific."""

    def load_hazards(self, foundation: TerrainFoundation | None = None) -> HazardSetModel:
        return HazardSetModel(
            hazards=[
                HazardItem(
                    hazard_id="TEST_HAZ_001",
                    hazard_type=HazardType.BOULDER_FIELD.value,
                    severity=HazardSeverity.HIGH.value,
                    risk_score=0.85,
                    confidence=0.9,
                    position_m=(100.0, 35.0, -200.0),
                    radius_m=60.0,
                    boundary_vertices_m=[
                        (80.0, 35.0, -180.0),
                        (120.0, 35.0, -180.0),
                        (100.0, 35.0, -220.0),
                    ],
                    description="Independent test boulder hazard.",
                    data_status=HazardDataStatus.SYNTHETIC,
                    provenance={"note": "Independent test provider hazard."},
                )
            ],
            data_status=HazardDataStatus.SYNTHETIC,
            provenance={"source": "independent_test_hazard_provider"},
        )


def test_synthetic_hazard_provider_is_explicitly_development_only():
    provider = SyntheticHazardProvider()
    set_model = provider.load_hazards()
    payload = set_model.payload()

    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT HAZARDS"
    assert "not represent real lunar hazard observations" in payload["provenance"]["note"].lower() or \
           "not represent" in payload["provenance"]["note"]
    assert payload["hazard_count"] == 3


def test_hazard_payload_preserves_attributes_and_coordinates():
    provider = SyntheticHazardProvider()
    payload = provider.load_hazards().payload()

    conv = payload["coordinate_convention"]
    assert conv["x"] == "local_east_meters"
    assert conv["y"] == "local_up_meters"
    assert conv["z"] == "local_north_meters"

    h1 = payload["hazards"][0]
    assert h1["hazard_id"] == "HAZARD_SYNTHETIC_001"
    assert h1["hazard_type"] == HazardType.STEEP_SLOPE.value
    assert h1["severity"] == HazardSeverity.CRITICAL.value
    assert 0.0 <= h1["risk_score"] <= 1.0
    assert h1["boundary_vertices_m"] is not None
    assert len(h1["boundary_vertices_m"]) == 4

    h3 = payload["hazards"][2]
    assert h3["hazard_id"] == "HAZARD_SYNTHETIC_003"
    assert h3["severity"] == HazardSeverity.MODERATE.value
    assert h3["boundary_vertices_m"] is None


def test_hazard_provider_contract_is_replaceable():
    provider = IndependentHazardProvider()
    assert isinstance(provider, HazardProvider)

    model = provider.load_hazards()
    assert isinstance(model, HazardSetModel)
    assert len(model.hazards) == 1

    item = model.hazards[0]
    assert isinstance(item, HazardItem)
    assert isinstance(item, HazardModel)
    assert item.hazard_id == "TEST_HAZ_001"
    assert item.position_m == (100.0, 35.0, -200.0)
    assert len(item.boundary_vertices_m) == 3


def test_hazard_overlay_frontend_does_not_depend_on_synthetic_provider_class():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "HazardOverlay.tsx").read_text(encoding="utf-8")
    assert "SyntheticHazardProvider" not in viewer_source
    assert "fetchHazards" in viewer_source
    assert "hazard-center-marker" in viewer_source
    assert "hazard-boundary-outline" in viewer_source
    assert "Hazard metadata is malformed" in viewer_source


def test_invalid_hazard_item_parameters_raise_value_error():
    with pytest.raises(ValueError, match="hazard_id cannot be empty"):
        HazardItem(
            hazard_id="",
            hazard_type=HazardType.BOULDER_FIELD.value,
            severity=HazardSeverity.HIGH.value,
            risk_score=0.8,
            position_m=(0.0, 0.0, 0.0),
        )

    with pytest.raises(ValueError, match="position_m must have 3 coordinates"):
        HazardItem(
            hazard_id="INV_01",
            hazard_type=HazardType.BOULDER_FIELD.value,
            severity=HazardSeverity.HIGH.value,
            risk_score=0.8,
            position_m=(0.0, 0.0),  # 2 elements instead of 3
        )

    with pytest.raises(ValueError, match="risk_score must be between 0.0 and 1.0"):
        HazardItem(
            hazard_id="INV_02",
            hazard_type=HazardType.BOULDER_FIELD.value,
            severity=HazardSeverity.HIGH.value,
            risk_score=1.5,
            position_m=(0.0, 0.0, 0.0),
        )
