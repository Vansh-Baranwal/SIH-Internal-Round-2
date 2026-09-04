"""Focused Phase 10.11 false-positive validation tests."""

import json
from pathlib import Path

import numpy as np

from lunar_hazard_mapper.m4_terrain import (
    ChangeCandidateConfig,
    ChangeCandidateRequest,
    ChangeClassificationConfig,
    ChangeClassificationRequest,
    CraterEjectaCandidateConfig,
    CraterEjectaCandidateRequest,
    FalsePositiveCategory,
    FalsePositiveValidationConfig,
    FalsePositiveValidationRequest,
    FalsePositiveValidationStatus,
    IlluminationAssessmentStatus,
    IlluminationFilterConfig,
    IlluminationFilterRequest,
    IlluminationFilterResult,
    NoiseSuppressionResult,
    NoiseSuppressionStatus,
    RegistrationStatus,
    TemporalRegistrationResult,
    classify_change_candidates,
    detect_change_candidates,
    filter_illumination,
    register_observation_pair,
    screen_crater_ejecta_candidates,
    validate_false_positives,
)
from lunar_hazard_mapper.m4_terrain.temporal_observation import LunarObservation, ObservationPair


def build_noise_result(tmp_path, signed, absolute=None, valid=None, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
    signed = np.asarray(signed, dtype=float)
    absolute = np.asarray(absolute if absolute is not None else np.abs(signed), dtype=float)
    valid = np.asarray(valid if valid is not None else np.ones(signed.shape, dtype=bool), dtype=bool)
    signed_path = tmp_path / "suppressed_signed.npy"
    absolute_path = tmp_path / "suppressed_absolute.npy"
    valid_path = tmp_path / "valid_mask.npy"
    np.save(signed_path, signed)
    np.save(absolute_path, absolute)
    np.save(valid_path, valid)
    values = {
        "observation_a_id": "obs-a",
        "observation_b_id": "obs-b",
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
        "propagated_valid_mask_reference": str(valid_path),
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


def build_pair():
    obs_a = LunarObservation(
        observation_id="obs-a",
        source="synthetic",
        image_reference="a.png",
        acquisition_timestamp="2024-01-01T00:00:00Z",
        file_path="a.png",
        dimensions=(9, 9),
        sun_azimuth_deg=30.0,
        sun_elevation_deg=45.0,
        phase_angle_deg=20.0,
        incidence_angle_deg=35.0,
        emission_angle_deg=25.0,
        is_real_data=True,
        provenance_source="synthetic",
        provenance="real",
        validation_status="validated",
    )
    obs_b = LunarObservation(
        observation_id="obs-b",
        source="synthetic",
        image_reference="b.png",
        acquisition_timestamp="2024-02-01T00:00:00Z",
        file_path="b.png",
        dimensions=(9, 9),
        sun_azimuth_deg=30.0,
        sun_elevation_deg=45.0,
        phase_angle_deg=20.0,
        incidence_angle_deg=35.0,
        emission_angle_deg=25.0,
        is_real_data=True,
        provenance_source="synthetic",
        provenance="real",
        validation_status="validated",
    )
    return ObservationPair(obs_a, obs_b, pair_id="pair-1")


def build_chain(tmp_path, signed, absolute=None, valid=None, **kwargs):
    noise = build_noise_result(tmp_path / "noise", signed=signed, absolute=absolute, valid=valid, **kwargs)
    candidate = detect_change_candidates(ChangeCandidateRequest(noise_result=noise, config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=4.0)))
    classification = classify_change_candidates(ChangeClassificationRequest(candidate_result=candidate, noise_result=noise, config=ChangeClassificationConfig(output_dir=tmp_path / "classification")))
    specialized = screen_crater_ejecta_candidates(CraterEjectaCandidateRequest(classification_result=classification, candidate_result=candidate, noise_result=noise, config=CraterEjectaCandidateConfig(tmp_path / "specialized")))
    return noise, candidate, classification, specialized


def test_clean_candidate_has_no_false_positive_evidence(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation")
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config))
    assert result.status is FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE
    assert result.candidates[0].overall_status is FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE
    assert "confirmed change" not in json.dumps(result.to_dict()).lower()
    assert FalsePositiveCategory.NO_FALSE_POSITIVE_EVIDENCE in result.candidates[0].detected_categories


def test_poor_registration_is_flagged_without_claiming_candidate_caused_it(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    registration = TemporalRegistrationResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        status=RegistrationStatus.SUCCESS,
        registration_engine="m2",
        backend_used=None,
        transformation_model="affine",
        transformation_parameters=None,
        initial_match_count=100,
        verified_inlier_count=5,
        inlier_ratio=0.05,
        spatial_coverage=0.30,
        registration_rmse=4.0,
        subpixel_refinement_available=True,
        subpixel_refinement_status="executed",
        registered_output_reference="warped.png",
        match_point_output_reference="matches.json",
        registration_quality_status="poor",
        warnings=("registration_metrics_suspect",),
        failure_reasons=(),
        provenance_status="real_observation_pair",
        message="poor global registration",
    )
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation", inlier_ratio_threshold=0.20, rmse_threshold=1.0)
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, registration_result=registration, config=config))
    assert FalsePositiveCategory.REGISTRATION_ARTIFACT in result.candidates[0].detected_categories
    assert result.candidates[0].overall_status in {FalsePositiveValidationStatus.LIKELY_FALSE_POSITIVE, FalsePositiveValidationStatus.FALSE_POSITIVE}
    assert "candidate caused" not in json.dumps(result.to_dict()).lower()


def test_boundary_candidate_is_flagged(tmp_path):
    signed = np.zeros((7, 7), dtype=float)
    signed[0:3, 0:3] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation")
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config))
    assert FalsePositiveCategory.BOUNDARY_ARTIFACT in result.candidates[0].detected_categories


def test_invalid_mask_boundary_is_flagged(tmp_path):
    signed = np.zeros((7, 7), dtype=float)
    signed[2:5, 2:5] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    valid = np.ones((7, 7), dtype=bool)
    valid[1:6, 1:6] = False
    noise = build_noise_result(tmp_path / "noise_masked", signed=signed, valid=valid)
    candidate = detect_change_candidates(ChangeCandidateRequest(noise_result=noise, config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=4.0)))
    classification = classify_change_candidates(ChangeClassificationRequest(candidate_result=candidate, noise_result=noise, config=ChangeClassificationConfig(output_dir=tmp_path / "classification")))
    specialized = screen_crater_ejecta_candidates(CraterEjectaCandidateRequest(classification_result=classification, candidate_result=candidate, noise_result=noise, config=CraterEjectaCandidateConfig(tmp_path / "specialized")))
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation")
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config))
    assert FalsePositiveCategory.MASK_ARTIFACT in result.candidates[0].detected_categories


def test_illumination_limitation_makes_validation_inconclusive(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    illumination = IlluminationFilterResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        difference_status="success",
        status="insufficient_illumination_model",
        assessment={"status": "insufficient_metadata", "angular_differences_deg": {"sun_azimuth_deg": None}, "available_fields": (), "missing_fields": ("sun_azimuth_deg",), "view_geometry_available": False, "warnings": ("illumination_metadata_incomplete",), "method": "metadata_gate"},
        raw_signed_difference_reference="raw.npy",
        raw_absolute_difference_reference="raw_abs.npy",
        raw_valid_mask_reference="raw_valid.npy",
        filtered_signed_difference_reference=None,
        filtered_absolute_difference_reference=None,
        illumination_mask_reference=None,
        before_statistics={},
        after_statistics={},
        illumination_compatible_count=0,
        illumination_excluded_count=0,
        retained_fraction=0.0,
        normalization_method=None,
        warnings=("illumination_metadata_incomplete",),
        failure_reasons=(),
        provenance={"phase": "m4_10.6", "method": "metadata_gate"},
        message="insufficient metadata",
    )
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation")
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, illumination_result=illumination, config=config))
    assert result.candidates[0].overall_status is FalsePositiveValidationStatus.INCONCLUSIVE
    assert FalsePositiveCategory.METADATA_LIMITATION in result.candidates[0].detected_categories


def test_small_support_candidate_is_noise_or_insufficient_support(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[4, 4] = 100.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation", minimum_support_pixels=3)
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config))
    assert FalsePositiveCategory.NOISE_ARTIFACT in result.candidates[0].detected_categories or FalsePositiveCategory.INSUFFICIENT_SUPPORT in result.candidates[0].detected_categories


def test_multiple_candidates_are_validated_independently(tmp_path):
    signed = np.zeros((12, 12), dtype=float)
    signed[2:5, 2:5] = 8.0
    signed[8:11, 8:11] = -8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation")
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config))
    assert len(result.candidates) == 2
    assert {item.source_candidate_id for item in result.candidates} == {"candidate-0001", "candidate-0002"}


def test_no_candidates_returns_no_candidates_status(tmp_path):
    noise = build_noise_result(tmp_path / "noise", signed=np.zeros((5, 5), dtype=float))
    candidate = detect_change_candidates(ChangeCandidateRequest(noise_result=noise, config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=4.0)))
    classification = classify_change_candidates(ChangeClassificationRequest(candidate_result=candidate, noise_result=noise, config=ChangeClassificationConfig(output_dir=tmp_path / "classification")))
    specialized = screen_crater_ejecta_candidates(CraterEjectaCandidateRequest(classification_result=classification, candidate_result=candidate, noise_result=noise, config=CraterEjectaCandidateConfig(tmp_path / "specialized")))
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation")))
    assert result.status is FalsePositiveValidationStatus.NO_CANDIDATES


def test_threshold_boundaries_and_reproducibility(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    config = FalsePositiveValidationConfig(output_dir=tmp_path / "validation", inlier_ratio_threshold=0.50)
    first = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config)).to_dict()
    second = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=config)).to_dict()
    assert first["status"] == second["status"]
    assert first["candidates"][0]["overall_status"] == second["candidates"][0]["overall_status"]


def test_provenance_and_guardrails(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    result = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation")))
    payload = json.loads(Path(result.summary_reference).read_text(encoding="utf-8"))
    assert payload["provenance"]["upstream_phase"] == "m4_10.10"
    serialized = json.dumps(payload).lower()
    assert "confirmed crater" not in serialized
    assert "confirmed ejecta" not in serialized
    assert "probability" not in serialized
    assert "confidence" not in serialized
    assert "material gain" not in serialized


def test_raw_artifacts_are_preserved(tmp_path):
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise, candidate, classification, specialized = build_chain(tmp_path, signed)
    before = np.load(noise.suppressed_signed_difference_reference).copy()
    validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation")))
    assert np.array_equal(np.load(noise.suppressed_signed_difference_reference), before)
