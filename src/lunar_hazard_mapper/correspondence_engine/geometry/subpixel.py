"""
Stage C.2: Sub-Pixel Refinement.

RANSAC-verified matches are typically only accurate to whole pixels (limited
by the feature detector's inherent localization precision). To hit the PS's
required sub-pixel accuracy (target <1.0 pixel RMSE per your roadmap doc),
refine each inlier match locally using phase correlation (robust, good default)
or iterative Lucas-Kanade optical flow (good for cases where phase correlation's
assumption of pure translation within the patch breaks down).
"""
from __future__ import annotations
import numpy as np
import cv2


def refine_subpixel_phase_correlation(source: np.ndarray, reference: np.ndarray,
                                       pts_src: np.ndarray, pts_ref: np.ndarray,
                                       patch_size: int = 32, max_shift_px: float = 2.0) -> np.ndarray:
    """
    For each match, extract a small patch around the reference point and the
    corresponding source point, then use phase correlation to find the
    sub-pixel shift needed to align them precisely. Returns refined pts_ref
    (the reference points are usually kept fixed; source points' correspondence
    is refined in sub-pixel space relative to them — adjust to your convention).

    max_shift_px: sanity bound on the accepted correction. cv2.phaseCorrelate
    can return large, spurious shifts when a patch lacks reliable texture
    (measured a real ~21px "correction" on low-texture synthetic crater floor
    patches during testing). Since this function REFINES an already-verified
    match by a small amount, any shift larger than this bound is almost
    certainly a correlation failure, not a real correction, and is rejected
    in favor of keeping the original point. Without this bound, 1-2 outlier
    points can dominate downstream RMSE via squaring, making "refined" output
    measurably LESS accurate than unrefined input.
    """
    refined_pts_ref = pts_ref.copy().astype(np.float64)
    half = patch_size // 2
    h, w = reference.shape[:2]

    for i, (ps, pr) in enumerate(zip(pts_src, pts_ref)):
        x_r, y_r = int(pr[0]), int(pr[1])
        x_s, y_s = int(ps[0]), int(ps[1])

        if not (half <= x_r < w - half and half <= y_r < reference.shape[0] - half):
            continue
        if not (half <= x_s < source.shape[1] - half and half <= y_s < source.shape[0] - half):
            continue

        patch_ref = reference[y_r - half:y_r + half, x_r - half:x_r + half].astype(np.float32)
        patch_src = source[y_s - half:y_s + half, x_s - half:x_s + half].astype(np.float32)

        if patch_ref.shape != patch_src.shape:
            continue

        try:
            shift, _response = cv2.phaseCorrelate(patch_src, patch_ref)
            shift_mag = (shift[0] ** 2 + shift[1] ** 2) ** 0.5
            if shift_mag > max_shift_px:
                continue  # reject implausible correction, keep original point
            refined_pts_ref[i, 0] += shift[0]
            refined_pts_ref[i, 1] += shift[1]
        except cv2.error:
            continue  # keep original if correlation fails (e.g. flat/textureless patch)

    return refined_pts_ref


def refine_subpixel_lucas_kanade(source: np.ndarray, reference: np.ndarray,
                                  pts_src: np.ndarray, pts_ref: np.ndarray,
                                  win_size: tuple[int, int] = (15, 15)) -> tuple[np.ndarray, np.ndarray]:
    """
    Alternative refinement using OpenCV's Lucas-Kanade optical flow — tracks
    each source point directly into the reference image with sub-pixel
    precision. Better when the local patch has some rotation/scale residual
    (not just pure translation) after RANSAC's global transform, since LK
    can handle small local deformations phase correlation assumes away.
    Returns (refined_pts_ref, status) where status marks which points tracked
    successfully.
    """
    pts_src_f32 = pts_src.astype(np.float32).reshape(-1, 1, 2)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    next_pts, status, _err = cv2.calcOpticalFlowPyrLK(
        source, reference, pts_src_f32, None, winSize=win_size,
        maxLevel=2, criteria=criteria
    )

    return next_pts.reshape(-1, 2), status.flatten().astype(bool)
