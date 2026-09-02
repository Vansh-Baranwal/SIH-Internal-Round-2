"""M4-08.1 IIRS data-contract tests using deterministic synthetic fixtures."""

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

from lunar_hazard_mapper.scientific.iirs import IIRSCube


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
        "dataset_name": "synthetic-iirs-contract-fixture",
        "sensor": "IIRS",
        "observation_date": "2026-01-01",
        "orbit_id": "fixture-orbit",
        "notes": "Synthetic fixture only.",
        "extra": {"fixture": True},
    }
    payload.update(overrides)
    return IIRSCube(**payload)


def test_valid_construction_and_shape_orientation():
    cube = make_cube()
    assert cube.data.shape == (2, 2, 3)
    assert cube.wavelengths_um.shape == (3,)
    assert cube.pixel_size_m == 20.0


@pytest.mark.parametrize("data", [np.ones((2, 3)), np.ones((2, 3, 4, 5)), np.ones((0, 2, 3))])
def test_shape_dimension_validation(data):
    with pytest.raises(ValueError):
        make_cube(data=data)


def test_wavelength_band_consistency_validation():
    with pytest.raises(ValueError, match="number of data bands"):
        make_cube(wavelengths_um=np.array([1.0, 2.0]))


@pytest.mark.parametrize("data", ["not-an-array", np.array([[["bad"]]]), np.array([[[True]]])])
def test_invalid_input_rejection(data):
    with pytest.raises((TypeError, ValueError)):
        make_cube(data=data)


@pytest.mark.parametrize("pixel_size_m", [0.0, -1.0, float("nan"), "20"])
def test_pixel_size_validation(pixel_size_m):
    with pytest.raises((TypeError, ValueError)):
        make_cube(pixel_size_m=pixel_size_m)


def test_nodata_behavior_and_valid_mask():
    cube = make_cube()
    assert cube.valid_mask.dtype == bool
    assert cube.valid_mask.shape == cube.data.shape
    assert not cube.valid_mask[0, 1, 1]
    assert cube.valid_mask.sum() == cube.data.size - 1

    no_nodata = make_cube(nodata=None)
    assert no_nodata.valid_mask.all()

    nan_nodata = make_cube(data=np.array([[[1.0, np.nan, 3.0]]]), wavelengths_um=np.array([1.0, 2.0, 3.0]), nodata=np.nan)
    assert nan_nodata.valid_mask.tolist() == [[[True, False, True]]]


def test_equality_and_inequality():
    assert make_cube() == make_cube()
    assert make_cube() != make_cube(dataset_name="another-fixture")


def test_contract_attributes_are_immutable():
    cube = make_cube()
    with pytest.raises(FrozenInstanceError):
        cube.sensor = "other"


def test_deterministic_serialization_uses_python_lists():
    cube = make_cube(extra={"z": 1, "a": "first"})
    payload = cube.to_dict()
    assert isinstance(payload["data"], list)
    assert isinstance(payload["wavelengths_um"], list)
    assert list(payload["extra"]) == ["a", "z"]
    assert payload == cube.to_dict()


def test_serialization_round_trip():
    original = make_cube()
    reconstructed = IIRSCube.from_dict(original.to_dict())
    assert reconstructed == original
    assert reconstructed.to_dict() == original.to_dict()


def test_invalid_serialized_data_rejection():
    with pytest.raises(ValueError, match="missing required"):
        IIRSCube.from_dict({"data": []})
    with pytest.raises(ValueError, match="transform"):
        IIRSCube.from_dict({
            "data": [[[1.0]]],
            "wavelengths_um": [1.0],
            "pixel_size_m": 20.0,
            "transform": [1.0],
            "crs": None,
            "nodata": None,
        })


def test_repeated_construction_determinism():
    cubes = [make_cube() for _ in range(5)]
    assert all(cube == cubes[0] for cube in cubes)
    assert all(cube.to_dict() == cubes[0].to_dict() for cube in cubes)
