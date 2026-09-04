import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain.coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from lunar_hazard_mapper.m4_terrain.geometric_verification import GeometricVerificationResult, GeometricVerificationStatus
from lunar_hazard_mapper.m4_terrain.localization_confidence import (
    LocalizationConfidenceRequest,
    LocalizationConfidenceStatus,
    evaluate_localization_confidence,
)


def evidence(**overrides):
    values = dict(
        status=GeometricVerificationStatus.SUCCESS, model="affine", verified_anchor_id="A",
        selected_anchor_ids=("A",), inlier_count=12, inlier_ratio=1.0,
        mean_reprojection_error_px=0.1, median_reprojection_error_px=0.1,
        max_reprojection_error_px=0.2, spatial_coverage=0.9,
        transform_matrix=np.asarray([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]]), residuals_px=(0.1, 0.1),
        provenance={"input_provenance": "synthetic"},
    )
    values.update(overrides)
    return GeometricVerificationResult(**values)


def estimate(**overrides):
    values = dict(
        status=CoordinateEstimationStatus.SUCCESS, unknown_image_id="U", reference_image_id="R", anchor_id="A",
        target_pixel=(1.0, 2.0), reference_pixel=(2.0, 3.0), estimated_coordinate=(10.0, 20.0),
        coordinate_system="projected", reference_frame="synthetic-frame", units="metres", axis_order=("x", "y"),
        provenance={"output_provenance": "synthetic"},
    )
    values.update(overrides)
    return CoordinateEstimationResult(**values)


def evaluate(verification=None, coordinate=None):
    return evaluate_localization_confidence(LocalizationConfidenceRequest(
        verification if verification is not None else evidence(),
        coordinate if coordinate is not None else estimate(),
        provenance={"pipeline": "m4", "source": "synthetic"},
    ))


def test_strong_evidence_is_high_but_uncalibrated():
    result = evaluate()
    assert result.status is LocalizationConfidenceStatus.HIGH
    assert result.evidence_score is not None and result.evidence_score <= 1.0
    assert result.score_calibrated is False
    assert "probability" not in result.to_dict()
    assert "accuracy" not in result.to_dict()


@pytest.mark.parametrize("changes", [
    {"inlier_count": 1, "inlier_ratio": 0.1},
    {"mean_reprojection_error_px": 5.0},
    {"spatial_coverage": 0.01},
])
def test_weak_dimensions_reduce_score(changes):
    result = evaluate(evidence(**changes))
    assert result.status in {LocalizationConfidenceStatus.LOW, LocalizationConfidenceStatus.MODERATE}


@pytest.mark.parametrize("status", [
    GeometricVerificationStatus.NOT_VERIFIED,
    GeometricVerificationStatus.DEGENERATE_CONFIGURATION,
    GeometricVerificationStatus.NO_INLIERS,
])
def test_invalid_geometry_does_not_score(status):
    result = evaluate(evidence(status=status))
    assert result.status is LocalizationConfidenceStatus.INVALID_INPUT
    assert result.evidence_score is None


@pytest.mark.parametrize("status", [
    CoordinateEstimationStatus.ESTIMATION_BLOCKED,
    CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING,
    CoordinateEstimationStatus.UNKNOWN_CRS,
    CoordinateEstimationStatus.OUT_OF_REFERENCE_EXTENT,
])
def test_blocked_coordinate_chain_is_distinct_from_low(status):
    result = evaluate(coordinate=estimate(status=status, estimated_coordinate=None))
    assert result.status is LocalizationConfidenceStatus.BLOCKED
    assert result.blocked_reason == status.value
    assert result.evidence_score is None


def test_missing_and_malformed_upstream_are_explicit():
    missing = evaluate_localization_confidence(LocalizationConfidenceRequest(None, None))
    malformed = evaluate_localization_confidence(LocalizationConfidenceRequest(object(), object()))
    assert missing.status is LocalizationConfidenceStatus.NOT_COMPUTABLE
    assert malformed.status is LocalizationConfidenceStatus.INVALID_INPUT


@pytest.mark.parametrize("changes", [
    {"inlier_ratio": np.nan}, {"mean_reprojection_error_px": np.inf},
    {"spatial_coverage": -0.1}, {"residuals_px": (np.nan,)},
])
def test_nonfinite_and_malformed_evidence_is_not_repaired(changes):
    result = evaluate(evidence(**changes))
    assert result.status is LocalizationConfidenceStatus.INVALID_INPUT
    assert result.evidence_score is None


def test_missing_residuals_and_contradictory_claims_are_invalid():
    assert evaluate(evidence(residuals_px=())).status is LocalizationConfidenceStatus.INVALID_INPUT
    assert evaluate(evidence(claims_localization=True)).status is LocalizationConfidenceStatus.INVALID_INPUT


def test_categories_have_documented_boundaries():
    assert evaluate(evidence(inlier_count=1, inlier_ratio=0.0, mean_reprojection_error_px=5.0, spatial_coverage=0.0)).status is LocalizationConfidenceStatus.LOW
    assert evaluate(evidence(inlier_count=12, inlier_ratio=1.0, mean_reprojection_error_px=0.0, spatial_coverage=1.0)).status is LocalizationConfidenceStatus.HIGH


def test_repeated_evaluation_and_provenance_are_deterministic():
    request = LocalizationConfidenceRequest(evidence(), estimate(), {"provenance": "synthetic"})
    first = evaluate_localization_confidence(request)
    second = evaluate_localization_confidence(request)
    assert first.to_dict() == second.to_dict()
    assert first.provenance["provenance"] == "synthetic"
    assert first.provenance["coordinate_estimation"]["provenance"]["output_provenance"] == "synthetic"


def test_metadata_coordinates_are_not_consumed_and_no_roi_is_created():
    result = evaluate()
    payload = result.to_dict()
    assert "metadata_coordinates" not in payload
    assert "roi" not in payload
    assert "ground_truth" not in payload