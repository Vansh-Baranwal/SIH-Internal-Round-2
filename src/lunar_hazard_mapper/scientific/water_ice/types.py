"""Input-only spatial evidence contracts for Phase 9 water-ice work."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isclose
from numbers import Real
from typing import Any, Dict, Mapping, Optional

import numpy as np
from affine import Affine


class WaterIceEvidenceSource(str, Enum):
    """Approved identities for a Phase 9 input evidence layer.

    These values identify provenance only.  They do not specify units,
    calibration, thresholds, quality, or any water-ice interpretation.
    """

    DIVINER = "Diviner"
    MINI_RF = "Mini-RF"
    LOLA = "LOLA"
    IIRS_HYDRATION_SIGNAL = "IIRS hydration signal"


@dataclass(frozen=True, eq=False)
class WaterIceEvidenceLayer:
    """One spatial 2-D input-evidence layer for later Phase 9 consumers.

    ``values`` contains source-provided numerical indicator values only; this
    contract does not calculate hydration, water-ice confidence, or hotspots.
    A cell is usable only when ``valid_mask`` is ``True``.  Invalid cells must
    use the configured ``nodata`` marker: ``NaN`` for a NaN marker or the exact
    finite sentinel for a numeric marker.  With ``nodata=None``, every cell
    must be valid and finite.
    """

    source: WaterIceEvidenceSource
    values: np.ndarray
    valid_mask: np.ndarray
    pixel_size_m: float
    transform: Affine
    crs: Optional[str]
    nodata: Optional[float]
    dataset_name: str
    sensor: Optional[str] = None
    observation_date: Optional[str] = None
    orbit_id: Optional[str] = None
    notes: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, WaterIceEvidenceSource):
            raise TypeError("source must be a WaterIceEvidenceSource instance.")

        values = np.asarray(self.values)
        if values.ndim != 2 or any(dimension <= 0 for dimension in values.shape):
            raise ValueError("values must be a non-empty 2D array.")
        if not _is_real_numeric_array(values):
            raise TypeError("values must contain real numeric values.")
        if np.isinf(values).any():
            raise ValueError("values must not contain infinite values.")

        valid_mask = np.asarray(self.valid_mask)
        if valid_mask.ndim != 2:
            raise ValueError("valid_mask must be a 2D array.")
        if valid_mask.shape != values.shape:
            raise ValueError("valid_mask shape must match values.")
        if valid_mask.dtype != bool:
            raise TypeError("valid_mask must be boolean.")

        pixel_size_m = _validate_pixel_size(self.pixel_size_m)
        _validate_transform(self.transform, pixel_size_m)
        _validate_crs(self.crs)
        nodata = _validate_nodata(self.nodata)
        _validate_nodata_semantics(values, valid_mask, nodata)

        if not isinstance(self.dataset_name, str) or not self.dataset_name.strip():
            raise ValueError("dataset_name must be a non-empty string.")
        for field_name in ("sensor", "observation_date", "orbit_id"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be a non-empty string or None.")
        if not isinstance(self.notes, str):
            raise TypeError("notes must be a string.")

        object.__setattr__(self, "values", values)
        object.__setattr__(self, "valid_mask", valid_mask)
        object.__setattr__(self, "pixel_size_m", pixel_size_m)
        object.__setattr__(self, "nodata", nodata)
        object.__setattr__(self, "extra", _normalise_extra(self.extra))

    @property
    def shape(self) -> tuple[int, int]:
        """Spatial shape in ``(height, width)`` order."""
        return self.values.shape

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this contract as a deterministic JSON-friendly payload.

        NaN values and a NaN nodata marker are represented by the string
        ``"NaN"`` so repeated payloads compare deterministically and remain
        valid JSON data.  :meth:`from_dict` restores those values to NaN.
        """
        return {
            "source": self.source.value,
            "values": _serialize_values(self.values),
            "valid_mask": self.valid_mask.tolist(),
            "pixel_size_m": float(self.pixel_size_m),
            "transform": list(tuple(self.transform)),
            "crs": self.crs,
            "nodata": _serialize_nodata(self.nodata),
            "dataset_name": self.dataset_name,
            "sensor": self.sensor,
            "observation_date": self.observation_date,
            "orbit_id": self.orbit_id,
            "notes": self.notes,
            "extra": _sorted_extra(self.extra),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WaterIceEvidenceLayer":
        """Reconstruct a layer from :meth:`to_dict` output."""
        if not isinstance(payload, dict):
            raise TypeError("WaterIceEvidenceLayer payload must be a dictionary.")
        required_fields = (
            "source",
            "values",
            "valid_mask",
            "pixel_size_m",
            "transform",
            "crs",
            "nodata",
            "dataset_name",
        )
        missing_fields = [name for name in required_fields if name not in payload]
        if missing_fields:
            raise ValueError(
                "WaterIceEvidenceLayer payload is missing required field(s): "
                + ", ".join(missing_fields)
            )
        try:
            source = WaterIceEvidenceSource(payload["source"])
        except (TypeError, ValueError) as exc:
            raise ValueError("WaterIceEvidenceLayer payload source is invalid.") from exc
        try:
            transform = Affine(*payload["transform"])
        except (TypeError, ValueError) as exc:
            raise ValueError("WaterIceEvidenceLayer payload transform is invalid.") from exc
        return cls(
            source=source,
            values=np.asarray(_deserialize_values(payload["values"])),
            valid_mask=np.asarray(payload["valid_mask"]),
            pixel_size_m=payload["pixel_size_m"],
            transform=transform,
            crs=payload["crs"],
            nodata=_deserialize_nodata(payload["nodata"]),
            dataset_name=payload["dataset_name"],
            sensor=payload.get("sensor"),
            observation_date=payload.get("observation_date"),
            orbit_id=payload.get("orbit_id"),
            notes=payload.get("notes", ""),
            extra=payload.get("extra", {}),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WaterIceEvidenceLayer):
            return NotImplemented
        return (
            self.source == other.source
            and np.array_equal(self.values, other.values, equal_nan=True)
            and np.array_equal(self.valid_mask, other.valid_mask)
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


def _is_real_numeric_array(values: np.ndarray) -> bool:
    return bool(
        np.issubdtype(values.dtype, np.number)
        and not np.issubdtype(values.dtype, np.complexfloating)
        and not np.issubdtype(values.dtype, np.bool_)
    )


def _validate_pixel_size(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("pixel_size_m must be a positive numeric value.")
    pixel_size_m = float(value)
    if not np.isfinite(pixel_size_m) or pixel_size_m <= 0.0:
        raise ValueError("pixel_size_m must be a positive finite value.")
    return pixel_size_m


def _validate_transform(transform: object, pixel_size_m: float) -> None:
    if not isinstance(transform, Affine):
        raise TypeError("transform must be an affine.Affine instance.")
    transform_values = np.asarray(tuple(transform), dtype=float)
    if not np.isfinite(transform_values).all():
        raise ValueError("transform values must be finite.")
    column_pixel_size = float(np.hypot(transform.a, transform.d))
    row_pixel_size = float(np.hypot(transform.b, transform.e))
    if column_pixel_size == 0.0 or row_pixel_size == 0.0:
        raise ValueError("transform must define non-zero spatial pixel axes.")
    if not (
        isclose(column_pixel_size, pixel_size_m, rel_tol=1e-9, abs_tol=1e-12)
        and isclose(row_pixel_size, pixel_size_m, rel_tol=1e-9, abs_tol=1e-12)
    ):
        raise ValueError("transform pixel scale must match pixel_size_m in both spatial axes.")


def _validate_crs(crs: object) -> None:
    if crs is not None and (not isinstance(crs, str) or not crs.strip()):
        raise ValueError("crs must be a non-empty string or None.")


def _validate_nodata(nodata: object) -> Optional[float]:
    if nodata is None:
        return None
    if isinstance(nodata, bool) or not isinstance(nodata, Real):
        raise TypeError("nodata must be a real numeric value or None.")
    nodata_value = float(nodata)
    if np.isinf(nodata_value):
        raise ValueError("nodata must be finite, NaN, or None.")
    return nodata_value


def _validate_nodata_semantics(
    values: np.ndarray, valid_mask: np.ndarray, nodata: Optional[float]
) -> None:
    if nodata is None:
        if not valid_mask.all():
            raise ValueError("nodata=None requires every cell to be valid.")
        if not np.isfinite(values).all():
            raise ValueError("nodata=None requires every value to be finite.")
    elif np.isnan(nodata):
        if valid_mask.any() and not np.isfinite(values[valid_mask]).all():
            raise ValueError("valid values must be finite.")
        if (~valid_mask).any() and not np.isnan(values[~valid_mask]).all():
            raise ValueError("invalid values must equal the configured nodata marker.")
    else:
        if valid_mask.any() and (
            not np.isfinite(values[valid_mask]).all() or np.any(values[valid_mask] == nodata)
        ):
            raise ValueError("valid values must be finite and distinct from nodata.")
        if (~valid_mask).any() and not np.all(values[~valid_mask] == nodata):
            raise ValueError("invalid values must equal the configured nodata marker.")


def _normalise_extra(extra: object) -> Dict[str, Any]:
    if not isinstance(extra, Mapping):
        raise TypeError("extra must be a mapping.")
    if not all(isinstance(key, str) for key in extra):
        raise TypeError("extra keys must be strings.")
    return {key: _normalise_metadata_value(extra[key]) for key in sorted(extra)}


def _normalise_metadata_value(value: object) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric_value = float(value) if isinstance(value, (float, np.floating)) else int(value)
        if isinstance(numeric_value, float) and not np.isfinite(numeric_value):
            raise ValueError("extra numeric values must be finite.")
        return numeric_value
    if isinstance(value, (list, tuple)):
        return [_normalise_metadata_value(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("nested extra keys must be strings.")
        return {key: _normalise_metadata_value(value[key]) for key in sorted(value)}
    raise TypeError("extra values must be JSON-friendly primitives, lists, or mappings.")


def _sorted_extra(extra: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: _sorted_extra(value) if isinstance(value, Mapping) else value
        for key, value in sorted(extra.items())
    }


def _nodata_equal(left: Optional[float], right: Optional[float]) -> bool:
    if left is None or right is None:
        return left is right
    return bool(np.isnan(left) and np.isnan(right)) or left == right


def _serialize_values(values: np.ndarray) -> list[list[float | int | str]]:
    serialized = values.tolist()
    return [
        ["NaN" if isinstance(value, Real) and np.isnan(value) else value for value in row]
        for row in serialized
    ]


def _deserialize_values(values: object) -> object:
    if not isinstance(values, list):
        return values
    return [
        [np.nan if value == "NaN" else value for value in row] if isinstance(row, list) else row
        for row in values
    ]


def _serialize_nodata(nodata: Optional[float]) -> Optional[float | str]:
    return "NaN" if nodata is not None and np.isnan(nodata) else nodata


def _deserialize_nodata(nodata: object) -> object:
    return np.nan if nodata == "NaN" else nodata
