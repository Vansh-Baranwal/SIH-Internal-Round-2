"""Robust geometric estimation, QuadTree spatial filtering, and sub-pixel refinement."""

from __future__ import annotations

import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional, Tuple, List

from .matchers import MatchResult


@dataclass
class GeometryResult:
    H: Optional[np.ndarray]       # 3x3 homography or None if estimation failed
    inlier_mask: np.ndarray        # boolean mask (N,) over input matches
    inlier_src: np.ndarray         # (M, 2) inlier source points
    inlier_dst: np.ndarray         # (M, 2) inlier destination points
    method: str = "RANSAC"


class RobustGeometry:
    """RANSAC/MAGSAC++ homography and affine estimation with sub-pixel refinement."""

    def __init__(
        self,
        method: str = "RANSAC",
        reproj_thresh: float = 4.0,
        confidence: float = 0.995,
        max_iters: int = 10000,
    ):
        self.reproj_thresh = reproj_thresh
        self.confidence = confidence
        self.max_iters = max_iters
        self.method_name = method.upper()
        if method.upper() == "MAGSAC":
            self._cv_method = cv2.USAC_MAGSAC
        elif method.upper() == "USAC":
            self._cv_method = cv2.USAC_DEFAULT
        else:
            self._cv_method = cv2.RANSAC

    def estimate_homography(self, match: MatchResult) -> GeometryResult:
        empty_mask = np.zeros(len(match.src_pts), dtype=bool)
        if len(match.src_pts) < 4:
            return GeometryResult(None, empty_mask, np.zeros((0, 2)), np.zeros((0, 2)), self.method_name)

        H, mask = cv2.findHomography(
            match.src_pts,
            match.dst_pts,
            method=self._cv_method,
            ransacReprojThreshold=self.reproj_thresh,
            confidence=self.confidence,
            maxIters=self.max_iters,
        )
        if mask is None:
            return GeometryResult(None, empty_mask, np.zeros((0, 2)), np.zeros((0, 2)), self.method_name)

        mask_bool = mask.ravel().astype(bool)
        inlier_src = match.src_pts[mask_bool]
        inlier_dst = match.dst_pts[mask_bool]
        return GeometryResult(H, mask_bool, inlier_src, inlier_dst, self.method_name)

    def warp_image(self, src: np.ndarray, H: np.ndarray, dst_shape: Tuple[int, int]) -> np.ndarray:
        """Warp src image using homography H to match dst_shape (h, w)."""
        h, w = dst_shape
        return cv2.warpPerspective(src, H, (w, h), flags=cv2.INTER_LINEAR)


class QuadTreeFilter:
    """Uniformly distribute keypoints across image using a spatial quad-tree grid."""

    def __init__(self, grid_size: int = 8):
        self.grid_size = grid_size

    def filter(
        self,
        src_pts: np.ndarray,
        dst_pts: np.ndarray,
        image_shape: Tuple[int, int],
        scores: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return at most one best match per grid cell."""
        if len(src_pts) == 0:
            return src_pts, dst_pts

        h, w = image_shape
        cell_h = max(1, h // self.grid_size)
        cell_w = max(1, w // self.grid_size)

        grid: dict[Tuple[int, int], int] = {}
        selected: List[int] = []

        if scores is None:
            scores = np.ones(len(src_pts))

        # Sort by score descending for best-first assignment
        order = np.argsort(-scores)
        for idx in order:
            x, y = src_pts[idx]
            cell = (int(y // cell_h), int(x // cell_w))
            if cell not in grid:
                grid[cell] = idx
                selected.append(idx)

        sel = np.array(selected)
        return src_pts[sel], dst_pts[sel]


def subpixel_refine(
    src: np.ndarray,
    dst: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    win_size: int = 15,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Refine match points to sub-pixel accuracy using Lucas-Kanade optical flow.
    Points from dst_pts are optionally phase-correlated; here we use LK tracking.
    """
    if len(src_pts) == 0:
        return src_pts, dst_pts

    gray_src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY) if src.ndim == 3 else src.astype(np.uint8)
    gray_dst = cv2.cvtColor(dst, cv2.COLOR_BGR2GRAY) if dst.ndim == 3 else dst.astype(np.uint8)

    pts = src_pts.reshape(-1, 1, 2).astype(np.float32)
    tracked, status, _ = cv2.calcOpticalFlowPyrLK(
        gray_src,
        gray_dst,
        pts,
        None,
        winSize=(win_size, win_size),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    if tracked is None or status is None:
        return src_pts, dst_pts

    good = status.ravel() == 1
    refined_src = src_pts[good]
    refined_dst = tracked.reshape(-1, 2)[good]
    return refined_src, refined_dst
