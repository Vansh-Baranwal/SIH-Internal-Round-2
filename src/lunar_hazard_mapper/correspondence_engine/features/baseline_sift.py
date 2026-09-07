"""
Stage B (Baseline): SIFT/AKAZE handcrafted feature matching.

Per your own evaluation strategy doc: "the existing SIFT/RANSAC implementation
will be treated as the baseline." This module is that baseline — always
available (ships with opencv-contrib-python, no downloads needed), used both
as a standalone fallback matcher and as the reference point for benchmarking
the deep-learning matchers against.
"""
from __future__ import annotations
import numpy as np
import cv2
from dataclasses import dataclass


@dataclass
class MatchResult:
    keypoints_source: np.ndarray   # Nx2 (x, y) in source image
    keypoints_reference: np.ndarray  # Nx2 (x, y) in reference image
    match_confidences: np.ndarray  # N, similarity/distance-based confidence
    backend: str


def match_sift(source: np.ndarray, reference: np.ndarray, ratio_thresh: float = 0.75) -> MatchResult:
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(source, None)
    kp2, des2 = sift.detectAndCompute(reference, None)

    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return MatchResult(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0), "sift")

    bf = cv2.BFMatcher()
    raw_matches = bf.knnMatch(des1, des2, k=2)

    good_matches = []
    for pair in raw_matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < ratio_thresh * n.distance:
                good_matches.append(m)

    pts_src = np.array([kp1[m.queryIdx].pt for m in good_matches])
    pts_ref = np.array([kp2[m.trainIdx].pt for m in good_matches])
    confidences = np.array([1.0 / (1.0 + m.distance) for m in good_matches])

    return MatchResult(pts_src, pts_ref, confidences, "sift")


def match_akaze(source: np.ndarray, reference: np.ndarray, ratio_thresh: float = 0.8) -> MatchResult:
    """AKAZE — faster than SIFT, better boundary preservation, secondary
    baseline per the algorithm comparison table in your planning doc."""
    if hasattr(cv2, "AKAZE_create"):
        akaze = cv2.AKAZE_create()  # OpenCV 4.x
    else:
        akaze = cv2.xfeatures2d.AKAZE_create()  # OpenCV 5.x — AKAZE moved to xfeatures2d
    kp1, des1 = akaze.detectAndCompute(source, None)
    kp2, des2 = akaze.detectAndCompute(reference, None)

    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return MatchResult(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0), "akaze")

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = bf.knnMatch(des1, des2, k=2)

    good_matches = []
    for pair in raw_matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < ratio_thresh * n.distance:
                good_matches.append(m)

    pts_src = np.array([kp1[m.queryIdx].pt for m in good_matches])
    pts_ref = np.array([kp2[m.trainIdx].pt for m in good_matches])
    confidences = np.array([1.0 / (1.0 + m.distance) for m in good_matches])

    return MatchResult(pts_src, pts_ref, confidences, "akaze")
