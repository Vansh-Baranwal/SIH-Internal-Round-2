"""
Registration Quality Metrics — per your roadmap doc Section 2.

1. RMSE on final inlier match points after transformation (target: < 1.0 pixels)
2. Inlier Count
3. Inlier Ratio (inliers / total initial matches)
4. Spatial Coverage (fraction of grid cells containing >=1 match)
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from lunar_hazard_mapper.correspondence_engine.geometry.spatial_uniform import compute_spatial_coverage


@dataclass
class RegistrationMetrics:
    rmse: float
    inlier_count: int
    total_matches: int
    inlier_ratio: float
    spatial_coverage: float
    meets_subpixel_target: bool  # RMSE < 1.0px

    def to_dict(self) -> dict:
        return {
            "rmse": round(self.rmse, 4),
            "inlier_count": self.inlier_count,
            "total_matches": self.total_matches,
            "inlier_ratio": round(self.inlier_ratio, 4),
            "spatial_coverage": round(self.spatial_coverage, 4),
            "meets_subpixel_target": self.meets_subpixel_target,
        }


def compute_rmse(pts_src_transformed: np.ndarray, pts_ref: np.ndarray) -> float:
    """RMSE between the transformed source points and their matched reference
    points — the standard registration accuracy metric."""
    if len(pts_src_transformed) == 0:
        return float("inf")
    diffs = pts_src_transformed - pts_ref
    return float(np.sqrt(np.mean(np.sum(diffs ** 2, axis=1))))


def apply_transform_to_points(pts: np.ndarray, transform_matrix: np.ndarray, model_type: str) -> np.ndarray:
    import cv2
    pts_reshaped = pts.reshape(-1, 1, 2).astype(np.float32)
    if model_type == "affine":
        transformed = cv2.transform(pts_reshaped, transform_matrix)
    elif model_type == "homography":
        transformed = cv2.perspectiveTransform(pts_reshaped, transform_matrix)
    else:
        raise ValueError(f"apply_transform_to_points doesn't support model_type={model_type} directly (TPS handled separately)")
    return transformed.reshape(-1, 2)


def apply_tps_to_points(pts: np.ndarray, tps_transformer) -> np.ndarray:
    """Warp points through a fitted cv2.ThinPlateSplineShapeTransformer.

    OpenCV's TPS transformer only exposes applyTransformation() for point
    sets shaped (1, N, 2) -- this wraps that quirk so callers can pass a
    plain (N, 2) array like they do for affine/homography.
    """
    pts_reshaped = pts.reshape(1, -1, 2).astype(np.float32)
    _cost, transformed = tps_transformer.applyTransformation(pts_reshaped)
    return transformed.reshape(-1, 2)


def evaluate_registration(pts_src_inlier_refined: np.ndarray, pts_ref_inlier_refined: np.ndarray,
                           inlier_count: int, total_matches: int,
                           transform_matrix: np.ndarray | None, model_type: str,
                           coverage_points: np.ndarray, image_shape: tuple[int, int],
                           tps_transformer=None) -> RegistrationMetrics:
    """
    IMPORTANT: pts_src_inlier_refined / pts_ref_inlier_refined must be the
    SUB-PIXEL REFINED inlier points, not the raw matcher output. Previously
    this function took the original unrefined match_result points + a mask,
    which meant reported RMSE never actually reflected sub-pixel refinement's
    contribution at all -- phase correlation vs Lucas-Kanade would report
    identical numbers regardless of which was used, since neither method's
    output ever reached this function.

    coverage_points: the FINAL post-uniform-filter point set (what's actually
    exported/delivered), since spatial coverage should reflect the delivered
    match distribution, not the pre-filter inlier set.
    """
    inlier_ratio = inlier_count / total_matches if total_matches > 0 else 0.0

    if inlier_count > 0 and model_type in ("affine", "homography") and transform_matrix is not None:
        transformed = apply_transform_to_points(pts_src_inlier_refined, transform_matrix, model_type)
        rmse = compute_rmse(transformed, pts_ref_inlier_refined)
    elif inlier_count > 0 and model_type == "tps" and tps_transformer is not None:
        transformed = apply_tps_to_points(pts_src_inlier_refined, tps_transformer)
        rmse = compute_rmse(transformed, pts_ref_inlier_refined)
    else:
        rmse = float("inf")

    coverage = compute_spatial_coverage(coverage_points, image_shape) if len(coverage_points) > 0 else 0.0

    return RegistrationMetrics(
        rmse=rmse,
        inlier_count=inlier_count,
        total_matches=total_matches,
        inlier_ratio=inlier_ratio,
        spatial_coverage=coverage,
        meets_subpixel_target=rmse < 1.0,
    )