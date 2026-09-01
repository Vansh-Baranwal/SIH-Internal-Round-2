"""Spectral intelligence: IIRS hyperspectral overlay and LUPEX water-ice confidence."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple


@dataclass
class SpectralBand:
    name: str
    wavelength_nm: float
    data: np.ndarray   # 2D float32 array (H, W)


@dataclass
class IceConfidenceMap:
    """Multi-sensor water-ice confidence, combining temperature, radar CPR, and OH reflectance."""
    temperature_score: np.ndarray   # normalised 0–1 (lower temp → higher score)
    cpr_score: np.ndarray           # Circular Polarization Ratio from radar
    reflectance_score: np.ndarray   # LOLA 1064-nm reflectance anomaly
    combined: np.ndarray            # weighted fusion


def register_iirs_to_optical(
    iirs_band: np.ndarray,
    optical: np.ndarray,
    iirs_gsd_m: float = 80.0,
    optical_gsd_m: float = 5.0,
) -> np.ndarray:
    """
    Upsample an IIRS spectral band to match the spatial resolution of an optical image.
    Uses bicubic interpolation — registration pre-registered externally via CorrespondenceEngine.
    """
    import cv2
    h, w = optical.shape[:2]
    resampled = cv2.resize(
        iirs_band.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC
    )
    # Normalise to [0, 1]
    lo, hi = resampled.min(), resampled.max()
    if hi > lo:
        resampled = (resampled - lo) / (hi - lo)
    return resampled


def compute_ice_confidence(
    temperature_k: np.ndarray,
    cpr: np.ndarray,
    oh_reflectance: np.ndarray,
    weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
) -> IceConfidenceMap:
    """
    Fuse multi-sensor ice indicators into a single confidence map.
    temperature_k: brightness temperature in Kelvin (lower = more likely ice)
    cpr: Circular Polarization Ratio from SAR (>1 indicates ice-like scattering)
    oh_reflectance: OH-band reflectance anomaly (LOLA/LAMP)
    """
    # Temperature: normalise so low temp → high confidence
    t_norm = np.clip(temperature_k, 40.0, 250.0)
    t_score = 1.0 - (t_norm - 40.0) / 210.0

    # CPR: normalise, clip at 2
    cpr_score = np.clip(cpr / 2.0, 0.0, 1.0)

    # OH reflectance: already 0–1 anomaly
    refl_score = np.clip(oh_reflectance, 0.0, 1.0)

    w_t, w_c, w_r = weights
    combined = w_t * t_score + w_c * cpr_score + w_r * refl_score
    combined = np.clip(combined, 0.0, 1.0)

    return IceConfidenceMap(
        temperature_score=t_score.astype(np.float32),
        cpr_score=cpr_score.astype(np.float32),
        reflectance_score=refl_score.astype(np.float32),
        combined=combined.astype(np.float32),
    )


def overlay_iirs_bands(
    bands: List[SpectralBand],
    reference_shape: Tuple[int, int],
    selected_wavelengths: Optional[List[float]] = None,
) -> Dict[str, np.ndarray]:
    """Return a dict of resampled band arrays keyed by band name, optionally filtered."""
    import cv2
    result = {}
    for band in bands:
        if selected_wavelengths and band.wavelength_nm not in selected_wavelengths:
            continue
        h, w = reference_shape
        resampled = cv2.resize(band.data.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
        lo, hi = resampled.min(), resampled.max()
        result[band.name] = ((resampled - lo) / max(hi - lo, 1e-6)).astype(np.float32)
    return result
