"""M4-08.5 numerical IIRS feature-set tests using synthetic fixtures only."""

import sys
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.iirs import (
    IIRSCube,
    compute_iirs_band_ratio,
    extract_iirs_spectral_features,
    preprocess_iirs_cube,
)


def make_cube(**overrides):
    """Return a small synthetic fixture, not a real IIRS measurement."""
    payload = {
        "data": np.array(
            [
                [[4.0, 2.0, 0.0], [8.0, 4.0, 0.0]],
                [[6.0, 3.0, 0.0], [2.0, 1.0, 0.0]],
            ],
            dtype=np.float32,
        ),
        "wavelengths_um": np.array([0.8, 1.2, 2.0], dtype=np.float32),
        "pixel_size_m": 20.0,
        "transform": Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
        "crs": "LOCAL_METER_FRAME",
        "nodata": -9999.0,
        "dataset_name": "synthetic-iirs-feature-fixture",
        "sensor": "IIRS",
        "observation_date": "2026-01-01",
        "orbit_id": "fixture-orbit",
        "notes": "Synthetic fixture only.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return IIRSCube(**payload)


def corrupt(cube, **changes):
    """Create invalid numerical test data without changing production contracts."""
    for attribute, value in changes.items():
        object.__setattr__(cube, attribute, value)
    return cube


def make_inputs(cube=None):
    cube = make_cube() if cube is None else cube
    preprocessed = preprocess_iirs_cube(cube)
    forward = compute_iirs_band_ratio(cube, preprocessed, 0, 1)
    reverse = compute_iirs_band_ratio(cube, preprocessed, 1, 0)
    return cube, preprocessed, forward, reverse


def test_valid_feature_extraction_preserves_spatial_shape():
    _, preprocessed, forward, reverse = make_inputs()
    features = extract_iirs_spectral_features(preprocessed, [forward, reverse])
    assert features.feature_maps.shape == (2, 2, 2)
    assert features.valid_mask.shape == (2, 2, 2)
    assert features.valid_mask.all()


def test_feature_values_reuse_existing_ratio_maps_without_recalculation():
    _, preprocessed, forward, reverse = make_inputs()
    features = extract_iirs_spectral_features(preprocessed, [forward, reverse])
    assert np.array_equal(features.feature_maps[:, :, 0], forward.ratio_map, equal_nan=True)
    assert np.array_equal(features.feature_maps[:, :, 1], reverse.ratio_map, equal_nan=True)
    assert features.feature_maps[:, :, 0].tolist() == [[2.0, 2.0], [2.0, 2.0]]
    assert features.feature_maps[:, :, 1].tolist() == [[0.5, 0.5], [0.5, 0.5]]


def test_feature_names_and_ratio_provenance_are_deterministic():
    _, preprocessed, forward, reverse = make_inputs()
    features = extract_iirs_spectral_features(preprocessed, [forward, reverse])
    assert features.feature_names == ("ratio_band_0_over_band_1", "ratio_band_1_over_band_0")
    assert features.ratio_bands == ((0, 1), (1, 0))
    assert features.ratio_wavelengths_um[0] == pytest.approx((0.8, 1.2))
    assert features.ratio_wavelengths_um[1] == pytest.approx((1.2, 0.8))
    assert features.normalization_methods == ("global_minmax", "global_minmax")


def test_nodata_and_zero_denominator_masks_propagate_to_features():
    data = make_cube().data.copy()
    data[0, 0, 0] = -9999.0
    data[1, 0, 1] = 0.0
    cube, preprocessed, forward, _ = make_inputs(make_cube(data=data))
    features = extract_iirs_spectral_features(preprocessed, [forward])
    assert not features.valid_mask[0, 0, 0]
    assert not features.valid_mask[1, 0, 0]
    assert np.isnan(features.feature_maps[0, 0, 0])
    assert np.isnan(features.feature_maps[1, 0, 0])
    assert cube.data[0, 0, 0] == -9999.0


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_nan_and_infinite_source_values_remain_invalid_features(invalid_value):
    cube = make_cube()
    data = cube.data.copy()
    data[0, 1, 0] = invalid_value
    _, preprocessed, forward, _ = make_inputs(corrupt(cube, data=data))
    features = extract_iirs_spectral_features(preprocessed, [forward])
    assert not features.valid_mask[0, 1, 0]
    assert np.isnan(features.feature_maps[0, 1, 0])


def test_original_cube_preprocessing_and_ratio_results_are_not_mutated():
    cube, preprocessed, forward, reverse = make_inputs()
    original_cube_data = cube.data.copy()
    original_wavelengths = cube.wavelengths_um.copy()
    original_cube_metadata = (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        dict(cube.extra),
    )
    original_preprocessed = (preprocessed.normalized_data.copy(), preprocessed.valid_mask.copy(), preprocessed.to_dict())
    original_forward = (forward.ratio_map.copy(), forward.valid_mask.copy(), forward.to_dict())
    original_reverse = (reverse.ratio_map.copy(), reverse.valid_mask.copy(), reverse.to_dict())

    extract_iirs_spectral_features(preprocessed, [forward, reverse])

    assert np.array_equal(cube.data, original_cube_data)
    assert np.array_equal(cube.wavelengths_um, original_wavelengths)
    assert (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        cube.extra,
    ) == original_cube_metadata
    assert np.array_equal(preprocessed.normalized_data, original_preprocessed[0])
    assert np.array_equal(preprocessed.valid_mask, original_preprocessed[1])
    assert preprocessed.to_dict() == original_preprocessed[2]
    assert np.array_equal(forward.ratio_map, original_forward[0])
    assert np.array_equal(forward.valid_mask, original_forward[1])
    assert forward.to_dict() == original_forward[2]
    assert np.array_equal(reverse.ratio_map, original_reverse[0])
    assert np.array_equal(reverse.valid_mask, original_reverse[1])
    assert reverse.to_dict() == original_reverse[2]


def test_repeated_extraction_equality_and_serialization_are_deterministic():
    _, preprocessed, forward, reverse = make_inputs()
    first = extract_iirs_spectral_features(preprocessed, [forward, reverse])
    second = extract_iirs_spectral_features(preprocessed, [forward, reverse])
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert isinstance(first.to_dict()["feature_maps"], list)
    assert isinstance(first.to_dict()["valid_mask"], list)


@pytest.mark.parametrize("ratio_results", [[], (), "not-a-sequence"])
def test_empty_or_invalid_feature_input_is_rejected_deterministically(ratio_results):
    _, preprocessed, _, _ = make_inputs()
    with pytest.raises((TypeError, ValueError)):
        extract_iirs_spectral_features(preprocessed, ratio_results)
