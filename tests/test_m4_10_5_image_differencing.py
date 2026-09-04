"""Focused Phase 10.5 tests using small test-only image fixtures."""

from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from lunar_hazard_mapper.m4_terrain import (
    DifferenceConfig,
    DifferenceStatus,
    ImageDifferenceResult,
    ImageDifferencingRequest,
    RegistrationStatus,
    TemporalRegistrationResult,
    difference_registered_pair,
)


def registration_result(tmp_path, first, second, **overrides):
    values = {
        "observation_a_id": "test-a",
        "observation_b_id": "test-b",
        "status": RegistrationStatus.SUCCESS,
        "registration_engine": "m2_correspondence_engine",
        "backend_used": None,
        "transformation_model": "affine",
        "transformation_parameters": None,
        "initial_match_count": 4,
        "verified_inlier_count": 4,
        "inlier_ratio": 1.0,
        "spatial_coverage": 1.0,
        "registration_rmse": 0.1,
        "subpixel_refinement_available": True,
        "subpixel_refinement_status": "executed",
        "registered_output_reference": str(first),
        "match_point_output_reference": None,
        "registration_quality_status": "metrics_available",
        "warnings": (),
        "failure_reasons": (),
        "provenance_status": "real_observation_pair",
        "message": "test-only registered pair",
        "reference_image_reference": str(second),
    }
    values.update(overrides)
    return TemporalRegistrationResult(**values)


def write_image(path, values, mode="L"):
    array = np.asarray(values)
    if mode == "L" and np.issubdtype(array.dtype, np.floating):
        mode = "F"
    elif mode in ("L", "RGB"):
        array = array.astype(np.uint8)
    Image.fromarray(array, mode=mode).save(path)


def run_difference(tmp_path, first_values, second_values, **config_overrides):
    extension = ".tif" if any(np.issubdtype(np.asarray(values).dtype, np.floating) for values in (first_values, second_values)) else ".png"
    first = tmp_path / f"registered_a{extension}"
    second = tmp_path / f"reference_b{extension}"
    write_image(first, first_values)
    write_image(second, second_values)
    result = difference_registered_pair(
        ImageDifferencingRequest(
            registration_result(tmp_path, first, second),
            DifferenceConfig(output_dir=tmp_path / "difference", **config_overrides),
        )
    )
    return result


def test_same_sized_grayscale_arrays_have_correct_signed_and_absolute_difference(tmp_path) -> None:
    result = run_difference(tmp_path, [[1, 2], [3, 4]], [[0, 1], [1, 2]])
    assert result.status is DifferenceStatus.SUCCESS
    assert np.array_equal(np.load(result.signed_difference_reference), [[1, 1], [2, 2]])
    assert np.array_equal(np.load(result.absolute_difference_reference), [[1, 1], [2, 2]])


def test_unsigned_input_subtracts_without_wraparound(tmp_path) -> None:
    result = run_difference(tmp_path, [[0]], [[255]])
    assert np.load(result.signed_difference_reference)[0, 0] == -255.0
    assert np.load(result.absolute_difference_reference)[0, 0] == 255.0


def test_float_input_and_statistics_are_correct(monkeypatch, tmp_path) -> None:
    arrays = [
        (np.array([[1.5, 2.5]], dtype=float), np.ones((1, 2), dtype=bool)),
        (np.array([[0.5, 1.0]], dtype=float), np.ones((1, 2), dtype=bool)),
    ]
    import lunar_hazard_mapper.m4_terrain.image_differencing as module
    monkeypatch.setattr(module, "_load_image", lambda path: arrays.pop(0))
    result = difference_registered_pair(ImageDifferencingRequest(registration_result(tmp_path, tmp_path / "a", tmp_path / "b"), DifferenceConfig(tmp_path / "out")))
    assert result.summary_statistics["signed_min"] == 1.0
    assert result.summary_statistics["signed_max"] == 1.5
    assert result.summary_statistics["signed_mean"] == 1.25
    assert result.summary_statistics["absolute_mean"] == 1.25


def test_valid_mask_counts_and_artifacts_are_created(tmp_path) -> None:
    result = run_difference(tmp_path, [[1, 2], [3, 4]], [[0, 1], [1, 2]])
    assert result.valid_pixel_count == 4
    assert result.invalid_pixel_count == 0
    assert result.valid_fraction == 1.0
    assert np.array_equal(np.load(result.valid_mask_reference), np.ones((2, 2), dtype=bool))
    assert (tmp_path / "difference" / "difference_summary.json").is_file()


def test_shape_mismatch_is_rejected_without_resizing(tmp_path) -> None:
    result = run_difference(tmp_path, [[1, 2]], [[1, 2], [3, 4]])
    assert result.status is DifferenceStatus.SHAPE_MISMATCH
    assert result.signed_difference_reference is None


def test_channel_mismatch_is_rejected(tmp_path) -> None:
    first = tmp_path / "a.png"
    second = tmp_path / "b.png"
    write_image(first, [[[1, 2, 3]]], mode="RGB")
    write_image(second, [[1]], mode="L")
    result = difference_registered_pair(ImageDifferencingRequest(registration_result(tmp_path, first, second), DifferenceConfig(tmp_path / "out")))
    assert result.status is DifferenceStatus.CHANNEL_MISMATCH


def test_nan_and_inf_are_excluded_from_statistics(monkeypatch, tmp_path) -> None:
    arrays = [
        (np.array([[1.0, np.nan], [np.inf, 4.0]]), np.array([[True, False], [False, True]])),
        (np.zeros((2, 2), dtype=float), np.ones((2, 2), dtype=bool)),
    ]
    import lunar_hazard_mapper.m4_terrain.image_differencing as module
    monkeypatch.setattr(module, "_load_image", lambda path: arrays.pop(0))
    result = difference_registered_pair(ImageDifferencingRequest(registration_result(tmp_path, tmp_path / "a", tmp_path / "b"), DifferenceConfig(tmp_path / "out")))
    assert result.valid_pixel_count == 2
    assert result.summary_statistics["signed_mean"] == 2.5


def test_zero_valid_pixels_has_explicit_status(monkeypatch, tmp_path) -> None:
    arrays = [
        (np.array([[np.nan]]), np.array([[False]])),
        (np.array([[1.0]]), np.array([[True]])),
    ]
    import lunar_hazard_mapper.m4_terrain.image_differencing as module
    monkeypatch.setattr(module, "_load_image", lambda path: arrays.pop(0))
    result = difference_registered_pair(ImageDifferencingRequest(registration_result(tmp_path, tmp_path / "a", tmp_path / "b"), DifferenceConfig(tmp_path / "out")))
    assert result.status is DifferenceStatus.NO_VALID_COMPARISON
    assert result.summary_statistics["signed_mean"] is None
    assert result.signed_difference_reference is None


def test_missing_registered_output_fails_cleanly(tmp_path) -> None:
    registration = registration_result(tmp_path, tmp_path / "missing-a", tmp_path / "missing-b")
    result = difference_registered_pair(ImageDifferencingRequest(registration, DifferenceConfig(tmp_path / "out")))
    assert result.status is DifferenceStatus.MISSING_REGISTERED_IMAGE


def test_failed_registration_cannot_reach_differencing(tmp_path) -> None:
    registration = registration_result(tmp_path, tmp_path / "a", tmp_path / "b", status=RegistrationStatus.FAILED)
    result = difference_registered_pair(ImageDifferencingRequest(registration, DifferenceConfig(tmp_path / "out")))
    assert result.status is DifferenceStatus.INVALID_REGISTRATION_INPUT
    assert result.failure_reasons == ("invalid_registration_input",)


def test_explicit_normalization_is_reported(tmp_path) -> None:
    result = run_difference(tmp_path, [[0, 10]], [[0, 5]], normalization="minmax")
    assert result.status is DifferenceStatus.SUCCESS
    assert result.normalization_method == "minmax"
    assert "normalization_enabled" in result.warnings


def test_raw_differencing_does_not_apply_illumination_correction(tmp_path) -> None:
    result = run_difference(tmp_path, [[10]], [[4]])
    assert result.normalization_method == "none"
    assert np.load(result.signed_difference_reference)[0, 0] == 6.0


def test_result_serialization_round_trips(tmp_path) -> None:
    result = run_difference(tmp_path, [[1]], [[0]])
    restored = ImageDifferenceResult.from_dict(result.to_dict())
    assert restored.status is DifferenceStatus.SUCCESS
    assert restored.observation_a_id == "test-a"
    assert restored.signed_difference_reference == result.signed_difference_reference


def test_invalid_normalization_configuration_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="normalization"):
        DifferenceConfig(tmp_path, normalization="illumination_corrected")