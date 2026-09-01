"""Feature extractors and matchers: SIFT, ORB, AKAZE baselines plus DL fallback stubs."""

from __future__ import annotations

import numpy as np
import cv2
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class MatchResult:
    src_pts: np.ndarray          # (N, 2) float32 — keypoints in source image
    dst_pts: np.ndarray          # (N, 2) float32 — keypoints in destination image
    scores: np.ndarray           # (N,) float32 — match confidence scores
    method: str = "unknown"
    raw_match_count: int = 0


def _ensure_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


class SIFTMatcher:
    """SIFT keypoint detector + FLANN ratio-test matcher."""

    def __init__(self, n_features: int = 2000, ratio_thresh: float = 0.75):
        self.ratio_thresh = ratio_thresh
        self.sift = cv2.SIFT_create(nfeatures=n_features)
        FLANN_INDEX_KDTREE = 1
        index_params = {"algorithm": FLANN_INDEX_KDTREE, "trees": 5}
        search_params = {"checks": 50}
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)

    def match(self, src: np.ndarray, dst: np.ndarray) -> MatchResult:
        gray_src = _ensure_gray(src)
        gray_dst = _ensure_gray(dst)
        kp1, des1 = self.sift.detectAndCompute(gray_src, None)
        kp2, des2 = self.sift.detectAndCompute(gray_dst, None)

        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="SIFT")

        raw_matches = self.flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < self.ratio_thresh * n.distance]

        if not good:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="SIFT", raw_match_count=len(raw_matches))

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good])
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good])
        scores = np.float32([1.0 - m.distance / 512.0 for m in good])
        return MatchResult(src_pts, dst_pts, scores, method="SIFT", raw_match_count=len(raw_matches))


class ORBMatcher:
    """ORB detector + BFMatcher with Hamming distance."""

    def __init__(self, n_features: int = 2000, ratio_thresh: float = 0.75):
        self.ratio_thresh = ratio_thresh
        self.orb = cv2.ORB_create(nfeatures=n_features)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def match(self, src: np.ndarray, dst: np.ndarray) -> MatchResult:
        gray_src = _ensure_gray(src)
        gray_dst = _ensure_gray(dst)
        kp1, des1 = self.orb.detectAndCompute(gray_src, None)
        kp2, des2 = self.orb.detectAndCompute(gray_dst, None)

        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="ORB")

        raw_matches = self.bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < self.ratio_thresh * n.distance]

        if not good:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="ORB", raw_match_count=len(raw_matches))

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good])
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good])
        scores = np.float32([1.0 - m.distance / 256.0 for m in good])
        return MatchResult(src_pts, dst_pts, scores, method="ORB", raw_match_count=len(raw_matches))


class AKAZEMatcher:
    """AKAZE detector + BFMatcher (scale/rotation invariant, non-linear diffusion)."""

    def __init__(self, ratio_thresh: float = 0.75):
        self.ratio_thresh = ratio_thresh
        self.akaze = cv2.AKAZE_create()
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def match(self, src: np.ndarray, dst: np.ndarray) -> MatchResult:
        gray_src = _ensure_gray(src)
        gray_dst = _ensure_gray(dst)
        kp1, des1 = self.akaze.detectAndCompute(gray_src, None)
        kp2, des2 = self.akaze.detectAndCompute(gray_dst, None)

        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="AKAZE")

        raw_matches = self.bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < self.ratio_thresh * n.distance]

        if not good:
            return MatchResult(np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32),
                               np.zeros(0, np.float32), method="AKAZE", raw_match_count=len(raw_matches))

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good])
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good])
        scores = np.float32([1.0 - m.distance / 512.0 for m in good])
        return MatchResult(src_pts, dst_pts, scores, method="AKAZE", raw_match_count=len(raw_matches))


class DLMatcher:
    """
    Stub for SuperPoint+LightGlue / LoFTR deep-learning matchers.
    Falls back to SIFT when DL libraries are unavailable.
    """

    def __init__(self, model: str = "superpoint+lightglue", device: str = "cpu"):
        self.model = model
        self.device = device
        self._fallback = SIFTMatcher(n_features=4000, ratio_thresh=0.8)
        self._dl_available = self._check_dl_available()

    def _check_dl_available(self) -> bool:
        try:
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def match(self, src: np.ndarray, dst: np.ndarray) -> MatchResult:
        # Try loading kornia or lightglue if available
        if self._dl_available:
            try:
                return self._match_superpoint(src, dst)
            except Exception:
                pass
        result = self._fallback.match(src, dst)
        result.method = f"{self.model}(SIFT-fallback)"
        return result

    def _match_superpoint(self, src: np.ndarray, dst: np.ndarray) -> MatchResult:
        # Attempt kornia-based matching when available
        import torch
        try:
            from kornia.feature import LoFTR as KorniaLoFTR
            matcher = KorniaLoFTR(pretrained="outdoor")
            matcher.eval()

            def to_tensor(img):
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
                return torch.tensor(g / 255.0, dtype=torch.float32)[None, None]

            with torch.inference_mode():
                result = matcher({"image0": to_tensor(src), "image1": to_tensor(dst)})

            m_kpts0 = result["keypoints0"].squeeze().cpu().numpy()
            m_kpts1 = result["keypoints1"].squeeze().cpu().numpy()
            conf = result["confidence"].squeeze().cpu().numpy()
            return MatchResult(m_kpts0, m_kpts1, conf, method="LoFTR(kornia)", raw_match_count=len(m_kpts0))
        except Exception:
            raise


MATCHER_REGISTRY = {
    "sift": SIFTMatcher,
    "orb": ORBMatcher,
    "akaze": AKAZEMatcher,
    "superpoint+lightglue": lambda: DLMatcher(model="superpoint+lightglue"),
    "loftr": lambda: DLMatcher(model="loftr"),
}


def match_images(src: np.ndarray, dst: np.ndarray, algorithm: str = "sift") -> MatchResult:
    """Convenience wrapper: select algorithm by name and run matching."""
    algo = algorithm.lower()
    if algo not in MATCHER_REGISTRY:
        raise ValueError(f"Unknown algorithm '{algorithm}'. Available: {list(MATCHER_REGISTRY)}")
    factory = MATCHER_REGISTRY[algo]
    matcher = factory() if callable(factory) else factory
    return matcher.match(src, dst)
