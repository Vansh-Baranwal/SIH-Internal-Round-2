"""Focused Phase 10.10 candidate-screening tests."""

import json
from pathlib import Path

import numpy as np

from lunar_hazard_mapper.m4_terrain import (
    ChangeClassificationConfig,
    ChangeClassificationRequest,
    CraterEjectaCandidateConfig,
    CraterEjectaCandidateRequest,
    CraterEjectaCandidateStatus,
    SpecializedCandidateType,
    classify_change_candidates,
    detect_change_candidates,
    screen_crater_ejecta_candidates,
)
from test_m4_10_9_change_classification import classify_request


def screening_request(tmp_path, signed, absolute=None, valid=None, **config_kwargs):
    classification_request = classify_request(tmp_path / "classification", signed, absolute=absolute, valid=valid)
    classification = classify_change_candidates(classification_request)
    candidate = classification_request.candidate_result
    noise = classification_request.noise_result
    return CraterEjectaCandidateRequest(
        classification,
        candidate,
        noise,
        CraterEjectaCandidateConfig(tmp_path / "screening", **config_kwargs),
    )


def test_compact_circular_like_candidate_uses_multiple_indicators(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    item = result.candidates[0]
    assert item.candidate_type is SpecializedCandidateType.NEW_CRATER_CANDIDATE
    assert "compact_circular_like_geometry" in item.supporting_indicators
    assert "bounded_aspect_ratio" in item.supporting_indicators
    assert "sufficient_image_space_area" in item.supporting_indicators
    assert item.geometry["equivalent_diameter_pixels"] > 0


def test_elongated_candidate_is_not_crater_like_from_intensity(tmp_path):
    signed = np.zeros((8, 14), dtype=float)
    signed[3, 3:10] = 20.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    item = result.candidates[0]
    assert item.geometry["aspect_ratio"] >= 3.0
    assert item.candidate_type is not SpecializedCandidateType.NEW_CRATER_CANDIDATE


def test_diffuse_morphology_alone_is_not_ejecta(tmp_path):
    signed = np.zeros((11, 11), dtype=float)
    coordinates = [(5, col) for col in range(2, 9)] + [(row, 5) for row in range(2, 9)]
    for row, col in coordinates:
        signed[row, col] = 8.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    item = result.candidates[0]
    assert item.geometry["extent"] < 0.55
    assert item.candidate_type is not SpecializedCandidateType.EJECTA_CANDIDATE


def test_radial_decline_is_recorded_without_physical_interpretation(tmp_path):
    signed = np.zeros((13, 13), dtype=float)
    absolute = np.zeros((13, 13), dtype=float)
    coordinates = [(row, 6) for row in range(3, 10)] + [(6, col) for col in range(3, 10)]
    for row, col in coordinates:
        signed[row, col] = 8.0
        distance = abs(row - 6) + abs(col - 6)
        absolute[row, col] = 14.0 - distance
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed, absolute=absolute, ejecta_min_area_pixels=7, ejecta_max_extent=0.55, ejecta_min_radial_decline=0.10))
    item = result.candidates[0]
    assert item.radial_descriptors["available"] is True
    assert item.radial_descriptors["radial_decline"] >= 0.10
    assert "radial_absolute_difference_decline" in item.supporting_indicators
    assert "deposition" not in json.dumps(item.to_dict()).lower()


def test_boundary_candidate_is_conservative(tmp_path):
    signed = np.zeros((8, 10), dtype=float)
    signed[0:3, 1:4] = 8.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    item = result.candidates[0]
    assert item.geometry["touches_image_boundary"] is True
    assert item.candidate_type is not SpecializedCandidateType.NEW_CRATER_CANDIDATE
    assert "boundary_truncation_limits_morphology" in item.limitations


def test_invalid_mask_and_nan_are_rejected(tmp_path):
    request = screening_request(tmp_path, np.full((5, 5), 8.0))
    mask_path = Path(request.candidate_result.candidate_mask_reference)
    mask = np.load(mask_path)
    mask[0, 0] = 9
    np.save(mask_path, mask)
    result = screen_crater_ejecta_candidates(request)
    assert result.status is CraterEjectaCandidateStatus.INVALID_CANDIDATE_ARTIFACT


def test_insufficient_pixels_are_undetermined(tmp_path):
    signed = np.zeros((5, 5), dtype=float)
    signed[2, 1:4] = 8.0
    request = screening_request(tmp_path, signed, minimum_morphology_pixels=9)
    result = screen_crater_ejecta_candidates(request)
    assert result.candidates[0].candidate_type is SpecializedCandidateType.UNDETERMINED


def test_multiple_candidates_are_screened_independently(tmp_path):
    signed = np.zeros((10, 16), dtype=float)
    signed[2:5, 2:5] = 8.0
    signed[7, 9:14] = -8.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    assert [item.source_candidate_id for item in result.candidates] == ["candidate-0001", "candidate-0002"]
    assert len(result.candidates) == 2


def test_no_specialized_candidates_is_successful_non_error(tmp_path):
    signed = np.zeros((8, 8), dtype=float)
    signed[3:5, 3:5] = 8.0
    result = screen_crater_ejecta_candidates(screening_request(tmp_path, signed))
    assert result.status is CraterEjectaCandidateStatus.NO_SPECIALIZED_CANDIDATES
    assert result.specialized_candidate_count == 0


def test_missing_artifact_and_shape_mismatch_are_explicit(tmp_path):
    request = screening_request(tmp_path / "missing", np.full((5, 5), 8.0))
    Path(request.candidate_result.candidate_labels_reference).unlink()
    missing = screen_crater_ejecta_candidates(request)
    assert missing.status is CraterEjectaCandidateStatus.MISSING_CANDIDATE_ARTIFACT

    mismatch_request = screening_request(tmp_path / "shape", np.full((5, 5), 8.0))
    np.save(mismatch_request.noise_result.suppressed_absolute_difference_reference, np.zeros((4, 4), dtype=float))
    mismatch = screen_crater_ejecta_candidates(mismatch_request)
    assert mismatch.status is CraterEjectaCandidateStatus.SHAPE_MISMATCH


def test_reproducible_semantics_and_provenance(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    first = screen_crater_ejecta_candidates(screening_request(tmp_path / "one", signed)).to_dict()
    second = screen_crater_ejecta_candidates(screening_request(tmp_path / "two", signed)).to_dict()
    path_fields = {"candidate_list_reference", "classified_candidates_reference", "specialized_candidates_reference", "summary_reference"}
    first_semantic = {key: value for key, value in first.items() if key not in path_fields}
    second_semantic = {key: value for key, value in second.items() if key not in path_fields}
    first_semantic["provenance"] = {key: value for key, value in first["provenance"].items() if key != "input_artifacts"}
    second_semantic["provenance"] = {key: value for key, value in second["provenance"].items() if key != "input_artifacts"}
    assert first_semantic == second_semantic
    assert first["specialized_candidates_reference"] != second["specialized_candidates_reference"]


def test_provenance_artifacts_and_scientific_guardrails(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    request = screening_request(tmp_path, signed)
    source_mask = np.load(request.candidate_result.candidate_mask_reference).copy()
    result = screen_crater_ejecta_candidates(request)
    payload = json.loads(Path(result.summary_reference).read_text(encoding="utf-8"))
    assert payload["provenance"]["upstream_phase"] == "m4_10.9"
    assert payload["provenance"]["phase_10_8_status"] == "success"
    assert "not confirmed" in payload["provenance"]["limitations"][0]
    serialized = json.dumps(payload).lower()
    assert "confidence" not in serialized
    assert "probability" not in serialized
    assert "this is a confirmed crater" not in serialized
    assert "this is confirmed ejecta" not in serialized
    assert np.array_equal(source_mask, np.load(request.candidate_result.candidate_mask_reference))
    assert Path(result.specialized_candidates_reference).is_file()
