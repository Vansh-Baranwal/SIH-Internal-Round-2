"""Deterministic, read-only preprocessing for IIRS cubes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .types import IIRSCube
from .validation import IIRSInputValidationResult, validate_iirs_cube


@dataclass(frozen=True, eq=False)
class IIRSSpectralPreprocessingResult:
    """Normalized cube values and their data-quality mask.

    ``normalized_data`` is an independent float64 copy.  Valid finite samples
    are normalized; invalid samples retain their source values and are always
    marked ``False`` in ``valid_mask``.  Consumers must use the mask whenever
    operating on the normalized data.
    """

    normalized_data: np.ndarray
    valid_mask: np.ndarray
    normalization_min: Optional[float]
    normalization_max: Optional[float]
    input_validation: IIRSInputValidationResult
    normalization_method: str = "global_minmax"

    @property
    def is_valid(self) -> bool:
        """Whether the input passed the existing IIRS input validator."""
        return self.input_validation.is_valid

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the preprocessing output without retaining the source cube."""
        return {
            "normalized_data": self.normalized_data.tolist(),
            "valid_mask": self.valid_mask.astype(bool).tolist(),
            "normalization_min": self.normalization_min,
            "normalization_max": self.normalization_max,
            "normalization_method": self.normalization_method,
            "input_validation": self.input_validation.to_dict(),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSSpectralPreprocessingResult):
            return NotImplemented
        return (
            np.array_equal(self.normalized_data, other.normalized_data, equal_nan=True)
            and np.array_equal(self.valid_mask, other.valid_mask)
            and self.normalization_min == other.normalization_min
            and self.normalization_max == other.normalization_max
            and self.input_validation == other.input_validation
            and self.normalization_method == other.normalization_method
        )


def preprocess_iirs_cube(cube: IIRSCube) -> IIRSSpectralPreprocessingResult:
    """Normalize valid IIRS samples while preserving the original cube.

    The established IIRS input validator is always run first.  Structurally
    unusable inputs fail clearly.  A structurally intact cube with NaN or
    infinity values can still yield an invalid result with an accurate quality
    mask, allowing callers to inspect the issue without those values entering
    normalization statistics.

    The selected method is global min--max normalization across all finite
    non-nodata values in the cube.  A zero range deterministically maps valid
    values to ``0.0``.  No wavelengths or spatial/source metadata are changed.
    """
    if not isinstance(cube, IIRSCube):
        raise TypeError("cube must be an IIRSCube instance.")

    validation = validate_iirs_cube(cube)
    data = np.asarray(cube.data)
    if data.ndim != 3 or not _is_real_numeric_array(data):
        raise ValueError("IIRSCube data is structurally unsuitable for preprocessing.")
    if not _valid_nodata(cube.nodata):
        raise ValueError("IIRSCube nodata semantics are unsuitable for preprocessing.")

    # A distinct float64 copy guarantees preprocessing and later source-array
    # mutations cannot affect one another.
    normalized_data = np.array(data, dtype=np.float64, copy=True)
    valid_mask = np.asarray(cube.valid_mask, dtype=bool).copy() & np.isfinite(normalized_data)

    if np.any(valid_mask):
        valid_values = normalized_data[valid_mask]
        normalization_min = float(np.min(valid_values))
        normalization_max = float(np.max(valid_values))
        value_range = normalization_max - normalization_min
        if value_range == 0.0:
            normalized_data[valid_mask] = 0.0
        else:
            normalized_data[valid_mask] = (
                normalized_data[valid_mask] - normalization_min
            ) / value_range
    else:
        normalization_min = None
        normalization_max = None

    return IIRSSpectralPreprocessingResult(
        normalized_data=normalized_data,
        valid_mask=valid_mask,
        normalization_min=normalization_min,
        normalization_max=normalization_max,
        input_validation=validation,
    )


def _is_real_numeric_array(values: np.ndarray) -> bool:
    return bool(
        np.issubdtype(values.dtype, np.number)
        and not np.issubdtype(values.dtype, np.complexfloating)
        and not np.issubdtype(values.dtype, np.bool_)
    )


def _valid_nodata(nodata: object) -> bool:
    if nodata is None:
        return True
    if isinstance(nodata, bool) or not isinstance(nodata, (int, float, np.number)):
        return False
    return not bool(np.isinf(float(nodata)))
