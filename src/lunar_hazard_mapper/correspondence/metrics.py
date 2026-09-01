"""Registration quality metrics: RMSE, inlier count/ratio, spatial coverage."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional

from .geometry import GeometryResult


@dataclass
class RegistrationMetrics:
    rmse_px: float
    inlier_count: int
    inlier_ratio: float
    spatial_coverage: float          # 0–1, fraction of image area covered by inlier matches
    method: str = "unknown"
    meets_target: bool = False       # True when RMSE < 1.0 px


def compute_metrics(
    geo: GeometryResult,
    image_shape: tuple,
    raw_match_count: int,
    method: str = "unknown",
) -> RegistrationMetrics:
    """Compute registration metrics from geometric estimation result."""
    inlier_count = int(geo.inlier_mask.sum())
    inlier_ratio = inlier_count / max(1, raw_match_count)

    if geo.H is not None and inlier_count >= 4:
        projected = _project_points(geo.inlier_src, geo.H)
        errors = np.linalg.norm(projected - geo.inlier_dst, axis=1)
        rmse = float(np.sqrt(np.mean(errors ** 2)))
    else:
        rmse = float("inf")

    coverage = _spatial_coverage(geo.inlier_dst, image_shape)

    return RegistrationMetrics(
        rmse_px=rmse,
        inlier_count=inlier_count,
        inlier_ratio=inlier_ratio,
        spatial_coverage=coverage,
        method=method,
        meets_target=rmse < 1.0,
    )


def _project_points(pts: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Project N×2 points through homography H."""
    n = len(pts)
    homogeneous = np.hstack([pts, np.ones((n, 1))])
    projected_h = (H @ homogeneous.T).T
    projected_h /= projected_h[:, 2:3]
    return projected_h[:, :2]


def _spatial_coverage(pts: np.ndarray, image_shape: tuple) -> float:
    """Estimate fraction of image bounding area covered by match points using convex hull."""
    if len(pts) < 3:
        return 0.0
    h, w = image_shape[:2]
    image_area = h * w
    if image_area == 0:
        return 0.0
    try:
        import cv2
        hull = cv2.convexHull(pts.astype(np.float32))
        hull_area = cv2.contourArea(hull)
        return min(1.0, hull_area / image_area)
    except Exception:
        return 0.0
