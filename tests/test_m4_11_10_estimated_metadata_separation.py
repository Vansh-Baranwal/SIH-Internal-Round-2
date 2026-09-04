import math

import numpy as np

from lunar_hazard_mapper.m4_terrain import DataProvenance, UnknownImage
from lunar_hazard_mapper.m4_terrain.coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from lunar_hazard_mapper.m4_terrain.estimated_metadata_separation import EstimatedMetadataSeparationRequest, SeparationStatus, separate_estimated_metadata
from lunar_hazard_mapper.m4_terrain.metadata_quality import FieldAssessment, FieldAssessmentStatus, MetadataAssessmentStatus, MetadataQualityResult


def image(**overrides):
    values = dict(image_id="unknown-1", image_reference="fixture.tif", provenance=DataProvenance.SYNTHETIC, provenance_source="synthetic-metadata-fixture", is_real_data=False, metadata_coordinates={"x": 12.0, "y": 8.0, "coordinate_system": "projected", "crs": "LUNAR-CRS", "reference_frame": "lunar-frame", "units": "metres", "axis_order": ("x", "y")}, metadata_quality="high", validation_status="validated")
    values.update(overrides)
    return UnknownImage(**values)


def quality(status=MetadataAssessmentStatus.METADATA_VALID, field_status=FieldAssessmentStatus.PRESENT_VALID):
    return MetadataQualityResult(image_id="unknown-1", assessment_status=status, completeness_status="complete", completeness_score=1.0, field_assessments={"metadata_coordinates": FieldAssessment("metadata_coordinates", field_status, "fixture")}, warnings=(), limitations=(), provenance=DataProvenance.SYNTHETIC)


def estimate(**overrides):
    values = dict(status=CoordinateEstimationStatus.SUCCESS, unknown_image_id="unknown-1", reference_image_id="reference-1", anchor_id="anchor-1", target_pixel=(1.0, 1.0), reference_pixel=(1.0, 1.0), estimated_coordinate=(15.0, 4.0), coordinate_system="projected", reference_frame="lunar-frame", units="metres", axis_order=("x", "y"), provenance={"reference_georeferencing": {"crs": "LUNAR-CRS"}, "output_provenance": "estimated"})
    values.update(overrides)
    return CoordinateEstimationResult(**values)


def request(**overrides):
    values = dict(request_id="separation-1", unknown_image=image(), metadata_quality=quality(), coordinate_estimation=estimate())
    values.update(overrides)
    return EstimatedMetadataSeparationRequest(**values)


def test_comparable_result_keeps_records_separate_and_calculates_coordinate_difference():
    result = separate_estimated_metadata(request())
    assert result.status is SeparationStatus.COMPARABLE
    assert result.estimated_coordinate["coordinate"] == (15.0, 4.0)
    assert result.metadata_coordinate["coordinate"] == (12.0, 8.0)
    assert result.signed_difference == (3.0, -4.0)
    assert result.absolute_difference == (3.0, 4.0)
    assert result.coordinate_space_separation == 5.0
    assert result.estimated_coordinate["origin"] != result.metadata_coordinate["origin"]
    assert "accuracy" not in result.to_dict()
    assert "ground_truth_error" not in result.to_dict()


def test_equal_coordinates_have_zero_separation_without_replacing_estimate():
    result = separate_estimated_metadata(request(coordinate_estimation=estimate(estimated_coordinate=(12.0, 8.0))))
    assert result.signed_difference == (0.0, 0.0)
    assert result.coordinate_space_separation == 0.0
    assert result.estimated_coordinate["coordinate"] == (12.0, 8.0)


def test_missing_metadata_is_not_zero_or_an_estimate_failure():
    result = separate_estimated_metadata(request(unknown_image=image(metadata_coordinates=None)))
    assert result.status is SeparationStatus.METADATA_MISSING
    assert result.metadata_coordinate is None
    assert result.estimated_coordinate["coordinate"] == (15.0, 4.0)
    assert result.signed_difference is None


def test_missing_or_blocked_estimate_is_explicit():
    missing = separate_estimated_metadata(request(coordinate_estimation=None))
    blocked = separate_estimated_metadata(request(coordinate_estimation=estimate(status=CoordinateEstimationStatus.ESTIMATION_BLOCKED, estimated_coordinate=None)))
    invalid = separate_estimated_metadata(request(coordinate_estimation=estimate(status=CoordinateEstimationStatus.INVALID_INPUT)))
    assert missing.status is SeparationStatus.ESTIMATE_MISSING
    assert blocked.status is SeparationStatus.BLOCKED
    assert invalid.status is SeparationStatus.ESTIMATE_INVALID


def test_invalid_and_nonfinite_metadata_are_not_compared():
    invalid_quality = separate_estimated_metadata(request(metadata_quality=quality(field_status=FieldAssessmentStatus.INVALID)))
    nonfinite = separate_estimated_metadata(request(unknown_image=image(metadata_coordinates={"x": np.nan, "y": 8.0, "coordinate_system": "projected", "crs": "LUNAR-CRS", "reference_frame": "lunar-frame", "units": "metres", "axis_order": ("x", "y")})))
    assert invalid_quality.status is SeparationStatus.METADATA_INVALID
    assert nonfinite.status is SeparationStatus.METADATA_INVALID


def test_metadata_quality_is_required_and_limited_quality_is_preserved():
    missing_quality = separate_estimated_metadata(request(metadata_quality=None))
    partial = separate_estimated_metadata(request(metadata_quality=quality(MetadataAssessmentStatus.METADATA_PARTIAL)))
    insufficient = separate_estimated_metadata(request(metadata_quality=quality(MetadataAssessmentStatus.METADATA_INSUFFICIENT)))
    assert missing_quality.status is SeparationStatus.BLOCKED
    assert partial.status is SeparationStatus.COMPARABLE
    assert any("partial" in item for item in partial.limitations)
    assert insufficient.status is SeparationStatus.NOT_COMPARABLE


def test_crs_frame_units_system_and_axis_mismatches_are_not_converted():
    for key, value in (("crs", "OTHER-CRS"), ("reference_frame", "other-frame"), ("units", "degrees"), ("coordinate_system", "geographic"), ("axis_order", ("y", "x"))):
        coordinates = dict(image().metadata_coordinates)
        coordinates[key] = value
        result = separate_estimated_metadata(request(unknown_image=image(metadata_coordinates=coordinates)))
        assert result.status is SeparationStatus.NOT_COMPARABLE
        assert result.signed_difference is None


def test_missing_semantics_and_unknown_coordinate_representation_are_not_guessed():
    no_crs = dict(image().metadata_coordinates)
    del no_crs["crs"]
    unknown = {"lon": 12.0, "lat": 8.0, "crs": "LUNAR-CRS", "coordinate_system": "geographic", "reference_frame": "lunar-frame", "units": "degrees", "axis_order": ("lon", "lat")}
    assert separate_estimated_metadata(request(unknown_image=image(metadata_coordinates=no_crs))).status is SeparationStatus.NOT_COMPARABLE
    assert separate_estimated_metadata(request(unknown_image=image(metadata_coordinates=unknown))).status is SeparationStatus.NOT_COMPARABLE


def test_quality_result_contradictions_and_wrong_identity_are_rejected():
    malformed = separate_estimated_metadata(request(metadata_quality=object()))
    wrong_image = separate_estimated_metadata(request(metadata_quality=MetadataQualityResult(image_id="other", assessment_status=MetadataAssessmentStatus.METADATA_VALID, completeness_status="complete", completeness_score=1.0, field_assessments={}, warnings=(), limitations=(), provenance=DataProvenance.SYNTHETIC)))
    assert malformed.status is SeparationStatus.INVALID_INPUT
    assert wrong_image.status is SeparationStatus.INVALID_INPUT


def test_provenance_and_determinism_are_preserved():
    first = separate_estimated_metadata(request(provenance={"caller": "test"}))
    second = separate_estimated_metadata(request(provenance={"caller": "test"}))
    assert first.to_dict() == second.to_dict()
    assert first.provenance["estimated_coordinate"]["output_provenance"] == "estimated"
    assert first.provenance["metadata_coordinate"]["source_metadata"] is True
    assert first.metadata_coordinate["provenance"]["source"] == "synthetic-metadata-fixture"


def test_no_longitude_wrapping_or_phase_11_8_11_9_behavior_is_added():
    coordinates = dict(image().metadata_coordinates)
    coordinates.update(x=359.0, y=8.0)
    result = separate_estimated_metadata(request(unknown_image=image(metadata_coordinates=coordinates), coordinate_estimation=estimate(estimated_coordinate=(1.0, 8.0))))
    assert result.status is SeparationStatus.COMPARABLE
    assert result.signed_difference == (-358.0, 0.0)
    assert "confidence" not in result.to_dict()
    assert "roi" not in result.to_dict()
    assert math.isclose(result.coordinate_space_separation, math.hypot(-358.0, 0.0))