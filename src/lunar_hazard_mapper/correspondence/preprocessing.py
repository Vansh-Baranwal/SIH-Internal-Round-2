"""Radiometric normalization, illumination-invariant filtering, and scale pyramid construction."""

import numpy as np
import cv2
from typing import List, Optional, Tuple


def normalize_radiometric(image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Normalize image to [0, 255] uint8 with CLAHE contrast enhancement."""
    if image.dtype != np.uint8:
        lo, hi = np.percentile(image[image > 0], (2, 98)) if image.any() else (image.min(), image.max())
        if hi == lo:
            normalized = np.zeros_like(image, dtype=np.uint8)
        else:
            normalized = np.clip((image - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    else:
        normalized = image.copy()

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    if normalized.ndim == 2:
        return clahe.apply(normalized)
    # Multi-channel: apply per channel
    channels = [clahe.apply(normalized[:, :, c]) for c in range(normalized.shape[2])]
    return np.stack(channels, axis=2)


def illumination_invariant_filter(image: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    """Compute gradient-magnitude (approximate phase-congruency) illumination-invariant image."""
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.astype(np.float32)

    blurred = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigma)
    gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(gx ** 2 + gy ** 2)
    normalized = cv2.normalize(gradient_magnitude, None, 0, 255, cv2.NORM_MINMAX)
    return normalized.astype(np.uint8)


def build_scale_pyramid(
    image: np.ndarray,
    target_gsd_m: float,
    source_gsd_m: float,
    max_levels: int = 4,
) -> Tuple[np.ndarray, float]:
    """
    Downsample image so its effective GSD matches target_gsd_m.
    Returns the resampled image and the actual scale factor applied.
    """
    if source_gsd_m <= 0 or target_gsd_m <= 0:
        return image, 1.0

    scale = source_gsd_m / target_gsd_m
    if scale >= 1.0:
        # Source is coarser than target — upsample or no change needed
        return image, 1.0

    # Iterative half-level pyramid downsampling
    current = image.copy()
    applied_scale = 1.0
    level = 0
    while applied_scale * 2.0 <= (1.0 / scale) and level < max_levels:
        current = cv2.pyrDown(current)
        applied_scale *= 2.0
        level += 1

    # Final resize to exact target scale
    exact_scale = source_gsd_m / target_gsd_m
    final_w = max(1, int(image.shape[1] * exact_scale))
    final_h = max(1, int(image.shape[0] * exact_scale))
    resampled = cv2.resize(image, (final_w, final_h), interpolation=cv2.INTER_AREA)
    return resampled, exact_scale
