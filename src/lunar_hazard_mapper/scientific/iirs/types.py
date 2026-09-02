"""IIRS hyperspectral data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from typing import Any, Dict, Mapping, Optional

import numpy as np
from affine import Affine


@dataclass(frozen=True, eq=False)
class IIRSCube:
    """Immutable contract for an IIRS cube arranged as ``(height, width, bands)``.

    ``valid_mask`` has the same three-dimensional shape as ``data``.  A value
    is valid when it is not the configured nodata value; if ``nodata`` is
    ``None``, all values are considered valid.
    """

    data: np.ndarray
    wavelengths_um: np.ndarray
    pixel_size_m: float
    transform: Affine
    crs: Optional[str]
    nodata: Optional[float]
    dataset_name: str = "unknown"
    sensor: str = "IIRS"
    observation_date: Optional[str] = None
    orbit_id: Optional[str] = None
    notes: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        data = np.asarray(self.data)
        if data.ndim != 3:
            raise ValueError("data must be a 3D array with shape (height, width, bands).")
        if any(dimension <= 0 for dimension in data.shape):
            raise ValueError("data dimensions must all be greater than zero.")
        if (
            not np.issubdtype(data.dtype, np.number)
            or np.issubdtype(data.dtype, np.complexfloating)
            or np.issubdtype(data.dtype, np.bool_)
        ):
            raise TypeError("data must contain real numeric values.")
        if np.isinf(data).any():
            raise ValueError("data must not contain infinite values.")

        wavelengths = np.asarray(self.wavelengths_um)
        if wavelengths.ndim != 1:
            raise ValueError("wavelengths_um must be a one-dimensional array.")
        if wavelengths.shape[0] != data.shape[2]:
            raise ValueError("wavelengths_um length must match the number of data bands.")
        if (
            not np.issubdtype(wavelengths.dtype, np.number)
            or np.issubdtype(wavelengths.dtype, np.complexfloating)
            or np.issubdtype(wavelengths.dtype, np.bool_)
        ):
            raise TypeError("wavelengths_um must contain real numeric values.")
        if not np.isfinite(wavelengths).all():
            raise ValueError("wavelengths_um must contain only finite values.")

        if isinstance(self.pixel_size_m, bool) or not isinstance(
            self.pixel_size_m, (int, float, np.number)
        ):
            raise TypeError("pixel_size_m must be a positive numeric value.")
        pixel_size_m = float(self.pixel_size_m)
        if not np.isfinite(pixel_size_m) or pixel_size_m <= 0.0:
            raise ValueError("pixel_size_m must be a positive finite value.")

        if not isinstance(self.transform, Affine):
            raise TypeError("transform must be an affine.Affine instance.")
        transform_values = np.asarray(tuple(self.transform), dtype=float)
        if not np.isfinite(transform_values).all():
            raise ValueError("transform values must be finite.")
        column_pixel_size = float(np.hypot(self.transform.a, self.transform.d))
        row_pixel_size = float(np.hypot(self.transform.b, self.transform.e))
        if column_pixel_size == 0.0 or row_pixel_size == 0.0:
            raise ValueError("transform must define non-zero spatial pixel axes.")
        if not (
            isclose(column_pixel_size, pixel_size_m, rel_tol=1e-9, abs_tol=1e-12)
            and isclose(row_pixel_size, pixel_size_m, rel_tol=1e-9, abs_tol=1e-12)
        ):
            raise ValueError("transform pixel scale must match pixel_size_m in both spatial axes.")

        nodata = self.nodata
        if nodata is not None:
            if isinstance(nodata, bool) or not isinstance(nodata, (int, float, np.number)):
                raise TypeError("nodata must be a real numeric value or None.")
            nodata = float(nodata)
            if np.isinf(nodata):
                raise ValueError("nodata must be finite, NaN, or None.")

        if self.crs is not None and (
            not isinstance(self.crs, str) or not self.crs.strip()
        ):
            raise ValueError("crs must be a non-empty string or None.")
        for field_name in ("dataset_name", "sensor"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")
        for field_name in ("observation_date", "orbit_id"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be a non-empty string or None.")
        if not isinstance(self.notes, str):
            raise TypeError("notes must be a string.")
        if not isinstance(self.extra, Mapping):
            raise TypeError("extra must be a mapping.")
        if not all(isinstance(key, str) for key in self.extra):
            raise TypeError("extra keys must be strings.")

        object.__setattr__(self, "data", data)
        object.__setattr__(self, "wavelengths_um", wavelengths)
        object.__setattr__(self, "pixel_size_m", pixel_size_m)
        object.__setattr__(self, "nodata", nodata)
        object.__setattr__(self, "extra", dict(self.extra))

    @property
    def valid_mask(self) -> np.ndarray:
        """Return the per-band nodata mask for this cube."""
        if self.nodata is None:
            return np.ones(self.data.shape, dtype=bool)
        if np.isnan(self.nodata):
            return ~np.isnan(self.data)
        return self.data != self.nodata

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this contract into a deterministic Python-list payload."""
        return {
            "data": self.data.tolist(),
            "wavelengths_um": self.wavelengths_um.tolist(),
            "pixel_size_m": float(self.pixel_size_m),
            "transform": list(tuple(self.transform)),
            "crs": self.crs,
            "nodata": self.nodata,
            "dataset_name": self.dataset_name,
            "sensor": self.sensor,
            "observation_date": self.observation_date,
            "orbit_id": self.orbit_id,
            "notes": self.notes,
            "extra": {key: self.extra[key] for key in sorted(self.extra)},
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "IIRSCube":
        """Reconstruct an IIRSCube from :meth:`to_dict` output."""
        if not isinstance(payload, dict):
            raise TypeError("IIRSCube payload must be a dictionary.")
        required_fields = (
            "data",
            "wavelengths_um",
            "pixel_size_m",
            "transform",
            "crs",
            "nodata",
        )
        missing_fields = [field_name for field_name in required_fields if field_name not in payload]
        if missing_fields:
            raise ValueError(
                "IIRSCube payload is missing required field(s): " + ", ".join(missing_fields)
            )
        try:
            transform = Affine(*payload["transform"])
        except (TypeError, ValueError) as exc:
            raise ValueError("IIRSCube payload transform is invalid.") from exc

        return cls(
            data=np.asarray(payload["data"]),
            wavelengths_um=np.asarray(payload["wavelengths_um"]),
            pixel_size_m=payload["pixel_size_m"],
            transform=transform,
            crs=payload["crs"],
            nodata=payload["nodata"],
            dataset_name=payload.get("dataset_name", "unknown"),
            sensor=payload.get("sensor", "IIRS"),
            observation_date=payload.get("observation_date"),
            orbit_id=payload.get("orbit_id"),
            notes=payload.get("notes", ""),
            extra=payload.get("extra", {}),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSCube):
            return NotImplemented
        return (
            np.array_equal(self.data, other.data, equal_nan=True)
            and np.array_equal(self.wavelengths_um, other.wavelengths_um, equal_nan=True)
            and self.pixel_size_m == other.pixel_size_m
            and tuple(self.transform) == tuple(other.transform)
            and self.crs == other.crs
            and _nodata_equal(self.nodata, other.nodata)
            and self.dataset_name == other.dataset_name
            and self.sensor == other.sensor
            and self.observation_date == other.observation_date
            and self.orbit_id == other.orbit_id
            and self.notes == other.notes
            and self.extra == other.extra
        )


def _nodata_equal(left: Optional[float], right: Optional[float]) -> bool:
    """Compare nodata values while treating two NaN sentinels as equal."""
    if left is None or right is None:
        return left is right
    return bool(np.isnan(left) and np.isnan(right)) or left == right
