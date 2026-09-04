"""Focused Phase 10.8 tests; arrays are deterministic test data only."""

import json
from pathlib import Path

import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain import (
    ChangeCandidateConfig,
    ChangeCandidateRequest,
    ChangeCandidateStatus,
    DataProvenance,
    NoiseSuppressionResult,
    NoiseSuppressionStatus,
    detect_change_candidates,
)


def noise_result(tmp_path, signed=None, absolute=None, valid=None, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
    signed = np.asarray(signed if signed is not None else np.zeros((7, 7), dtype=float))
    absolute = np.asarray(absolute if absolute is not None else np.abs(signed), dtype=float)
    valid = np.asarray(valid if valid is not None else np.ones(signed.shape, dtype=bool), dtype=bool)
    signed_path = tmp_path / "suppressed_signed.npy"
    absolute_path = tmp_path / "suppressed_absolute.npy"
    mask_path = tmp_path / "valid_mask.npy"
    np.save(signed_path, signed)
    np.save(absolute_path, absolute)
    np.save(mask_path, valid)
    values = {
        "observation_a_id": "test-a",
        "observation_b_id": "test-b",
        "illumination_status": "success",
        "status": NoiseSuppressionStatus.SUCCESS,
        "method": "masked_median",
        "kernel_size": 3,
        "minimum_valid_neighbors": 2,
        "image_shape": signed.shape,
        "channel_count": 1,
        "valid_pixel_count": int(np.count_nonzero(valid)),
        "invalid_pixel_count": int(valid.size - np.count_nonzero(valid)),
        "signed_difference_input_reference": "phase10.6-signed.npy",
        "absolute_difference_input_reference": "phase10.6-absolute.npy",
        "valid_mask_input_reference": "phase10.6-mask.npy",
        "suppressed_signed_difference_reference": str(signed_path),
        "suppressed_absolute_difference_reference": str(absolute_path),
        "propagated_valid_mask_reference": str(mask_path),
        "before_statistics": {},
        "after_statistics": {},
        "high_frequency_residual_std": 0.0,
        "warnings": (),
        "failure_reasons": (),
        "provenance": {"phase": "m4_10.7", "raw_difference_preserved": True},
        "message": "test-only noise-suppressed representation",
    }
    values.update(overrides)
    return NoiseSuppressionResult(**values)


def request(tmp_path, signed=None, absolute=None, valid=None, **kwargs):
    return ChangeCandidateRequest(
        noise_result=noise_result(tmp_path, signed=signed, absolute=absolute, valid=valid, **kwargs),
        config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=5.0),
    )


def test_coherent_region_is_detected_with_statistics(tmp_path) -> None:
    signed = np.zeros((7, 7), dtype=float)
    signed[2:5, 2:5] = 8.0
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert result.status is ChangeCandidateStatus.SUCCESS
    assert result.candidate_count == 1
    candidate = result.candidates[0]
    assert candidate.candidate_id == "candidate-0001"
    assert candidate.pixel_count == 9
    assert candidate.bounding_box == {"min_row": 2, "min_col": 2, "max_row": 4, "max_col": 4}
    assert candidate.centroid == {"row": 3.0, "col": 3.0}
    assert candidate.peak_absolute_difference == 8.0
    assert candidate.signed_mean == 8.0
    assert candidate.sign_characterization == "positive"


def test_isolated_noise_pixel_is_not_candidate(tmp_path) -> None:
    signed = np.zeros((7, 7), dtype=float)
    signed[3, 3] = 9.0
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert result.status is ChangeCandidateStatus.NO_CANDIDATES
    assert result.candidate_count == 0


def test_multiple_components_have_deterministic_ids(tmp_path) -> None:
    signed = np.zeros((9, 9), dtype=float)
    signed[1:3, 1:3] = 7.0
    signed[6:8, 6:8] = -9.0
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert [candidate.candidate_id for candidate in result.candidates] == ["candidate-0001", "candidate-0002"]
    assert [candidate.sign_characterization for candidate in result.candidates] == ["positive", "negative"]


def test_invalid_high_difference_cannot_be_candidate(tmp_path) -> None:
    signed = np.zeros((7, 7), dtype=float)
    valid = np.ones((7, 7), dtype=bool)
    valid[2:5, 2:5] = False
    signed[2:5, 2:5] = 100.0
    result = detect_change_candidates(request(tmp_path, signed=signed, valid=valid))
    assert result.status is ChangeCandidateStatus.NO_CANDIDATES
    assert np.all(np.load(result.candidate_mask_reference)[~valid] == 0)


def test_nan_high_difference_cannot_be_candidate(tmp_path) -> None:
    signed = np.zeros((7, 7), dtype=float)
    signed[2:5, 2:5] = np.nan
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert result.status is ChangeCandidateStatus.NO_CANDIDATES


def test_threshold_boundary_is_inclusive_and_configurable(tmp_path) -> None:
    signed = np.zeros((5, 5), dtype=float)
    signed[1:4, 1:4] = 5.0
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert result.candidate_count == 1


def test_no_valid_data_is_explicit(tmp_path) -> None:
    valid = np.zeros((4, 4), dtype=bool)
    result = detect_change_candidates(request(tmp_path, valid=valid, signed=np.full((4, 4), np.nan)))
    assert result.status is ChangeCandidateStatus.NO_VALID_DATA
    assert result.candidate_mask_reference is None


def test_shape_mismatch_is_rejected(tmp_path) -> None:
    result = detect_change_candidates(request(tmp_path, valid=np.ones((2, 2), dtype=bool)))
    assert result.status is ChangeCandidateStatus.SHAPE_MISMATCH


def test_missing_suppressed_artifact_is_rejected(tmp_path) -> None:
    result = detect_change_candidates(request(tmp_path, suppressed_signed_difference_reference=None))
    assert result.status is ChangeCandidateStatus.MISSING_SUPPRESSED_ARTIFACT


def test_non_successful_noise_result_is_rejected(tmp_path) -> None:
    result = detect_change_candidates(request(tmp_path, status=NoiseSuppressionStatus.NO_VALID_DATA))
    assert result.status is ChangeCandidateStatus.INVALID_NOISE_INPUT


def test_candidate_mask_preserves_invalid_valid_non_candidate_and_candidate_states(tmp_path) -> None:
    signed = np.zeros((5, 5), dtype=float)
    valid = np.ones((5, 5), dtype=bool)
    valid[0, 0] = False
    signed[2:4, 2:4] = 8.0
    result = detect_change_candidates(request(tmp_path, signed=signed, valid=valid))
    mask = np.load(result.candidate_mask_reference)
    assert mask[0, 0] == 0
    assert mask[0, 1] == 1
    assert mask[2, 2] == 2


def test_signed_mixed_response_is_retained_without_physical_interpretation(tmp_path) -> None:
    signed = np.zeros((5, 5), dtype=float)
    signed[1:4, 1:4] = np.array([[8, -8, 8], [-8, 8, -8], [8, -8, 8]])
    result = detect_change_candidates(request(tmp_path, signed=signed))
    assert result.candidates[0].sign_characterization == "mixed"
    assert result.candidates[0].signed_median == 8.0
    assert "physical lunar change" in result.message


def test_artifacts_and_summary_are_created(tmp_path) -> None:
    result = detect_change_candidates(request(tmp_path, signed=np.full((5, 5), 8.0)))
    assert result.status is ChangeCandidateStatus.SUCCESS
    assert Path(result.candidate_labels_reference).is_file()
    assert Path(result.candidate_list_reference).is_file()
    assert Path(tmp_path / "candidates" / "change_candidate_summary.json").is_file()


def test_repeated_runs_are_reproducible(tmp_path) -> None:
    signed = np.zeros((7, 7), dtype=float)
    signed[2:5, 2:5] = 8.0
    first = detect_change_candidates(request(tmp_path / "one", signed=signed))
    second = detect_change_candidates(request(tmp_path / "two", signed=signed))
    assert first.to_dict()["candidates"] == second.to_dict()["candidates"]
    assert np.array_equal(np.load(first.candidate_labels_reference), np.load(second.candidate_labels_reference))


def test_provenance_and_no_confidence_are_explicit(tmp_path) -> None:
    result = detect_change_candidates(request(tmp_path))
    payload = result.to_dict()
    assert payload["provenance"]["upstream_phase"] == "m4_10.7"
    assert "confidence" not in json.dumps(payload).lower()
    assert "candidate" in payload["message"].lower()