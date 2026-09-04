import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain.anchor_selection import AnchorSelectionResult, AnchorSelectionStatus
from lunar_hazard_mapper.m4_terrain.geometric_verification import (
    GeometricVerificationConfig,
    GeometricVerificationRequest,
    GeometricVerificationStatus,
    verify_geometry,
)


@pytest.fixture
def affine_point_pairs():
    src = np.array([
        [10.0, 20.0],
        [50.0, 30.0],
        [80.0, 80.0],
        [120.0, 100.0],
        [140.0, 60.0],
    ], dtype=np.float32)
    dst = src + np.array([[30.0, 10.0], [30.0, 10.0], [30.0, 10.0], [30.0, 10.0], [30.0, 10.0]], dtype=np.float32)
    return src, dst


@pytest.fixture
def anchor_selection_result():
    return AnchorSelectionResult(
        status=AnchorSelectionStatus.SINGLE_ANCHOR_SELECTED,
        selected_anchor_ids=["A-001"],
        rejected_anchor_ids=[],
        ambiguous_anchor_ids=[],
        ranking=(("A-001", 42.0),),
        warnings=(),
        limitations=("Selection limited to Phase 11.5 semantics.",),
        provenance={"unknown_image_provenance": "real", "candidate_provenance": "real"},
    )


def test_valid_affine_geometry_verifies(anchor_selection_result, affine_point_pairs):
    src, dst = affine_point_pairs
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=3, min_inlier_ratio=0.5, max_reprojection_error_px=5.0),
    )
    result = verify_geometry(request)
    assert result.status is GeometricVerificationStatus.SUCCESS
    assert result.inlier_count >= 3
    assert result.inlier_ratio > 0.5
    assert result.model == "affine"
    assert not result.claims_localization
    assert not result.claims_coordinate_estimation


def test_duplicate_source_points_are_rejected(anchor_selection_result):
    src = np.array([[10.0, 10.0], [10.0, 10.0], [30.0, 30.0], [40.0, 40.0]], dtype=np.float32)
    dst = np.array([[15.0, 12.0], [15.0, 12.0], [35.0, 35.0], [45.0, 45.0]], dtype=np.float32)
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=2),
    )
    result = verify_geometry(request)
    assert result.status in {
        GeometricVerificationStatus.INVALID_INPUT,
        GeometricVerificationStatus.DEGENERATE_CONFIGURATION,
        GeometricVerificationStatus.NOT_VERIFIED,
    }


def test_tps_model_is_rejected():
    with pytest.raises(ValueError):
        GeometricVerificationConfig(model="tps")


def test_insufficient_correspondences_are_rejected(anchor_selection_result):
    src = np.array([[10.0, 10.0], [20.0, 20.0]], dtype=np.float32)
    dst = np.array([[15.0, 12.0], [25.0, 22.0]], dtype=np.float32)
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=3),
    )
    result = verify_geometry(request)
    assert result.status in {GeometricVerificationStatus.INSUFFICIENT_CORRESPONDENCES, GeometricVerificationStatus.NOT_VERIFIED}


def test_invalid_input_is_rejected():
    with pytest.raises(TypeError):
        verify_geometry(object())


def test_nan_points_are_rejected(anchor_selection_result):
    src = np.array([[10.0, np.nan], [20.0, 20.0]], dtype=np.float32)
    dst = np.array([[15.0, 12.0], [25.0, 22.0]], dtype=np.float32)
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=2),
    )
    result = verify_geometry(request)
    assert result.status in {
        GeometricVerificationStatus.INVALID_INPUT,
        GeometricVerificationStatus.NONFINITE_COORDINATES,
        GeometricVerificationStatus.VERIFICATION_BLOCKED,
    }


def test_provenance_is_preserved(anchor_selection_result):
    src = np.array([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0]], dtype=np.float32)
    dst = src + 5.0
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=2),
    )
    result = verify_geometry(request)
    assert result.provenance["unknown_image_provenance"] == "real"


def test_no_coordinate_estimation_in_result(anchor_selection_result, affine_point_pairs):
    src, dst = affine_point_pairs
    request = GeometricVerificationRequest(
        anchor_selection_result=anchor_selection_result,
        point_pairs={"A-001": {"source": src, "reference": dst}},
        config=GeometricVerificationConfig(model="affine", min_inliers=3),
    )
    result = verify_geometry(request)
    payload = result.to_dict()
    assert "estimated_coordinates" not in payload
    assert "estimated_latitude_deg" not in payload
    assert not result.claims_coordinate_estimation
    assert not result.claims_localization
