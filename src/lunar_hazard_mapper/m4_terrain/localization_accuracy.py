"""Phase 11.11 accuracy testing against an explicit reference contract.

This module is deliberately downstream of coordinate estimation.  Source image
metadata, landmark coordinates, confidence, reprojection residuals, and ROI
retrieval results are never accepted as truth references here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from statistics import mean
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus


class AccuracyStatus(str, Enum):
    ACCURACY_COMPUTED = "accuracy_computed"
    NO_GROUND_TRUTH = "no_ground_truth"
    BLOCKED = "blocked"
    NOT_COMPARABLE = "not_comparable"
    INVALID_ESTIMATE = "invalid_estimate"
    INVALID_TRUTH = "invalid_truth"
    INVALID_INPUT = "invalid_input"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class LocalizationTruthReference:
    """An explicitly identified, auditable test reference coordinate."""

    reference_id: str
    coordinate: Tuple[float, ...]
    coordinate_system: str
    crs: str
    reference_frame: str
    units: str
    axis_order: Tuple[str, ...]
    source: str
    provenance: Mapping[str, Any]
    authority_status: str
    validation_state: str
    dataset_version: str
    uncertainty: Optional[Tuple[float, ...]] = None
    notes: str = ""


@dataclass(frozen=True)
class AccuracyEvaluationConfig:
    """Optional evaluation configuration; no scientific threshold is defaulted."""

    tolerance: Optional[float] = None
    tolerance_units: Optional[str] = None
    tolerance_coordinate_space: Optional[str] = None


@dataclass(frozen=True)
class LocalizationAccuracyTestCase:
    test_case_id: str
    estimate: Optional[CoordinateEstimationResult]
    truth_reference: Optional[LocalizationTruthReference]
    config: AccuracyEvaluationConfig = field(default_factory=AccuracyEvaluationConfig)
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalizationAccuracyResult:
    test_case_id: str
    status: AccuracyStatus
    truth_reference_id: Optional[str] = None
    signed_axis_error: Optional[Tuple[float, ...]] = None
    absolute_axis_error: Optional[Tuple[float, ...]] = None
    coordinate_space_error: Optional[float] = None
    tolerance_passed: Optional[bool] = None
    coordinate_system: Optional[str] = None
    crs: Optional[str] = None
    reference_frame: Optional[str] = None
    units: Optional[str] = None
    axis_order: Optional[Tuple[str, ...]] = None
    reason: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "status": self.status.value,
            "truth_reference_id": self.truth_reference_id,
            "signed_axis_error": list(self.signed_axis_error) if self.signed_axis_error is not None else None,
            "absolute_axis_error": list(self.absolute_axis_error) if self.absolute_axis_error is not None else None,
            "coordinate_space_error": self.coordinate_space_error,
            "tolerance_passed": self.tolerance_passed,
            "coordinate_system": self.coordinate_system,
            "crs": self.crs,
            "reference_frame": self.reference_frame,
            "units": self.units,
            "axis_order": list(self.axis_order) if self.axis_order is not None else None,
            "reason": self.reason,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class LocalizationAccuracyEvaluation:
    status: AccuracyStatus
    results: Tuple[LocalizationAccuracyResult, ...]
    evaluated_cases: int
    unavailable_cases: int
    aggregate: Mapping[str, Any]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"results": [result.to_dict() for result in self.results], "evaluated_cases": self.evaluated_cases, "unavailable_cases": self.unavailable_cases, "aggregate": dict(self.aggregate), "provenance": dict(self.provenance)}


def _valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_numbers(values: Any, dimension: int) -> bool:
    try:
        return isinstance(values, (tuple, list)) and len(values) == dimension and all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError, OverflowError):
        return False


def _result(case: LocalizationAccuracyTestCase, status: AccuracyStatus, reason: str, **values: Any) -> LocalizationAccuracyResult:
    return LocalizationAccuracyResult(test_case_id=case.test_case_id, status=status, reason=reason, provenance={**dict(case.provenance), "truth_reference": case.truth_reference.reference_id if case.truth_reference else None, "evaluation": "phase_11.11_downstream_only", **values.pop("provenance", {})}, **values)


def _truth_is_valid(truth: LocalizationTruthReference) -> bool:
    try:
        required = (truth.reference_id, truth.coordinate_system, truth.crs, truth.reference_frame, truth.units, truth.source, truth.authority_status, truth.validation_state, truth.dataset_version)
        return all(_valid_text(value) for value in required) and isinstance(truth.provenance, Mapping) and _valid_text(truth.provenance.get("source")) and _valid_text(truth.provenance.get("dataset_version")) and len(truth.coordinate) >= 2 and _valid_numbers(truth.coordinate, len(truth.coordinate)) and len(truth.axis_order) == len(truth.coordinate) and all(_valid_text(axis) for axis in truth.axis_order) and truth.authority_status.lower() in {"authoritative", "ground_truth"} and truth.validation_state.lower() in {"validated", "verified"}
    except (AttributeError, TypeError):
        return False


def _estimate_record(estimate: CoordinateEstimationResult) -> Optional[Tuple[Tuple[float, ...], Dict[str, Any]]]:
    if not isinstance(estimate, CoordinateEstimationResult) or estimate.status is not CoordinateEstimationStatus.SUCCESS or estimate.estimated_coordinate is None:
        return None
    try:
        coordinate = tuple(float(value) for value in estimate.estimated_coordinate)
    except (TypeError, ValueError, OverflowError):
        return None
    if not coordinate or not all(math.isfinite(value) for value in coordinate):
        return None
    reference_geo = estimate.provenance.get("reference_georeferencing", {}) if isinstance(estimate.provenance, Mapping) else {}
    return coordinate, {"coordinate_system": estimate.coordinate_system, "crs": reference_geo.get("crs"), "reference_frame": estimate.reference_frame, "units": estimate.units, "axis_order": tuple(estimate.axis_order) if estimate.axis_order is not None else None}


def evaluate_localization_accuracy(case: LocalizationAccuracyTestCase) -> LocalizationAccuracyResult:
    """Compare an existing estimate to an explicitly supplied truth reference."""
    if not isinstance(case, LocalizationAccuracyTestCase) or not _valid_text(case.test_case_id):
        raise TypeError("case must be a LocalizationAccuracyTestCase with a non-empty test_case_id")
    if not isinstance(case.config, AccuracyEvaluationConfig):
        return _result(case, AccuracyStatus.INVALID_INPUT, "evaluation_configuration_is_malformed")
    if case.truth_reference is None:
        return _result(case, AccuracyStatus.NO_GROUND_TRUTH, "authoritative_test_reference_is_missing")
    if not isinstance(case.truth_reference, LocalizationTruthReference) or not _truth_is_valid(case.truth_reference):
        return _result(case, AccuracyStatus.INVALID_TRUTH, "truth_reference_is_invalid_or_lacks_authority_provenance")
    if case.estimate is None:
        return _result(case, AccuracyStatus.INVALID_ESTIMATE, "coordinate_estimation_result_is_missing", truth_reference_id=case.truth_reference.reference_id)
    estimate_record = _estimate_record(case.estimate)
    if estimate_record is None:
        return _result(case, AccuracyStatus.INVALID_ESTIMATE, "coordinate_estimate_is_not_a_finite_success_result", truth_reference_id=case.truth_reference.reference_id)
    estimated, semantics = estimate_record
    truth = case.truth_reference
    if len(estimated) != len(truth.coordinate):
        return _result(case, AccuracyStatus.NOT_COMPARABLE, "coordinate_dimensionality_is_incompatible", truth_reference_id=truth.reference_id)
    fields = ("coordinate_system", "crs", "reference_frame", "units", "axis_order")
    if any(semantics[field] is None or semantics[field] != getattr(truth, field) for field in fields):
        return _result(case, AccuracyStatus.NOT_COMPARABLE, "coordinate_semantics_are_incompatible_without_authorized_conversion", truth_reference_id=truth.reference_id)
    signed = tuple(estimated[index] - float(truth.coordinate[index]) for index in range(len(estimated)))
    absolute = tuple(abs(value) for value in signed)
    coordinate_space_error = math.sqrt(sum(value * value for value in signed)) if truth.coordinate_system.lower() in {"projected", "cartesian"} and truth.units.lower() not in {"degree", "degrees", "radian", "radians"} else None
    config = case.config
    if config.tolerance is not None and (not math.isfinite(float(config.tolerance)) or config.tolerance < 0 or config.tolerance_units != truth.units or config.tolerance_coordinate_space != truth.coordinate_system or coordinate_space_error is None):
        return _result(case, AccuracyStatus.INVALID_INPUT, "tolerance_is_missing_explicit_compatible_units_or_coordinate_space", truth_reference_id=truth.reference_id)
    return _result(case, AccuracyStatus.ACCURACY_COMPUTED, "accuracy_calculated_against_authoritative_test_reference", truth_reference_id=truth.reference_id, signed_axis_error=signed, absolute_axis_error=absolute, coordinate_space_error=coordinate_space_error, tolerance_passed=(coordinate_space_error <= config.tolerance if config.tolerance is not None else None), coordinate_system=truth.coordinate_system, crs=truth.crs, reference_frame=truth.reference_frame, units=truth.units, axis_order=truth.axis_order, provenance={"truth_source": truth.source, "truth_provenance": dict(truth.provenance), "truth_authority_status": truth.authority_status, "truth_validation_state": truth.validation_state, "dataset_version": truth.dataset_version})


def evaluate_accuracy_collection(cases: Sequence[LocalizationAccuracyTestCase]) -> LocalizationAccuracyEvaluation:
    """Evaluate cases independently and aggregate only compatible computed results."""
    results = tuple(evaluate_localization_accuracy(case) for case in cases)
    computed = tuple(result for result in results if result.status is AccuracyStatus.ACCURACY_COMPUTED)
    aggregate: Dict[str, Any] = {"metric": "mean_absolute_axis_error", "values": None, "coordinate_space_rmse": None, "limitations": "Aggregates include only compatible ACCURACY_COMPUTED cases."}
    if computed:
        dimensions = len(computed[0].absolute_axis_error or ())
        if all(len(result.absolute_axis_error or ()) == dimensions and result.axis_order == computed[0].axis_order and result.units == computed[0].units and result.crs == computed[0].crs and result.coordinate_system == computed[0].coordinate_system and result.reference_frame == computed[0].reference_frame for result in computed):
            aggregate["values"] = tuple(mean(result.absolute_axis_error[index] for result in computed if result.absolute_axis_error is not None) for index in range(dimensions))
        distances = [result.coordinate_space_error for result in computed if result.coordinate_space_error is not None]
        if distances and len(distances) == len(computed):
            aggregate["coordinate_space_rmse"] = math.sqrt(mean(distance * distance for distance in distances))
    status = AccuracyStatus.ACCURACY_COMPUTED if computed else AccuracyStatus.INSUFFICIENT_DATA if results else AccuracyStatus.INSUFFICIENT_DATA
    return LocalizationAccuracyEvaluation(status, results, len(computed), len(results) - len(computed), aggregate, {"evaluation": "phase_11.11_downstream_only", "truth_selection": "explicit_per_case_reference"})


__all__ = ["AccuracyStatus", "AccuracyEvaluationConfig", "LocalizationTruthReference", "LocalizationAccuracyTestCase", "LocalizationAccuracyResult", "LocalizationAccuracyEvaluation", "evaluate_localization_accuracy", "evaluate_accuracy_collection"]