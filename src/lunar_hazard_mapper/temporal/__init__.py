"""Temporal change detection: sub-pixel differencing between aligned multi-temporal image pairs."""

from __future__ import annotations

import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ChangeDetectionResult:
    diff_map: np.ndarray          # uint8 [0, 255] absolute difference
    change_mask: np.ndarray       # bool — pixels where |diff| > threshold
    change_fraction: float        # 0–1 fraction of pixels changed
    mean_diff: float
    max_diff: float
    heatmap_b64: Optional[str] = None


def detect_changes(
    image_before: np.ndarray,
    image_after: np.ndarray,
    threshold: float = 15.0,
    blur_sigma: float = 2.0,
    include_heatmap: bool = False,
) -> ChangeDetectionResult:
    """
    Sub-pixel change detection between two aligned images.
    Both images should be pre-registered (output of CorrespondenceEngine).
    """
    g1 = _to_gray_f32(image_before)
    g2 = _to_gray_f32(image_after)

    # Resize to same shape if needed
    if g1.shape != g2.shape:
        g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]), interpolation=cv2.INTER_LINEAR)

    # Gaussian blur to reduce noise
    if blur_sigma > 0:
        g1 = cv2.GaussianBlur(g1, (0, 0), blur_sigma)
        g2 = cv2.GaussianBlur(g2, (0, 0), blur_sigma)

    diff = np.abs(g1 - g2)
    diff_u8 = np.clip(diff, 0, 255).astype(np.uint8)
    change_mask = diff > threshold
    change_fraction = float(change_mask.sum()) / max(1, change_mask.size)
    mean_diff = float(diff.mean())
    max_diff = float(diff.max())

    heatmap_b64 = None
    if include_heatmap:
        heatmap_b64 = _make_heatmap_b64(diff_u8)

    return ChangeDetectionResult(
        diff_map=diff_u8,
        change_mask=change_mask,
        change_fraction=change_fraction,
        mean_diff=mean_diff,
        max_diff=max_diff,
        heatmap_b64=heatmap_b64,
    )


def _to_gray_f32(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return img.astype(np.float32)


def _make_heatmap_b64(diff_u8: np.ndarray) -> str:
    import base64
    colormap = cv2.applyColorMap(diff_u8, cv2.COLORMAP_JET)
    _, buf = cv2.imencode(".png", colormap)
    return base64.b64encode(buf.tobytes()).decode()


def temporal_stack_diff(
    images: list,
    reference_idx: int = 0,
    threshold: float = 15.0,
) -> list:
    """Compute change detection from a reference image to all others in the stack."""
    ref = images[reference_idx]
    results = []
    for i, img in enumerate(images):
        if i == reference_idx:
            results.append(None)
        else:
            results.append(detect_changes(ref, img, threshold=threshold))
    return results
