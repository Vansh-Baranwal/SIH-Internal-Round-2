"""Focused Phase 10.12 temporal-change validation tests."""

from pathlib import Path

import numpy as np

from lunar_hazard_mapper.m4_terrain import (
    ChangeCandidateConfig,
    ChangeCandidateRequest,
    ChangeClassificationConfig,
    ChangeClassificationRequest,
    CraterEjectaCandidateConfig,
    CraterEjectaCandidateRequest,
    DifferenceConfig,
    DifferenceStatus,
    FalsePositiveValidationConfig,
    FalsePositiveValidationRequest,
    FalsePositiveValidationStatus,
    ImageDifferenceResult,
    IlluminationAssessment,
    IlluminationAssessmentStatus,
    IlluminationFilterConfig,
    IlluminationFilterResult,
    IlluminationFilterStatus,
    LunarObservation,
    NoiseSuppressionResult,
    NoiseSuppressionStatus,
    ObservationPair,
    PairEligibility,
    PairSelectionResult,
    RegistrationStatus,
    TemporalChangeValidationConfig,
    TemporalChangeValidationRequest,
    TemporalChangeValidationStatus,
    TemporalRegistrationResult,
    classify_change_candidates,
    detect_change_candidates,
    screen_crater_ejecta_candidates,
    validate_false_positives,
    validate_temporal_change,
)


def _build_pair():
    obs_a = LunarObservation(
        observation_id="obs-a",
        source="TMC",
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
        provenance_source="real_source",
        provenance="real",
        validation_status="validated",
    )
    obs_b = LunarObservation(
        observation_id="obs-b",
        source="TMC",
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
        provenance_source="real_source",
        provenance="real",
        validation_status="validated",
    )
    return ObservationPair(obs_a, obs_b, pair_id="pair-1")


def _build_noise_result(tmp_path, signed, valid=None):
    output_dir = tmp_path / "noise"
    output_dir.mkdir(parents=True, exist_ok=True)
    signed_array = np.asarray(signed, dtype=float)
    absolute_array = np.abs(signed_array)
    valid_mask = np.asarray(valid if valid is not None else np.ones_like(signed_array, dtype=bool), dtype=bool)
    signed_path = output_dir / "signed_difference.npy"
    absolute_path = output_dir / "absolute_difference.npy"
    valid_path = output_dir / "valid_mask.npy"
    np.save(signed_path, signed_array)
    np.save(absolute_path, absolute_array)
    np.save(valid_path, valid_mask)
    return NoiseSuppressionResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        illumination_status="success",
        status=NoiseSuppressionStatus.SUCCESS,
        method="masked_median",
        kernel_size=3,
        minimum_valid_neighbors=2,
        image_shape=signed_array.shape,
        channel_count=1,
        valid_pixel_count=int(np.count_nonzero(valid_mask)),
        invalid_pixel_count=int(valid_mask.size - np.count_nonzero(valid_mask)),
        signed_difference_input_reference="phase10.5-signed.npy",
        absolute_difference_input_reference="phase10.5-absolute.npy",
        valid_mask_input_reference="phase10.5-valid.npy",
        suppressed_signed_difference_reference=str(signed_path),
        suppressed_absolute_difference_reference=str(absolute_path),
        propagated_valid_mask_reference=str(valid_path),
        before_statistics={},
        after_statistics={},
        high_frequency_residual_std=0.0,
        warnings=(),
        failure_reasons=(),
        provenance={"phase": "m4_10.7", "raw_difference_preserved": True},
        message="test-noise",
    )


def _build_authoritative_chain(tmp_path):
    pair = _build_pair()
    signed = np.zeros((9, 9), dtype=float)
    signed[3:6, 3:6] = 8.0
    noise = _build_noise_result(tmp_path, signed)
    candidate = detect_change_candidates(ChangeCandidateRequest(noise_result=noise, config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=4.0)))
    classification = classify_change_candidates(ChangeClassificationRequest(candidate_result=candidate, noise_result=noise, config=ChangeClassificationConfig(output_dir=tmp_path / "classification")))
    specialized = screen_crater_ejecta_candidates(CraterEjectaCandidateRequest(classification_result=classification, candidate_result=candidate, noise_result=noise, config=CraterEjectaCandidateConfig(tmp_path / "specialized")))
    fp = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation")))
    selection = PairSelectionResult(
        "obs-a",
        "obs-b",
        PairEligibility.ELIGIBLE,
        (),
        (),
        99.0,
        None,
        "compatible",
        "compatible",
        "supported",
        None,
        None,
        1.0,
        "real",
    )
    registration = TemporalRegistrationResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        status=RegistrationStatus.SUCCESS,
        registration_engine="m2",
        backend_used=None,
        transformation_model="affine",
        transformation_parameters=None,
        initial_match_count=100,
        verified_inlier_count=80,
        inlier_ratio=0.80,
        spatial_coverage=0.80,
        registration_rmse=0.5,
        subpixel_refinement_available=True,
        subpixel_refinement_status="executed",
        registered_output_reference="registered.png",
        match_point_output_reference="matches.json",
        registration_quality_status="good",
        warnings=(),
        failure_reasons=(),
        provenance_status="real_observation_pair",
        message="ok",
    )
    diff = ImageDifferenceResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        registration_status="success",
        status=DifferenceStatus.SUCCESS,
        method="registered_a_minus_reference_b",
        image_shape=(9, 9),
        channel_count=1,
        valid_pixel_count=81,
        invalid_pixel_count=0,
        valid_fraction=0.9,
        signed_difference_reference=str(noise.suppressed_signed_difference_reference),
        absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
        valid_mask_reference=str(noise.propagated_valid_mask_reference),
        summary_statistics={"signed_mean": 0.0, "signed_max": 8.0},
        normalization_method="none",
        warnings=(),
        failure_reasons=(),
        provenance={"phase": "m4_10.5"},
        message="ok",
    )
    illumination = IlluminationFilterResult(
        observation_a_id="obs-a",
        observation_b_id="obs-b",
        difference_status="success",
        status=IlluminationFilterStatus.SUCCESS,
        assessment=IlluminationAssessment(
            status=IlluminationAssessmentStatus.COMPARABLE,
            angular_differences_deg={
                "sun_azimuth_deg": 0.0,
                "sun_elevation_deg": 0.0,
                "phase_angle_deg": 0.0,
                "incidence_angle_deg": 0.0,
                "emission_angle_deg": 0.0,
            },
            available_fields=(
                "sun_azimuth_deg",
                "sun_elevation_deg",
                "phase_angle_deg",
                "incidence_angle_deg",
                "emission_angle_deg",
            ),
            missing_fields=(),
            view_geometry_available=True,
            warnings=(),
            method="metadata_gate",
        ),
        raw_signed_difference_reference=str(noise.suppressed_signed_difference_reference),
        raw_absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
        raw_valid_mask_reference=str(noise.propagated_valid_mask_reference),
        filtered_signed_difference_reference=str(noise.suppressed_signed_difference_reference),
        filtered_absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
        illumination_mask_reference=None,
        before_statistics={},
        after_statistics={},
        illumination_compatible_count=81,
        illumination_excluded_count=0,
        retained_fraction=1.0,
        normalization_method="none",
        warnings=(),
        failure_reasons=(),
        provenance={"phase": "m4_10.6"},
        message="ok",
    )
    return pair, selection, registration, diff, illumination, noise, candidate, classification, specialized, fp


def test_valid_chain_accepts_temporal_change(tmp_path):
    pair, selection, registration, diff, illumination, noise, candidate, classification, specialized, false_positive = _build_authoritative_chain(tmp_path)
    request = TemporalChangeValidationRequest(
        pair=pair,
        config=TemporalChangeValidationConfig(output_dir=tmp_path / "final"),
        selection_result=selection,
        registration_result=registration,
        difference_result=diff,
        illumination_result=illumination,
        noise_result=noise,
        candidate_result=candidate,
        classification_result=classification,
        specialized_result=specialized,
        false_positive_result=false_positive,
    )
    result = validate_temporal_change(request)
    assert result.status is TemporalChangeValidationStatus.VALIDATED_TEMPORAL_CHANGE
    assert any(gate.name == "final_acceptance" and gate.passed for gate in result.gates)


def test_false_positive_rejection_blocks_final_acceptance(tmp_path):
    pair, selection, registration, diff, illumination, noise, candidate, classification, specialized, _ = _build_authoritative_chain(tmp_path)
    strong_false_positive = validate_false_positives(FalsePositiveValidationRequest(
        specialized_result=specialized,
        classification_result=classification,
        candidate_result=candidate,
        noise_result=noise,
        config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation"),
        registration_result=TemporalRegistrationResult(
            observation_a_id="obs-a",
            observation_b_id="obs-b",
            status=RegistrationStatus.SUCCESS,
            registration_engine="m2",
            backend_used=None,
            transformation_model="affine",
            transformation_parameters=None,
            initial_match_count=10,
            verified_inlier_count=2,
            inlier_ratio=0.10,
            spatial_coverage=0.20,
            registration_rmse=2.0,
            subpixel_refinement_available=True,
            subpixel_refinement_status="executed",
            registered_output_reference="registered.png",
            match_point_output_reference="matches.json",
            registration_quality_status="poor",
            warnings=("registration_metrics_suspect",),
            failure_reasons=(),
            provenance_status="real_observation_pair",
            message="poor registration",
        ),
    ))
    result = validate_temporal_change(TemporalChangeValidationRequest(
        pair=pair,
        config=TemporalChangeValidationConfig(output_dir=tmp_path / "final"),
        selection_result=selection,
        registration_result=registration,
        difference_result=diff,
        illumination_result=illumination,
        noise_result=noise,
        candidate_result=candidate,
        classification_result=classification,
        specialized_result=specialized,
        false_positive_result=strong_false_positive,
    ))
    assert result.status is TemporalChangeValidationStatus.REJECTED_FALSE_POSITIVE


def test_missing_false_positive_makes_validation_inconclusive(tmp_path):
    pair, selection, registration, diff, illumination, noise, candidate, classification, specialized, _ = _build_authoritative_chain(tmp_path)
    request = TemporalChangeValidationRequest(
        pair=pair,
        config=TemporalChangeValidationConfig(output_dir=tmp_path / "final"),
        selection_result=selection,
        registration_result=registration,
        difference_result=diff,
        illumination_result=illumination,
        noise_result=noise,
        candidate_result=candidate,
        classification_result=classification,
        specialized_result=specialized,
    )
    result = validate_temporal_change(request)
    assert result.status is TemporalChangeValidationStatus.INCONCLUSIVE


def test_same_timestamp_or_synthetic_pair_is_blocked(tmp_path):
    pair = _build_pair()
    same_time_pair = object.__new__(ObservationPair)
    object.__setattr__(same_time_pair, "observation_a", pair.observation_a)
    object.__setattr__(same_time_pair, "observation_b", LunarObservation(
        observation_id="obs-c",
        source="TMC",
        image_reference="c.png",
        acquisition_timestamp="2024-01-01T00:00:00Z",
        file_path="c.png",
        dimensions=(9, 9),
        sun_azimuth_deg=30.0,
        sun_elevation_deg=45.0,
        phase_angle_deg=20.0,
        incidence_angle_deg=35.0,
        emission_angle_deg=25.0,
        is_real_data=True,
        provenance_source="real_source",
        provenance="real",
        validation_status="validated",
    ))
    object.__setattr__(same_time_pair, "pair_id", "pair-same")
    request = TemporalChangeValidationRequest(
        pair=same_time_pair,
        config=TemporalChangeValidationConfig(output_dir=tmp_path / "blocked"),
    )
    result = validate_temporal_change(request)
    assert result.status is TemporalChangeValidationStatus.VALIDATION_BLOCKED


def test_no_candidates_returns_no_candidates_status(tmp_path):
    pair = _build_pair()
    noise = _build_noise_result(tmp_path, np.zeros((5, 5), dtype=float))
    candidate = detect_change_candidates(ChangeCandidateRequest(noise_result=noise, config=ChangeCandidateConfig(output_dir=tmp_path / "candidates", absolute_difference_threshold=4.0)))
    classification = classify_change_candidates(ChangeClassificationRequest(candidate_result=candidate, noise_result=noise, config=ChangeClassificationConfig(output_dir=tmp_path / "classification")))
    specialized = screen_crater_ejecta_candidates(CraterEjectaCandidateRequest(classification_result=classification, candidate_result=candidate, noise_result=noise, config=CraterEjectaCandidateConfig(tmp_path / "specialized")))
    false_positive = validate_false_positives(FalsePositiveValidationRequest(specialized_result=specialized, classification_result=classification, candidate_result=candidate, noise_result=noise, config=FalsePositiveValidationConfig(output_dir=tmp_path / "validation")))
    request = TemporalChangeValidationRequest(
        pair=pair,
        config=TemporalChangeValidationConfig(output_dir=tmp_path / "no-candidates"),
        selection_result=PairSelectionResult(
            "obs-a",
            "obs-b",
            PairEligibility.ELIGIBLE,
            (),
            (),
            99.0,
            None,
            "compatible",
            "compatible",
            "supported",
            None,
            None,
            1.0,
            "real",
        ),
        registration_result=TemporalRegistrationResult(
            observation_a_id="obs-a",
            observation_b_id="obs-b",
            status=RegistrationStatus.SUCCESS,
            registration_engine="m2",
            backend_used=None,
            transformation_model="affine",
            transformation_parameters=None,
            initial_match_count=100,
            verified_inlier_count=80,
            inlier_ratio=0.80,
            spatial_coverage=0.80,
            registration_rmse=0.5,
            subpixel_refinement_available=True,
            subpixel_refinement_status="executed",
            registered_output_reference="registered.png",
            match_point_output_reference="matches.json",
            registration_quality_status="good",
            warnings=(),
            failure_reasons=(),
            provenance_status="real_observation_pair",
            message="ok",
        ),
        difference_result=ImageDifferenceResult(
            observation_a_id="obs-a",
            observation_b_id="obs-b",
            registration_status="success",
            status=DifferenceStatus.SUCCESS,
            method="registered_a_minus_reference_b",
            image_shape=(5, 5),
            channel_count=1,
            valid_pixel_count=25,
            invalid_pixel_count=0,
            valid_fraction=1.0,
            signed_difference_reference=str(noise.suppressed_signed_difference_reference),
            absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
            valid_mask_reference=str(noise.propagated_valid_mask_reference),
            summary_statistics={"signed_mean": 0.0},
            normalization_method="none",
            warnings=(),
            failure_reasons=(),
            provenance={"phase": "m4_10.5"},
            message="ok",
        ),
        illumination_result=IlluminationFilterResult(
            observation_a_id="obs-a",
            observation_b_id="obs-b",
            difference_status="success",
            status=IlluminationFilterStatus.SUCCESS,
            assessment=IlluminationAssessment(
                status=IlluminationAssessmentStatus.COMPARABLE,
                angular_differences_deg={
                    "sun_azimuth_deg": 0.0,
                    "sun_elevation_deg": 0.0,
                    "phase_angle_deg": 0.0,
                    "incidence_angle_deg": 0.0,
                    "emission_angle_deg": 0.0,
                },
                available_fields=(
                    "sun_azimuth_deg",
                    "sun_elevation_deg",
                    "phase_angle_deg",
                    "incidence_angle_deg",
                    "emission_angle_deg",
                ),
                missing_fields=(),
                view_geometry_available=True,
                warnings=(),
                method="metadata_gate",
            ),
            raw_signed_difference_reference=str(noise.suppressed_signed_difference_reference),
            raw_absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
            raw_valid_mask_reference=str(noise.propagated_valid_mask_reference),
            filtered_signed_difference_reference=str(noise.suppressed_signed_difference_reference),
            filtered_absolute_difference_reference=str(noise.suppressed_absolute_difference_reference),
            illumination_mask_reference=None,
            before_statistics={},
            after_statistics={},
            illumination_compatible_count=25,
            illumination_excluded_count=0,
            retained_fraction=1.0,
            normalization_method="none",
            warnings=(),
            failure_reasons=(),
            provenance={"phase": "m4_10.6"},
            message="ok",
        ),
        noise_result=noise,
        candidate_result=candidate,
        classification_result=classification,
        specialized_result=specialized,
        false_positive_result=false_positive,
    )
    result = validate_temporal_change(request)
    assert result.status is TemporalChangeValidationStatus.NO_CANDIDATES
