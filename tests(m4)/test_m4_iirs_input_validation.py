"""M4-08.2 IIRS input-validation tests using deterministic synthetic fixtures."""

import sys
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.iirs import IIRSCube, validate_iirs_cube


def make_cube(**overrides):
    """Return a small synthetic fixture, not a real IIRS measurement."""
    payload = {
        "data": np.array(
            [
                [[1.0, 2.0, 3.0], [4.0, -9999.0, 6.0]],
                [[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
            ],
            dtype=np.float32,
        ),
        "wavelengths_um": np.array([0.8, 1.2, 2.0], dtype=np.float32),
        "pixel_size_m": 20.0,
        "transform": Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
        "crs": "LOCAL_METER_FRAME",
        "nodata": -9999.0,
        "dataset_name": "synthetic-iirs-validation-fixture",
        "sensor": "IIRS",
        "observation_date": "2026-01-01",
        "orbit_id": "fixture-orbit",
        "notes": "Synthetic fixture only.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return IIRSCube(**payload)


def corrupt(cube, **changes):
    """Create a deliberately invalid state to test a read-only validator."""
    for attribute, value in changes.items():
        object.__setattr__(cube, attribute, value)
    return cube


def test_valid_iirs_cube_is_accepted():
    result = validate_iirs_cube(make_cube())
    assert result.is_valid
    assert result.valid
    assert result.errors == ()
    assert result.warnings == ()


@pytest.mark.parametrize(
    "data, expected_error",
    [
        (np.ones((2, 3)), "non-empty 3D"),
        (np.empty((0, 2, 3)), "non-empty 3D"),
        (np.array([[["bad"]]]), "real numeric"),
    ],
)
def test_invalid_cube_structure_is_reported(data, expected_error):
    result = validate_iirs_cube(corrupt(make_cube(), data=data))
    assert not result.is_valid
    assert any(expected_error in error for error in result.errors)


def test_wavelength_dimension_mismatch_is_reported():
    result = validate_iirs_cube(corrupt(make_cube(), wavelengths_um=np.array([0.8, 1.2])))
    assert not result.is_valid
    assert "wavelength_count_matches_bands" in result.checks
    assert any("number of data bands" in error for error in result.errors)


@pytest.mark.parametrize("wavelengths", [np.array([0.8, np.nan, 2.0]), np.array([0.8, np.inf, 2.0]), np.array([0.8, -1.0, 2.0])])
def test_invalid_wavelength_values_are_reported(wavelengths):
    result = validate_iirs_cube(corrupt(make_cube(), wavelengths_um=wavelengths))
    assert not result.is_valid
    assert any("positive finite" in error for error in result.errors)


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_invalid_spectral_values_are_detected(invalid_value):
    data = make_cube().data.copy()
    data[0, 0, 0] = invalid_value
    result = validate_iirs_cube(corrupt(make_cube(), data=data))
    assert not result.is_valid
    assert any("NaN or infinite" in error for error in result.errors)


def test_nodata_values_are_excluded_without_preprocessing():
    cube = make_cube()
    original_data = cube.data.copy()
    result = validate_iirs_cube(cube)
    assert result.is_valid
    assert np.array_equal(cube.data, original_data)

    nan_cube = make_cube(data=np.array([[[1.0, np.nan, 3.0]]]), nodata=np.nan)
    assert validate_iirs_cube(nan_cube).is_valid


def test_all_nodata_cube_is_reported_as_unusable():
    cube = make_cube(data=np.full((1, 1, 3), -9999.0), wavelengths_um=np.array([0.8, 1.2, 2.0]))
    result = validate_iirs_cube(cube)
    assert not result.is_valid
    assert any("no finite samples outside nodata" in error for error in result.errors)


def test_invalid_pixel_size_is_reported():
    result = validate_iirs_cube(corrupt(make_cube(), pixel_size_m=0.0))
    assert not result.is_valid
    assert any("pixel_size_m" in error for error in result.errors)


@pytest.mark.parametrize(
    "attribute, value, expected_error",
    [
        ("transform", Affine.scale(10.0, -20.0), "transform pixel scale"),
        ("crs", "", "crs must be"),
    ],
)
def test_invalid_spatial_metadata_is_reported(attribute, value, expected_error):
    result = validate_iirs_cube(corrupt(make_cube(), **{attribute: value}))
    assert not result.is_valid
    assert any(expected_error in error for error in result.errors)


def test_valid_optional_spatial_and_source_metadata_is_accepted():
    cube = make_cube(crs=None, observation_date=None, orbit_id=None)
    assert validate_iirs_cube(cube).is_valid


def test_repeated_validation_is_deterministic():
    cube = make_cube()
    assert validate_iirs_cube(cube).to_dict() == validate_iirs_cube(cube).to_dict()


def test_validation_preserves_all_cube_state_and_performs_no_preprocessing():
    cube = make_cube()
    original_data = cube.data.copy()
    original_wavelengths = cube.wavelengths_um.copy()
    original_pixel_size = cube.pixel_size_m
    original_transform = tuple(cube.transform)
    original_crs = cube.crs
    original_nodata = cube.nodata
    original_metadata = (
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        dict(cube.extra),
    )

    result = validate_iirs_cube(cube)

    assert result.is_valid
    assert np.array_equal(cube.data, original_data)
    assert np.array_equal(cube.wavelengths_um, original_wavelengths)
    assert cube.pixel_size_m == original_pixel_size
    assert tuple(cube.transform) == original_transform
    assert cube.crs == original_crs
    assert cube.nodata == original_nodata
    assert (
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        cube.extra,
    ) == original_metadata


def test_invalid_input_type_is_reported_without_raising():
    result = validate_iirs_cube(object())
    assert not result.is_valid
    assert result.errors == ("cube must be an IIRSCube instance.",)
