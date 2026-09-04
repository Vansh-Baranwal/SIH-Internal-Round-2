"""Focused Phase 11.12 final-decision tests."""

from types import SimpleNamespace

from lunar_hazard_mapper.m4_terrain import DataProvenance, UnknownImage
from lunar_hazard_mapper.m4_terrain.coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from lunar_hazard_mapper.m4_terrain.localization_accuracy import AccuracyStatus, LocalizationAccuracyEvaluation, LocalizationAccuracyResult
from lunar_hazard_mapper.m4_terrain.lunar_gps_final_validation import FinalValidationStatus, LunarGPSFinalValidationRequest, validate_lunar_gps


def estimate(status=CoordinateEstimationStatus.SUCCESS, coordinate=(1.0, 2.0)):
    return CoordinateEstimationResult(status, "unknown", "reference", "anchor", (1.0, 1.0), (2.0, 2.0), coordinate if status is CoordinateEstimationStatus.SUCCESS else None, "projected" if status is CoordinateEstimationStatus.SUCCESS else None, "frame" if status is CoordinateEstimationStatus.SUCCESS else None, "metres" if status is CoordinateEstimationStatus.SUCCESS else None, ("x", "y") if status is CoordinateEstimationStatus.SUCCESS else None, provenance={"reference_georeferencing": {"crs": "CRS"}})


def accuracy(status=AccuracyStatus.NO_GROUND_TRUTH, tolerance_passed=None, authority=None):
    return LocalizationAccuracyEvaluation(status, (LocalizationAccuracyResult("case", status, tolerance_passed=tolerance_passed, provenance={"truth_authority_status": authority} if authority else {}),), 0, 1, {}, {})


def request(**overrides):
    values = dict(validation_request_id="validation-1", unknown_image=UnknownImage("unknown", "fixture", provenance=DataProvenance.UNAVAILABLE, provenance_source="fixture"), metadata_quality=object(), landmark_retrieval=object(), landmark_correspondence=object(), anchor_selection=object(), geometric_verification=object(), coordinate_estimation=estimate(), localization_confidence=None, roi_retrieval=None, metadata_separation=None, accuracy=accuracy())
    values.update(overrides)
    return LunarGPSFinalValidationRequest(**values)


def test_missing_authoritative_truth_is_technically_valid_only():
    result = validate_lunar_gps(request())
    assert result.status is FinalValidationStatus.TECHNICALLY_VALID
    assert result.validation_level == 2
    assert "authoritative real lunar truth is unavailable" in result.interpretation


def test_authoritative_accuracy_requires_explicit_passing_criterion():
    measured = accuracy(AccuracyStatus.ACCURACY_COMPUTED, tolerance_passed=None, authority="authoritative")
    assert validate_lunar_gps(request(accuracy=measured)).status is FinalValidationStatus.TECHNICALLY_VALID
    passed = accuracy(AccuracyStatus.ACCURACY_COMPUTED, tolerance_passed=True, authority="authoritative")
    assert validate_lunar_gps(request(accuracy=passed)).status is FinalValidationStatus.VALIDATED


def test_failed_estimate_is_blocked_and_invalid_estimate_is_invalid():
    assert validate_lunar_gps(request(coordinate_estimation=estimate(CoordinateEstimationStatus.ESTIMATION_BLOCKED))).status is FinalValidationStatus.BLOCKED
    assert validate_lunar_gps(request(coordinate_estimation=estimate(CoordinateEstimationStatus.INVALID_TRANSFORMATION))).status is FinalValidationStatus.INVALID


def test_required_artifact_missing_is_invalid_and_optional_evidence_can_be_absent():
    assert validate_lunar_gps(request(metadata_quality=None)).status is FinalValidationStatus.INVALID
    assert validate_lunar_gps(request()).status is FinalValidationStatus.TECHNICALLY_VALID


def test_synthetic_truth_evidence_cannot_validate():
    synthetic = accuracy(AccuracyStatus.ACCURACY_COMPUTED, tolerance_passed=True, authority="authoritative")
    synthetic_result = synthetic.results[0]
    synthetic_result = LocalizationAccuracyResult("case", synthetic_result.status, tolerance_passed=True, provenance={"truth_authority_status": "authoritative", "truth_provenance": {"classification": "synthetic"}})
    synthetic = LocalizationAccuracyEvaluation(synthetic.status, (synthetic_result,), 1, 0, {}, {})
    result = validate_lunar_gps(request(accuracy=synthetic))
    assert result.status is FinalValidationStatus.TECHNICALLY_VALID
    assert result.provenance["synthetic_evidence_present"] is True


def test_result_is_deterministic_and_traceable():
    first = validate_lunar_gps(request()).to_dict()
    second = validate_lunar_gps(request()).to_dict()
    assert first == second
    assert {entry["source"] for entry in first["evidence_matrix"]} == {f"11.{number}_{label}" for number, label in ((1, "unknown_image"), (2, "metadata_quality"), (3, "landmark_retrieval"), (4, "landmark_correspondence"), (5, "anchor_selection"), (6, "geometric_verification"), (7, "coordinate_estimation"), (8, "localization_confidence"), (9, "roi_retrieval"), (10, "metadata_separation"), (11, "accuracy"))}