"""Focused Phase 10.7 tests; arrays are software-test fixtures only."""

import json

import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain import (
    IlluminationAssessment,
    IlluminationAssessmentStatus,
    IlluminationFilterResult,
    IlluminationFilterStatus,
    NoiseSuppressionConfig,
    NoiseSuppressionRequest,
    NoiseSuppressionStatus,
    suppress_noise,
)


def illumination_result(tmp_path, signed=None, absolute=None, valid=None, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
    signed = np.asarray(signed if signed is not None else np.ones((5, 5), dtype=float))
    absolute = np.asarray(absolute if absolute is not None else np.abs(signed), dtype=float)
    valid = np.asarray(valid if valid is not None else np.ones(signed.shape[:2], dtype=bool), dtype=bool)
    signed_path = tmp_path / "illumination_signed.npy"
    absolute_path = tmp_path / "illumination_absolute.npy"
    mask_path = tmp_path / "illumination_mask.npy"
    np.save(signed_path, signed)
    np.save(absolute_path, absolute)
    np.save(mask_path, valid)
    values = {
        "observation_a_id": "test-a",
        "observation_b_id": "test-b",
        "difference_status": "success",
        "status": IlluminationFilterStatus.SUCCESS,
        "assessment": IlluminationAssessment(
            IlluminationAssessmentStatus.COMPARABLE, {}, (), (), False, ()
        ),
        "raw_signed_difference_reference": "raw-signed.npy",
        "raw_absolute_difference_reference": "raw-absolute.npy",
        "raw_valid_mask_reference": "raw-mask.npy",
        "filtered_signed_difference_reference": str(signed_path),
        "filtered_absolute_difference_reference": str(absolute_path),
        "illumination_mask_reference": str(mask_path),
        "before_statistics": {},
        "after_statistics": {},
        "illumination_compatible_count": int(np.count_nonzero(valid)),
        "illumination_excluded_count": int(valid.size - np.count_nonzero(valid)),
        "retained_fraction": float(np.mean(valid)),
        "normalization_method": "none",
        "warnings": (),
        "failure_reasons": (),
        "provenance": {"phase": "m4_10.6", "raw_difference_preserved": True},
        "message": "test-only illumination result",
    }
    values.update(overrides)
    return IlluminationFilterResult(**values)


def request(tmp_path, **kwargs):
    return NoiseSuppressionRequest(
        illumination_result=illumination_result(tmp_path, **kwargs),
        config=NoiseSuppressionConfig(output_dir=tmp_path / "noise"),
    )


def test_masked_median_suppression_succeeds_and_creates_outputs(tmp_path) -> None:
    signed = np.full((5, 5), 10.0)
    signed[2, 2] = 100.0
    result = suppress_noise(request(tmp_path, signed=signed))
    assert result.status is NoiseSuppressionStatus.SUCCESS
    assert result.method == "masked_median"
    assert result.image_shape == (5, 5)
    assert result.suppressed_signed_difference_reference is not None
    assert np.load(result.suppressed_signed_difference_reference)[2, 2] == 10.0
    assert result.suppressed_absolute_difference_reference is not None
    assert (tmp_path / "noise" / "noise_suppression_summary.json").is_file()


def test_high_frequency_residual_diagnostic_is_finite(tmp_path) -> None:
    signed = np.ones((7, 7), dtype=float)
    signed[::2, ::2] += 5.0
    result = suppress_noise(request(tmp_path, signed=signed))
    assert result.high_frequency_residual_std is not None
    assert np.isfinite(result.high_frequency_residual_std)
    assert result.high_frequency_residual_std > 0.0


def test_conservative_filter_preserves_simple_edge_shape(tmp_path) -> None:
    signed = np.zeros((5, 5), dtype=float)
    signed[:, 3:] = 10.0
    result = suppress_noise(request(tmp_path, signed=signed))
    filtered = np.load(result.suppressed_signed_difference_reference)
    assert np.all(filtered[:, 0:2] == 0.0)
    assert np.all(filtered[:, 4] == 10.0)


def test_invalid_pixels_remain_nan_and_mask_is_propagated(tmp_path) -> None:
    valid = np.ones((5, 5), dtype=bool)
    valid[0, 0] = False
    signed = np.ones((5, 5), dtype=float)
    signed[0, 0] = np.nan
    result = suppress_noise(request(tmp_path, signed=signed, valid=valid))
    filtered = np.load(result.suppressed_signed_difference_reference)
    assert np.isnan(filtered[0, 0])
    assert np.array_equal(np.load(result.propagated_valid_mask_reference), valid)
    assert result.invalid_pixel_count == 1


def test_invalid_neighbors_do_not_contaminate_valid_output(tmp_path) -> None:
    valid = np.ones((5, 5), dtype=bool)
    valid[1:4, 1:4] = False
    signed = np.full((5, 5), 7.0)
    signed[~valid] = np.nan
    result = suppress_noise(request(tmp_path, signed=signed, valid=valid))
    filtered = np.load(result.suppressed_signed_difference_reference)
    assert np.all(filtered[valid] == 7.0)
    assert np.isnan(filtered[~valid]).all()


def test_absolute_difference_remains_nonnegative(tmp_path) -> None:
    signed = np.array([[1.0, -4.0, 2.0], [1.0, -4.0, 2.0], [1.0, -4.0, 2.0]])
    result = suppress_noise(request(tmp_path, signed=signed, absolute=np.abs(signed)))
    assert np.all(np.load(result.suppressed_absolute_difference_reference) >= 0.0)


def test_zero_valid_input_is_explicit(tmp_path) -> None:
    valid = np.zeros((3, 3), dtype=bool)
    result = suppress_noise(request(tmp_path, signed=np.full((3, 3), np.nan), valid=valid))
    assert result.status is NoiseSuppressionStatus.NO_VALID_DATA
    assert result.suppressed_signed_difference_reference is None


def test_missing_filtered_artifact_is_rejected(tmp_path) -> None:
    upstream = illumination_result(tmp_path, filtered_signed_difference_reference=None)
    result = suppress_noise(NoiseSuppressionRequest(upstream, NoiseSuppressionConfig(tmp_path / "noise")))
    assert result.status is NoiseSuppressionStatus.MISSING_FILTERED_ARTIFACT


def test_non_successful_illumination_result_is_rejected(tmp_path) -> None:
    upstream = illumination_result(tmp_path, status=IlluminationFilterStatus.INSUFFICIENT_ILLUMINATION_MODEL)
    result = suppress_noise(NoiseSuppressionRequest(upstream, NoiseSuppressionConfig(tmp_path / "noise")))
    assert result.status is NoiseSuppressionStatus.INVALID_ILLUMINATION_INPUT


def test_shape_and_mask_mismatch_are_rejected(tmp_path) -> None:
    upstream = illumination_result(tmp_path, valid=np.ones((4, 4), dtype=bool))
    result = suppress_noise(NoiseSuppressionRequest(upstream, NoiseSuppressionConfig(tmp_path / "noise")))
    assert result.status is NoiseSuppressionStatus.MASK_MISMATCH


def test_unsupported_method_is_explicit(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        NoiseSuppressionConfig(tmp_path, method="bilateral")


def test_none_method_is_reproducible_and_preserves_values(tmp_path) -> None:
    signed = np.array([[1.0, -2.0], [3.0, 4.0]])
    config = NoiseSuppressionConfig(tmp_path / "noise", method="none")
    result = suppress_noise(NoiseSuppressionRequest(illumination_result(tmp_path, signed=signed), config))
    assert np.array_equal(np.load(result.suppressed_signed_difference_reference), signed)
    assert result.warnings == ("no_suppression_applied",)


def test_repeated_runs_are_numerically_reproducible(tmp_path) -> None:
    signed = np.arange(25, dtype=float).reshape(5, 5)
    first = suppress_noise(request(tmp_path / "first", signed=signed))
    second = suppress_noise(request(tmp_path / "second", signed=signed))
    assert np.array_equal(np.load(first.suppressed_signed_difference_reference), np.load(second.suppressed_signed_difference_reference), equal_nan=True)
    assert first.method == second.method
    assert first.kernel_size == second.kernel_size


def test_provenance_and_integrity_message_are_preserved(tmp_path) -> None:
    result = suppress_noise(request(tmp_path))
    payload = result.to_dict()
    assert payload["provenance"]["upstream_phase"] == "m4_10.6"
    assert "physical lunar change" in payload["message"]
    assert "change_confidence" not in json.dumps(payload).lower()