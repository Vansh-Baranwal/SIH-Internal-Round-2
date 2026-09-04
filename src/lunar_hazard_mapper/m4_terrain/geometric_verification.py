"""Phase 11.6 geometric verification for M4 landmark anchors.

This module consumes the deterministic Phase 11.5 anchor-selection result and
checks whether the candidate point pairs admit a robust geometric transform.
It explicitly does not estimate coordinates, localize the unknown image, or
claim a spatial solution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import cv2
import numpy as np

from lunar_hazard_mapper.correspondence_engine.geometry.ransac import (
    RegistrationTransform,
    geometric_verification,
)
from lunar_hazard_mapper.m4_terrain.anchor_selection import AnchorSelectionResult


class GeometricVerificationStatus(str, Enum):
    SUCCESS = "success"
    VERIFIED = "verified"
    NO_ANCHORS = "no_anchors"
    NO_CORRESPONDENCES = "no_correspondences"
    INSUFFICIENT_CORRESPONDENCES = "insufficient_correspondences"
    INVALID_INPUT = "invalid_input"
    NONFINITE_COORDINATES = "nonfinite_coordinates"
    DEGENERATE_CONFIGURATION = "degenerate_configuration"
    TRANSFORMATION_ESTIMATION_FAILED = "transformation_estimation_failed"
    NO_INLIERS = "no_inliers"
    INSUFFICIENT_INLIERS = "insufficient_inliers"
    NOT_VERIFIED = "not_verified"
    VERIFICATION_BLOCKED = "verification_blocked"
    PROVENANCE_BLOCKED = "provenance_blocked"


@dataclass(frozen=True)
class GeometricVerificationConfig:
    model: str = "affine"
    min_inliers: int = 3
    min_inlier_ratio: float = 0.25
    max_reprojection_error_px: float = 5.0
    ransac_thresh_px: float = 3.0

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string.")
        model = self.model.lower()
        if model not in {"affine", "homography"}:
            raise ValueError("Phase 11.6 supports affine and homography only; TPS is intentionally deferred.")
        object.__setattr__(self, "model", model)
        if not isinstance(self.min_inliers, int) or self.min_inliers < 1:
            raise ValueError("min_inliers must be a positive integer.")
        ratio = float(self.min_inlier_ratio)
        if not np.isfinite(ratio) or not (0.0 <= ratio <= 1.0):
            raise ValueError("min_inlier_ratio must be between 0.0 and 1.0.")
        object.__setattr__(self, "min_inlier_ratio", ratio)
        err = float(self.max_reprojection_error_px)
        if not np.isfinite(err) or err <= 0.0:
            raise ValueError("max_reprojection_error_px must be positive and finite.")
        object.__setattr__(self, "max_reprojection_error_px", err)
        thresh = float(self.ransac_thresh_px)
        if not np.isfinite(thresh) or thresh <= 0.0:
            raise ValueError("ransac_thresh_px must be positive and finite.")
        object.__setattr__(self, "ransac_thresh_px", thresh)


@dataclass(frozen=True)
class GeometricVerificationRequest:
    anchor_selection_result: AnchorSelectionResult
    point_pairs: Mapping[str, Mapping[str, Any]]
    config: Optional[GeometricVerificationConfig] = None

    def __post_init__(self) -> None:
        if not isinstance(self.anchor_selection_result, AnchorSelectionResult):
            raise TypeError("anchor_selection_result must be an AnchorSelectionResult instance.")
        if self.point_pairs is None:
            raise TypeError("point_pairs must not be None.")
        if self.config is None:
            object.__setattr__(self, "config", GeometricVerificationConfig())
        if not isinstance(self.config, GeometricVerificationConfig):
            raise TypeError("config must be a GeometricVerificationConfig instance.")


@dataclass(frozen=True)
class GeometricVerificationResult:
    status: GeometricVerificationStatus
    model: str
    verified_anchor_id: Optional[str]
    selected_anchor_ids: Tuple[str, ...]
    inlier_count: int
    inlier_ratio: float
    mean_reprojection_error_px: float
    median_reprojection_error_px: float = np.inf
    max_reprojection_error_px: float = np.inf
    outlier_count: int = 0
    spatial_coverage: float = 0.0
    transform_matrix: Optional[np.ndarray] = None
    residuals_px: Tuple[float, ...] = ()
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    claims_geometric_verification: bool = True
    claims_localization: bool = False
    claims_coordinate_estimation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status.value,
            "model": self.model,
            "verified_anchor_id": self.verified_anchor_id,
            "selected_anchor_ids": list(self.selected_anchor_ids),
            "inlier_count": self.inlier_count,
            "outlier_count": self.outlier_count,
            "inlier_ratio": self.inlier_ratio,
            "mean_reprojection_error_px": self.mean_reprojection_error_px,
            "median_reprojection_error_px": self.median_reprojection_error_px,
            "max_reprojection_error_px": self.max_reprojection_error_px,
            "spatial_coverage": self.spatial_coverage,
            "transform_matrix": None if self.transform_matrix is None else self.transform_matrix.tolist(),
            "residuals_px": list(self.residuals_px),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
            "claims_geometric_verification": self.claims_geometric_verification,
            "claims_localization": self.claims_localization,
            "claims_coordinate_estimation": self.claims_coordinate_estimation,
        }
        return payload


def _coerce_point_array(payload: Any, *, candidate_id: str, role: str) -> np.ndarray:
    if payload is None:
        raise ValueError(f"{candidate_id}:{role} is missing.")
    arr = np.asarray(payload, dtype=np.float32)
    if arr.size == 0:
        raise ValueError(f"{candidate_id}:{role} is empty.")
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"{candidate_id}:{role} must be an array of shape (N, 2).")
    if not np.isfinite(arr).all():
        raise ValueError(f"{candidate_id}:{role} contains NaN or Inf values.")
    return arr


def _check_degenerate_points(source_points: np.ndarray, reference_points: np.ndarray, *, model: str) -> Optional[str]:
    if len(source_points) != len(reference_points):
        return "source_and_reference_point_counts_do_not_match"
    if len(source_points) < 2:
        return "too_few_points"
    if np.unique(source_points, axis=0).shape[0] != len(source_points):
        return "duplicate_source_points"
    if np.unique(reference_points, axis=0).shape[0] != len(reference_points):
        return "duplicate_destination_points"
    min_required = 3 if model == "affine" else 4
    if len(source_points) < min_required:
        return None
    source_centered = source_points - source_points.mean(axis=0)
    ref_centered = reference_points - reference_points.mean(axis=0)
    if np.linalg.matrix_rank(source_centered) < 2:
        return "source_points_are_collinear_or_degenerate"
    if np.linalg.matrix_rank(ref_centered) < 2:
        return "reference_points_are_collinear_or_degenerate"
    return None


def _compute_spatial_coverage(source_points: np.ndarray, reference_points: np.ndarray, *, source_shape: Optional[Sequence[int]] = None) -> float:
    if len(source_points) < 2:
        return 0.0
    x_span = float(np.ptp(source_points[:, 0]))
    y_span = float(np.ptp(source_points[:, 1]))
    if x_span <= 0.0 or y_span <= 0.0:
        return 0.0
    image_area = 1.0
    if source_shape is not None and len(source_shape) >= 2:
        image_area = max(1.0, float(source_shape[0]) * float(source_shape[1]))
    box_area = x_span * y_span
    return float(min(1.0, box_area / image_area))


def _compute_reprojection_error(
    transform: RegistrationTransform,
    source_points: np.ndarray,
    reference_points: np.ndarray,
) -> np.ndarray:
    if transform is None:
        return np.full(len(source_points), np.inf, dtype=np.float32)
    if transform.model_type == "affine":
        matrix = transform.transform_matrix
        if matrix is None:
            return np.full(len(source_points), np.inf, dtype=np.float32)
        warped = cv2.transform(source_points.reshape(-1, 1, 2), matrix)
        diff = warped.reshape(-1, 2) - reference_points
        return np.linalg.norm(diff, axis=1)
    if transform.model_type == "homography":
        matrix = transform.transform_matrix
        if matrix is None:
            return np.full(len(source_points), np.inf, dtype=np.float32)
        warped = cv2.perspectiveTransform(source_points.reshape(-1, 1, 2), matrix)
        diff = warped.reshape(-1, 2) - reference_points
        return np.linalg.norm(diff, axis=1)
    return np.full(len(source_points), np.inf, dtype=np.float32)


def verify_geometry(request: GeometricVerificationRequest) -> GeometricVerificationResult:
    if not isinstance(request, GeometricVerificationRequest):
        raise TypeError("request must be an GeometricVerificationRequest instance.")

    config = request.config
    selected_anchor_ids = tuple(str(anchor_id) for anchor_id in request.anchor_selection_result.selected_anchor_ids)

    if not selected_anchor_ids:
        return GeometricVerificationResult(
            status=GeometricVerificationStatus.NO_ANCHORS,
            model=config.model,
            verified_anchor_id=None,
            selected_anchor_ids=selected_anchor_ids,
            inlier_count=0,
            inlier_ratio=0.0,
            mean_reprojection_error_px=np.inf,
            median_reprojection_error_px=np.inf,
            max_reprojection_error_px=np.inf,
            outlier_count=0,
            spatial_coverage=0.0,
            transform_matrix=None,
            residuals_px=(),
            warnings=("no_selected_anchors",),
            limitations=("Phase 11.5 produced no selected anchors; no geometric verification was attempted.",),
            provenance={
                **dict(request.anchor_selection_result.provenance),
                "selection_config": dict(request.anchor_selection_result.provenance.get("selection_config", {})),
                "verification_config": config.__dict__.copy(),
                "geometric_verification_performed": False,
            },
            claims_geometric_verification=False,
            claims_localization=False,
            claims_coordinate_estimation=False,
        )

    candidate_scores: list[tuple[str, RegistrationTransform, np.ndarray, np.ndarray, int, float, float, float, float, int, float, tuple[float, ...]]] = []
    too_short_candidates: list[str] = []
    invalid_candidates: list[str] = []
    degenerate_candidates: list[str] = []
    nonfinite_candidates: list[str] = []

    for anchor_id in selected_anchor_ids:
        pair = request.point_pairs.get(anchor_id)
        if pair is None or not isinstance(pair, Mapping):
            invalid_candidates.append(anchor_id)
            continue
        source_payload = pair.get("source")
        reference_payload = pair.get("reference")
        try:
            source_points = _coerce_point_array(source_payload, candidate_id=anchor_id, role="source")
            reference_points = _coerce_point_array(reference_payload, candidate_id=anchor_id, role="reference")
        except ValueError:
            nonfinite_candidates.append(anchor_id)
            continue
        if source_points.shape != reference_points.shape:
            invalid_candidates.append(anchor_id)
            continue
        degenerate_reason = _check_degenerate_points(source_points, reference_points, model=config.model)
        if degenerate_reason is not None:
            degenerate_candidates.append(anchor_id)
            continue
        if len(source_points) < config.min_inliers:
            too_short_candidates.append(anchor_id)
            continue

        try:
            transform = geometric_verification(
                source_points.astype(np.float32),
                reference_points.astype(np.float32),
                model=config.model,
                ransac_thresh=config.ransac_thresh_px,
            )
        except (cv2.error, TypeError, ValueError):
            return GeometricVerificationResult(
                status=GeometricVerificationStatus.TRANSFORMATION_ESTIMATION_FAILED,
                model=config.model,
                verified_anchor_id=None,
                selected_anchor_ids=selected_anchor_ids,
                inlier_count=0,
                inlier_ratio=0.0,
                mean_reprojection_error_px=np.inf,
                median_reprojection_error_px=np.inf,
                max_reprojection_error_px=np.inf,
                outlier_count=0,
                spatial_coverage=0.0,
                transform_matrix=None,
                residuals_px=(),
                warnings=("transformation_estimation_failed",),
                limitations=("The configured estimator could not fit a valid geometric transform to the supplied point pairs.",),
                provenance={
                    **dict(request.anchor_selection_result.provenance),
                    "verification_config": config.__dict__.copy(),
                    "failed_anchor_id": anchor_id,
                    "geometric_verification_performed": False,
                },
                claims_geometric_verification=False,
                claims_localization=False,
                claims_coordinate_estimation=False,
            )

        inlier_mask = transform.inlier_mask.astype(bool) if hasattr(transform, "inlier_mask") else np.ones(len(source_points), dtype=bool)
        reprojection_errors = _compute_reprojection_error(transform, source_points, reference_points)
        inlier_errors = reprojection_errors[inlier_mask] if np.any(inlier_mask) else np.array([], dtype=np.float32)
        inlier_count = int(np.count_nonzero(inlier_mask))
        outlier_count = int(len(source_points) - inlier_count)
        inlier_ratio = float(inlier_count / len(source_points)) if len(source_points) else 0.0
        mean_error = float(np.mean(inlier_errors)) if inlier_errors.size else np.inf
        median_error = float(np.median(inlier_errors)) if inlier_errors.size else np.inf
        max_error = float(np.max(inlier_errors)) if inlier_errors.size else np.inf
        residuals = tuple(float(v) for v in reprojection_errors.tolist())
        spatial_coverage = _compute_spatial_coverage(source_points, reference_points, source_shape=pair.get("source_shape"))
        candidate_scores.append((anchor_id, transform, source_points, reference_points, inlier_count, inlier_ratio, mean_error, median_error, max_error, outlier_count, spatial_coverage, residuals))

    if not candidate_scores:
        if degenerate_candidates:
            return GeometricVerificationResult(
                status=GeometricVerificationStatus.DEGENERATE_CONFIGURATION,
                model=config.model,
                verified_anchor_id=None,
                selected_anchor_ids=selected_anchor_ids,
                inlier_count=0,
                inlier_ratio=0.0,
                mean_reprojection_error_px=np.inf,
                median_reprojection_error_px=np.inf,
                max_reprojection_error_px=np.inf,
                outlier_count=0,
                spatial_coverage=0.0,
                transform_matrix=None,
                residuals_px=(),
                warnings=("degenerate_point_configuration",),
                limitations=(
                    "The candidate point set is degenerate, duplicated, or collinear for the selected transformation model.",
                    "Geometric verification is blocked without a valid transformation configuration.",
                ),
                provenance={
                    **dict(request.anchor_selection_result.provenance),
                    "verification_config": config.__dict__.copy(),
                    "degenerate_anchor_ids": tuple(degenerate_candidates),
                    "geometric_verification_performed": False,
                },
                claims_geometric_verification=False,
                claims_localization=False,
                claims_coordinate_estimation=False,
            )
        if nonfinite_candidates:
            return GeometricVerificationResult(
                status=GeometricVerificationStatus.NONFINITE_COORDINATES,
                model=config.model,
                verified_anchor_id=None,
                selected_anchor_ids=selected_anchor_ids,
                inlier_count=0,
                inlier_ratio=0.0,
                mean_reprojection_error_px=np.inf,
                median_reprojection_error_px=np.inf,
                max_reprojection_error_px=np.inf,
                outlier_count=0,
                spatial_coverage=0.0,
                transform_matrix=None,
                residuals_px=(),
                warnings=("nonfinite_coordinates",),
                limitations=("The point-pair input contains NaN or Inf values and is invalid for geometric verification.",),
                provenance={
                    **dict(request.anchor_selection_result.provenance),
                    "verification_config": config.__dict__.copy(),
                    "invalid_anchor_ids": tuple(nonfinite_candidates),
                    "geometric_verification_performed": False,
                },
                claims_geometric_verification=False,
                claims_localization=False,
                claims_coordinate_estimation=False,
            )
        if too_short_candidates:
            return GeometricVerificationResult(
                status=GeometricVerificationStatus.INSUFFICIENT_CORRESPONDENCES,
                model=config.model,
                verified_anchor_id=None,
                selected_anchor_ids=selected_anchor_ids,
                inlier_count=0,
                inlier_ratio=0.0,
                mean_reprojection_error_px=np.inf,
                median_reprojection_error_px=np.inf,
                max_reprojection_error_px=np.inf,
                outlier_count=0,
                spatial_coverage=0.0,
                transform_matrix=None,
                residuals_px=(),
                warnings=("insufficient_point_pairs_for_model",),
                limitations=(
                    "The selected points do not satisfy the configured minimum point count for the chosen model.",
                    "Geometric verification is verification-only and does not estimate coordinates.",
                ),
                provenance={
                    **dict(request.anchor_selection_result.provenance),
                    "verification_config": config.__dict__.copy(),
                    "too_short_anchor_ids": tuple(too_short_candidates),
                    "geometric_verification_performed": False,
                },
                claims_geometric_verification=False,
                claims_localization=False,
                claims_coordinate_estimation=False,
            )
        if invalid_candidates:
            return GeometricVerificationResult(
                status=GeometricVerificationStatus.INVALID_INPUT,
                model=config.model,
                verified_anchor_id=None,
                selected_anchor_ids=selected_anchor_ids,
                inlier_count=0,
                inlier_ratio=0.0,
                mean_reprojection_error_px=np.inf,
                median_reprojection_error_px=np.inf,
                max_reprojection_error_px=np.inf,
                outlier_count=0,
                spatial_coverage=0.0,
                transform_matrix=None,
                residuals_px=(),
                warnings=("invalid_point_pair_payload",),
                limitations=("At least one selected anchor did not contain valid source/reference point arrays.",),
                provenance={
                    **dict(request.anchor_selection_result.provenance),
                    "verification_config": config.__dict__.copy(),
                    "invalid_anchor_ids": tuple(invalid_candidates),
                    "geometric_verification_performed": False,
                },
                claims_geometric_verification=False,
                claims_localization=False,
                claims_coordinate_estimation=False,
            )

        return GeometricVerificationResult(
            status=GeometricVerificationStatus.NO_CORRESPONDENCES,
            model=config.model,
            verified_anchor_id=None,
            selected_anchor_ids=selected_anchor_ids,
            inlier_count=0,
            inlier_ratio=0.0,
            mean_reprojection_error_px=np.inf,
            median_reprojection_error_px=np.inf,
            max_reprojection_error_px=np.inf,
            outlier_count=0,
            spatial_coverage=0.0,
            transform_matrix=None,
            residuals_px=(),
            warnings=("no_verifiable_point_pairs",),
            limitations=("No selected anchor yielded enough valid point-pair evidence for geometric verification.",),
            provenance={
                **dict(request.anchor_selection_result.provenance),
                "verification_config": config.__dict__.copy(),
                "geometric_verification_performed": False,
            },
            claims_geometric_verification=False,
            claims_localization=False,
            claims_coordinate_estimation=False,
        )

    best_anchor_id, best_transform, best_source_points, best_reference_points, best_inlier_count, best_inlier_ratio, best_mean_error, best_median_error, best_max_error, best_outlier_count, best_coverage, best_residuals = max(
        candidate_scores,
        key=lambda item: (item[4], item[5], -item[6]),
    )

    if best_inlier_count < config.min_inliers or best_inlier_ratio < config.min_inlier_ratio:
        return GeometricVerificationResult(
            status=GeometricVerificationStatus.INSUFFICIENT_INLIERS,
            model=config.model,
            verified_anchor_id=None,
            selected_anchor_ids=selected_anchor_ids,
            inlier_count=best_inlier_count,
            inlier_ratio=best_inlier_ratio,
            mean_reprojection_error_px=best_mean_error,
            median_reprojection_error_px=best_median_error,
            max_reprojection_error_px=best_max_error,
            outlier_count=best_outlier_count,
            spatial_coverage=best_coverage,
            transform_matrix=(None if best_transform.transform_matrix is None else best_transform.transform_matrix.copy()),
            residuals_px=best_residuals,
            warnings=("below_minimum_inlier_threshold",),
            limitations=(
                "The strongest candidate anchor did not satisfy the configured inlier count or inlier-ratio threshold.",
                "Geometric verification is a verification-only step and does not produce a localization result.",
            ),
            provenance={
                **dict(request.anchor_selection_result.provenance),
                "verification_config": config.__dict__.copy(),
                "verified_anchor_id": best_anchor_id,
                "inlier_count": best_inlier_count,
                "inlier_ratio": best_inlier_ratio,
                "geometric_verification_performed": False,
            },
            claims_geometric_verification=False,
            claims_localization=False,
            claims_coordinate_estimation=False,
        )

    if best_mean_error > config.max_reprojection_error_px:
        return GeometricVerificationResult(
            status=GeometricVerificationStatus.NOT_VERIFIED,
            model=config.model,
            verified_anchor_id=None,
            selected_anchor_ids=selected_anchor_ids,
            inlier_count=best_inlier_count,
            inlier_ratio=best_inlier_ratio,
            mean_reprojection_error_px=best_mean_error,
            median_reprojection_error_px=best_median_error,
            max_reprojection_error_px=best_max_error,
            outlier_count=best_outlier_count,
            spatial_coverage=best_coverage,
            transform_matrix=(None if best_transform.transform_matrix is None else best_transform.transform_matrix.copy()),
            residuals_px=best_residuals,
            warnings=("reprojection_error_exceeds_threshold",),
            limitations=(
                "The best-fit geometric transform exceeded the configured reprojection-error tolerance.",
                "This phase validates geometry only; it does not estimate coordinates or localize the image.",
            ),
            provenance={
                **dict(request.anchor_selection_result.provenance),
                "verification_config": config.__dict__.copy(),
                "verified_anchor_id": best_anchor_id,
                "inlier_count": best_inlier_count,
                "inlier_ratio": best_inlier_ratio,
                "geometric_verification_performed": False,
            },
            claims_geometric_verification=False,
            claims_localization=False,
            claims_coordinate_estimation=False,
        )

    result = GeometricVerificationResult(
        status=GeometricVerificationStatus.SUCCESS,
        model=config.model,
        verified_anchor_id=best_anchor_id,
        selected_anchor_ids=selected_anchor_ids,
        inlier_count=best_inlier_count,
        inlier_ratio=best_inlier_ratio,
        mean_reprojection_error_px=best_mean_error,
        median_reprojection_error_px=best_median_error,
        max_reprojection_error_px=best_max_error,
        outlier_count=best_outlier_count,
        spatial_coverage=best_coverage,
        transform_matrix=(None if best_transform.transform_matrix is None else best_transform.transform_matrix.copy()),
        residuals_px=best_residuals,
        warnings=(),
        limitations=(
            "This result confirms only geometric consistency for the anchor candidate; it does not estimate image coordinates or localize the scene.",
        ),
        provenance={
            **dict(request.anchor_selection_result.provenance),
            "verification_config": config.__dict__.copy(),
            "verified_anchor_id": best_anchor_id,
            "inlier_count": best_inlier_count,
            "inlier_ratio": best_inlier_ratio,
            "mean_reprojection_error_px": best_mean_error,
            "median_reprojection_error_px": best_median_error,
            "max_reprojection_error_px": best_max_error,
            "spatial_coverage": best_coverage,
            "geometric_verification_performed": True,
        },
        claims_geometric_verification=True,
        claims_localization=False,
        claims_coordinate_estimation=False,
    )
    return result


__all__ = [
    "GeometricVerificationConfig",
    "GeometricVerificationRequest",
    "GeometricVerificationResult",
    "GeometricVerificationStatus",
    "verify_geometry",
]