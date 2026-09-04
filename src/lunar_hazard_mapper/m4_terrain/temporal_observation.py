"""M4 Phase 10.1 multi-date observation contract.

This module defines the metadata boundary for genuine temporal analysis. It
does not load imagery, select pairs, register images, or detect change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional

from .provenance import DataProvenance


class ObservationContractError(ValueError):
    """Raised when observation metadata cannot satisfy the contract."""


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ObservationContractError("acquisition_timestamp must be a non-empty ISO-8601 string.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationContractError(
            "acquisition_timestamp must be parseable ISO-8601 date/time metadata."
        ) from exc
    # A timezone-less source value is still preserved verbatim; UTC is used
    # only as the comparison convention for pair distinctness.
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationContractError(f"{field_name} must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ObservationContractError(f"{field_name} must be a finite number.")
    return number


def _require_mapping(value: Any, field_name: str, *, allow_empty: bool = True) -> Dict[str, Any]:
    if not isinstance(value, dict) or (not allow_empty and not value):
        suffix = " and non-empty" if not allow_empty else ""
        raise ObservationContractError(f"{field_name} must be a dictionary{suffix} when supplied.")
    return value


def _validate_coordinate_container(value: Any, field_name: str) -> None:
    if not isinstance(value, (list, tuple)) or not value:
        raise ObservationContractError(f"{field_name} must be a non-empty coordinate container.")
    if all(not isinstance(item, (list, tuple)) for item in value):
        if len(value) < 2:
            raise ObservationContractError(f"{field_name} must contain at least two coordinates.")
        for item in value:
            _finite_number(item, field_name)
        return
    for item in value:
        _validate_coordinate_container(item, field_name)


def _validate_footprint(value: Dict[str, Any]) -> None:
    if not value:
        raise ObservationContractError("footprint must not be an empty dictionary.")
    bounds = value.get("bounds", value if {"west", "south", "east", "north"}.issubset(value) else None)
    if bounds is not None:
        bounds = _require_mapping(bounds, "footprint.bounds", allow_empty=False)
        try:
            coordinates = [_finite_number(bounds[key], f"footprint.bounds.{key}") for key in ("west", "south", "east", "north")]
        except KeyError as exc:
            raise ObservationContractError("footprint.bounds must contain west, south, east, and north.") from exc
        if coordinates[2] <= coordinates[0] or coordinates[3] <= coordinates[1]:
            raise ObservationContractError("footprint.bounds must have positive width and height.")
    elif "coordinates" in value:
        _validate_coordinate_container(value["coordinates"], "footprint.coordinates")
    else:
        raise ObservationContractError("footprint must contain bounds or coordinates.")


def _validate_view_geometry(value: Dict[str, Any]) -> None:
    if not value:
        raise ObservationContractError("view_geometry must not be an empty dictionary.")
    for field_name in ("position_m", "target_m"):
        if field_name not in value:
            continue
        vector = value[field_name]
        if isinstance(vector, dict):
            if set(vector) < {"x", "y", "z"}:
                raise ObservationContractError(f"view_geometry.{field_name} must contain x, y, and z.")
            vector = [vector[axis] for axis in ("x", "y", "z")]
        if not isinstance(vector, (list, tuple)) or len(vector) != 3:
            raise ObservationContractError(f"view_geometry.{field_name} must contain three coordinates.")
        for coordinate in vector:
            _finite_number(coordinate, f"view_geometry.{field_name}")


@dataclass(frozen=True)
class LunarObservation:
    """One source observation and the metadata available for it.

    ``acquisition_timestamp`` remains optional here because an ingestion
    record may be incomplete. ``ObservationPair`` requires it on both sides.
    No timestamp or other metadata is inferred from a filename or generated.
    """

    observation_id: str
    source: str
    image_reference: str
    acquisition_timestamp: Optional[str] = None
    file_path: Optional[str] = None
    product_id: Optional[str] = None
    crs: Optional[str] = None
    geospatial_reference: Optional[Dict[str, Any]] = None
    dimensions: Optional[tuple[int, int]] = None
    gsd_m: Optional[float] = None
    footprint: Optional[Dict[str, Any]] = None
    view_geometry: Optional[Dict[str, Any]] = None
    sun_azimuth_deg: Optional[float] = None
    sun_elevation_deg: Optional[float] = None
    phase_angle_deg: Optional[float] = None
    incidence_angle_deg: Optional[float] = None
    emission_angle_deg: Optional[float] = None
    metadata_quality: Optional[str] = None
    provenance_source: str = ""
    provenance: DataProvenance = DataProvenance.UNAVAILABLE
    is_real_data: bool = False
    validation_status: str = "unvalidated"
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        for field_name in ("observation_id", "source", "image_reference"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ObservationContractError(f"{field_name} must be a non-empty string.")
        if self.file_path is not None and (not isinstance(self.file_path, str) or not self.file_path.strip()):
            raise ObservationContractError("file_path must be a non-empty string when supplied.")
        if self.crs is not None and (not isinstance(self.crs, str) or not self.crs.strip()):
            raise ObservationContractError("crs must be a non-empty string when supplied.")
        for field_name in ("geospatial_reference", "footprint", "view_geometry"):
            value = getattr(self, field_name)
            if value is not None:
                _require_mapping(value, field_name)
        if self.footprint is not None:
            _validate_footprint(self.footprint)
        if self.view_geometry is not None:
            _validate_view_geometry(self.view_geometry)
        if self.metadata_quality is not None and (
                not isinstance(self.metadata_quality, str) or not self.metadata_quality.strip()):
            raise ObservationContractError("metadata_quality must be a non-empty string when supplied.")
        for field_name in ("validation_status",):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ObservationContractError(f"{field_name} must be a non-empty string.")
        if not isinstance(self.is_real_data, bool):
            raise ObservationContractError("is_real_data must be a boolean.")
        try:
            provenance = self.provenance if isinstance(self.provenance, DataProvenance) else DataProvenance(self.provenance)
        except ValueError as exc:
            raise ObservationContractError("provenance must be a recognized DataProvenance value.") from exc
        object.__setattr__(self, "provenance", provenance)
        if provenance == DataProvenance.REAL and not self.is_real_data:
            raise ObservationContractError("REAL provenance requires is_real_data=True.")
        if self.is_real_data and provenance != DataProvenance.REAL:
            raise ObservationContractError("is_real_data=True requires REAL provenance.")
        if not isinstance(self.provenance_source, str) or not self.provenance_source.strip():
            raise ObservationContractError("provenance_source is required and must identify the source record.")
        if self.acquisition_timestamp is not None:
            _parse_timestamp(self.acquisition_timestamp)
        if self.dimensions is not None:
            if (not isinstance(self.dimensions, (tuple, list)) or len(self.dimensions) != 2 or
                    any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in self.dimensions)):
                raise ObservationContractError("dimensions must contain two positive integers (height, width).")
            object.__setattr__(self, "dimensions", tuple(self.dimensions))
        if self.gsd_m is not None and _finite_number(self.gsd_m, "gsd_m") <= 0:
            raise ObservationContractError("gsd_m must be positive when supplied.")
        for field_name, upper_bound in (
            ("sun_azimuth_deg", 360.0), ("sun_elevation_deg", 90.0),
            ("phase_angle_deg", 180.0), ("incidence_angle_deg", 180.0),
            ("emission_angle_deg", 180.0),
        ):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite_number(value, field_name)
                lower_bound = 0.0
                valid = lower_bound <= number < upper_bound if field_name == "sun_azimuth_deg" else lower_bound <= number <= upper_bound
                if not valid:
                    raise ObservationContractError(f"{field_name} must be in [{lower_bound}, {upper_bound}{')' if field_name == 'sun_azimuth_deg' else ']'}.")

    @property
    def parsed_acquisition_time(self) -> Optional[datetime]:
        return None if self.acquisition_timestamp is None else _parse_timestamp(self.acquisition_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable contract payload."""
        payload = dict(self.__dict__)
        payload["provenance"] = self.provenance.value
        payload["dimensions"] = list(self.dimensions) if self.dimensions is not None else None
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LunarObservation":
        if not isinstance(payload, dict):
            raise ObservationContractError("LunarObservation payload must be a dictionary.")
        try:
            return cls(**payload)
        except ObservationContractError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ObservationContractError(
                f"Malformed LunarObservation payload: {exc}"
            ) from exc


@dataclass(frozen=True)
class ObservationPair:
    """Two genuine, temporally distinct observations for later Phase 10 work."""

    observation_a: LunarObservation
    observation_b: LunarObservation
    pair_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.observation_a, LunarObservation) or not isinstance(self.observation_b, LunarObservation):
            raise ObservationContractError("observation_a and observation_b must both be LunarObservation instances.")
        if self.observation_a.observation_id == self.observation_b.observation_id or self.observation_a.image_reference == self.observation_b.image_reference:
            raise ObservationContractError("Observation A and B must not reference the same observation.")
        if self.observation_a.parsed_acquisition_time is None or self.observation_b.parsed_acquisition_time is None:
            raise ObservationContractError("Both observations require genuine acquisition timestamps for a temporal pair.")
        if self.observation_a.parsed_acquisition_time == self.observation_b.parsed_acquisition_time:
            raise ObservationContractError("Observation A and B must have distinct acquisition timestamps.")
        if not self.observation_a.is_real_data or not self.observation_b.is_real_data:
            raise ObservationContractError("Temporal pairs require is_real_data=True for both observations.")

    @property
    def temporally_distinct(self) -> bool:
        return self.observation_a.parsed_acquisition_time != self.observation_b.parsed_acquisition_time

    @property
    def temporal_metadata(self):
        """Return the Phase 10.2 temporal view for both observations."""
        from .temporal_metadata import temporal_view_for_pair

        return temporal_view_for_pair(self)

    @property
    def spatial_compatibility(self) -> str:
        """Report available spatial compatibility evidence without selecting pairs."""
        if self.observation_a.crs is None or self.observation_b.crs is None:
            return "unknown"
        return "compatible_crs" if self.observation_a.crs == self.observation_b.crs else "different_crs"

    def to_dict(self) -> Dict[str, Any]:
        return {"pair_id": self.pair_id, "observation_a": self.observation_a.to_dict(), "observation_b": self.observation_b.to_dict()}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ObservationPair":
        if not isinstance(payload, dict):
            raise ObservationContractError("ObservationPair payload must be a dictionary.")
        missing = [key for key in ("observation_a", "observation_b") if key not in payload]
        if missing:
            raise ObservationContractError(
                f"Malformed ObservationPair payload; missing fields: {missing}."
            )
        try:
            return cls(
                observation_a=LunarObservation.from_dict(payload["observation_a"]),
                observation_b=LunarObservation.from_dict(payload["observation_b"]),
                pair_id=payload.get("pair_id"),
            )
        except ObservationContractError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ObservationContractError(
                f"Malformed ObservationPair payload: {exc}"
            ) from exc