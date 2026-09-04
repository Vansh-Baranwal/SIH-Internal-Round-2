"""Phase 11.7 coordinate estimation from verified image geometry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from .geometric_verification import GeometricVerificationResult, GeometricVerificationStatus


class CoordinateEstimationStatus(str, Enum):
    SUCCESS = "success"
    ESTIMATION_BLOCKED = "estimation_blocked"
    VERIFICATION_NOT_ACCEPTED = "verification_not_accepted"
    INVALID_INPUT = "invalid_input"
    MISSING_REFERENCE_COORDINATE = "missing_reference_coordinate"
    MISSING_REFERENCE_GEOREFERENCING = "missing_reference_georeferencing"
    UNKNOWN_CRS = "unknown_crs"
    UNSUPPORTED_COORDINATE_SYSTEM = "unsupported_coordinate_system"
    INVALID_TRANSFORMATION = "invalid_transformation"
    NONFINITE_RESULT = "nonfinite_result"
    OUT_OF_REFERENCE_EXTENT = "out_of_reference_extent"
    MULTIPLE_CONFLICTING_ESTIMATES = "multiple_conflicting_estimates"
    PROVENANCE_BLOCKED = "provenance_blocked"
    COORDINATE_ESTIMATION_FAILED = "coordinate_estimation_failed"


@dataclass(frozen=True)
class ReferenceImageGeoreferencing:
    """Authoritative pixel-to-coordinate metadata for one reference raster."""

    reference_image_id: str
    width: int
    height: int
    transform: Tuple[float, ...]
    crs: str
    coordinate_system: str
    reference_frame: str
    units: str
    axis_order: Tuple[str, str]
    source: str
    provenance: Any

    def __post_init__(self) -> None:
        if not isinstance(self.reference_image_id, str) or not self.reference_image_id.strip():
            raise ValueError("reference_image_id must be non-empty.")
        if not isinstance(self.width, int) or self.width <= 0 or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("width and height must be positive integers.")
        if len(self.transform) != 6 or not all(math.isfinite(float(value)) for value in self.transform):
            raise ValueError("transform must contain six finite coefficients.")
        for name, value in (("crs", self.crs), ("coordinate_system", self.coordinate_system), ("reference_frame", self.reference_frame), ("units", self.units), ("source", self.source)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty.")
        if len(self.axis_order) != 2 or not all(isinstance(axis, str) and axis.strip() for axis in self.axis_order):
            raise ValueError("axis_order must contain two non-empty axis names.")
        if self.provenance is None:
            raise ValueError("provenance is required.")


@dataclass(frozen=True)
class CoordinateEstimationRequest:
    """Inputs to one deterministic unknown-pixel coordinate estimate."""

    unknown_image_id: str
    target_pixel: Tuple[float, float]
    geometric_verification: GeometricVerificationResult
    reference_georeferencing: Optional[ReferenceImageGeoreferencing]
    reference_image_id: str
    anchor_id: Optional[str] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CoordinateEstimationResult:
    status: CoordinateEstimationStatus
    unknown_image_id: str
    reference_image_id: Optional[str]
    anchor_id: Optional[str]
    target_pixel: Optional[Tuple[float, float]]
    reference_pixel: Optional[Tuple[float, float]]
    estimated_coordinate: Optional[Tuple[float, float]]
    coordinate_system: Optional[str]
    reference_frame: Optional[str]
    units: Optional[str]
    axis_order: Optional[Tuple[str, str]]
    method: str = "verified_pixel_to_reference_affine_to_map"
    transformation_model: Optional[str] = None
    transformation_parameters: Optional[Tuple[Tuple[float, ...], ...]] = None
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "unknown_image_id": self.unknown_image_id,
            "reference_image_id": self.reference_image_id,
            "anchor_id": self.anchor_id,
            "target_pixel": list(self.target_pixel) if self.target_pixel is not None else None,
            "reference_pixel": list(self.reference_pixel) if self.reference_pixel is not None else None,
            "estimated_coordinate": list(self.estimated_coordinate) if self.estimated_coordinate is not None else None,
            "coordinate_system": self.coordinate_system,
            "reference_frame": self.reference_frame,
            "units": self.units,
            "axis_order": list(self.axis_order) if self.axis_order is not None else None,
            "method": self.method,
            "transformation_model": self.transformation_model,
            "transformation_parameters": [list(row) for row in self.transformation_parameters] if self.transformation_parameters else None,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
        }


def _blocked(request: CoordinateEstimationRequest, status: CoordinateEstimationStatus, warning: str, limitation: str, *, reference_pixel: Optional[Tuple[float, float]] = None, provenance: Optional[Dict[str, Any]] = None) -> CoordinateEstimationResult:
    return CoordinateEstimationResult(status, request.unknown_image_id, request.reference_image_id, request.anchor_id, request.target_pixel, reference_pixel, None, None, None, None, None, limitations=(limitation,), warnings=(warning,), provenance=provenance or dict(request.provenance))


def estimate_coordinate(request: CoordinateEstimationRequest) -> CoordinateEstimationResult:
    """Estimate a coordinate through the verified source-pixel chain."""
    if not isinstance(request, CoordinateEstimationRequest):
        raise TypeError("request must be a CoordinateEstimationRequest instance.")
    if not isinstance(request.unknown_image_id, str) or not request.unknown_image_id.strip() or not isinstance(request.reference_image_id, str) or not request.reference_image_id.strip():
        return _blocked(request, CoordinateEstimationStatus.INVALID_INPUT, "invalid_image_identity", "Unknown and reference image identities are required.")
    try:
        target = np.asarray(request.target_pixel, dtype=np.float64)
        if target.shape != (2,) or not np.isfinite(target).all():
            raise ValueError
    except (TypeError, ValueError):
        return _blocked(request, CoordinateEstimationStatus.INVALID_INPUT, "invalid_target_pixel", "The target pixel must contain two finite numeric values.")
    verification = request.geometric_verification
    if not isinstance(verification, GeometricVerificationResult):
        return _blocked(request, CoordinateEstimationStatus.INVALID_INPUT, "invalid_verification_result", "A Phase 11.6 result is required.")
    if verification.status not in {GeometricVerificationStatus.SUCCESS, GeometricVerificationStatus.VERIFIED}:
        return _blocked(request, CoordinateEstimationStatus.VERIFICATION_NOT_ACCEPTED, "verification_status_not_accepted", "Only a verified Phase 11.6 transformation may produce an estimate.")
    if verification.verified_anchor_id is None or request.anchor_id is not None and request.anchor_id != verification.verified_anchor_id:
        return _blocked(request, CoordinateEstimationStatus.INVALID_INPUT, "anchor_identity_mismatch", "The request anchor must match the verified Phase 11.6 anchor.")
    if verification.model not in {"affine", "homography"} or verification.transform_matrix is None:
        return _blocked(request, CoordinateEstimationStatus.INVALID_TRANSFORMATION, "missing_or_unsupported_transformation", "The verified transformation model and matrix are required.")
    matrix = np.asarray(verification.transform_matrix, dtype=np.float64)
    expected_shape = (2, 3) if verification.model == "affine" else (3, 3)
    if matrix.shape != expected_shape or not np.isfinite(matrix).all():
        return _blocked(request, CoordinateEstimationStatus.INVALID_TRANSFORMATION, "malformed_transformation_matrix", "The verified transformation matrix has invalid dimensions or values.")
    if (verification.model == "affine" and abs(np.linalg.det(matrix[:, :2])) <= np.finfo(float).eps) or (verification.model == "homography" and abs(np.linalg.det(matrix)) <= np.finfo(float).eps):
        return _blocked(request, CoordinateEstimationStatus.INVALID_TRANSFORMATION, "singular_transformation_matrix", "The verified transformation is singular and cannot define a usable geometric mapping.")
    geo = request.reference_georeferencing
    if geo is None:
        return _blocked(request, CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING, "missing_reference_georeferencing", "A reference pixel-to-coordinate mapping is required.")
    if geo.reference_image_id != request.reference_image_id:
        return _blocked(request, CoordinateEstimationStatus.INVALID_INPUT, "reference_image_identity_mismatch", "The georeferencing must belong to the selected reference image.")
    if not geo.crs.strip() or geo.crs.lower() in {"unknown", "none", "null"}:
        return _blocked(request, CoordinateEstimationStatus.UNKNOWN_CRS, "unknown_crs", "CRS is missing or ambiguous; no coordinate system was guessed.")
    if geo.coordinate_system.lower() in {"unknown", "unsupported", "pixel", "image-relative"}:
        return _blocked(request, CoordinateEstimationStatus.UNSUPPORTED_COORDINATE_SYSTEM, "unsupported_coordinate_system", "The reference mapping does not declare a supported map-coordinate system.")
    coefficients = np.asarray(geo.transform, dtype=np.float64)
    if coefficients.shape != (6,) or not np.isfinite(coefficients).all() or abs(coefficients[0] * coefficients[4] - coefficients[1] * coefficients[3]) <= np.finfo(float).eps:
        return _blocked(request, CoordinateEstimationStatus.INVALID_TRANSFORMATION, "invalid_reference_geotransform", "The reference affine geotransform is malformed or singular.")
    if verification.model == "affine":
        reference = matrix[:, :2] @ target + matrix[:, 2]
    else:
        homogeneous = matrix @ np.array([target[0], target[1], 1.0])
        if not np.isfinite(homogeneous).all() or abs(homogeneous[2]) <= np.finfo(float).eps:
            return _blocked(request, CoordinateEstimationStatus.NONFINITE_RESULT, "nonfinite_transform_output", "The verified homography produced a non-finite or undefined reference pixel.")
        reference = homogeneous[:2] / homogeneous[2]
    if not np.isfinite(reference).all():
        return _blocked(request, CoordinateEstimationStatus.NONFINITE_RESULT, "nonfinite_transform_output", "The verified transformation produced a non-finite reference pixel.")
    reference_tuple = (float(reference[0]), float(reference[1]))
    if not (0.0 <= reference[0] <= geo.width and 0.0 <= reference[1] <= geo.height):
        return _blocked(request, CoordinateEstimationStatus.OUT_OF_REFERENCE_EXTENT, "reference_pixel_out_of_extent", "The transformed point is outside the reference raster extent.", reference_pixel=reference_tuple)
    col, row = reference
    coordinate = np.array([coefficients[0] * col + coefficients[1] * row + coefficients[2], coefficients[3] * col + coefficients[4] * row + coefficients[5]])
    if not np.isfinite(coordinate).all():
        return _blocked(request, CoordinateEstimationStatus.NONFINITE_RESULT, "nonfinite_coordinate", "The reference geotransform produced a non-finite coordinate.", reference_pixel=reference_tuple)
    provenance = {**dict(request.provenance), "unknown_image_id": request.unknown_image_id, "reference_image_id": request.reference_image_id, "anchor_id": verification.verified_anchor_id, "geometric_verification": verification.to_dict(), "reference_georeferencing": {"source": geo.source, "crs": geo.crs, "coordinate_system": geo.coordinate_system, "reference_frame": geo.reference_frame, "units": geo.units, "axis_order": list(geo.axis_order), "provenance": geo.provenance}, "estimation_method": "unknown_pixel_to_verified_reference_pixel_to_reference_affine_geotransform", "output_provenance": "estimated"}
    return CoordinateEstimationResult(CoordinateEstimationStatus.SUCCESS, request.unknown_image_id, request.reference_image_id, verification.verified_anchor_id, (float(target[0]), float(target[1])), reference_tuple, (float(coordinate[0]), float(coordinate[1])), geo.coordinate_system, geo.reference_frame, geo.units, geo.axis_order, transformation_model=verification.model, transformation_parameters=tuple(tuple(float(value) for value in row) for row in matrix), provenance=provenance)


def estimate_multiple_coordinates(requests: Sequence[CoordinateEstimationRequest]) -> Tuple[CoordinateEstimationResult, ...]:
    """Estimate each verified anchor independently; never average results."""
    return tuple(estimate_coordinate(request) for request in requests)


__all__ = ["CoordinateEstimationRequest", "CoordinateEstimationResult", "CoordinateEstimationStatus", "ReferenceImageGeoreferencing", "estimate_coordinate", "estimate_multiple_coordinates"]