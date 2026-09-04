"""Phase 11.1 unknown-image input contract.

This module defines the input boundary for an unknown lunar image that is not
assumed to have a known ground location. The contract only describes the image
record and available metadata; it does not perform localization, feature
extraction, or coordinate estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlparse

from .provenance import DataProvenance


class UnknownImageContractError(ValueError):
    """Raised when a lunar image record violates the Phase 11.1 contract."""


class UnknownImageReferenceType(str, Enum):
    LOCAL_AVAILABLE = "local_available"
    EXTERNAL_REFERENCE = "external_reference"
    LOCAL_MISSING = "local_missing"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    INVALID = "invalid"


def _finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnknownImageContractError(f"{field_name} must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise UnknownImageContractError(f"{field_name} must be a finite number.")
    return number


def _parse_iso_date(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise UnknownImageContractError(f"{field_name} must be a non-empty ISO-8601 string when supplied.")
    try:
        if "T" in value or " " in value:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        else:
            datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise UnknownImageContractError(f"{field_name} must be parseable ISO-8601 metadata.") from exc


def _require_mapping(value: Any, field_name: str, *, allow_empty: bool = True) -> Dict[str, Any]:
    if not isinstance(value, dict) or (not allow_empty and not value):
        suffix = " and non-empty" if not allow_empty else ""
        raise UnknownImageContractError(f"{field_name} must be a dictionary{suffix} when supplied.")
    return value


def _validate_footprint(value: Dict[str, Any]) -> None:
    if not value:
        raise UnknownImageContractError("footprint must not be an empty dictionary.")
    bounds = value.get("bounds", value if {"west", "south", "east", "north"}.issubset(value) else None)
    if bounds is not None:
        bounds = _require_mapping(bounds, "footprint.bounds", allow_empty=False)
        try:
            coordinates = [_finite_number(bounds[key], f"footprint.bounds.{key}") for key in ("west", "south", "east", "north")]
        except KeyError as exc:
            raise UnknownImageContractError("footprint.bounds must contain west, south, east, and north.") from exc
        if coordinates[2] <= coordinates[0] or coordinates[3] <= coordinates[1]:
            raise UnknownImageContractError("footprint.bounds must have positive width and height.")
    elif "coordinates" in value:
        coords = value["coordinates"]
        if not isinstance(coords, (list, tuple)) or not coords:
            raise UnknownImageContractError("footprint.coordinates must be a non-empty coordinate container.")
        for item in coords:
            if isinstance(item, (list, tuple)):
                for coordinate in item:
                    _finite_number(coordinate, "footprint.coordinates")
            else:
                _finite_number(item, "footprint.coordinates")
    else:
        raise UnknownImageContractError("footprint must contain bounds or coordinates.")


def _validate_geometry_map(value: Dict[str, Any], field_name: str) -> None:
    if not value:
        raise UnknownImageContractError(f"{field_name} must not be an empty dictionary.")
    for key in ("position_m", "target_m"):
        if key not in value:
            continue
        vector = value[key]
        if isinstance(vector, dict):
            if set(vector) < {"x", "y", "z"}:
                raise UnknownImageContractError(f"{field_name}.{key} must contain x, y, and z.")
            vector = [vector[axis] for axis in ("x", "y", "z")]
        if not isinstance(vector, (list, tuple)) or len(vector) != 3:
            raise UnknownImageContractError(f"{field_name}.{key} must contain three coordinates.")
        for coordinate in vector:
            _finite_number(coordinate, f"{field_name}.{key}")


def _normalize_optional_sequence(value: Any, field_name: str) -> Optional[tuple[str, ...]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = tuple(value)
    else:
        raise UnknownImageContractError(f"{field_name} must be a string or sequence of strings when supplied.")
    normalized = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise UnknownImageContractError(f"{field_name} entries must be non-empty strings.")
        normalized.append(item.strip())
    return tuple(normalized)


def _reference_status_from_value(reference: str, *, local_path: Optional[str], external_reference: Optional[str]) -> UnknownImageReferenceType:
    if not reference or not reference.strip():
        return UnknownImageReferenceType.INVALID
    if local_path is not None and local_path.strip():
        candidate = Path(local_path)
        if candidate.exists():
            return UnknownImageReferenceType.LOCAL_AVAILABLE
        return UnknownImageReferenceType.LOCAL_MISSING
    if external_reference is not None and external_reference.strip():
        return UnknownImageReferenceType.EXTERNAL_REFERENCE
    parsed = urlparse(reference)
    if parsed.scheme and (parsed.netloc or parsed.scheme in {"http", "https", "s3", "gs", "ftp"}):
        return UnknownImageReferenceType.EXTERNAL_REFERENCE
    if Path(reference).exists():
        return UnknownImageReferenceType.LOCAL_AVAILABLE
    if Path(reference).is_absolute() or reference.startswith(".") or reference.startswith("~"):
        return UnknownImageReferenceType.LOCAL_MISSING
    return UnknownImageReferenceType.UNKNOWN


@dataclass(frozen=True)
class UnknownImage:
    """Input contract for a lunar image with unknown geographic location."""

    image_id: str
    image_reference: str
    image_reference_type: UnknownImageReferenceType = UnknownImageReferenceType.UNKNOWN
    provenance: DataProvenance = DataProvenance.UNAVAILABLE
    provenance_source: str = ""
    is_real_data: bool = False
    source_id: Optional[str] = None
    product_id: Optional[str] = None
    local_path: Optional[str] = None
    external_reference: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    image_format: Optional[str] = None
    dtype: Optional[str] = None
    bit_depth: Optional[int] = None
    gsd_m: Optional[float] = None
    crs: Optional[str] = None
    geospatial_reference: Optional[Dict[str, Any]] = None
    footprint: Optional[Dict[str, Any]] = None
    acquisition_timestamp: Optional[str] = None
    acquisition_date: Optional[str] = None
    sensor: Optional[str] = None
    source_name: Optional[str] = None
    illumination: Optional[Dict[str, Any]] = None
    view_geometry: Optional[Dict[str, Any]] = None
    metadata_coordinates: Optional[Dict[str, Any]] = None
    metadata_quality: Optional[str] = None
    validation_status: str = "unvalidated"
    warnings: tuple[str, ...] = ()
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.image_id, str) or not self.image_id.strip():
            raise UnknownImageContractError("image_id must be a non-empty string.")
        if not isinstance(self.image_reference, str) or not self.image_reference.strip():
            raise UnknownImageContractError("image_reference must be a non-empty string.")

        if not isinstance(self.provenance_source, str) or not self.provenance_source.strip():
            raise UnknownImageContractError("provenance_source must be a non-empty string identifying the provenance record.")

        try:
            provenance = self.provenance if isinstance(self.provenance, DataProvenance) else DataProvenance(self.provenance)
        except ValueError as exc:
            raise UnknownImageContractError("provenance must be a recognized DataProvenance value.") from exc
        object.__setattr__(self, "provenance", provenance)

        if not isinstance(self.is_real_data, bool):
            raise UnknownImageContractError("is_real_data must be a boolean.")
        if provenance == DataProvenance.REAL and not self.is_real_data:
            raise UnknownImageContractError("REAL provenance requires is_real_data=True.")
        if self.is_real_data and provenance != DataProvenance.REAL:
            raise UnknownImageContractError("is_real_data=True requires REAL provenance.")

        image_reference_type = self.image_reference_type
        if isinstance(image_reference_type, str):
            try:
                image_reference_type = UnknownImageReferenceType(image_reference_type)
            except ValueError as exc:
                raise UnknownImageContractError("image_reference_type must be a valid UnknownImageReferenceType value.") from exc
        elif not isinstance(image_reference_type, UnknownImageReferenceType):
            raise UnknownImageContractError("image_reference_type must be a valid UnknownImageReferenceType value.")
        object.__setattr__(self, "image_reference_type", image_reference_type)

        if self.source_id is not None and (not isinstance(self.source_id, str) or not self.source_id.strip()):
            raise UnknownImageContractError("source_id must be a non-empty string when supplied.")
        if self.product_id is not None and (not isinstance(self.product_id, str) or not self.product_id.strip()):
            raise UnknownImageContractError("product_id must be a non-empty string when supplied.")
        if self.local_path is not None and (not isinstance(self.local_path, str) or not self.local_path.strip()):
            raise UnknownImageContractError("local_path must be a non-empty string when supplied.")
        if self.external_reference is not None and (not isinstance(self.external_reference, str) or not self.external_reference.strip()):
            raise UnknownImageContractError("external_reference must be a non-empty string when supplied.")

        if image_reference_type is UnknownImageReferenceType.LOCAL_AVAILABLE:
            if not self.local_path or not self.local_path.strip():
                raise UnknownImageContractError("local_path is required for LOCAL_AVAILABLE image_reference_type.")
        elif image_reference_type is UnknownImageReferenceType.EXTERNAL_REFERENCE:
            if not self.external_reference or not self.external_reference.strip():
                raise UnknownImageContractError("external_reference is required for EXTERNAL_REFERENCE image_reference_type.")
        elif image_reference_type in {UnknownImageReferenceType.LOCAL_MISSING, UnknownImageReferenceType.UNAVAILABLE}:
            if self.local_path is not None and not self.local_path.strip():
                raise UnknownImageContractError("local_path must be a non-empty string when supplied for local-missing or unavailable references.")

        for field_name, value in (("width", self.width), ("height", self.height), ("channels", self.channels), ("bit_depth", self.bit_depth)):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise UnknownImageContractError(f"{field_name} must be a positive integer when supplied.")

        if self.gsd_m is not None:
            gsd = _finite_number(self.gsd_m, "gsd_m")
            if gsd <= 0:
                raise UnknownImageContractError("gsd_m must be positive when supplied.")

        if self.crs is not None and (not isinstance(self.crs, str) or not self.crs.strip()):
            raise UnknownImageContractError("crs must be a non-empty string when supplied.")
        if self.image_format is not None and (not isinstance(self.image_format, str) or not self.image_format.strip()):
            raise UnknownImageContractError("image_format must be a non-empty string when supplied.")
        if self.dtype is not None and (not isinstance(self.dtype, str) or not self.dtype.strip()):
            raise UnknownImageContractError("dtype must be a non-empty string when supplied.")
        if self.sensor is not None and (not isinstance(self.sensor, str) or not self.sensor.strip()):
            raise UnknownImageContractError("sensor must be a non-empty string when supplied.")
        if self.source_name is not None and (not isinstance(self.source_name, str) or not self.source_name.strip()):
            raise UnknownImageContractError("source_name must be a non-empty string when supplied.")
        if self.metadata_quality is not None and (not isinstance(self.metadata_quality, str) or not self.metadata_quality.strip()):
            raise UnknownImageContractError("metadata_quality must be a non-empty string when supplied.")
        if not isinstance(self.validation_status, str) or not self.validation_status.strip():
            raise UnknownImageContractError("validation_status must be a non-empty string.")

        for field_name, value in (("geospatial_reference", self.geospatial_reference), ("footprint", self.footprint), ("illumination", self.illumination), ("view_geometry", self.view_geometry), ("metadata_coordinates", self.metadata_coordinates)):
            if value is not None:
                _require_mapping(value, field_name)
        if self.footprint is not None:
            _validate_footprint(self.footprint)
        if self.illumination is not None:
            for key in ("sun_azimuth_deg", "sun_elevation_deg"):
                if key in self.illumination:
                    _finite_number(self.illumination[key], f"illumination.{key}")
        if self.view_geometry is not None:
            _validate_geometry_map(self.view_geometry, "view_geometry")
        if self.metadata_coordinates is not None:
            if not isinstance(self.metadata_coordinates, dict) or not self.metadata_coordinates:
                raise UnknownImageContractError("metadata_coordinates must be a non-empty dictionary when supplied.")

        if self.acquisition_timestamp is not None:
            _parse_iso_date(self.acquisition_timestamp, "acquisition_timestamp")
        if self.acquisition_date is not None:
            _parse_iso_date(self.acquisition_date, "acquisition_date")

        if self.warnings is None:
            object.__setattr__(self, "warnings", tuple())
        elif isinstance(self.warnings, str):
            object.__setattr__(self, "warnings", (self.warnings.strip(),))
        elif not isinstance(self.warnings, tuple):
            try:
                object.__setattr__(self, "warnings", tuple(self.warnings))
            except TypeError as exc:
                raise UnknownImageContractError("warnings must be a string or sequence of strings when supplied.") from exc
        for warning in self.warnings:
            if not isinstance(warning, str) or not warning.strip():
                raise UnknownImageContractError("warnings entries must be non-empty strings.")

        if self.notes is not None and (not isinstance(self.notes, str) or not self.notes.strip()):
            raise UnknownImageContractError("notes must be a non-empty string when supplied.")

        inferred_reference_type = _reference_status_from_value(self.image_reference, local_path=self.local_path, external_reference=self.external_reference)
        if image_reference_type is UnknownImageReferenceType.UNKNOWN and inferred_reference_type is not UnknownImageReferenceType.UNKNOWN:
            object.__setattr__(self, "image_reference_type", inferred_reference_type)
        if self.image_reference_type is UnknownImageReferenceType.INVALID:
            raise UnknownImageContractError("image_reference must not be malformed or empty.")

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.__dict__)
        payload["provenance"] = self.provenance.value
        payload["image_reference_type"] = self.image_reference_type.value
        payload["warnings"] = list(self.warnings)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "UnknownImage":
        if not isinstance(payload, dict):
            raise UnknownImageContractError("UnknownImage payload must be a dictionary.")
        try:
            if "warnings" in payload and payload["warnings"] is not None and not isinstance(payload["warnings"], (list, tuple)):
                raise UnknownImageContractError("warnings must be a list or tuple when supplied.")
            if "image_reference_type" in payload and payload["image_reference_type"] is not None:
                value = payload["image_reference_type"]
                payload = dict(payload)
                payload["image_reference_type"] = UnknownImageReferenceType(value).value if isinstance(value, str) else value
            return cls(**payload)
        except (TypeError, ValueError, KeyError) as exc:
            raise UnknownImageContractError(f"Malformed UnknownImage payload: {exc}") from exc


__all__ = [
    "UnknownImage",
    "UnknownImageContractError",
    "UnknownImageReferenceType",
]
