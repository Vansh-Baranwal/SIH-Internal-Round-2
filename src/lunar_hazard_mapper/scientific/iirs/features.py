"""Neutral numerical feature extraction from existing IIRS ratio results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

import numpy as np

from .band_ratio import IIRSBandRatioResult
from .preprocessing import IIRSSpectralPreprocessingResult


@dataclass(frozen=True, eq=False)
class IIRSSpectralFeatureSet:
    """Spatial numerical features derived directly from existing ratio maps.

    The final axis of ``feature_maps`` and ``valid_mask`` is the feature axis.
    Each feature preserves the exact spatial grid and mask of its source
    :class:`IIRSBandRatioResult`; no ratio is recalculated here.
    """

    feature_maps: np.ndarray
    valid_mask: np.ndarray
    feature_names: Tuple[str, ...]
    ratio_bands: Tuple[Tuple[int, int], ...]
    ratio_wavelengths_um: Tuple[Tuple[float, float], ...]
    normalization_methods: Tuple[str, ...]

    def __post_init__(self) -> None:
        feature_maps = np.asarray(self.feature_maps)
        valid_mask = np.asarray(self.valid_mask)
        if feature_maps.ndim != 3 or any(size <= 0 for size in feature_maps.shape):
            raise ValueError("feature_maps must be a non-empty 3D array with shape (height, width, features).")
        if valid_mask.shape != feature_maps.shape or valid_mask.dtype != bool:
            raise ValueError("valid_mask must be boolean and match feature_maps shape.")
        if not np.issubdtype(feature_maps.dtype, np.number):
            raise TypeError("feature_maps must contain numeric values.")
        if not np.isfinite(feature_maps[valid_mask]).all():
            raise ValueError("valid feature values must be finite.")
        if not np.isnan(feature_maps[~valid_mask]).all():
            raise ValueError("invalid feature values must be NaN.")

        feature_count = feature_maps.shape[2]
        if not (
            len(self.feature_names)
            == len(self.ratio_bands)
            == len(self.ratio_wavelengths_um)
            == len(self.normalization_methods)
            == feature_count
        ):
            raise ValueError("feature provenance must contain one entry per feature map.")
        if any(not isinstance(name, str) or not name for name in self.feature_names):
            raise ValueError("feature_names must contain non-empty strings.")

        object.__setattr__(self, "feature_maps", feature_maps)
        object.__setattr__(self, "valid_mask", valid_mask)
        object.__setattr__(self, "feature_names", tuple(self.feature_names))
        object.__setattr__(self, "ratio_bands", tuple(tuple(pair) for pair in self.ratio_bands))
        object.__setattr__(
            self,
            "ratio_wavelengths_um",
            tuple(tuple(float(value) for value in pair) for pair in self.ratio_wavelengths_um),
        )
        object.__setattr__(self, "normalization_methods", tuple(self.normalization_methods))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the feature set deterministically using Python lists."""
        return {
            "feature_maps": self.feature_maps.tolist(),
            "valid_mask": self.valid_mask.tolist(),
            "feature_names": list(self.feature_names),
            "ratio_bands": [list(pair) for pair in self.ratio_bands],
            "ratio_wavelengths_um": [list(pair) for pair in self.ratio_wavelengths_um],
            "normalization_methods": list(self.normalization_methods),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSSpectralFeatureSet):
            return NotImplemented
        return (
            np.array_equal(self.feature_maps, other.feature_maps, equal_nan=True)
            and np.array_equal(self.valid_mask, other.valid_mask)
            and self.feature_names == other.feature_names
            and self.ratio_bands == other.ratio_bands
            and self.ratio_wavelengths_um == other.ratio_wavelengths_um
            and self.normalization_methods == other.normalization_methods
        )


def extract_iirs_spectral_features(
    preprocessed: IIRSSpectralPreprocessingResult,
    ratio_results: Sequence[IIRSBandRatioResult],
) -> IIRSSpectralFeatureSet:
    """Represent existing ratio maps as neutral, spatial numerical features.

    ``preprocessed`` establishes the required IIRS spatial shape.  Each ratio
    result is copied into a feature-map slice in the supplied order, with its
    validity mask and band/wavelength provenance preserved unchanged.  This
    function intentionally does not calculate band ratios or interpret them.
    """
    if not isinstance(preprocessed, IIRSSpectralPreprocessingResult):
        raise TypeError("preprocessed must be an IIRSSpectralPreprocessingResult instance.")
    if not isinstance(ratio_results, Sequence) or isinstance(ratio_results, (str, bytes)):
        raise TypeError("ratio_results must be a sequence of IIRSBandRatioResult instances.")
    if not ratio_results:
        raise ValueError("ratio_results must contain at least one ratio result.")

    spatial_shape = np.asarray(preprocessed.normalized_data).shape[:2]
    if np.asarray(preprocessed.normalized_data).ndim != 3:
        raise ValueError("preprocessed normalized_data must have shape (height, width, bands).")

    feature_maps: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    feature_names: list[str] = []
    ratio_bands: list[Tuple[int, int]] = []
    ratio_wavelengths_um: list[Tuple[float, float]] = []
    normalization_methods: list[str] = []

    for ratio in ratio_results:
        if not isinstance(ratio, IIRSBandRatioResult):
            raise TypeError("ratio_results must contain only IIRSBandRatioResult instances.")
        if ratio.ratio_map.shape != spatial_shape or ratio.valid_mask.shape != spatial_shape:
            raise ValueError("each ratio result must match the preprocessing spatial shape.")

        feature_maps.append(np.array(ratio.ratio_map, dtype=np.float64, copy=True))
        masks.append(np.array(ratio.valid_mask, dtype=bool, copy=True))
        feature_names.append(f"ratio_band_{ratio.numerator_band}_over_band_{ratio.denominator_band}")
        ratio_bands.append((ratio.numerator_band, ratio.denominator_band))
        ratio_wavelengths_um.append(
            (ratio.numerator_wavelength_um, ratio.denominator_wavelength_um)
        )
        normalization_methods.append(ratio.normalization_method)

    return IIRSSpectralFeatureSet(
        feature_maps=np.stack(feature_maps, axis=2),
        valid_mask=np.stack(masks, axis=2),
        feature_names=tuple(feature_names),
        ratio_bands=tuple(ratio_bands),
        ratio_wavelengths_um=tuple(ratio_wavelengths_um),
        normalization_methods=tuple(normalization_methods),
    )
