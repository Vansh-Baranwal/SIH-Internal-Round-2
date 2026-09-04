"""M4 Phase 10.3 metadata-only image-pair selection.

This module evaluates candidate pairs before registration. It does not run
the correspondence engine, transform images, or claim that physical lunar
change occurred.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from .provenance import DataProvenance
from .temporal_metadata import (
    TemporalMetadata,
    TemporalMetadataStatus,
    TemporalPairView,
)
from .temporal_observation import LunarObservation, ObservationContractError, ObservationPair


class PairEligibility(str, Enum):
    ELIGIBLE = "eligible"
    REJECTED = "rejected"


class ImageReferenceStatus(str, Enum):
    LOCAL_AVAILABLE = "local_available"
    EXTERNAL_REFERENCE = "external_reference"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    UNKNOWN = "unknown"
    DIFFERENT = "different"
    SUPPORTED = "supported"


KNOWN_SENSORS = ("TMC", "OHRC", "IIRS", "LRO NAC", "NAC", "SELENE")
_TEMPORAL_FIELDS = ("acquisition_timestamp",)
_OPTIONAL_FIELDS = (
    "dimensions", "gsd_m", "crs", "footprint", "view_geometry",
    "sun_azimuth_deg", "sun_elevation_deg", "phase_angle_deg",
    "incidence_angle_deg", "emission_angle_deg",
)


def _sensor_name(source: str) -> Optional[str]:
    normalized = source.upper().replace("_", " ")
    for sensor in sorted(KNOWN_SENSORS, key=len, reverse=True):
        if sensor in normalized:
            return sensor
    return None


def _bounds(observation: LunarObservation) -> Optional[tuple[float, float, float, float]]:
    footprint = observation.footprint
    if not footprint:
        return None
    candidate = footprint.get("bounds")
    if candidate is None and {"west", "south", "east", "north"}.issubset(footprint):
        candidate = footprint
    if not isinstance(candidate, dict):
        return None
    try:
        return tuple(float(candidate[key]) for key in ("west", "south", "east", "north"))
    except (KeyError, TypeError, ValueError):
        return None


def _image_reference_status(observation: LunarObservation) -> ImageReferenceStatus:
    reference = observation.file_path or observation.image_reference
    if not isinstance(reference, str) or not reference.strip():
        return ImageReferenceStatus.INVALID
    is_windows_path = len(reference) >= 3 and reference[1] == ":" and reference[2] in "\\/"
    parsed = urlparse(reference)
    if not is_windows_path and parsed.scheme and (parsed.netloc or parsed.scheme in ("s3", "gs", "file")):
        if parsed.scheme == "file":
            return ImageReferenceStatus.LOCAL_AVAILABLE if Path(parsed.path).exists() else ImageReferenceStatus.UNAVAILABLE
        return ImageReferenceStatus.EXTERNAL_REFERENCE
    if Path(reference).exists():
        return ImageReferenceStatus.LOCAL_AVAILABLE
    if observation.file_path is not None or Path(reference).is_absolute():
        return ImageReferenceStatus.UNAVAILABLE
    return ImageReferenceStatus.UNKNOWN


def _metadata_completeness(observation: LunarObservation) -> float:
    present = sum(getattr(observation, field) is not None for field in _OPTIONAL_FIELDS)
    return present / len(_OPTIONAL_FIELDS)


def _spatial_signals(first: LunarObservation, second: LunarObservation) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if first.crs is None or second.crs is None:
        crs_status = CompatibilityStatus.UNKNOWN.value
        warnings.append("missing_crs")
    elif first.crs == second.crs:
        crs_status = CompatibilityStatus.COMPATIBLE.value
    else:
        crs_status = CompatibilityStatus.DIFFERENT.value
        warnings.append("different_crs_requires_later_transform")

    first_bounds, second_bounds = _bounds(first), _bounds(second)
    if first_bounds is None or second_bounds is None or crs_status != CompatibilityStatus.COMPATIBLE.value:
        footprint_status = CompatibilityStatus.UNKNOWN.value
        warnings.append("footprint_overlap_unknown")
    else:
        horizontal = min(first_bounds[2], second_bounds[2]) - max(first_bounds[0], second_bounds[0])
        vertical = min(first_bounds[3], second_bounds[3]) - max(first_bounds[1], second_bounds[1])
        if horizontal > 0 and vertical > 0:
            footprint_status = CompatibilityStatus.COMPATIBLE.value
        else:
            footprint_status = CompatibilityStatus.DIFFERENT.value
    return crs_status, footprint_status, warnings


def _candidate_score(
    temporal_a: TemporalMetadata,
    temporal_b: TemporalMetadata,
    crs_status: str,
    footprint_status: str,
    sensor_status: str,
    reference_a: ImageReferenceStatus,
    reference_b: ImageReferenceStatus,
    completeness: float,
) -> float:
    temporal_scores = {
        TemporalMetadataStatus.VALID: 1.0,
        TemporalMetadataStatus.LIMITED_PRECISION: 0.75,
        TemporalMetadataStatus.TIMEZONE_NAIVE: 0.6,
    }
    temporal_score = sum(
        temporal_scores.get(metadata.metadata_quality, 0.0)
        for metadata in (temporal_a, temporal_b)
    ) / 2
    spatial_score = {
        CompatibilityStatus.COMPATIBLE.value: 1.0,
        CompatibilityStatus.UNKNOWN.value: 0.5,
        CompatibilityStatus.DIFFERENT.value: 0.25,
    }
    sensor_score = 1.0 if sensor_status == CompatibilityStatus.SUPPORTED.value else 0.5
    reference_score = sum(
        {ImageReferenceStatus.LOCAL_AVAILABLE: 1.0, ImageReferenceStatus.EXTERNAL_REFERENCE: 0.8, ImageReferenceStatus.UNAVAILABLE: 0.25, ImageReferenceStatus.UNKNOWN: 0.5, ImageReferenceStatus.INVALID: 0.0}[status]
        for status in (reference_a, reference_b)
    ) / 2
    score = (
        temporal_score + spatial_score.get(footprint_status, 0.5) +
        spatial_score.get(crs_status, 0.5) + sensor_score + reference_score + completeness
    ) / 6
    return round(score * 100, 3)


@dataclass(frozen=True)
class PairSelectionResult:
    """Explainable eligibility result for one candidate observation pair."""

    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    eligibility: PairEligibility
    hard_rejection_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    candidate_selection_score: Optional[float]
    temporal_metadata: Optional[TemporalPairView]
    crs_compatibility: str
    footprint_compatibility: str
    sensor_compatibility: str
    image_reference_a: ImageReferenceStatus
    image_reference_b: ImageReferenceStatus
    metadata_completeness: float
    provenance_status: str

    @property
    def eligible(self) -> bool:
        return self.eligibility is PairEligibility.ELIGIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "eligibility": self.eligibility.value,
            "hard_rejection_reasons": list(self.hard_rejection_reasons),
            "warnings": list(self.warnings),
            "candidate_selection_score": self.candidate_selection_score,
            "temporal_metadata": self.temporal_metadata.to_dict() if self.temporal_metadata else None,
            "crs_compatibility": self.crs_compatibility,
            "footprint_compatibility": self.footprint_compatibility,
            "sensor_compatibility": self.sensor_compatibility,
            "image_reference_a": self.image_reference_a.value,
            "image_reference_b": self.image_reference_b.value,
            "metadata_completeness": self.metadata_completeness,
            "provenance_status": self.provenance_status,
        }


def evaluate_pair(
    observation_a: Optional[LunarObservation],
    observation_b: Optional[LunarObservation],
) -> PairSelectionResult:
    """Evaluate one pair as an eligible candidate without registration."""
    reasons: list[str] = []
    warnings: list[str] = []
    if observation_a is None or observation_b is None:
        return PairSelectionResult(None, None, PairEligibility.REJECTED, ("missing_observation",), (), None, None, CompatibilityStatus.UNKNOWN.value, CompatibilityStatus.UNKNOWN.value, CompatibilityStatus.UNKNOWN.value, ImageReferenceStatus.INVALID, ImageReferenceStatus.INVALID, 0.0, "unavailable")
    if not isinstance(observation_a, LunarObservation) or not isinstance(observation_b, LunarObservation):
        return PairSelectionResult(None, None, PairEligibility.REJECTED, ("invalid_observation",), (), None, None, CompatibilityStatus.UNKNOWN.value, CompatibilityStatus.UNKNOWN.value, CompatibilityStatus.UNKNOWN.value, ImageReferenceStatus.INVALID, ImageReferenceStatus.INVALID, 0.0, "invalid")

    reference_a = _image_reference_status(observation_a)
    reference_b = _image_reference_status(observation_b)
    if reference_a is ImageReferenceStatus.INVALID or reference_b is ImageReferenceStatus.INVALID:
        reasons.append("invalid_image_reference")
    if observation_a.observation_id == observation_b.observation_id or observation_a.image_reference == observation_b.image_reference:
        reasons.append("same_observation")
    if observation_a.provenance is not DataProvenance.REAL or not observation_a.is_real_data or observation_b.provenance is not DataProvenance.REAL or not observation_b.is_real_data:
        reasons.append("non_real_provenance")

    temporal_a = TemporalMetadata.from_observation(observation_a)
    temporal_b = TemporalMetadata.from_observation(observation_b)
    temporal_view: Optional[TemporalPairView] = None
    if temporal_a.metadata_quality in (TemporalMetadataStatus.MISSING, TemporalMetadataStatus.INVALID):
        reasons.append("missing_temporal_metadata" if temporal_a.metadata_quality is TemporalMetadataStatus.MISSING else "invalid_temporal_metadata")
    if temporal_b.metadata_quality in (TemporalMetadataStatus.MISSING, TemporalMetadataStatus.INVALID):
        reasons.append("missing_temporal_metadata" if temporal_b.metadata_quality is TemporalMetadataStatus.MISSING else "invalid_temporal_metadata")
    if temporal_a.metadata_quality is TemporalMetadataStatus.CONFLICTING or temporal_b.metadata_quality is TemporalMetadataStatus.CONFLICTING:
        reasons.append("conflicting_temporal_metadata")
    if temporal_a.original_timestamp is not None and temporal_b.original_timestamp is not None:
        if temporal_a.normalized_timestamp is not None and temporal_b.normalized_timestamp is not None and temporal_a.normalized_timestamp == temporal_b.normalized_timestamp:
            reasons.append("same_acquisition_instant")
        if temporal_a.precision.value == "date" and temporal_b.precision.value == "date" and temporal_a.acquisition_date == temporal_b.acquisition_date:
            reasons.append("same_acquisition_date")
        if temporal_a.metadata_quality is TemporalMetadataStatus.TIMEZONE_NAIVE or temporal_b.metadata_quality is TemporalMetadataStatus.TIMEZONE_NAIVE:
            warnings.append("timezone_naive_temporal_metadata")
        if temporal_a.metadata_quality is TemporalMetadataStatus.LIMITED_PRECISION or temporal_b.metadata_quality is TemporalMetadataStatus.LIMITED_PRECISION:
            warnings.append("limited_temporal_precision")
        try:
            temporal_view = ObservationPair(observation_a, observation_b).temporal_metadata
        except ObservationContractError:
            pass
    else:
        temporal_view = None

    crs_status, footprint_status, spatial_warnings = _spatial_signals(observation_a, observation_b)
    warnings.extend(spatial_warnings)
    if footprint_status == CompatibilityStatus.DIFFERENT.value and crs_status == CompatibilityStatus.COMPATIBLE.value:
        reasons.append("non_overlapping_footprints")

    sensor_a, sensor_b = _sensor_name(observation_a.source), _sensor_name(observation_b.source)
    if sensor_a is None or sensor_b is None:
        sensor_status = CompatibilityStatus.UNKNOWN.value
        warnings.append("unknown_sensor_combination")
    else:
        sensor_status = CompatibilityStatus.SUPPORTED.value
    if reference_a is ImageReferenceStatus.UNKNOWN or reference_b is ImageReferenceStatus.UNKNOWN:
        warnings.append("image_reference_availability_unknown")
    if reference_a is ImageReferenceStatus.UNAVAILABLE or reference_b is ImageReferenceStatus.UNAVAILABLE:
        warnings.append("image_reference_unavailable")
    if reference_a is ImageReferenceStatus.EXTERNAL_REFERENCE or reference_b is ImageReferenceStatus.EXTERNAL_REFERENCE:
        warnings.append("external_image_reference")
    completeness = round((_metadata_completeness(observation_a) + _metadata_completeness(observation_b)) / 2, 3)
    if completeness < 1.0:
        warnings.append("optional_metadata_missing")
    if observation_a.gsd_m is not None and observation_b.gsd_m is not None and observation_a.gsd_m != observation_b.gsd_m:
        warnings.append("different_gsd")
    if observation_a.dimensions is not None and observation_b.dimensions is not None and observation_a.dimensions != observation_b.dimensions:
        warnings.append("different_dimensions")
    provenance_status = "real" if not "non_real_provenance" in reasons else "non_real"
    eligible = not reasons
    score = _candidate_score(temporal_a, temporal_b, crs_status, footprint_status, sensor_status, reference_a, reference_b, completeness) if eligible else None
    return PairSelectionResult(
        observation_a.observation_id, observation_b.observation_id,
        PairEligibility.ELIGIBLE if eligible else PairEligibility.REJECTED,
        tuple(dict.fromkeys(reasons)), tuple(dict.fromkeys(warnings)), score,
        temporal_view, crs_status, footprint_status, sensor_status,
        reference_a, reference_b, completeness, provenance_status,
    )


def select_candidate_pairs(
    observations: Iterable[LunarObservation],
) -> list[PairSelectionResult]:
    """Return unique eligible candidates in deterministic identity order."""
    unique: dict[tuple[str, str], LunarObservation] = {}
    for observation in observations:
        if isinstance(observation, LunarObservation):
            unique.setdefault((observation.observation_id, observation.image_reference), observation)
    ordered = [unique[key] for key in sorted(unique)]
    results = [evaluate_pair(first, second) for index, first in enumerate(ordered) for second in ordered[index + 1:]]
    return [result for result in results if result.eligible]