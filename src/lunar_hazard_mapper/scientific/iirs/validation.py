"""Read-only structural validation for :class:`IIRSCube` inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from typing import Any, Dict, Mapping, Tuple

import numpy as np
from affine import Affine

from .types import IIRSCube


@dataclass(frozen=True)
class IIRSInputValidationResult:
    """Deterministic outcome of a read-only IIRS input validation pass."""

    is_valid: bool
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    checks: Dict[str, bool] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        """Alias for ``is_valid`` for callers that use the shorter term."""
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this validation result in a stable, JSON-friendly form."""
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checks": {key: self.checks[key] for key in sorted(self.checks)},
        }


def validate_iirs_cube(cube: object) -> IIRSInputValidationResult:
    """Inspect an IIRSCube for downstream structural and numeric suitability.

    The function never modifies the supplied object or its arrays.  It only
    reports contract, numeric, spatial, and required-metadata problems; it
    deliberately performs no spectral processing or data repair.
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: Dict[str, bool] = {}

    if not isinstance(cube, IIRSCube):
        checks["cube_type"] = False
        errors.append("cube must be an IIRSCube instance.")
        return _result(errors, warnings, checks)
    checks["cube_type"] = True

    data = _validate_data(cube, errors, checks)
    wavelengths = _validate_wavelengths(cube, data, errors, checks)
    _validate_spatial_metadata(cube, errors, checks)
    _validate_required_metadata(cube, errors, checks)

    if data is not None and wavelengths is not None:
        # This explicitly records that validation observed the established
        # spatial-row-major / spectral-last orientation without transforming it.
        checks["cube_orientation_height_width_bands"] = data.ndim == 3

    return _result(errors, warnings, checks)


def _validate_data(
    cube: IIRSCube,
    errors: list[str],
    checks: Dict[str, bool],
) -> np.ndarray | None:
    try:
        data = np.asarray(cube.data)
    except Exception:
        checks["data_structure"] = False
        errors.append("data must be convertible to a numeric 3D array.")
        return None

    structure_valid = data.ndim == 3 and all(dimension > 0 for dimension in data.shape)
    checks["data_structure"] = structure_valid
    if not structure_valid:
        errors.append("data must be a non-empty 3D array with shape (height, width, bands).")
        return None

    numeric_valid = _is_real_numeric_array(data)
    checks["data_numeric"] = numeric_valid
    if not numeric_valid:
        errors.append("data must contain real numeric values.")
        return None

    nodata_valid, nodata = _validate_nodata(cube.nodata, errors)
    checks["nodata_semantics"] = nodata_valid
    if not nodata_valid:
        checks["data_finite_or_nodata"] = False
        checks["has_usable_samples"] = False
        return data

    valid_mask = _nodata_mask(data, nodata)
    finite_or_nodata = bool(np.all(np.isfinite(data) | ~valid_mask))
    checks["data_finite_or_nodata"] = finite_or_nodata
    if not finite_or_nodata:
        errors.append("data contains NaN or infinite values that are not configured nodata.")

    has_usable_samples = bool(np.any(valid_mask & np.isfinite(data)))
    checks["has_usable_samples"] = has_usable_samples
    if not has_usable_samples:
        errors.append("data contains no finite samples outside nodata.")
    return data


def _validate_wavelengths(
    cube: IIRSCube,
    data: np.ndarray | None,
    errors: list[str],
    checks: Dict[str, bool],
) -> np.ndarray | None:
    try:
        wavelengths = np.asarray(cube.wavelengths_um)
    except Exception:
        checks["wavelength_structure"] = False
        errors.append("wavelengths_um must be convertible to a one-dimensional numeric array.")
        return None

    structure_valid = wavelengths.ndim == 1
    checks["wavelength_structure"] = structure_valid
    if not structure_valid:
        errors.append("wavelengths_um must be a one-dimensional array.")
        return None

    count_valid = data is not None and wavelengths.shape[0] == data.shape[-1]
    checks["wavelength_count_matches_bands"] = count_valid
    if not count_valid:
        errors.append("wavelengths_um length must match the number of data bands.")

    numeric_valid = _is_real_numeric_array(wavelengths)
    checks["wavelength_numeric"] = numeric_valid
    if not numeric_valid:
        errors.append("wavelengths_um must contain real numeric values.")
        return wavelengths

    finite_positive = bool(np.isfinite(wavelengths).all() and np.all(wavelengths > 0.0))
    checks["wavelength_finite_positive"] = finite_positive
    if not finite_positive:
        errors.append("wavelengths_um must contain only positive finite values.")
    return wavelengths


def _validate_spatial_metadata(
    cube: IIRSCube,
    errors: list[str],
    checks: Dict[str, bool],
) -> None:
    pixel_size_valid = _is_real_scalar(cube.pixel_size_m)
    if pixel_size_valid:
        pixel_size_valid = bool(np.isfinite(float(cube.pixel_size_m)) and float(cube.pixel_size_m) > 0.0)
    checks["pixel_size"] = pixel_size_valid
    if not pixel_size_valid:
        errors.append("pixel_size_m must be a positive finite numeric value.")

    transform_valid = isinstance(cube.transform, Affine)
    if transform_valid:
        try:
            transform_values = np.asarray(tuple(cube.transform), dtype=float)
            transform_valid = bool(np.isfinite(transform_values).all())
        except (TypeError, ValueError):
            transform_valid = False
    checks["transform"] = transform_valid
    if not transform_valid:
        errors.append("transform must be a finite affine.Affine instance.")

    scale_valid = False
    if pixel_size_valid and transform_valid:
        column_size = float(np.hypot(cube.transform.a, cube.transform.d))
        row_size = float(np.hypot(cube.transform.b, cube.transform.e))
        scale_valid = (
            column_size > 0.0
            and row_size > 0.0
            and isclose(column_size, float(cube.pixel_size_m), rel_tol=1e-9, abs_tol=1e-12)
            and isclose(row_size, float(cube.pixel_size_m), rel_tol=1e-9, abs_tol=1e-12)
        )
    checks["transform_matches_pixel_size"] = scale_valid
    if not scale_valid:
        errors.append("transform pixel scale must match pixel_size_m in both spatial axes.")

    crs_valid = cube.crs is None or (isinstance(cube.crs, str) and bool(cube.crs.strip()))
    checks["crs"] = crs_valid
    if not crs_valid:
        errors.append("crs must be a non-empty string or None.")


def _validate_required_metadata(
    cube: IIRSCube,
    errors: list[str],
    checks: Dict[str, bool],
) -> None:
    metadata_valid = (
        isinstance(cube.dataset_name, str)
        and bool(cube.dataset_name.strip())
        and isinstance(cube.sensor, str)
        and bool(cube.sensor.strip())
        and (cube.observation_date is None or (isinstance(cube.observation_date, str) and bool(cube.observation_date.strip())))
        and (cube.orbit_id is None or (isinstance(cube.orbit_id, str) and bool(cube.orbit_id.strip())))
        and isinstance(cube.notes, str)
        and isinstance(cube.extra, Mapping)
        and all(isinstance(key, str) for key in cube.extra)
    )
    checks["required_metadata"] = metadata_valid
    if not metadata_valid:
        errors.append("IIRSCube metadata fields do not satisfy the contract requirements.")


def _validate_nodata(nodata: object, errors: list[str]) -> tuple[bool, float | None]:
    if nodata is None:
        return True, None
    if not _is_real_scalar(nodata):
        errors.append("nodata must be a real numeric value or None.")
        return False, None
    numeric_nodata = float(nodata)
    if np.isinf(numeric_nodata):
        errors.append("nodata must be finite, NaN, or None.")
        return False, None
    return True, numeric_nodata


def _nodata_mask(data: np.ndarray, nodata: float | None) -> np.ndarray:
    if nodata is None:
        return np.ones(data.shape, dtype=bool)
    if np.isnan(nodata):
        return ~np.isnan(data)
    return data != nodata


def _is_real_numeric_array(values: np.ndarray) -> bool:
    return bool(
        np.issubdtype(values.dtype, np.number)
        and not np.issubdtype(values.dtype, np.complexfloating)
        and not np.issubdtype(values.dtype, np.bool_)
    )


def _is_real_scalar(value: object) -> bool:
    return bool(
        not isinstance(value, bool)
        and isinstance(value, (int, float, np.number))
        and not isinstance(value, complex)
        and not np.iscomplexobj(value)
    )


def _result(
    errors: list[str], warnings: list[str], checks: Dict[str, bool]
) -> IIRSInputValidationResult:
    return IIRSInputValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        checks=dict(checks),
    )
