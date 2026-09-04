"""
Stage C.1: Geometric Verification (RANSAC/MAGSAC++) & transformation estimation.

Rejects outlier matches (wrong correspondences that survived Stage B's ratio
test) by finding the largest set of matches consistent with a single global
geometric transformation. Supports affine/homography (flat terrain, nadir
imaging) and thin-plate-spline (complex topography, per your doc's "Piecewise/
Thin Plate Spline: For complex topography" guidance).
"""
from __future__ import annotations
import numpy as np
import cv2
from dataclasses import dataclass


@dataclass
class RegistrationTransform:
    transform_matrix: np.ndarray | None   # 2x3 (affine) or 3x3 (homography), None for TPS
    tps_transformer: object | None        # cv2.ThinPlateSplineShapeTransformer, if used
    inlier_mask: np.ndarray               # boolean array, same length as input matches
    model_type: str


def estimate_affine(pts_src: np.ndarray, pts_ref: np.ndarray,
                     ransac_thresh: float = 3.0) -> RegistrationTransform:
    """Best for flat terrain / near-nadir imaging with modest viewpoint difference.

    NOTE: unlike estimate_homography() below, this intentionally does not
    offer a MAGSAC++ option -- cv2.estimateAffinePartial2D() in the OpenCV
    version pinned in requirements.txt (opencv-contrib-python) only supports
    cv2.RANSAC / cv2.LMEDS as its `method` argument; passing cv2.USAC_MAGSAC
    raises "Unknown or unsupported robust estimation method". Plain RANSAC
    is the correct choice here, not a shortcut.
    """
    if len(pts_src) < 3:
        return RegistrationTransform(None, None, np.zeros(len(pts_src), dtype=bool), "affine")

    matrix, inliers = cv2.estimateAffinePartial2D(
        pts_src, pts_ref, method=cv2.RANSAC, ransacReprojThreshold=ransac_thresh
    )
    inlier_mask = inliers.flatten().astype(bool) if inliers is not None else np.zeros(len(pts_src), dtype=bool)
    return RegistrationTransform(matrix, None, inlier_mask, "affine")


def estimate_homography(pts_src: np.ndarray, pts_ref: np.ndarray,
                         ransac_thresh: float = 3.0, use_magsac: bool = True) -> RegistrationTransform:
    """Full projective model — for larger viewpoint/perspective differences than affine handles."""
    if len(pts_src) < 4:
        return RegistrationTransform(None, None, np.zeros(len(pts_src), dtype=bool), "homography")

    method = cv2.USAC_MAGSAC if use_magsac else cv2.RANSAC
    matrix, inliers = cv2.findHomography(pts_src, pts_ref, method=method, ransacReprojThreshold=ransac_thresh)
    inlier_mask = inliers.flatten().astype(bool) if inliers is not None else np.zeros(len(pts_src), dtype=bool)
    return RegistrationTransform(matrix, None, inlier_mask, "homography")


def estimate_thin_plate_spline(pts_src: np.ndarray, pts_ref: np.ndarray,
                                inlier_mask: np.ndarray) -> RegistrationTransform:
    """
    Non-rigid model for complex topography (crater fields, rilles) where a
    single affine/homography can't capture local terrain-induced distortion.
    Requires an already-verified inlier set (typically from a prior
    affine/homography RANSAC pass) as its control points.
    """
    pts_src_in = pts_src[inlier_mask].astype(np.float32)
    pts_ref_in = pts_ref[inlier_mask].astype(np.float32)

    # FIX: duplicate control points (common with SIFT/AKAZE, which can emit
    # multiple keypoints -- different orientations/scales -- at the same
    # pixel location) make OpenCV's TPS solve singular for the affected rows.
    # It doesn't raise an error; applyTransformation() silently returns (0, 0)
    # for those points instead, which was previously blowing up RMSE into the
    # hundreds of pixels. Deduplicating on the source coordinate before
    # fitting removes the singularity.
    _, unique_idx = np.unique(pts_src_in, axis=0, return_index=True)
    unique_idx = np.sort(unique_idx)
    pts_src_in = pts_src_in[unique_idx]
    pts_ref_in = pts_ref_in[unique_idx]

    pts_src_in = pts_src_in.reshape(1, -1, 2)
    pts_ref_in = pts_ref_in.reshape(1, -1, 2)

    if pts_src_in.shape[1] < 4:
        return RegistrationTransform(None, None, inlier_mask, "tps")

    tps = cv2.createThinPlateSplineShapeTransformer()
    matches = [cv2.DMatch(i, i, 0) for i in range(pts_src_in.shape[1])]
    # OpenCV's convention is estimateTransformation(transformingShape,
    # targetShape, matches) -- the fitted spline maps points FROM
    # transformingShape TO targetShape. We want source->reference, matching
    # how affine/homography are used everywhere else in this pipeline.
    tps.estimateTransformation(pts_src_in, pts_ref_in, matches)

    return RegistrationTransform(None, tps, inlier_mask, "tps")


def geometric_verification(pts_src: np.ndarray, pts_ref: np.ndarray,
                            model: str = "affine", ransac_thresh: float = 3.0) -> RegistrationTransform:
    """
    Main entry point for Stage C.1.
    model: "affine" | "homography" | "tps" (tps runs homography first for
           inlier selection, then fits the spline on those inliers).
    """
    if model == "affine":
        return estimate_affine(pts_src, pts_ref, ransac_thresh)
    elif model == "homography":
        return estimate_homography(pts_src, pts_ref, ransac_thresh)
    elif model == "tps":
        coarse = estimate_homography(pts_src, pts_ref, ransac_thresh)
        return estimate_thin_plate_spline(pts_src, pts_ref, coarse.inlier_mask)
    else:
        raise ValueError(f"unknown model: {model}")