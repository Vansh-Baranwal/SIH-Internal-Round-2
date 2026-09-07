"""M4-09.1 tests for the input-only water-ice evidence contract."""

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.water_ice import (
    WaterIceEvidenceLayer,
    WaterIceEvidenceSource,
)


def make_layer(**overrides):
    """Return deterministic synthetic contract data, not scientific validation."""
    payload = {
        "source": WaterIceEvidenceSource.DIVINER,
        "values": np.array([[1.0, np.nan], [3.0, 4.0]], dtype=np.float32),
        "valid_mask": np.array([[True, False], [True, True]], dtype=bool),
        "pixel_size_m": 100.0,
        "transform": Affine.translation(1000.0, 2000.0) @ Affine.scale(100.0, -100.0),
        "crs": "LOCAL_METER_FRAME",
        "nodata": np.nan,
        "dataset_name": "synthetic-diviner-evidence",
        "sensor": "Diviner",
        "observation_date": "2026-01-01",
        "orbit_id": "synthetic-orbit",
        "notes": "Synthetic fixture only; it does not establish water ice.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return WaterIceEvidenceLayer(**payload)


def test_valid_construction_preserves_spatial_evidence_only():
    layer = make_layer()
    assert layer.shape == (2, 2)
    assert layer.source is WaterIceEvidenceSource.DIVINER
    assert layer.valid_mask.tolist() == [[True, False], [True, True]]
    assert not hasattr(layer, "confidence")
    assert not hasattr(layer, "register")
    assert not hasattr(layer, "hydration_formula")


@pytest.mark.parametrize(
    "values",
    [np.ones(3), np.ones((1, 2, 3)), np.ones((0, 2)), np.array([[True]]), np.array([[1 + 2j]])],
)
def test_values_must_be_non_empty_2d_real_numeric(values):
    with pytest.raises((TypeError, ValueError)):
        make_layer(values=values, valid_mask=np.ones(np.asarray(values).shape, dtype=bool))


@pytest.mark.parametrize("valid_mask", [np.ones(4, dtype=bool), np.ones((1, 2, 3), dtype=bool)])
def test_valid_mask_must_be_2d(valid_mask):
    with pytest.raises(ValueError, match="valid_mask must be a 2D"):
        make_layer(valid_mask=valid_mask)


def test_valid_mask_must_be_boolean():
    with pytest.raises(TypeError, match="valid_mask must be boolean"):
        make_layer(valid_mask=np.ones((2, 2), dtype=np.uint8))


def test_values_and_valid_mask_shapes_must_match():
    with pytest.raises(ValueError, match="shape must match"):
        make_layer(valid_mask=np.ones((1, 2), dtype=bool))


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"pixel_size_m": 0.0}, "positive finite"),
        ({"transform": "not-an-affine"}, "affine.Affine"),
        ({"transform": Affine(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)}, "non-zero spatial"),
        ({"transform": Affine.scale(20.0, -20.0)}, "pixel scale"),
        ({"crs": "  "}, "crs"),
    ],
)
def test_invalid_spatial_metadata_is_rejected(override, expected):
    with pytest.raises((TypeError, ValueError), match=expected):
        make_layer(**override)


def test_nodata_semantics_are_explicit_and_coherent():
    numeric_nodata = make_layer(
        values=np.array([[1.0, -9999.0], [3.0, 4.0]]),
        nodata=-9999.0,
    )
    assert not numeric_nodata.valid_mask[0, 1]

    with pytest.raises(ValueError, match="invalid values"):
        make_layer(values=np.array([[1.0, 2.0], [3.0, 4.0]]))
    with pytest.raises(ValueError, match="nodata=None"):
        make_layer(nodata=None)


@pytest.mark.parametrize(
    "override",
    [
        {"dataset_name": ""},
        {"dataset_name": "   "},
        {"source": "Diviner"},
        {"sensor": ""},
    ],
)
def test_required_provenance_and_identity_are_validated(override):
    with pytest.raises((TypeError, ValueError)):
        make_layer(**override)


def test_invalid_mask_is_the_contractual_invalid_data_indicator():
    layer = make_layer()
    assert np.isnan(layer.values[~layer.valid_mask]).all()
    assert np.isfinite(layer.values[layer.valid_mask]).all()
    with pytest.raises(ValueError, match="valid values"):
        make_layer(valid_mask=np.ones((2, 2), dtype=bool))


def test_contract_attributes_are_immutable():
    layer = make_layer()
    with pytest.raises(FrozenInstanceError):
        layer.dataset_name = "other"


def test_serialization_is_deterministic_and_json_friendly():
    layer = make_layer(extra={"z": 1, "a": {"y": "last", "b": "first"}})
    payload = layer.to_dict()
    assert isinstance(payload["values"], list)
    assert isinstance(payload["valid_mask"], list)
    assert payload["nodata"] == "NaN"
    assert payload["values"][0][1] == "NaN"
    assert list(payload["extra"]) == ["a", "z"]
    assert list(payload["extra"]["a"]) == ["b", "y"]
    assert payload == layer.to_dict()


def test_serialization_round_trip_preserves_contract_semantics():
    original = make_layer()
    reconstructed = WaterIceEvidenceLayer.from_dict(original.to_dict())
    assert reconstructed == original
    assert reconstructed.to_dict() == original.to_dict()


def test_repeated_construction_and_serialization_are_deterministic():
    layers = [make_layer() for _ in range(3)]
    assert all(layer == layers[0] for layer in layers)
    assert all(layer.to_dict() == layers[0].to_dict() for layer in layers)
