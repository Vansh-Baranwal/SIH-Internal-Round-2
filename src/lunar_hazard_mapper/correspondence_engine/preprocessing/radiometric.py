"""
Stage A.1: Radiometric Calibration.

Different sensors (TMC panchromatic, OHRC panchromatic, IIRS hyperspectral)
have different intensity/brightness distributions even when imaging the same
material, due to different sensor gain, dynamic range, and calibration.
Normalize both images to a common intensity distribution BEFORE feature
matching, so descriptors aren't thrown off by sensor-specific brightness bias.
"""
from __future__ import annotations
import numpy as np
import cv2


def normalize_histogram(image: np.ndarray) -> np.ndarray:
    """CLAHE (adaptive histogram equalization) — better than global equalization
    for lunar imagery since it preserves local contrast in both bright (sunlit)
    and dark (shadowed) regions simultaneously, common in the same lunar scene."""
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image)


def match_histograms(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Match source image's intensity distribution to the reference image's
    distribution. Useful when source/reference come from genuinely different
    sensors (e.g. TMC vs OHRC) and you want them on a comparable brightness
    scale before descriptor extraction.
    """
    from skimage.exposure import match_histograms as skimage_match
    matched = skimage_match(source, reference, channel_axis=None)
    return cv2.normalize(matched, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def radiometric_pipeline(source: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Full Stage A.1: apply CLAHE to both, then histogram-match source to reference."""
    src_eq = normalize_histogram(source)
    ref_eq = normalize_histogram(reference)
    src_matched = match_histograms(src_eq, ref_eq)
    return src_matched, ref_eq
