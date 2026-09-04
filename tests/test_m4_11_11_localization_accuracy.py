"""Focused Phase 11.11 tests using explicitly synthetic test references."""

import math

import pytest

from lunar_hazard_mapper.m4_terrain import (
    AccuracyEvaluationConfig,
    AccuracyStatus,
    LocalizationAccuracyTestCase,
    LocalizationTruthReference,
    evaluate_accuracy_collection,
    evaluate_localization_accuracy,
)
from lunar_hazard_mapper.m4_terrain.coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus


def estimate(coordinate=(15.0, 4.0), **overrides):
    values = dict(status=CoordinateEstimationStatus.SUCCESS, unknown_image_id="unknown", reference_image_id="reference", anchor_id="anchor", target_pixel=(1.0, 1.0), reference_pixel=(2.0, 2.0), estimated_coordinate=coordinate, coordinate_system="projected", reference_frame="synthetic-lunar-frame", units="metres", axis_order=("x", "y"), provenance={"reference_georeferencing": {"crs": "SYNTHETIC-CRS"}, "output_provenance": "estimated"})
    values.update(overrides)
    return CoordinateEstimationResult(**values)


def truth(coordinate=(12.0, 8.0), **overrides):
    values = dict(reference_id="truth-1", coordinate=coordinate, coordinate_system="projected", crs="SYNTHETIC-CRS", reference_frame="synthetic-lunar-frame", units="metres", axis_order=("x", "y"), source="controlled-synthetic-fixture", provenance={"source": "controlled-synthetic-fixture", "dataset_version": "fixture-v1", "classification": "synthetic"}, authority_status="authoritative", validation_state="validated", dataset_version="fixture-v1", notes="Mechanics only; not lunar truth.")
    values.update(overrides)
    return LocalizationTruthReference(**values)


def case(**overrides):
    values = dict(test_case_id="case-1", estimate=estimate(), truth_reference=truth())
    values.update(overrides)
    return LocalizationAccuracyTestCase(**values)


def test_signed_absolute_and_coordinate_space_errors_are_reference_errors():
    result = evaluate_localization_accuracy(case())
    assert result.status is AccuracyStatus.ACCURACY_COMPUTED
    assert result.signed_axis_error == (3.0, -4.0)
    assert result.absolute_axis_error == (3.0, 4.0)
    assert result.coordinate_space_error == 5.0
    assert result.provenance["truth_provenance"]["classification"] == "synthetic"


def test_equal_coordinates_and_known_offset_are_deterministic():
    zero = evaluate_localization_accuracy(case(estimate=estimate((12.0, 8.0))))
    offset = evaluate_localization_accuracy(case(estimate=estimate((15.0, 4.0))))
    assert zero.to_dict() == evaluate_localization_accuracy(case(estimate=estimate((12.0, 8.0)))).to_dict()
    assert zero.absolute_axis_error == (0.0, 0.0)
    assert offset.coordinate_space_error == pytest.approx(math.hypot(3.0, -4.0))


@pytest.mark.parametrize("field", ["coordinate_system", "crs", "reference_frame", "units", "axis_order"])
def test_coordinate_semantics_must_match_without_conversion(field):
    values = {field: {"coordinate_system": "cartesian", "crs": "OTHER", "reference_frame": "OTHER", "units": "kilometres", "axis_order": ("y", "x")}[field]}
    assert evaluate_localization_accuracy(case(truth_reference=truth(**values))).status is AccuracyStatus.NOT_COMPARABLE


def test_dimension_mismatch_missing_semantics_and_angular_coordinates_are_explicit():
    assert evaluate_localization_accuracy(case(truth_reference=truth(coordinate=(12.0, 8.0, 1.0), axis_order=("x", "y", "z")))).status is AccuracyStatus.NOT_COMPARABLE
    assert evaluate_localization_accuracy(case(estimate=estimate(provenance={"reference_georeferencing": {}, "output_provenance": "estimated"}))).status is AccuracyStatus.NOT_COMPARABLE
    angular = truth(coordinate=(12.0, 8.0), coordinate_system="geographic", units="degrees")
    angular_estimate = estimate((359.0, 8.0), coordinate_system="geographic", units="degrees")
    result = evaluate_localization_accuracy(case(estimate=angular_estimate, truth_reference=angular))
    assert result.status is AccuracyStatus.ACCURACY_COMPUTED
    assert result.signed_axis_error == (347.0, 0.0)
    assert result.coordinate_space_error is None


def test_missing_invalid_unverified_and_nonfinite_inputs_are_not_computed():
    assert evaluate_localization_accuracy(case(truth_reference=None)).status is AccuracyStatus.NO_GROUND_TRUTH
    assert evaluate_localization_accuracy(case(truth_reference=truth(authority_status="unverified"))).status is AccuracyStatus.INVALID_TRUTH
    assert evaluate_localization_accuracy(case(estimate=None)).status is AccuracyStatus.INVALID_ESTIMATE
    assert evaluate_localization_accuracy(case(estimate=estimate(estimated_coordinate=(float("nan"), 4.0)))).status is AccuracyStatus.INVALID_ESTIMATE
    assert evaluate_localization_accuracy(case(truth_reference=truth(provenance={"source": "fixture"}))).status is AccuracyStatus.INVALID_TRUTH


def test_tolerance_requires_explicit_compatible_configuration_and_is_not_hardcoded():
    result = evaluate_localization_accuracy(case(config=AccuracyEvaluationConfig(tolerance=5.0, tolerance_units="metres", tolerance_coordinate_space="projected")))
    assert result.tolerance_passed is True
    invalid = evaluate_localization_accuracy(case(config=AccuracyEvaluationConfig(tolerance=5.0)))
    assert invalid.status is AccuracyStatus.INVALID_INPUT


def test_collection_aggregates_only_compatible_computed_cases():
    evaluation = evaluate_accuracy_collection((case(), case(test_case_id="case-2", estimate=estimate((13.0, 8.0))), case(test_case_id="missing", truth_reference=None)))
    assert evaluation.evaluated_cases == 2
    assert evaluation.unavailable_cases == 1
    assert evaluation.aggregate["values"] == (2.0, 2.0)
    assert evaluation.aggregate["coordinate_space_rmse"] == pytest.approx(math.sqrt((25.0 + 1.0) / 2.0))


def test_evaluation_does_not_change_estimate_or_consume_phase_11_8_11_9_or_11_10_data():
    original = estimate()
    before = original.to_dict()
    result = evaluate_localization_accuracy(case(estimate=original))
    assert original.to_dict() == before
    assert "confidence" not in result.to_dict()
    assert "roi" not in result.to_dict()
    assert "metadata" not in result.to_dict()
    assert result.provenance["truth_provenance"]["classification"] == "synthetic"


def test_failed_estimation_status_is_invalid_estimate_and_reprojection_is_not_accuracy():
    result = evaluate_localization_accuracy(case(estimate=estimate(status=CoordinateEstimationStatus.ESTIMATION_BLOCKED)))
    assert result.status is AccuracyStatus.INVALID_ESTIMATE
    assert "reprojection" not in result.to_dict()