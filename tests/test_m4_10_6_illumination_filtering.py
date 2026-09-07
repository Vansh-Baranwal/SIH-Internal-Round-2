"""Focused Phase 10.6 tests; fixtures are software-test data only."""

import json

import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    DifferenceStatus,
    IlluminationAssessmentStatus,
    IlluminationFilterConfig,
    IlluminationFilterRequest,
    IlluminationFilterStatus,
    ImageDifferenceResult,
    ObservationPair,
    TemporalRegistrationResult,
    RegistrationStatus,
    assess_illumination,
    angular_difference_deg,
    filter_illumination,
)
from lunar_hazard_mapper.m4_terrain.temporal_observation import LunarObservation


def observation(identifier: str, timestamp: str, **overrides) -> LunarObservation:
    values = {
        "observation_id": identifier,
        "source": "TMC test fixture",
        "image_reference": f"test-{identifier}.png",
        "acquisition_timestamp": timestamp,
        "sun_azimuth_deg": 10.0,
        "sun_elevation_deg": 30.0,
        "phase_angle_deg": 40.0,
        "incidence_angle_deg": 20.0,
        "emission_angle_deg": 15.0,
        "provenance_source": "tests/test_m4_10_6_illumination_filtering.py",
        "provenance": DataProvenance.REAL,
        "is_real_data": True,
    }
    values.update(overrides)
    return LunarObservation(**values)


def pair(**overrides) -> ObservationPair:
    return ObservationPair(
        observation("a", "2024-01-01T00:00:00Z", **overrides.pop("first", {})),
        observation("b", "2024-02-01T00:00:00Z", **overrides.pop("second", {})),
    )


def difference_result(tmp_path, signed=None, absolute=None, valid=None, **overrides) -> ImageDifferenceResult:
    signed = np.asarray(signed if signed is not None else [[1.0, -2.0], [3.0, 4.0]], dtype=float)
    absolute = np.asarray(absolute if absolute is not None else np.abs(signed), dtype=float)
    valid = np.asarray(valid if valid is not None else np.ones(signed.shape[:2], dtype=bool), dtype=bool)
    signed_path = tmp_path / "signed.npy"
    absolute_path = tmp_path / "absolute.npy"
    mask_path = tmp_path / "valid.npy"
    np.save(signed_path, signed)
    np.save(absolute_path, absolute)
    np.save(mask_path, valid)
    values = {
        "observation_a_id": "a",
        "observation_b_id": "b",
        "registration_status": "success",
        "status": DifferenceStatus.SUCCESS,
        "method": "registered_a_minus_reference_b",
        "image_shape": signed.shape,
        "channel_count": 1 if signed.ndim == 2 else signed.shape[2],
        "valid_pixel_count": int(np.count_nonzero(valid)),
        "invalid_pixel_count": int(valid.size - np.count_nonzero(valid)),
        "valid_fraction": float(np.mean(valid)),
        "signed_difference_reference": str(signed_path),
        "absolute_difference_reference": str(absolute_path),
        "valid_mask_reference": str(mask_path),
        "summary_statistics": {},
        "normalization_method": "none",
        "warnings": (),
        "failure_reasons": (),
        "provenance": {"phase": "m4_10.5", "registration_result": "success"},
        "message": "test-only difference",
    }
    values.update(overrides)
    return ImageDifferenceResult(**values)


def registration_stub() -> TemporalRegistrationResult:
    return TemporalRegistrationResult(
        "a", "b", RegistrationStatus.SUCCESS, "m2_correspondence_engine", None,
        "affine", None, 4, 4, 1.0, 1.0, 0.1, True, "executed", "a.png", None,
        "metrics_available", (), (), "real_observation_pair", "test", "b.png",
    )


def test_identical_complete_geometry_is_comparable() -> None:
    assessment = assess_illumination(pair(), IlluminationFilterConfig(output_dir="out"))
    assert assessment.status is IlluminationAssessmentStatus.COMPARABLE
    assert all(value == 0.0 for value in assessment.angular_differences_deg.values())


def test_circular_azimuth_difference_is_shortest_angle() -> None:
    assert angular_difference_deg(359.0, 1.0, circular=True) == 2.0
    assert angular_difference_deg(None, 1.0, circular=True) is None


def test_different_sun_geometry_is_detected() -> None:
    assessment = assess_illumination(
        pair(second={"sun_elevation_deg": 45.0}),
        IlluminationFilterConfig(output_dir="out"),
    )
    assert assessment.status is IlluminationAssessmentStatus.DIFFERENT
    assert assessment.angular_differences_deg["sun_elevation_deg"] == 15.0


def test_missing_illumination_metadata_is_insufficient() -> None:
    assessment = assess_illumination(
        pair(first={"sun_azimuth_deg": None, "sun_elevation_deg": None}),
        IlluminationFilterConfig(output_dir="out"),
    )
    assert assessment.status is IlluminationAssessmentStatus.UNKNOWN
    assert "sun_azimuth_deg" in assessment.missing_fields
    assert assessment.angular_differences_deg["sun_azimuth_deg"] is None


def test_successful_difference_reaches_filter_and_preserves_raw(tmp_path) -> None:
    difference = difference_result(tmp_path)
    result = filter_illumination(IlluminationFilterRequest(
        difference, pair(), IlluminationFilterConfig(tmp_path / "filtered")
    ))
    assert result.status is IlluminationFilterStatus.SUCCESS
    assert result.raw_signed_difference_reference == difference.signed_difference_reference
    assert result.filtered_signed_difference_reference != difference.signed_difference_reference
    assert result.illumination_compatible_count == 4
    assert np.array_equal(np.load(result.filtered_signed_difference_reference), np.load(difference.signed_difference_reference))


def test_failed_difference_cannot_reach_filter(tmp_path) -> None:
    difference = difference_result(tmp_path, status=DifferenceStatus.SHAPE_MISMATCH)
    result = filter_illumination(IlluminationFilterRequest(
        difference, pair(), IlluminationFilterConfig(tmp_path / "filtered")
    ))
    assert result.status is IlluminationFilterStatus.INVALID_DIFFERENCE_INPUT
    assert result.filtered_signed_difference_reference is None


def test_existing_valid_mask_is_combined(tmp_path) -> None:
    valid = np.array([[True, False], [True, True]])
    result = filter_illumination(IlluminationFilterRequest(
        difference_result(tmp_path, valid=valid), pair(), IlluminationFilterConfig(tmp_path / "filtered")
    ))
    assert result.illumination_compatible_count == 3
    assert result.illumination_excluded_count == 0
    assert np.array_equal(np.load(result.illumination_mask_reference), valid)


def test_different_geometry_global_gate_excludes_without_zero_fill(tmp_path) -> None:
    difference = difference_result(tmp_path)
    result = filter_illumination(IlluminationFilterRequest(
        difference,
        pair(second={"sun_elevation_deg": 60.0}),
        IlluminationFilterConfig(tmp_path / "filtered"),
    ))
    assert result.status is IlluminationFilterStatus.SUCCESS
    assert result.illumination_compatible_count == 0
    assert result.illumination_excluded_count == 4
    filtered = np.load(result.filtered_signed_difference_reference)
    assert np.isnan(filtered).all()
    assert not np.any(filtered == 0.0)


def test_unknown_geometry_preserves_raw_and_reports_unavailable_model(tmp_path) -> None:
    difference = difference_result(tmp_path)
    result = filter_illumination(IlluminationFilterRequest(
        difference,
        pair(first={"sun_azimuth_deg": None}, second={"sun_azimuth_deg": None}),
        IlluminationFilterConfig(tmp_path / "filtered"),
    ))
    assert result.status is IlluminationFilterStatus.INSUFFICIENT_ILLUMINATION_MODEL
    assert result.filtered_signed_difference_reference is None
    assert result.raw_signed_difference_reference == difference.signed_difference_reference


def test_before_after_statistics_and_retained_fraction(tmp_path) -> None:
    result = filter_illumination(IlluminationFilterRequest(
        difference_result(tmp_path), pair(), IlluminationFilterConfig(tmp_path / "filtered")
    ))
    assert result.before_statistics["valid_count"] == 4
    assert result.after_statistics["valid_count"] == 4
    assert result.before_statistics["mean_absolute_difference"] == 2.5
    assert result.retained_fraction == 1.0


def test_zero_retained_pixels_is_explicit(tmp_path) -> None:
    result = filter_illumination(IlluminationFilterRequest(
        difference_result(tmp_path),
        pair(second={"sun_elevation_deg": 60.0}),
        IlluminationFilterConfig(tmp_path / "filtered"),
    ))
    assert result.after_statistics["valid_count"] == 0
    assert result.after_statistics["mean_absolute_difference"] is None


def test_thresholds_are_explicit_configuration(tmp_path) -> None:
    config = IlluminationFilterConfig(tmp_path, sun_elevation_tolerance_deg=5.0)
    assessment = assess_illumination(pair(second={"sun_elevation_deg": 34.0}), config)
    assert assessment.status is IlluminationAssessmentStatus.COMPARABLE


def test_result_serialization_contains_no_change_confidence(tmp_path) -> None:
    result = filter_illumination(IlluminationFilterRequest(
        difference_result(tmp_path), pair(), IlluminationFilterConfig(tmp_path / "filtered")
    ))
    payload = result.to_dict()
    assert "change_confidence" not in json.dumps(payload).lower()
    assert payload["provenance"]["phase"] == "m4_10.6"


def test_registration_result_reference_is_a_phase_10_4_input() -> None:
    assert registration_stub().status is RegistrationStatus.SUCCESS