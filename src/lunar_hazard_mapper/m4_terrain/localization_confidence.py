"""Phase 11.8 localization evidence quality evaluation.

The score in this module is an uncalibrated engineering evidence score.  It
describes the internal strength of verified upstream evidence; it is not a
probability, positional accuracy, metadata agreement, or ground-truth result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, Mapping, Optional, Tuple

from .coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus
from .geometric_verification import GeometricVerificationResult, GeometricVerificationStatus


class LocalizationConfidenceStatus(str, Enum):
    NOT_COMPUTABLE = "not_computable"
    BLOCKED = "blocked"
    INVALID_INPUT = "invalid_input"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True)
class LocalizationConfidenceRequest:
    geometric_verification: Optional[GeometricVerificationResult]
    coordinate_estimation: Optional[CoordinateEstimationResult]
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalizationConfidenceResult:
    status: LocalizationConfidenceStatus
    unknown_image_id: Optional[str]
    reference_image_id: Optional[str]
    anchor_id: Optional[str]
    evidence_score: Optional[float]
    score_calibrated: bool
    confidence_category: Optional[str]
    raw_evidence: Dict[str, Any] = field(default_factory=dict)
    normalized_components: Dict[str, float] = field(default_factory=dict)
    contributing_factors: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    blocked_reason: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "unknown_image_id": self.unknown_image_id,
            "reference_image_id": self.reference_image_id,
            "anchor_id": self.anchor_id,
            "evidence_score": self.evidence_score,
            "score_calibrated": self.score_calibrated,
            "confidence_category": self.confidence_category,
            "raw_evidence": dict(self.raw_evidence),
            "normalized_components": dict(self.normalized_components),
            "contributing_factors": list(self.contributing_factors),
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "blocked_reason": self.blocked_reason,
            "provenance": dict(self.provenance),
        }


def _terminal_result(
    request: LocalizationConfidenceRequest,
    status: LocalizationConfidenceStatus,
    warning: str,
    limitation: str,
    *,
    reason: Optional[str] = None,
) -> LocalizationConfidenceResult:
    verification = request.geometric_verification
    estimation = request.coordinate_estimation
    return LocalizationConfidenceResult(
        status=status,
        unknown_image_id=getattr(estimation, "unknown_image_id", None),
        reference_image_id=getattr(estimation, "reference_image_id", None),
        anchor_id=getattr(estimation, "anchor_id", None),
        evidence_score=None,
        score_calibrated=False,
        confidence_category=None,
        limitations=(limitation,),
        warnings=(warning,),
        blocked_reason=reason,
        provenance={
            **dict(request.provenance),
            "geometric_verification": dict(getattr(verification, "provenance", {}) or {}),
            "coordinate_estimation": dict(getattr(estimation, "provenance", {}) or {}),
        },
    )


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _category(score: float) -> LocalizationConfidenceStatus:
    if score < 0.40:
        return LocalizationConfidenceStatus.LOW
    if score < 0.75:
        return LocalizationConfidenceStatus.MODERATE
    return LocalizationConfidenceStatus.HIGH


def evaluate_localization_confidence(request: LocalizationConfidenceRequest) -> LocalizationConfidenceResult:
    """Evaluate finite, verified 11.6/11.7 evidence without claiming accuracy."""
    if not isinstance(request, LocalizationConfidenceRequest):
        raise TypeError("request must be a LocalizationConfidenceRequest instance.")
    verification = request.geometric_verification
    estimation = request.coordinate_estimation
    if verification is None or estimation is None:
        return _terminal_result(request, LocalizationConfidenceStatus.NOT_COMPUTABLE, "missing_upstream_result", "Both Phase 11.6 geometry and Phase 11.7 coordinate results are required.")
    if not isinstance(verification, GeometricVerificationResult) or not isinstance(estimation, CoordinateEstimationResult):
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "malformed_upstream_result", "Upstream results must use the frozen Phase 11.6 and 11.7 result contracts.")
    if estimation.status is not CoordinateEstimationStatus.SUCCESS:
        blocked = estimation.status in {
            CoordinateEstimationStatus.ESTIMATION_BLOCKED,
            CoordinateEstimationStatus.VERIFICATION_NOT_ACCEPTED,
            CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING,
            CoordinateEstimationStatus.UNKNOWN_CRS,
            CoordinateEstimationStatus.UNSUPPORTED_COORDINATE_SYSTEM,
            CoordinateEstimationStatus.PROVENANCE_BLOCKED,
            CoordinateEstimationStatus.OUT_OF_REFERENCE_EXTENT,
        }
        return _terminal_result(
            request,
            LocalizationConfidenceStatus.BLOCKED if blocked else LocalizationConfidenceStatus.INVALID_INPUT,
            f"coordinate_estimation_{estimation.status.value}",
            "The coordinate-estimation chain did not complete; no evidence score was manufactured.",
            reason=estimation.status.value if blocked else None,
        )
    if verification.status not in {GeometricVerificationStatus.SUCCESS, GeometricVerificationStatus.VERIFIED}:
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "geometry_not_verified", "Coordinate success contradicts the requirement for a verified Phase 11.6 geometry result.")
    if not verification.claims_geometric_verification or verification.claims_localization or verification.claims_coordinate_estimation:
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "contradictory_verification_claims", "Upstream verification claims are contradictory or cross the frozen Phase 11.6 boundary.")
    values = {
        "inlier_count": verification.inlier_count,
        "inlier_ratio": verification.inlier_ratio,
        "mean_reprojection_error_px": verification.mean_reprojection_error_px,
        "median_reprojection_error_px": verification.median_reprojection_error_px,
        "max_reprojection_error_px": verification.max_reprojection_error_px,
        "spatial_coverage": verification.spatial_coverage,
        "model": verification.model,
        "verification_status": verification.status.value,
        "coordinate_estimation_status": estimation.status.value,
    }
    if not isinstance(verification.inlier_count, int) or verification.inlier_count < 1:
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "invalid_inlier_count", "Verified evidence must contain a positive integer inlier count.")
    numeric = ("inlier_ratio", "mean_reprojection_error_px", "median_reprojection_error_px", "max_reprojection_error_px", "spatial_coverage")
    if any(not _finite(values[key]) for key in numeric):
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "nonfinite_evidence", "All supplied evidence dimensions must be finite.")
    if not 0.0 <= values["inlier_ratio"] <= 1.0 or not 0.0 <= values["spatial_coverage"] <= 1.0 or any(values[key] < 0.0 for key in numeric[1:]):
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "invalid_evidence_range", "Evidence values are outside their explicit physical or normalized ranges.")
    if verification.model not in {"affine", "homography"} or verification.verified_anchor_id is None or estimation.estimated_coordinate is None:
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "incomplete_success_evidence", "A successful result must contain a supported model, anchor, and estimated coordinate.")
    if len(verification.residuals_px) == 0:
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "missing_residual_evidence", "Reprojection residual evidence is required for this score.")
    if any(not _finite(value) or float(value) < 0.0 for value in verification.residuals_px):
        return _terminal_result(request, LocalizationConfidenceStatus.INVALID_INPUT, "invalid_residual_evidence", "Residuals must be finite and non-negative.")

    # Engineering weights are deliberately explicit, bounded, and not statistical.
    support = min(1.0, verification.inlier_count / 12.0)
    residual = max(0.0, 1.0 - verification.mean_reprojection_error_px / 5.0)
    components = {"inlier_support": support, "inlier_ratio": float(verification.inlier_ratio), "reprojection_quality": residual, "spatial_coverage": float(verification.spatial_coverage)}
    score = 0.25 * support + 0.20 * components["inlier_ratio"] + 0.30 * residual + 0.25 * components["spatial_coverage"]
    score = max(0.0, min(1.0, float(score)))
    category = _category(score)
    factors = []
    factors.append("verified geometry and completed coordinate-estimation chain")
    factors.append(f"{verification.inlier_count} verified inliers with ratio {verification.inlier_ratio:.3f}")
    factors.append(f"mean reprojection residual {verification.mean_reprojection_error_px:.3f} px")
    factors.append(f"spatial coverage {verification.spatial_coverage:.3f}")
    return LocalizationConfidenceResult(
        status=category,
        unknown_image_id=estimation.unknown_image_id,
        reference_image_id=estimation.reference_image_id,
        anchor_id=estimation.anchor_id,
        evidence_score=score,
        score_calibrated=False,
        confidence_category=category.value,
        raw_evidence=values,
        normalized_components=components,
        contributing_factors=tuple(factors),
        limitations=("This uncalibrated engineering evidence score is not a probability or positional accuracy measure.", "Pixel residuals remain in upstream pixel units; no physical-unit conversion was applied.", "Metadata coordinates and ground truth are not used."),
        warnings=tuple(verification.warnings) + tuple(estimation.warnings),
        provenance={**dict(request.provenance), "geometric_verification": verification.to_dict(), "coordinate_estimation": estimation.to_dict()},
    )


__all__ = ["LocalizationConfidenceRequest", "LocalizationConfidenceResult", "LocalizationConfidenceStatus", "evaluate_localization_confidence"]