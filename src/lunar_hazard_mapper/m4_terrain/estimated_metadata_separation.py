"""Phase 11.10 separation of estimated and source-metadata coordinates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, Mapping, Optional, Tuple

from .coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from .metadata_quality import FieldAssessmentStatus, MetadataAssessmentStatus, MetadataQualityResult
from .unknown_image import UnknownImage


class SeparationStatus(str, Enum):
    COMPARABLE = "comparable"
    NOT_COMPARABLE = "not_comparable"
    METADATA_MISSING = "metadata_missing"
    METADATA_INVALID = "metadata_invalid"
    ESTIMATE_MISSING = "estimate_missing"
    ESTIMATE_INVALID = "estimate_invalid"
    BLOCKED = "blocked"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class EstimatedMetadataSeparationRequest:
    request_id: str
    unknown_image: Optional[UnknownImage]
    metadata_quality: Optional[MetadataQualityResult]
    coordinate_estimation: Optional[CoordinateEstimationResult]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be non-empty.")


@dataclass(frozen=True)
class EstimatedMetadataSeparationResult:
    request_id: str
    status: SeparationStatus
    estimated_coordinate: Optional[Dict[str, Any]]
    metadata_coordinate: Optional[Dict[str, Any]]
    metadata_quality_status: Optional[str]
    coordinate_system: Optional[str] = None
    crs: Optional[str] = None
    reference_frame: Optional[str] = None
    units: Optional[str] = None
    axis_order: Optional[Tuple[str, ...]] = None
    signed_difference: Optional[Tuple[float, ...]] = None
    absolute_difference: Optional[Tuple[float, ...]] = None
    coordinate_space_separation: Optional[float] = None
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    reason: Optional[str] = None
    interpretation: str = "This is a source-metadata coordinate separation, not localization accuracy or ground-truth error."
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "estimated_coordinate": dict(self.estimated_coordinate) if self.estimated_coordinate else None,
            "metadata_coordinate": dict(self.metadata_coordinate) if self.metadata_coordinate else None,
            "metadata_quality_status": self.metadata_quality_status,
            "coordinate_system": self.coordinate_system,
            "crs": self.crs,
            "reference_frame": self.reference_frame,
            "units": self.units,
            "axis_order": list(self.axis_order) if self.axis_order else None,
            "signed_difference": list(self.signed_difference) if self.signed_difference else None,
            "absolute_difference": list(self.absolute_difference) if self.absolute_difference else None,
            "coordinate_space_separation": self.coordinate_space_separation,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "reason": self.reason,
            "interpretation": self.interpretation,
            "provenance": dict(self.provenance),
        }


def _result(request: EstimatedMetadataSeparationRequest, status: SeparationStatus, reason: Optional[str], *, estimated: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None, quality: Optional[str] = None, **kwargs: Any) -> EstimatedMetadataSeparationResult:
    values = dict(
        request_id=request.request_id,
        status=status,
        estimated_coordinate=estimated,
        metadata_coordinate=metadata,
        metadata_quality_status=quality,
        limitations=("A metadata separation is not evidence of accuracy, truth, or correctness.",),
        provenance={**dict(request.provenance), "estimated_coordinate": estimated.get("provenance", {}) if estimated else None, "metadata_coordinate": metadata.get("provenance", {}) if metadata else None, "comparison": {"performed": status is SeparationStatus.COMPARABLE}},
        reason=reason,
    )
    values.update(kwargs)
    return EstimatedMetadataSeparationResult(**values)


def _estimated_record(result: CoordinateEstimationResult) -> Dict[str, Any]:
    reference = result.provenance.get("reference_georeferencing", {}) if isinstance(result.provenance, dict) else {}
    return {
        "coordinate": tuple(float(value) for value in result.estimated_coordinate) if result.estimated_coordinate is not None else None,
        "coordinate_system": result.coordinate_system,
        "crs": reference.get("crs"),
        "reference_frame": result.reference_frame,
        "units": result.units,
        "axis_order": tuple(result.axis_order) if result.axis_order is not None else None,
        "provenance": dict(result.provenance),
        "origin": "phase_11.7_coordinate_estimation",
    }


def _metadata_record(image: UnknownImage) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    raw = image.metadata_coordinates
    if raw is None:
        return None, None
    if not isinstance(raw, dict) or not raw:
        return None, "metadata_coordinates_not_a_nonempty_mapping"
    coordinate = raw.get("coordinate")
    axis_order = raw.get("axis_order")
    if coordinate is None:
        if "x" in raw and "y" in raw:
            coordinate = (raw["x"], raw["y"])
        elif "lon" in raw and "lat" in raw:
            coordinate = (raw["lon"], raw["lat"])
    if coordinate is None or not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
        return None, "metadata_coordinate_values_are_missing_or_not_two_dimensional"
    if axis_order is None or not isinstance(axis_order, (list, tuple)) or len(axis_order) != 2 or any(not isinstance(axis, str) or not axis.strip() for axis in axis_order):
        return None, "metadata_axis_order_is_missing_or_invalid"
    semantics = (raw.get("coordinate_system"), raw.get("crs"), raw.get("reference_frame"), raw.get("units"))
    if any(not isinstance(value, str) or not value.strip() for value in semantics):
        return None, "metadata_coordinate_semantics_are_missing"
    try:
        values = tuple(float(value) for value in coordinate)
    except (TypeError, ValueError, OverflowError):
        return None, "metadata_coordinate_values_are_not_numeric"
    if not all(math.isfinite(value) for value in values):
        return None, "metadata_coordinate_values_are_nonfinite"
    return {"coordinate": tuple(coordinate), "numeric_coordinate": values, "coordinate_system": raw["coordinate_system"], "crs": raw["crs"], "reference_frame": raw["reference_frame"], "units": raw["units"], "axis_order": tuple(axis_order), "raw": dict(raw), "provenance": {"source": image.provenance_source, "image_id": image.image_id, "source_metadata": True}, "origin": "phase_11.1_unknown_image_metadata"}, None


def separate_estimated_metadata(request: EstimatedMetadataSeparationRequest) -> EstimatedMetadataSeparationResult:
    """Report the relationship between two separate coordinate records."""
    if not isinstance(request, EstimatedMetadataSeparationRequest):
        raise TypeError("request must be an EstimatedMetadataSeparationRequest instance.")
    if request.unknown_image is None or not isinstance(request.unknown_image, UnknownImage):
        return _result(request, SeparationStatus.INVALID_INPUT, "unknown_image_is_required")
    estimate = request.coordinate_estimation
    if estimate is None:
        return _result(request, SeparationStatus.ESTIMATE_MISSING, "coordinate_estimation_is_missing")
    if not isinstance(estimate, CoordinateEstimationResult):
        return _result(request, SeparationStatus.ESTIMATE_INVALID, "coordinate_estimation_is_malformed")
    estimated = _estimated_record(estimate)
    if estimate.status is not CoordinateEstimationStatus.SUCCESS:
        blocked = estimate.status in {CoordinateEstimationStatus.ESTIMATION_BLOCKED, CoordinateEstimationStatus.VERIFICATION_NOT_ACCEPTED, CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING, CoordinateEstimationStatus.UNKNOWN_CRS, CoordinateEstimationStatus.UNSUPPORTED_COORDINATE_SYSTEM, CoordinateEstimationStatus.PROVENANCE_BLOCKED}
        return _result(request, SeparationStatus.BLOCKED if blocked else SeparationStatus.ESTIMATE_INVALID, f"coordinate_estimation_{estimate.status.value}", estimated=estimated)
    if estimate.estimated_coordinate is None or len(estimate.estimated_coordinate) != 2 or not all(math.isfinite(float(value)) for value in estimate.estimated_coordinate):
        return _result(request, SeparationStatus.ESTIMATE_INVALID, "estimated_coordinate_is_missing_or_nonfinite", estimated=estimated)
    metadata, metadata_reason = _metadata_record(request.unknown_image)
    quality = request.metadata_quality
    if metadata is None and metadata_reason is None:
        return _result(request, SeparationStatus.METADATA_MISSING, "source_metadata_coordinate_is_missing", estimated=estimated)
    if quality is None:
        return _result(request, SeparationStatus.BLOCKED, "metadata_quality_result_is_required", estimated=estimated, metadata=metadata)
    if not isinstance(quality, MetadataQualityResult) or quality.image_id != request.unknown_image.image_id:
        return _result(request, SeparationStatus.INVALID_INPUT, "metadata_quality_result_is_malformed_or_for_wrong_image", estimated=estimated, metadata=metadata)
    quality_name = quality.assessment_status.value
    field = quality.field_assessments.get("metadata_coordinates")
    if field is not None and field.status is FieldAssessmentStatus.INVALID:
        return _result(request, SeparationStatus.METADATA_INVALID, "metadata_quality_marks_coordinate_invalid", estimated=estimated, metadata=metadata, quality=quality_name)
    if metadata_reason is not None:
        return _result(request, SeparationStatus.METADATA_INVALID if "values" in metadata_reason or "mapping" in metadata_reason else SeparationStatus.NOT_COMPARABLE, metadata_reason, estimated=estimated, metadata=metadata, quality=quality_name)
    if field is None or field.status in {FieldAssessmentStatus.MISSING, FieldAssessmentStatus.UNKNOWN}:
        return _result(request, SeparationStatus.NOT_COMPARABLE, "metadata_quality_does_not_authorize_coordinate_comparison", estimated=estimated, metadata=metadata, quality=quality_name)
    if quality.assessment_status in {MetadataAssessmentStatus.METADATA_INVALID, MetadataAssessmentStatus.METADATA_UNKNOWN, MetadataAssessmentStatus.METADATA_INSUFFICIENT}:
        return _result(request, SeparationStatus.NOT_COMPARABLE, "metadata_quality_is_not_sufficient_for_comparison", estimated=estimated, metadata=metadata, quality=quality_name)
    estimated_values = tuple(float(value) for value in estimated["coordinate"])
    metadata_values = tuple(float(value) for value in metadata["numeric_coordinate"])
    comparable_fields = ("coordinate_system", "crs", "reference_frame", "units", "axis_order")
    if any(estimated[key] != metadata[key] for key in comparable_fields):
        return _result(request, SeparationStatus.NOT_COMPARABLE, "coordinate_semantics_are_not_compatible_without_authorized_conversion", estimated=estimated, metadata=metadata, quality=quality_name)
    signed = tuple(estimated_values[index] - metadata_values[index] for index in range(2))
    absolute = tuple(abs(value) for value in signed)
    limitation = ("Metadata quality is partial; comparison remains a source-metadata separation and is not calibrated truth.",) if quality.assessment_status is MetadataAssessmentStatus.METADATA_PARTIAL else ()
    return _result(request, SeparationStatus.COMPARABLE, None, estimated=estimated, metadata=metadata, quality=quality_name, coordinate_system=estimated["coordinate_system"], crs=estimated["crs"], reference_frame=estimated["reference_frame"], units=estimated["units"], axis_order=estimated["axis_order"], signed_difference=signed, absolute_difference=absolute, coordinate_space_separation=math.hypot(*signed), limitations=("A metadata separation is not evidence of accuracy, truth, or correctness.",) + limitation, provenance={**dict(request.provenance), "estimated_coordinate": dict(estimated["provenance"]), "metadata_coordinate": dict(metadata["provenance"]), "comparison": {"performed": True, "metadata_quality": quality_name, "interpretation": "coordinate-space difference only"}})


__all__ = ["SeparationStatus", "EstimatedMetadataSeparationRequest", "EstimatedMetadataSeparationResult", "separate_estimated_metadata"]