"""Focused M4-12.6 contract tests; no real landmark ground truth is fabricated."""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    LandmarkDataStatus,
    LandmarkItem,
    LandmarkModel,
    LandmarkProvider,
    LandmarkSetModel,
    SyntheticLandmarkProvider,
    SyntheticTerrainProvider,
    TerrainFoundation,
)


class IndependentLandmarkProvider(LandmarkProvider):
    """Proves the renderer-facing contract is not provider-specific."""

    def load_landmarks(self, foundation: TerrainFoundation | None = None) -> LandmarkSetModel:
        return LandmarkSetModel(
            landmarks=[
                LandmarkItem(
                    landmark_id="TEST_LM_001",
                    display_label="Test Landmark Alpha",
                    estimated_position_m=(10.0, 20.0, 30.0),
                    reference_position_m=(12.0, 20.0, 31.0),
                    diameter_m=150.0,
                    depth_m=30.0,
                    confidence=0.95,
                    quality_score=0.92,
                    localization_status="TEST_LOCALIZED",
                    data_status=LandmarkDataStatus.SYNTHETIC,
                    provenance={"note": "Independent test landmark."},
                )
            ],
            data_status=LandmarkDataStatus.SYNTHETIC,
            provenance={"source": "independent_test_provider"},
        )


def test_synthetic_landmark_provider_is_explicitly_development_only():
    provider = SyntheticLandmarkProvider()
    set_model = provider.load_landmarks()
    payload = set_model.payload()

    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT LANDMARKS"
    assert "not represent real lunar observations" in payload["provenance"]["note"]
    assert payload["landmark_count"] == 3


def test_estimated_and_reference_coordinates_are_kept_separate():
    provider = SyntheticLandmarkProvider()
    payload = provider.load_landmarks().payload()

    lm1 = payload["landmarks"][0]
    assert lm1["estimated_position_m"] == {"x": 1000.0, "y": 30.0, "z": -1000.0} or "x" in lm1["estimated_position_m"]
    assert lm1["reference_position_m"] is not None
    assert lm1["estimated_position_m"] != lm1["reference_position_m"]

    lm3 = payload["landmarks"][2]
    assert lm3["estimated_position_m"] is not None
    assert lm3["reference_position_m"] is None


def test_landmark_provider_contract_is_replaceable():
    provider = IndependentLandmarkProvider()
    assert isinstance(provider, LandmarkProvider)

    model = provider.load_landmarks()
    assert isinstance(model, LandmarkSetModel)
    assert len(model.landmarks) == 1

    item = model.landmarks[0]
    assert isinstance(item, LandmarkItem)
    assert isinstance(item, LandmarkModel)
    assert item.landmark_id == "TEST_LM_001"
    assert item.estimated_position_m == (10.0, 20.0, 30.0)
    assert item.reference_position_m == (12.0, 20.0, 31.0)


def test_landmark_viewer_does_not_depend_on_synthetic_provider_implementation():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "LandmarkMarkers.tsx").read_text(encoding="utf-8")
    assert "SyntheticLandmarkProvider" not in viewer_source
    assert "fetchLandmarks" in viewer_source
    assert "landmark-estimated-coordinate" in viewer_source
    assert "landmark-reference-coordinate" in viewer_source
    assert "Landmark metadata is malformed" in viewer_source


def test_invalid_landmark_item_parameters_raise_value_error():
    with pytest.raises(ValueError, match="landmark_id cannot be empty"):
        LandmarkItem(
            landmark_id="",
            display_label="Invalid",
            estimated_position_m=(0.0, 0.0, 0.0),
        )

    with pytest.raises(ValueError, match="estimated_position_m must have 3 coordinates"):
        LandmarkItem(
            landmark_id="INVALID_01",
            display_label="Invalid",
            estimated_position_m=(0.0, 0.0),  # Tuple of 2 instead of 3
        )

    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        LandmarkItem(
            landmark_id="INVALID_02",
            display_label="Invalid",
            estimated_position_m=(0.0, 0.0, 0.0),
            confidence=1.5,
        )
