"""Focused Phase 10.9 tests."""

import json
from pathlib import Path

import numpy as np

from lunar_hazard_mapper.m4_terrain import (
    ChangeClassificationConfig,
    ChangeClassificationRequest,
    ChangeClassificationStatus,
    classify_change_candidates,
    detect_change_candidates,
)
from test_m4_10_8_change_candidate_detection import noise_result, request


def classify_request(tmp_path, signed, absolute=None, valid=None, **config_kwargs):
    upstream_noise = noise_result(tmp_path / "noise", signed=signed, absolute=absolute, valid=valid)
    candidates = detect_change_candidates(request(tmp_path / "detection", signed=signed, absolute=absolute, valid=valid))
    return ChangeClassificationRequest(
        candidates,
        upstream_noise,
        ChangeClassificationConfig(tmp_path / "classification", **config_kwargs),
    )


def test_positive_negative_and_mixed_sign_responses(tmp_path):
    signed = np.zeros((9, 15), dtype=float)
    signed[1:4, 1:4] = 8
    signed[1:4, 6:9] = -8
    signed[1:4, 11:14] = np.array([[8, -8, 8], [-8, 8, -8], [8, -8, 8]])
    result = classify_change_candidates(classify_request(tmp_path, signed))
    assert result.status is ChangeClassificationStatus.SUCCESS
    assert [item.primary_classification for item in result.classifications] == ["POSITIVE_DOMINANT", "NEGATIVE_DOMINANT", "MIXED_SIGN"]


def test_threshold_boundary_and_neutral_sign_are_deterministic(tmp_path):
    signed = np.zeros((5, 7), dtype=float)
    signed[1:4, 1:4] = 8 * np.array([[1, 1, 1], [1, -1, -1], [1, 1, 1]])
    result = classify_change_candidates(classify_request(tmp_path, signed, sign_dominance_fraction=7 / 9))
    assert result.classifications[0].primary_classification == "POSITIVE_DOMINANT"


def test_geometry_edge_elongated_and_compact(tmp_path):
    signed = np.zeros((8, 14), dtype=float)
    signed[2:5, 1:4] = 8
    signed[7, 5:12] = 8
    result = classify_change_candidates(classify_request(tmp_path, signed))
    first, second = result.classifications
    assert first.morphology["classification"] == "COMPACT"
    assert second.morphology["classification"] == "ELONGATED"
    assert "EDGE_LIKE" in second.secondary_characteristics
    assert second.geometry["touches_image_boundary"] is True


def test_invalid_pixels_and_labels_are_rejected_without_input_mutation(tmp_path):
    signed = np.zeros((5, 5), dtype=float)
    signed[1:4, 1:4] = 8
    request_value = classify_request(tmp_path, signed)
    original = np.load(request_value.candidate_result.candidate_labels_reference).copy()
    labels_path = Path(request_value.candidate_result.candidate_labels_reference)
    malformed = original.copy()
    malformed[1, 1] = 9
    np.save(labels_path, malformed)
    result = classify_change_candidates(request_value)
    assert result.status is ChangeClassificationStatus.INVALID_CANDIDATE_ARTIFACT
    assert np.array_equal(np.load(labels_path), malformed)


def test_no_candidates_and_provenance_outputs(tmp_path):
    result = classify_change_candidates(classify_request(tmp_path, np.zeros((5, 5), dtype=float)))
    assert result.status is ChangeClassificationStatus.NO_CANDIDATES
    assert Path(result.summary_reference).is_file()
    payload = json.loads(Path(result.summary_reference).read_text(encoding="utf-8"))
    assert payload["provenance"]["upstream_phase"] == "m4_10.8"
    assert "physical lunar change" in payload["provenance"]["limitations"][0]
    assert "crater" not in json.dumps(payload).lower()


def test_reproducible_output(tmp_path):
    signed = np.zeros((7, 7), dtype=float)
    signed[2:5, 2:5] = 8
    first = classify_change_candidates(classify_request(tmp_path / "one", signed)).to_dict()
    second = classify_change_candidates(classify_request(tmp_path / "two", signed)).to_dict()
    location_fields = {
        "candidate_mask_reference",
        "candidate_labels_reference",
        "classified_candidates_reference",
        "summary_reference",
    }
    first_semantic = {key: value for key, value in first.items() if key not in location_fields}
    second_semantic = {key: value for key, value in second.items() if key not in location_fields}
    first_semantic["provenance"] = {key: value for key, value in first["provenance"].items() if key != "input_artifacts"}
    second_semantic["provenance"] = {key: value for key, value in second["provenance"].items() if key != "input_artifacts"}
    assert first_semantic == second_semantic
    assert first["classified_candidates_reference"] != second["classified_candidates_reference"]
    assert Path(first["classified_candidates_reference"]).is_file()
    assert Path(second["classified_candidates_reference"]).is_file()
