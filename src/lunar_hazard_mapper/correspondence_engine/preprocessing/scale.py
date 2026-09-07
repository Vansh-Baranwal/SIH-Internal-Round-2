"""
Stage A.3: Scale Handling.

OHRC (~0.25-0.3 m/pixel) and TMC (5 m/pixel) differ in ground sample distance
by roughly 15-20x. Feature matchers work far better when both images are
brought to a similar apparent scale BEFORE extraction, rather than expecting
the matcher to handle a huge scale gap on its own. Downsample the
higher-resolution image using a Gaussian pyramid (proper anti-aliased
downsampling, not naive decimation which introduces aliasing artifacts that
hurt feature detection).
"""
from __future__ import annotations
import numpy as np
import cv2


def estimate_scale_ratio(source_gsd_m: float, reference_gsd_m: float) -> float:
    """e.g. OHRC=0.3m, TMC=5m -> ratio ~16.7, meaning OHRC should be
    downsampled by that factor to roughly match TMC's apparent scale."""
    return reference_gsd_m / source_gsd_m


def gaussian_pyramid_downsample(image: np.ndarray, target_scale_ratio: float) -> tuple[np.ndarray, float]:
    """
    Downsamples `image` by successive Gaussian pyramid levels (each halves
    resolution with proper blur-before-decimate anti-aliasing) until it's
    close to `target_scale_ratio`. Returns (downsampled_image, actual_ratio_achieved)
    since pyramid levels are powers of 2 and won't hit the target exactly.
    """
    current = image.copy()
    achieved_ratio = 1.0
    while achieved_ratio * 2 <= target_scale_ratio:
        current = cv2.pyrDown(current)
        achieved_ratio *= 2
    return current, achieved_ratio


def match_scale(source: np.ndarray, reference: np.ndarray,
                 source_gsd_m: float, reference_gsd_m: float) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Full Stage A.3: determine which image is higher resolution, downsample it
    toward the other's GSD. Returns (adjusted_source, reference, scale_factor_applied)
    — scale_factor_applied is needed later to rescale matched keypoint
    coordinates back to the ORIGINAL full-resolution image for final output.
    """
    if source_gsd_m < reference_gsd_m:
        ratio = estimate_scale_ratio(source_gsd_m, reference_gsd_m)
        adjusted_source, achieved = gaussian_pyramid_downsample(source, ratio)
        return adjusted_source, reference, achieved
    elif reference_gsd_m < source_gsd_m:
        ratio = estimate_scale_ratio(reference_gsd_m, source_gsd_m)
        adjusted_reference, achieved = gaussian_pyramid_downsample(reference, ratio)
        return source, adjusted_reference, 1.0 / achieved
    else:
        return source, reference, 1.0
