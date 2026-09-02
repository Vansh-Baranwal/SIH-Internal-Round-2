"""M4-08.4 generic IIRS band-ratio tests with synthetic fixtures only."""

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
    preprocess_iirs_cube,
)


def make_cube(**overrides):
    """Return a tiny synthetic cube; it is not a real IIRS measurement."""
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
        "dataset_name": "synthetic-iirs-ratio-fixture",
        "sensor": "IIRS",
        "observation_date": "2026-01-01",
        "orbit_id": "fixture-orbit",
        "notes": "Synthetic fixture only.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return IIRSCube(**payload)


def corrupt(cube, **changes):
    """Deliberately create invalid numerical test data without production mutation."""
    for attribute, value in changes.items():
        object.__setattr__(cube, attribute, value)
    return cube


def ratio_for(cube, numerator=0, denominator=1):
    preprocessed = preprocess_iirs_cube(cube)
    return compute_iirs_band_ratio(cube, preprocessed, numerator, denominator), preprocessed


def test_basic_ratio_calculation_and_spatial_shape():
    result, _ = ratio_for(make_cube())
    assert result.ratio_map.shape == (2, 2)
    assert result.valid_mask.shape == (2, 2)
    assert result.valid_mask.all()
    assert result.ratio_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]


def test_band_selection_and_wavelength_metadata():
    cube = make_cube()
    forward, preprocessed = ratio_for(cube, 0, 1)
    reverse = compute_iirs_band_ratio(cube, preprocessed, 1, 0)
    assert forward.numerator_band == 0
    assert forward.denominator_band == 1
    assert forward.numerator_wavelength_um == pytest.approx(0.8)
    assert forward.denominator_wavelength_um == pytest.approx(1.2)
    assert np.allclose(reverse.ratio_map, 0.5)


def test_nodata_mask_propagates_to_ratio_output():
    data = make_cube().data.copy()
    data[0, 1, 0] = -9999.0
    result, _ = ratio_for(make_cube(data=data))
    assert not result.valid_mask[0, 1]
    assert np.isnan(result.ratio_map[0, 1])
    assert result.valid_mask.sum() == 3


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_numerator_values_propagate_as_invalid(invalid_value):
    cube = make_cube()
    data = cube.data.copy()
    data[0, 0, 0] = invalid_value
    result, _ = ratio_for(corrupt(cube, data=data))
    assert not result.valid_mask[0, 0]
    assert np.isnan(result.ratio_map[0, 0])


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_denominator_values_propagate_as_invalid(invalid_value):
    cube = make_cube()
    data = cube.data.copy()
    data[0, 0, 1] = invalid_value
    result, _ = ratio_for(corrupt(cube, data=data))
    assert not result.valid_mask[0, 0]
    assert np.isnan(result.ratio_map[0, 0])


def test_zero_denominator_is_invalid_and_never_produces_infinity():
    data = make_cube().data.copy()
    data[1, 0, 1] = 0.0
    result, _ = ratio_for(make_cube(data=data))
    assert not result.valid_mask[1, 0]
    assert np.isnan(result.ratio_map[1, 0])
    assert not np.isinf(result.ratio_map).any()


@pytest.mark.parametrize("numerator, denominator", [(-1, 1), (0, 3), (True, 1), (0, "1")])
def test_invalid_band_selection_is_rejected(numerator, denominator):
    cube = make_cube()
    preprocessed = preprocess_iirs_cube(cube)
    with pytest.raises((TypeError, ValueError)):
        compute_iirs_band_ratio(cube, preprocessed, numerator, denominator)


def test_cube_and_preprocessing_result_are_not_mutated():
    cube = make_cube()
    preprocessed = preprocess_iirs_cube(cube)
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
    original_normalized = preprocessed.normalized_data.copy()
    original_mask = preprocessed.valid_mask.copy()
    original_preprocessing_metadata = (
        preprocessed.normalization_min,
        preprocessed.normalization_max,
        preprocessed.normalization_method,
        preprocessed.input_validation.to_dict(),
    )

    compute_iirs_band_ratio(cube, preprocessed, 0, 1)

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
    assert np.array_equal(preprocessed.normalized_data, original_normalized)
    assert np.array_equal(preprocessed.valid_mask, original_mask)
    assert (
        preprocessed.normalization_min,
        preprocessed.normalization_max,
        preprocessed.normalization_method,
        preprocessed.input_validation.to_dict(),
    ) == original_preprocessing_metadata


def test_repeated_execution_is_equal_and_serialization_is_deterministic():
    cube = make_cube()
    preprocessed = preprocess_iirs_cube(cube)
    first = compute_iirs_band_ratio(cube, preprocessed, 0, 1)
    second = compute_iirs_band_ratio(cube, preprocessed, 0, 1)
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert isinstance(first.to_dict()["ratio_map"], list)
    assert isinstance(first.to_dict()["valid_mask"], list)
