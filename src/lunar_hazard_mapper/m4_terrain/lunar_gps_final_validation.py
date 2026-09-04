"""Phase 11.12 final, evidence-based Lunar GPS validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from .coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from .estimated_metadata_separation import EstimatedMetadataSeparationResult
from .geometric_verification import GeometricVerificationResult, GeometricVerificationStatus
from .landmark_correspondence import LandmarkCorrespondenceResult
from .landmark_retrieval import LandmarkRetrievalResult
from .localization_accuracy import AccuracyStatus, LocalizationAccuracyEvaluation, LocalizationAccuracyResult
from .localization_confidence import LocalizationConfidenceResult, LocalizationConfidenceStatus
from .metadata_quality import MetadataQualityResult
from .roi_retrieval import ROIStatus, ROIRetrievalResult
from .unknown_image import UnknownImage
from .anchor_selection import AnchorSelectionResult, AnchorSelectionStatus


class FinalValidationStatus(str, Enum):
    VALIDATED = "validated"
    TECHNICALLY_VALID = "technically_valid"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"
    INVALID = "invalid"


@dataclass(frozen=True)
class LunarGPSFinalValidationRequest:
    """The complete Phase 11 evidence chain, supplied by its owning phases."""

    validation_request_id: str
    unknown_image: Optional[UnknownImage]
    metadata_quality: Optional[MetadataQualityResult]
    landmark_retrieval: Optional[LandmarkRetrievalResult]
    landmark_correspondence: Optional[LandmarkCorrespondenceResult]
    anchor_selection: Optional[AnchorSelectionResult]
    geometric_verification: Optional[GeometricVerificationResult]
    coordinate_estimation: Optional[CoordinateEstimationResult]
    localization_confidence: Optional[LocalizationConfidenceResult]
    roi_retrieval: Optional[ROIRetrievalResult]
    metadata_separation: Optional[EstimatedMetadataSeparationResult]
    accuracy: Optional[LocalizationAccuracyEvaluation | LocalizationAccuracyResult]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.validation_request_id, str) or not self.validation_request_id.strip():
            raise ValueError("validation_request_id must be non-empty.")


@dataclass(frozen=True)
class LunarGPSFinalValidationResult:
    validation_request_id: str
    status: FinalValidationStatus
    validation_level: int
    estimated_coordinate: Optional[Tuple[float, ...]]
    upstream_statuses: Mapping[str, Optional[str]]
    evidence_matrix: Tuple[Mapping[str, Any], ...]
    consistency_checks: Tuple[Mapping[str, Any], ...]
    blocking_reasons: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    evidence_supporting_decision: Tuple[str, ...] = ()
    interpretation: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_request_id": self.validation_request_id,
            "status": self.status.value,
            "validation_level": self.validation_level,
            "estimated_coordinate": list(self.estimated_coordinate) if self.estimated_coordinate is not None else None,
            "upstream_statuses": dict(self.upstream_statuses),
            "evidence_matrix": [dict(item) for item in self.evidence_matrix],
            "consistency_checks": [dict(item) for item in self.consistency_checks],
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "evidence_supporting_decision": list(self.evidence_supporting_decision),
            "interpretation": self.interpretation,
            "provenance": dict(self.provenance),
        }


def _status(value: Any) -> Optional[str]:
    result = getattr(value, "status", None)
    return result.value if isinstance(result, Enum) else str(result) if result is not None else None


def _accuracy_results(value: Any) -> Tuple[LocalizationAccuracyResult, ...]:
    if isinstance(value, LocalizationAccuracyEvaluation):
        return value.results
    if isinstance(value, LocalizationAccuracyResult):
        return (value,)
    return ()


def _synthetic(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_synthetic(item) or (isinstance(item, str) and "synthetic" in item.lower()) for item in value.values())
    if isinstance(value, UnknownImage):
        return value.provenance.value == "synthetic" or str(value.provenance_source).lower() == "synthetic"
    provenance = getattr(value, "provenance", {})
    if isinstance(provenance, Mapping):
        return any(_synthetic(item) or (isinstance(item, str) and "synthetic" in item.lower()) for item in provenance.values())
    return isinstance(provenance, str) and "synthetic" in provenance.lower()


def _check(name: str, passed: bool, reason: str) -> Dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed", "reason": reason}


def validate_lunar_gps(request: LunarGPSFinalValidationRequest) -> LunarGPSFinalValidationResult:
    """Make a deterministic final decision without recomputing upstream evidence."""
    if not isinstance(request, LunarGPSFinalValidationRequest):
        raise TypeError("request must be a LunarGPSFinalValidationRequest instance.")
    items = {"11.1_unknown_image": request.unknown_image, "11.2_metadata_quality": request.metadata_quality, "11.3_landmark_retrieval": request.landmark_retrieval, "11.4_landmark_correspondence": request.landmark_correspondence, "11.5_anchor_selection": request.anchor_selection, "11.6_geometric_verification": request.geometric_verification, "11.7_coordinate_estimation": request.coordinate_estimation, "11.8_localization_confidence": request.localization_confidence, "11.9_roi_retrieval": request.roi_retrieval, "11.10_metadata_separation": request.metadata_separation, "11.11_accuracy": request.accuracy}
    statuses = {name: _status(value) for name, value in items.items()}
    checks = []
    failures = []
    required = ("11.1_unknown_image", "11.2_metadata_quality", "11.3_landmark_retrieval", "11.4_landmark_correspondence", "11.5_anchor_selection", "11.6_geometric_verification", "11.7_coordinate_estimation", "11.11_accuracy")
    for name in required:
        passed = items[name] is not None
        checks.append(_check(f"required_{name}", passed, "artifact supplied" if passed else "required upstream artifact is missing"))
        if not passed:
            failures.append(f"{name}_missing")
    estimate = request.coordinate_estimation
    if isinstance(estimate, CoordinateEstimationResult) and estimate.status is CoordinateEstimationStatus.SUCCESS and estimate.estimated_coordinate is None:
        failures.append("coordinate_estimation_success_without_coordinate")
        checks.append(_check("coordinate_estimate_coherence", False, "successful estimation has no coordinate"))
    elif estimate is not None:
        checks.append(_check("coordinate_estimate_coherence", True, "coordinate-estimation result is internally coherent"))
    verification = request.geometric_verification
    if isinstance(verification, GeometricVerificationResult) and isinstance(estimate, CoordinateEstimationResult) and estimate.status is CoordinateEstimationStatus.SUCCESS:
        passed = verification.status in {GeometricVerificationStatus.SUCCESS, GeometricVerificationStatus.VERIFIED} and not verification.claims_localization and not verification.claims_coordinate_estimation
        checks.append(_check("geometry_claim_boundary", passed, "geometry remains supporting evidence" if passed else "geometry claims contradict its frozen boundary"))
        if not passed:
            failures.append("contradictory_geometric_evidence")
    confidence = request.localization_confidence
    if isinstance(confidence, LocalizationConfidenceResult) and isinstance(estimate, CoordinateEstimationResult):
        passed = not (confidence.status is LocalizationConfidenceStatus.BLOCKED and confidence.evidence_score is not None)
        checks.append(_check("confidence_state_coherence", passed, "confidence state is coherent" if passed else "blocked confidence contains a score"))
        if not passed:
            failures.append("contradictory_confidence_evidence")
    roi = request.roi_retrieval
    if isinstance(roi, ROIRetrievalResult) and isinstance(estimate, CoordinateEstimationResult) and roi.status in {ROIStatus.SUCCESS, ROIStatus.PARTIAL}:
        passed = roi.reference_product_id == estimate.reference_image_id
        checks.append(_check("roi_reference_identity", passed, "ROI product matches estimated reference" if passed else "ROI product does not match estimated reference"))
        if not passed:
            failures.append("roi_reference_identity_mismatch")
    accuracy_results = _accuracy_results(request.accuracy)
    if any(result.status is AccuracyStatus.ACCURACY_COMPUTED and not str(result.provenance.get("truth_authority_status", "")).lower() in {"authoritative", "ground_truth"} for result in accuracy_results):
        failures.append("accuracy_computed_without_authoritative_truth")
        checks.append(_check("accuracy_authority", False, "computed accuracy lacks authoritative truth provenance"))
    elif request.accuracy is not None:
        checks.append(_check("accuracy_authority", True, "accuracy evidence does not contradict its truth provenance"))
    synthetic = any(_synthetic(value) for value in items.values() if value is not None) or any(_synthetic(result) for result in accuracy_results)
    if isinstance(request.unknown_image, UnknownImage) and request.unknown_image.is_real_data and request.unknown_image.provenance.value == "synthetic":
        failures.append("synthetic_provenance_marked_real")
    authoritative = bool(accuracy_results) and all(result.status is AccuracyStatus.ACCURACY_COMPUTED for result in accuracy_results) and not synthetic
    estimate_success = isinstance(estimate, CoordinateEstimationResult) and estimate.status is CoordinateEstimationStatus.SUCCESS and estimate.estimated_coordinate is not None
    if failures:
        status = FinalValidationStatus.INVALID
        level = 0
        interpretation = "Critical Phase 11 evidence is contradictory or invalid; no final validation claim is issued."
    elif isinstance(estimate, CoordinateEstimationResult) and estimate.status is not CoordinateEstimationStatus.SUCCESS:
        invalid_estimate = estimate.status in {CoordinateEstimationStatus.INVALID_INPUT, CoordinateEstimationStatus.INVALID_TRANSFORMATION, CoordinateEstimationStatus.NONFINITE_RESULT, CoordinateEstimationStatus.COORDINATE_ESTIMATION_FAILED, CoordinateEstimationStatus.MULTIPLE_CONFLICTING_ESTIMATES}
        status = FinalValidationStatus.INVALID if invalid_estimate else FinalValidationStatus.BLOCKED
        level = 0 if invalid_estimate else 1
        interpretation = "Coordinate estimation produced invalid evidence; no final validation claim is issued." if invalid_estimate else "Coordinate estimation did not produce a successful coordinate; final Lunar GPS validation is blocked."
    elif not estimate_success:
        status = FinalValidationStatus.BLOCKED
        level = 1
        interpretation = "Coordinate estimation did not produce a successful coordinate; final Lunar GPS validation is blocked."
    elif authoritative and all(result.tolerance_passed is True for result in accuracy_results):
        status = FinalValidationStatus.VALIDATED
        level = 4
        interpretation = "Authoritative truth was evaluated with compatible coordinate semantics and the supplied accuracy evidence supports the validation claim."
    elif authoritative and any(result.tolerance_passed is False for result in accuracy_results):
        status = FinalValidationStatus.INCONCLUSIVE
        level = 3
        interpretation = "Authoritative accuracy was measured, but the supplied evaluation criterion was not satisfied."
    else:
        status = FinalValidationStatus.TECHNICALLY_VALID
        level = 2
        interpretation = "The frozen Phase 11 evidence chain is technically usable, but authoritative real lunar truth is unavailable; scientific localization validation is not established."
    evidence = tuple({"source": name, "status": statuses[name], "used_for": "supporting evidence" if name not in required else "required chain evidence", "limitation": "not authoritative truth" if name != "11.11_accuracy" else "requires authoritative truth provenance"} for name in items)
    limitations = ("Confidence, geometry, ROI retrieval, and metadata separation are not accuracy evidence.", "Synthetic evidence validates mechanics only.", "No acceptance threshold is invented or inferred.")
    return LunarGPSFinalValidationResult(request.validation_request_id, status, level, tuple(estimate.estimated_coordinate) if estimate_success else None, statuses, evidence, tuple(checks), tuple(failures), warnings=(), limitations=limitations, evidence_supporting_decision=("Phase 11.11 accuracy evidence is absent or non-authoritative." if not authoritative else "Authoritative accuracy evidence is present and compatible." ,), interpretation=interpretation, provenance={**dict(request.provenance), "phase": "11.12", "synthetic_evidence_present": synthetic, "scientific_validation_claim": status is FinalValidationStatus.VALIDATED})


__all__ = ["FinalValidationStatus", "LunarGPSFinalValidationRequest", "LunarGPSFinalValidationResult", "validate_lunar_gps"]