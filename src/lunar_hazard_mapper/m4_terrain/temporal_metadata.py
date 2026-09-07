"""M4 Phase 10.2 temporal metadata normalization and assessment.

This module handles timestamp metadata only. It does not select image pairs,
register imagery, or infer temporal change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, Mapping, Optional


class TemporalMetadataError(ValueError):
    """Raised when temporal metadata input cannot be structurally assessed."""


class TemporalPrecision(str, Enum):
    DATE = "date"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    SUBSECOND = "subsecond"
    UNKNOWN = "unknown"


class TemporalMetadataStatus(str, Enum):
    VALID = "valid"
    LIMITED_PRECISION = "limited_precision"
    TIMEZONE_NAIVE = "timezone_naive"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICTING = "conflicting"


_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HOUR_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}$")
_MINUTE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}$")
_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?$")
_SUBSECOND = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.\d+")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TemporalMetadataError("timestamp must be a non-empty ISO-8601 string.")
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemporalMetadataError("timestamp must be parseable ISO-8601 metadata.") from exc


def _precision(value: str) -> TemporalPrecision:
    if _DATE_ONLY.fullmatch(value):
        return TemporalPrecision.DATE
    if _HOUR_ONLY.fullmatch(value):
        return TemporalPrecision.HOUR
    if _MINUTE_ONLY.fullmatch(value):
        return TemporalPrecision.MINUTE
    if _SUBSECOND.match(value):
        return TemporalPrecision.SUBSECOND
    if _SECOND.fullmatch(value):
        return TemporalPrecision.SECOND
    return TemporalPrecision.UNKNOWN


@dataclass(frozen=True)
class TemporalMetadata:
    """Original and assessed temporal metadata for one observation.

    ``normalized_timestamp`` retains timezone-naive values as naive datetimes;
    no timezone is assigned when the source did not provide one.
    """

    original_timestamp: Optional[str] = None
    normalized_timestamp: Optional[datetime] = None
    acquisition_date: Optional[str] = None
    precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    timezone_aware: bool = False
    source_field: Optional[str] = None
    metadata_quality: TemporalMetadataStatus = TemporalMetadataStatus.MISSING
    authoritative: bool = False
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    notes: str = ""

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        source_field: str,
        authoritative: bool = False,
    ) -> "TemporalMetadata":
        if value is None:
            return cls(source_field=source_field, authoritative=authoritative)
        if not isinstance(value, str) or not value.strip():
            return cls(
                original_timestamp=value if isinstance(value, str) else None,
                source_field=source_field,
                metadata_quality=TemporalMetadataStatus.INVALID,
                authoritative=authoritative,
                notes="Temporal metadata is missing or blank." if value == "" else "Temporal metadata is not a string.",
            )
        original = value
        normalized_value = value.strip()
        try:
            normalized = _parse_timestamp(normalized_value)
        except TemporalMetadataError as exc:
            return cls(
                original_timestamp=original,
                source_field=source_field,
                metadata_quality=TemporalMetadataStatus.INVALID,
                authoritative=authoritative,
                notes=str(exc),
            )
        precision = _precision(normalized_value)
        if precision in (TemporalPrecision.DATE, TemporalPrecision.HOUR, TemporalPrecision.MINUTE):
            quality = TemporalMetadataStatus.LIMITED_PRECISION
        elif normalized.tzinfo is None:
            quality = TemporalMetadataStatus.TIMEZONE_NAIVE
        else:
            quality = TemporalMetadataStatus.VALID
        timezone_aware = normalized.tzinfo is not None
        normalized = normalized.astimezone(timezone.utc) if normalized.tzinfo is not None else normalized
        if precision is TemporalPrecision.DATE:
            normalized = None
        return cls(
            original_timestamp=original,
            normalized_timestamp=normalized,
            acquisition_date=normalized_value[:10],
            precision=precision,
            timezone_aware=timezone_aware,
            source_field=source_field,
            metadata_quality=quality,
            authoritative=authoritative,
        )

    @classmethod
    def from_observation(
        cls,
        observation: Any,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "TemporalMetadata":
        """Resolve explicit observation metadata without using filenames.

        The Phase 10.1 observation field has precedence over an external
        mapping. The mapping is intentionally limited to explicit timestamp
        fields so generic manifest fields such as ``created_at`` are not
        mistaken for acquisition time.
        """
        timestamp = getattr(observation, "acquisition_timestamp", None)
        direct = cls.from_value(
            timestamp,
            source_field="observation.acquisition_timestamp",
            authoritative=True,
        )
        if metadata is None:
            return direct
        if not isinstance(metadata, Mapping):
            raise TemporalMetadataError("metadata must be a mapping when supplied.")

        candidates = []
        if "acquisition_timestamp" in metadata:
            candidates.append(("metadata.acquisition_timestamp", metadata["acquisition_timestamp"]))
        elif "acquisition_date" in metadata:
            candidates.append(("metadata.acquisition_date", metadata["acquisition_date"]))
        if not candidates:
            return direct
        external = cls.from_value(
            candidates[0][1], source_field=candidates[0][0], authoritative=True
        )
        if direct.original_timestamp is None:
            return external
        if direct.metadata_quality == TemporalMetadataStatus.INVALID:
            return direct
        if external.original_timestamp is None:
            return direct
        if direct.normalized_timestamp != external.normalized_timestamp:
            return cls(
                **{
                    **direct.__dict__,
                    "metadata_quality": TemporalMetadataStatus.CONFLICTING,
                    "notes": (
                        "Conflicting acquisition metadata from "
                        f"{direct.source_field} and {external.source_field}."
                    ),
                }
            )
        return direct

    @property
    def usable_for_absolute_ordering(self) -> bool:
        return (
            self.normalized_timestamp is not None
            and self.timezone_aware
            and self.precision in (TemporalPrecision.SECOND, TemporalPrecision.SUBSECOND)
            and self.metadata_quality not in (
                TemporalMetadataStatus.INVALID,
                TemporalMetadataStatus.CONFLICTING,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_timestamp": self.original_timestamp,
            "normalized_timestamp": self.normalized_timestamp.isoformat() if self.normalized_timestamp else None,
            "acquisition_date": self.acquisition_date,
            "precision": self.precision.value,
            "timezone_aware": self.timezone_aware,
            "source_field": self.source_field,
            "metadata_quality": self.metadata_quality.value,
            "authoritative": self.authoritative,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class TemporalPairView:
    """Temporal metadata exposed for both members of an observation pair."""

    observation_a: TemporalMetadata
    observation_b: TemporalMetadata
    chronological_order: str
    temporal_separation_seconds: Optional[float]
    timestamps_available: bool
    metadata_quality: TemporalMetadataStatus

    @classmethod
    def from_pair(cls, pair: Any) -> "TemporalPairView":
        first = TemporalMetadata.from_observation(pair.observation_a)
        second = TemporalMetadata.from_observation(pair.observation_b)
        timestamps_available = first.original_timestamp is not None and second.original_timestamp is not None
        if not timestamps_available or first.metadata_quality in (TemporalMetadataStatus.INVALID, TemporalMetadataStatus.CONFLICTING) or second.metadata_quality in (TemporalMetadataStatus.INVALID, TemporalMetadataStatus.CONFLICTING):
            order = "unknown"
            separation = None
        elif first.precision is TemporalPrecision.DATE and second.precision is TemporalPrecision.DATE:
            if first.acquisition_date == second.acquisition_date:
                order = "unknown"
            else:
                order = "a_before_b" if first.acquisition_date < second.acquisition_date else "b_before_a"
            separation = None
        elif first.timezone_aware != second.timezone_aware:
            order = "unknown"
            separation = None
        elif not first.timezone_aware:
            delta = second.normalized_timestamp - first.normalized_timestamp
            order = "a_before_b" if delta.total_seconds() > 0 else "b_before_a"
            separation = None
        else:
            delta = second.normalized_timestamp - first.normalized_timestamp
            order = "a_before_b" if delta.total_seconds() > 0 else "b_before_a"
            separation = (
                abs(delta.total_seconds())
                if first.precision in (TemporalPrecision.SECOND, TemporalPrecision.SUBSECOND)
                and second.precision in (TemporalPrecision.SECOND, TemporalPrecision.SUBSECOND)
                else None
            )
        statuses = {first.metadata_quality, second.metadata_quality}
        if TemporalMetadataStatus.INVALID in statuses or TemporalMetadataStatus.CONFLICTING in statuses:
            quality = TemporalMetadataStatus.CONFLICTING if TemporalMetadataStatus.CONFLICTING in statuses else TemporalMetadataStatus.INVALID
        elif TemporalMetadataStatus.TIMEZONE_NAIVE in statuses:
            quality = TemporalMetadataStatus.TIMEZONE_NAIVE
        elif TemporalMetadataStatus.LIMITED_PRECISION in statuses:
            quality = TemporalMetadataStatus.LIMITED_PRECISION
        elif TemporalMetadataStatus.VALID in statuses:
            quality = TemporalMetadataStatus.VALID
        else:
            quality = TemporalMetadataStatus.MISSING
        return cls(first, second, order, separation, timestamps_available, quality)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_a": self.observation_a.to_dict(),
            "observation_b": self.observation_b.to_dict(),
            "chronological_order": self.chronological_order,
            "temporal_separation_seconds": self.temporal_separation_seconds,
            "timestamps_available": self.timestamps_available,
            "metadata_quality": self.metadata_quality.value,
        }


def temporal_view_for_pair(pair: Any) -> TemporalPairView:
    """Build the Phase 10.2 temporal view without selecting or judging a pair."""
    return TemporalPairView.from_pair(pair)