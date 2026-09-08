"""
Stage A.2: Illumination Handling.

If simple histogram normalization isn't enough (e.g. severe sun-angle
differences causing completely different shadow patterns between source and
reference), apply an illumination-invariant transform. Phase congruency
detects structural features (edges, corners, ridges) based on the PHASE of
frequency components rather than raw intensity/gradient magnitude — this
makes it far more stable across illumination changes than plain gradients,
since a crater rim's phase signature stays similar whether it's brightly lit
or in partial shadow, even though its raw brightness changes completely.
"""
from __future__ import annotations
import numpy as np
import cv2


def directional_gradient_illumination_invariant(image: np.ndarray) -> np.ndarray:
    """
    Lightweight illumination-invariant feature map using multi-orientation
    gradient energy (a simplified stand-in for full phase congruency, much
    faster to compute, still substantially more illumination-robust than raw
    pixel intensity or a single Sobel gradient).
    """
    img_f = image.astype(np.float32) / 255.0
    orientations = [0, 45, 90, 135]
    energy_maps = []
    for angle in orientations:
        kernel = cv2.getGaborKernel((15, 15), sigma=4.0, theta=np.radians(angle),
                                     lambd=10.0, gamma=0.5, psi=0)
        filtered = cv2.filter2D(img_f, cv2.CV_32F, kernel)
        energy_maps.append(np.abs(filtered))
    energy = np.mean(energy_maps, axis=0)
    return cv2.normalize(energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def phase_congruency_map(image: np.ndarray) -> np.ndarray:
    """
    Full phase-congruency-style edge map using the `phasepack` library if
    available; falls back to the lightweight Gabor-energy approximation above
    if the library isn't installed, so the pipeline never hard-fails here.
    """
    try:
        from phasepack import phasecong
        img_f = image.astype(np.float64) / 255.0
        result = phasecong(img_f, nscale=4, norient=4)
        pc = result[0]  # phase congruency map
        return cv2.normalize(pc, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    except ImportError:
        return directional_gradient_illumination_invariant(image)


def simulate_sun_angle_filter(image: np.ndarray, azimuth: float) -> np.ndarray:
    """
    Simulates highlighting edges perpendicular to the sun azimuth angle
    to synthetically normalize shadows, preventing SIFT from hallucinating
    false positives across different times of day.
    """
    img_f = image.astype(np.float32) / 255.0
    
    # Gabor filter aligned with the sun azimuth
    kernel = cv2.getGaborKernel((21, 21), sigma=5.0, theta=np.radians(azimuth),
                                 lambd=10.0, gamma=0.5, psi=0)
    filtered = cv2.filter2D(img_f, cv2.CV_32F, kernel)
    energy = np.abs(filtered)
    
    return cv2.normalize(energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
