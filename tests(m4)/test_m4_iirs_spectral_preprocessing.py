"""M4-08.3 IIRS preprocessing tests using deterministic synthetic fixtures."""

import sys
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.iirs import IIRSCube, preprocess_iirs_cube


def make_cube(**overrides):
    """Return a tiny synthetic fixture, not a real IIRS measurement."""
    payload = {
        "data": np.array(
            [
                [[2.0, 4.0, -9999.0], [6.0, 8.0, 10.0]],
                [[12.0, 14.0, 16.0], [18.0, 20.0, 22.0]],
            ],
            dtype=np.float32,
        ),
        "wavelengths_um": np.array([0.8, 1.2, 2.0], dtype=np.float32),
        "pixel_size_m": 20.0,
        "transform": Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
        "crs": "LOCAL_METER_FRAME",
        "nodata": -9999.0,
        "dataset_name": "synthetic-iirs-preprocessing-fixture",
        "sensor": "IIRS",
        "observation_date": "2026-01-01",
        "orbit_id": "fixture-orbit",
        "notes": "Synthetic fixture only.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return IIRSCube(**payload)


def corrupt(cube, **changes):
    """Create invalid numerical test state without changing production contracts."""
    for attribute, value in changes.items():
        object.__setattr__(cube, attribute, value)
    return cube


def test_valid_cube_can_be_preprocessed_with_preserved_shape():
    cube = make_cube()
    result = preprocess_iirs_cube(cube)
    assert result.is_valid
    assert result.normalized_data.shape == cube.data.shape == (2, 2, 3)
    assert result.valid_mask.shape == cube.data.shape
    assert result.normalization_method == "global_minmax"


def test_global_minmax_normalization_is_correct_and_deterministic():
    cube = make_cube()
    first = preprocess_iirs_cube(cube)
    second = preprocess_iirs_cube(cube)
    assert first == second
    assert first.normalization_min == 2.0
    assert first.normalization_max == 22.0
    assert first.normalized_data[0, 0, 0] == 0.0
    assert first.normalized_data[1, 1, 2] == 1.0


def test_nodata_is_masked_and_excluded_from_normalization_statistics():
    result = preprocess_iirs_cube(make_cube())
    assert not result.valid_mask[0, 0, 2]
    assert result.normalized_data[0, 0, 2] == -9999.0
    assert result.normalization_min == 2.0
    assert result.normalization_max == 22.0


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_values_are_masked_and_do_not_contaminate_statistics(invalid_value):
    cube = make_cube()
    data = cube.data.copy()
    data[0, 0, 0] = invalid_value
    result = preprocess_iirs_cube(corrupt(cube, data=data))
    assert not result.is_valid
    assert not result.valid_mask[0, 0, 0]
    assert result.normalization_min == 4.0
    assert result.normalization_max == 22.0
    if np.isnan(invalid_value):
        assert np.isnan(result.normalized_data[0, 0, 0])
    else:
        assert result.normalized_data[0, 0, 0] == invalid_value


def test_nan_nodata_is_treated_as_invalid_without_contamination():
    cube = make_cube(
        data=np.array([[[2.0, np.nan, 6.0]]]),
        wavelengths_um=np.array([0.8, 1.2, 2.0]),
        nodata=np.nan,
    )
    result = preprocess_iirs_cube(cube)
    assert result.is_valid
    assert result.valid_mask.tolist() == [[[True, False, True]]]
    assert result.normalization_min == 2.0
    assert result.normalization_max == 6.0
    assert np.isnan(result.normalized_data[0, 0, 1])


def test_invalid_values_are_not_silently_made_valid():
    cube = make_cube()
    data = cube.data.copy()
    data[0, 1, 0] = np.inf
    result = preprocess_iirs_cube(corrupt(cube, data=data))
    assert not result.valid_mask[0, 1, 0]
    assert np.isinf(result.normalized_data[0, 1, 0])


def test_original_cube_is_preserved_including_all_metadata():
    cube = make_cube()
    original_data = cube.data.copy()
    original_wavelengths = cube.wavelengths_um.copy()
    original_properties = (
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

    preprocess_iirs_cube(cube)

    assert np.array_equal(cube.data, original_data)
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
    ) == original_properties


def test_preprocessing_result_is_independent_of_later_source_array_mutation():
    cube = make_cube()
    result = preprocess_iirs_cube(cube)
    normalized_before = result.normalized_data.copy()
    mask_before = result.valid_mask.copy()
    cube.data[0, 0, 0] = 999.0
    assert np.array_equal(result.normalized_data, normalized_before)
    assert np.array_equal(result.valid_mask, mask_before)


def test_constant_valid_data_has_stable_zero_range_normalization():
    cube = make_cube(data=np.full((1, 1, 3), 5.0), wavelengths_um=np.array([0.8, 1.2, 2.0]))
    result = preprocess_iirs_cube(cube)
    assert result.is_valid
    assert result.normalization_min == result.normalization_max == 5.0
    assert result.normalized_data.tolist() == [[[0.0, 0.0, 0.0]]]


def test_all_invalid_values_are_explicit_and_deterministic():
    cube = make_cube(data=np.full((1, 1, 3), -9999.0), wavelengths_um=np.array([0.8, 1.2, 2.0]))
    first = preprocess_iirs_cube(cube)
    second = preprocess_iirs_cube(cube)
    assert not first.is_valid
    assert not first.valid_mask.any()
    assert first.normalization_min is None
    assert first.normalization_max is None
    assert np.array_equal(first.normalized_data, cube.data)
    assert first == second


def test_serialized_result_uses_lists_and_does_not_include_source_cube():
    payload = preprocess_iirs_cube(make_cube()).to_dict()
    assert isinstance(payload["normalized_data"], list)
    assert isinstance(payload["valid_mask"], list)
    assert "source_cube" not in payload
