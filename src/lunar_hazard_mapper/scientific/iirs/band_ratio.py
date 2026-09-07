"""Deterministic band-ratio computation on preprocessed IIRS data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from .preprocessing import IIRSSpectralPreprocessingResult
from .types import IIRSCube


@dataclass(frozen=True, eq=False)
class IIRSBandRatioResult:
    """A single numerical band-ratio map on the IIRS spatial grid."""

    ratio_map: np.ndarray
    valid_mask: np.ndarray
    numerator_band: int
    denominator_band: int
    numerator_wavelength_um: float
    denominator_wavelength_um: float
    normalization_method: str

    def __post_init__(self) -> None:
        ratio_map = np.asarray(self.ratio_map)
        valid_mask = np.asarray(self.valid_mask)
        if ratio_map.ndim != 2:
            raise ValueError("ratio_map must be a two-dimensional spatial array.")
        if valid_mask.shape != ratio_map.shape or valid_mask.dtype != bool:
            raise ValueError("valid_mask must be a boolean array matching ratio_map shape.")
        if not np.issubdtype(ratio_map.dtype, np.number):
            raise TypeError("ratio_map must contain numeric values.")
        if not np.isfinite(ratio_map[valid_mask]).all():
            raise ValueError("valid ratio_map values must be finite.")
        if not np.isnan(ratio_map[~valid_mask]).all():
            raise ValueError("invalid ratio_map values must be NaN.")
        for name, value in (
            ("numerator_band", self.numerator_band),
            ("denominator_band", self.denominator_band),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        for name, value in (
            ("numerator_wavelength_um", self.numerator_wavelength_um),
            ("denominator_wavelength_um", self.denominator_wavelength_um),
        ):
            if not isinstance(value, (int, float, np.number)) or not np.isfinite(float(value)):
                raise ValueError(f"{name} must be a finite numeric value.")
        if not isinstance(self.normalization_method, str) or not self.normalization_method:
            raise ValueError("normalization_method must be a non-empty string.")

        object.__setattr__(self, "ratio_map", ratio_map)
        object.__setattr__(self, "valid_mask", valid_mask)
        object.__setattr__(self, "numerator_band", int(self.numerator_band))
        object.__setattr__(self, "denominator_band", int(self.denominator_band))
        object.__setattr__(self, "numerator_wavelength_um", float(self.numerator_wavelength_um))
        object.__setattr__(self, "denominator_wavelength_um", float(self.denominator_wavelength_um))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this ratio result deterministically using Python lists."""
        return {
            "ratio_map": self.ratio_map.tolist(),
            "valid_mask": self.valid_mask.tolist(),
            "numerator_band": self.numerator_band,
            "denominator_band": self.denominator_band,
            "numerator_wavelength_um": self.numerator_wavelength_um,
            "denominator_wavelength_um": self.denominator_wavelength_um,
            "normalization_method": self.normalization_method,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSBandRatioResult):
            return NotImplemented
        return (
            np.array_equal(self.ratio_map, other.ratio_map, equal_nan=True)
            and np.array_equal(self.valid_mask, other.valid_mask)
            and self.numerator_band == other.numerator_band
            and self.denominator_band == other.denominator_band
            and self.numerator_wavelength_um == other.numerator_wavelength_um
            and self.denominator_wavelength_um == other.denominator_wavelength_um
            and self.normalization_method == other.normalization_method
        )


def compute_iirs_band_ratio(
    cube: IIRSCube,
    preprocessed: IIRSSpectralPreprocessingResult,
    numerator_band: int,
    denominator_band: int,
) -> IIRSBandRatioResult:
    """Compute one ratio map from two normalized IIRS bands.

    The function consumes the established M4-08.3 normalized data and quality
    mask.  A ratio pixel is valid only when both selected samples are valid,
    finite, the denominator is exactly non-zero, and the resulting division is
    finite.  Invalid pixels are represented by ``NaN`` and ``False`` in the
    output mask.  No epsilon or material-specific threshold is used.
    """
    if not isinstance(cube, IIRSCube):
        raise TypeError("cube must be an IIRSCube instance.")
    if not isinstance(preprocessed, IIRSSpectralPreprocessingResult):
        raise TypeError("preprocessed must be an IIRSSpectralPreprocessingResult instance.")

    data = np.asarray(preprocessed.normalized_data)
    quality_mask = np.asarray(preprocessed.valid_mask)
    if data.ndim != 3 or data.shape != cube.data.shape:
        raise ValueError("preprocessed normalized_data must match the IIRSCube shape.")
    if quality_mask.shape != data.shape or quality_mask.dtype != bool:
        raise ValueError("preprocessed valid_mask must be boolean and match normalized_data shape.")

    wavelengths = np.asarray(cube.wavelengths_um)
    band_count = data.shape[2]
    if wavelengths.ndim != 1 or wavelengths.shape[0] != band_count:
        raise ValueError("IIRSCube wavelengths_um must match the preprocessed band count.")
    _validate_band_index("numerator_band", numerator_band, band_count)
    _validate_band_index("denominator_band", denominator_band, band_count)

    numerator = data[:, :, numerator_band]
    denominator = data[:, :, denominator_band]
    valid_mask = (
        quality_mask[:, :, numerator_band]
        & quality_mask[:, :, denominator_band]
        & np.isfinite(numerator)
        & np.isfinite(denominator)
        & (denominator != 0.0)
    )

    ratio_map = np.full(numerator.shape, np.nan, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        calculated = numerator[valid_mask] / denominator[valid_mask]
    finite_results = np.isfinite(calculated)
    if not finite_results.all():
        spatial_indices = np.flatnonzero(valid_mask)
        valid_mask = valid_mask.copy()
        valid_mask.flat[spatial_indices[~finite_results]] = False
        calculated = calculated[finite_results]
        spatial_indices = spatial_indices[finite_results]
        ratio_map.flat[spatial_indices] = calculated
    else:
        ratio_map[valid_mask] = calculated

    return IIRSBandRatioResult(
        ratio_map=ratio_map,
        valid_mask=valid_mask,
        numerator_band=numerator_band,
        denominator_band=denominator_band,
        numerator_wavelength_um=wavelengths[numerator_band],
        denominator_wavelength_um=wavelengths[denominator_band],
        normalization_method=preprocessed.normalization_method,
    )


def _validate_band_index(name: str, index: object, band_count: int) -> None:
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
        raise TypeError(f"{name} must be an integer band index.")
    if not 0 <= int(index) < band_count:
        raise ValueError(f"{name} must be in [0, {band_count}).")
