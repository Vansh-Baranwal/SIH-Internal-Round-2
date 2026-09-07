import numpy as np

from lunar_hazard_mapper.m4_terrain.coordinate_estimation import (
    CoordinateEstimationRequest,
    CoordinateEstimationStatus,
    ReferenceImageGeoreferencing,
    estimate_coordinate,
    estimate_multiple_coordinates,
)
from lunar_hazard_mapper.m4_terrain.geometric_verification import (
    GeometricVerificationResult,
    GeometricVerificationStatus,
)


def verification(matrix, model="affine", status=GeometricVerificationStatus.SUCCESS, anchor="A"):
    return GeometricVerificationResult(
        status=status, model=model, verified_anchor_id=anchor,
        selected_anchor_ids=(anchor,), inlier_count=4, inlier_ratio=1.0,
        mean_reprojection_error_px=0.0, transform_matrix=np.asarray(matrix),
    )


def georef(reference_id="R", **kwargs):
    values = dict(
        reference_image_id=reference_id, width=100, height=80,
        transform=(2.0, 0.5, 100.0, 0.25, -3.0, 500.0),
        crs="LUNAR_TEST_CRS", coordinate_system="projected",
        reference_frame="synthetic-lunar-frame", units="metres",
        axis_order=("easting", "northing"), source="synthetic-raster-metadata",
        provenance="synthetic",
    )
    values.update(kwargs)
    return ReferenceImageGeoreferencing(**values)


_DEFAULT_GEOREF = object()


def request(v, g=_DEFAULT_GEOREF, target=(5.0, 7.0), **kwargs):
    anchor_id = kwargs.pop("anchor_id", "A")
    return CoordinateEstimationRequest(
        unknown_image_id="unknown-1", target_pixel=target,
        geometric_verification=v, reference_georeferencing=georef() if g is _DEFAULT_GEOREF else g,
        reference_image_id="R", anchor_id=anchor_id, provenance={"source": "synthetic-fixture"}, **kwargs,
    )


def test_valid_affine_chain_preserves_coordinate_semantics():
    result = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]])))
    assert result.status is CoordinateEstimationStatus.SUCCESS
    assert result.reference_pixel == (15.0, 27.0)
    assert result.estimated_coordinate == (143.5, 422.75)
    assert result.coordinate_system == "projected"
    assert result.axis_order == ("easting", "northing")


def test_valid_homography_chain():
    result = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20], [0, 0, 1]], "homography")))
    assert result.status is CoordinateEstimationStatus.SUCCESS
    assert result.reference_pixel == (15.0, 27.0)


def test_not_verified_is_blocked():
    result = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]], status=GeometricVerificationStatus.NOT_VERIFIED)))
    assert result.status is CoordinateEstimationStatus.VERIFICATION_NOT_ACCEPTED
    assert result.estimated_coordinate is None


def test_malformed_and_singular_transformations_are_blocked():
    malformed = estimate_coordinate(request(verification([[1, 0], [0, 1]])))
    assert malformed.status is CoordinateEstimationStatus.INVALID_TRANSFORMATION
    singular = estimate_coordinate(request(verification([[0, 0, 10], [0, 0, 20]])))
    assert singular.status is CoordinateEstimationStatus.INVALID_TRANSFORMATION
    assert singular.estimated_coordinate is None


def test_missing_mapping_and_unknown_crs_are_blocked():
    missing = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]]), None))
    assert missing.status is CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING
    unknown = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]]), georef(crs="unknown")))
    assert unknown.status is CoordinateEstimationStatus.UNKNOWN_CRS


def test_unsupported_coordinate_system_and_identity_mismatch_are_blocked():
    unsupported = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]]), georef(coordinate_system="pixel")))
    assert unsupported.status is CoordinateEstimationStatus.UNSUPPORTED_COORDINATE_SYSTEM
    mismatch = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]]), georef("other")))
    assert mismatch.status is CoordinateEstimationStatus.INVALID_INPUT


def test_extent_and_boundary_handling_are_explicit():
    outside = estimate_coordinate(request(verification([[1, 0, 200], [0, 1, 20]])))
    assert outside.status is CoordinateEstimationStatus.OUT_OF_REFERENCE_EXTENT
    boundary = estimate_coordinate(request(verification([[1, 0, 95], [0, 1, 73]])))
    assert boundary.status is CoordinateEstimationStatus.SUCCESS


def test_multiple_estimates_are_independent_and_not_averaged():
    first = request(verification([[1, 0, 10], [0, 1, 20]]))
    second = request(verification([[1, 0, 11], [0, 1, 20]], anchor="B"), anchor_id="B")
    results = estimate_multiple_coordinates((first, second))
    assert [item.estimated_coordinate for item in results] == [(143.5, 422.75), (145.5, 423.0)]


def test_repeated_execution_and_provenance_are_deterministic():
    item = request(verification([[1, 0, 10], [0, 1, 20]]))
    first = estimate_coordinate(item)
    second = estimate_coordinate(item)
    assert first.to_dict() == second.to_dict()
    assert first.provenance["output_provenance"] == "estimated"
    assert first.provenance["reference_georeferencing"]["provenance"] == "synthetic"
    assert "confidence" not in first.to_dict()
    assert "accuracy" not in first.to_dict()
    assert "roi" not in first.to_dict()


def test_nonfinite_target_is_invalid():
    result = estimate_coordinate(request(verification([[1, 0, 10], [0, 1, 20]]), target=(np.nan, 1.0)))
    assert result.status is CoordinateEstimationStatus.INVALID_INPUT