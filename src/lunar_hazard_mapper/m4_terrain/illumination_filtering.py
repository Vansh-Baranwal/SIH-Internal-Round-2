"""M4 Phase 10.6 conservative illumination-aware difference filtering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .image_differencing import ImageDifferenceResult, DifferenceStatus
from .temporal_observation import ObservationPair


class IlluminationAssessmentStatus(str, Enum):
    COMPARABLE = "comparable"
    DIFFERENT = "different"
    UNKNOWN = "unknown"
    INSUFFICIENT_METADATA = "insufficient_metadata"


class IlluminationFilterStatus(str, Enum):
    SUCCESS = "success"
    INSUFFICIENT_ILLUMINATION_MODEL = "insufficient_illumination_model"
    INVALID_DIFFERENCE_INPUT = "invalid_difference_input"
    MISSING_DIFFERENCE_ARTIFACT = "missing_difference_artifact"
    INVALID_DIFFERENCE_ARTIFACT = "invalid_difference_artifact"
    SHAPE_MISMATCH = "shape_mismatch"
    FILTERING_FAILED = "filtering_failed"


@dataclass(frozen=True)
class IlluminationFilterConfig:
    """Explicit metadata-gate tolerances; these are engineering heuristics."""

    output_dir: Path
    sun_azimuth_tolerance_deg: float = 0.0
    sun_elevation_tolerance_deg: float = 0.0
    phase_angle_tolerance_deg: float = 0.0
    incidence_angle_tolerance_deg: float = 0.0
    emission_angle_tolerance_deg: float = 0.0
    filter_different_geometry: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if not isinstance(self.filter_different_geometry, bool):
            raise ValueError("filter_different_geometry must be a boolean")
        for field_name in (
            "sun_azimuth_tolerance_deg", "sun_elevation_tolerance_deg",
            "phase_angle_tolerance_deg", "incidence_angle_tolerance_deg",
            "emission_angle_tolerance_deg",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
                raise ValueError(f"{field_name} must be a finite non-negative number")


@dataclass(frozen=True)
class IlluminationAssessment:
    """Observable illumination compatibility evidence, not change confidence."""

    status: IlluminationAssessmentStatus
    angular_differences_deg: dict[str, Optional[float]]
    available_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    view_geometry_available: bool
    warnings: tuple[str, ...]
    method: str = "metadata_gate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "angular_differences_deg": self.angular_differences_deg,
            "available_fields": list(self.available_fields),
            "missing_fields": list(self.missing_fields),
            "view_geometry_available": self.view_geometry_available,
            "warnings": list(self.warnings),
            "method": self.method,
        }


@dataclass(frozen=True)
class IlluminationFilterRequest:
    """Phase 10.6 input referencing Phase 10.5 output and its observation pair."""

    difference_result: ImageDifferenceResult
    pair: ObservationPair
    config: IlluminationFilterConfig


@dataclass(frozen=True)
class IlluminationFilterResult:
    """Raw-preserving illumination-gated difference result for Phase 10.7."""

    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    difference_status: Optional[str]
    status: IlluminationFilterStatus
    assessment: IlluminationAssessment
    raw_signed_difference_reference: Optional[str]
    raw_absolute_difference_reference: Optional[str]
    raw_valid_mask_reference: Optional[str]
    filtered_signed_difference_reference: Optional[str]
    filtered_absolute_difference_reference: Optional[str]
    illumination_mask_reference: Optional[str]
    before_statistics: dict[str, Optional[float]]
    after_statistics: dict[str, Optional[float]]
    illumination_compatible_count: int
    illumination_excluded_count: int
    retained_fraction: float
    normalization_method: Optional[str]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        status_value = self.status.value if hasattr(self.status, "value") else str(self.status)
        assessment_payload = self.assessment.to_dict() if hasattr(self.assessment, "to_dict") else self.assessment
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "difference_status": self.difference_status,
            "status": status_value,
            "assessment": assessment_payload,
            "raw_signed_difference_reference": self.raw_signed_difference_reference,
            "raw_absolute_difference_reference": self.raw_absolute_difference_reference,
            "raw_valid_mask_reference": self.raw_valid_mask_reference,
            "filtered_signed_difference_reference": self.filtered_signed_difference_reference,
            "filtered_absolute_difference_reference": self.filtered_absolute_difference_reference,
            "illumination_mask_reference": self.illumination_mask_reference,
            "before_statistics": self.before_statistics,
            "after_statistics": self.after_statistics,
            "illumination_compatible_count": self.illumination_compatible_count,
            "illumination_excluded_count": self.illumination_excluded_count,
            "retained_fraction": self.retained_fraction,
            "normalization_method": self.normalization_method,
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }


_ANGLE_FIELDS = (
    ("sun_azimuth_deg", "sun_azimuth_tolerance_deg"),
    ("sun_elevation_deg", "sun_elevation_tolerance_deg"),
    ("phase_angle_deg", "phase_angle_tolerance_deg"),
    ("incidence_angle_deg", "incidence_angle_tolerance_deg"),
    ("emission_angle_deg", "emission_angle_tolerance_deg"),
)


def angular_difference_deg(first: Optional[float], second: Optional[float], *, circular: bool = False) -> Optional[float]:
    """Return an angular difference, preserving ``None`` for missing metadata."""
    if first is None or second is None:
        return None
    difference = abs(float(first) - float(second))
    return min(difference, 360.0 - difference) if circular else difference


def assess_illumination(pair: ObservationPair, config: IlluminationFilterConfig) -> IlluminationAssessment:
    first, second = pair.observation_a, pair.observation_b
    differences: dict[str, Optional[float]] = {}
    available: list[str] = []
    missing: list[str] = []
    exceeds = False
    for field_name, tolerance_field in _ANGLE_FIELDS:
        first_value, second_value = getattr(first, field_name), getattr(second, field_name)
        difference = angular_difference_deg(first_value, second_value, circular=field_name == "sun_azimuth_deg")
        differences[field_name] = difference
        if difference is None:
            missing.append(field_name)
        else:
            available.append(field_name)
            if difference > getattr(config, tolerance_field):
                exceeds = True
    view_available = first.view_geometry is not None and second.view_geometry is not None
    warnings: list[str] = []
    if not view_available:
        warnings.append("view_geometry_unavailable")
    if not available:
        status = IlluminationAssessmentStatus.INSUFFICIENT_METADATA
    elif missing:
        status = IlluminationAssessmentStatus.UNKNOWN
        warnings.append("illumination_metadata_incomplete")
    elif exceeds:
        status = IlluminationAssessmentStatus.DIFFERENT
    else:
        status = IlluminationAssessmentStatus.COMPARABLE
    return IlluminationAssessment(status, differences, tuple(available), tuple(missing), view_available, tuple(warnings))


def _stats(values: np.ndarray) -> dict[str, Optional[float]]:
    if values.size == 0:
        return {"valid_count": 0, "mean_absolute_difference": None, "median_absolute_difference": None, "std_absolute_difference": None}
    absolute = np.abs(values)
    return {
        "valid_count": int(values.size),
        "mean_absolute_difference": float(np.mean(absolute)),
        "median_absolute_difference": float(np.median(absolute)),
        "std_absolute_difference": float(np.std(absolute)),
    }


def _failure(request: IlluminationFilterRequest, status: IlluminationFilterStatus, reason: str, message: str) -> IlluminationFilterResult:
    difference = request.difference_result
    assessment = assess_illumination(request.pair, request.config)
    return IlluminationFilterResult(
        difference.observation_a_id, difference.observation_b_id,
        getattr(difference.status, "value", None), status, assessment,
        difference.signed_difference_reference, difference.absolute_difference_reference,
        difference.valid_mask_reference, None, None, None, {}, {}, 0, 0, 0.0,
        difference.normalization_method, assessment.warnings, (reason,),
        {"phase": "m4_10.6", "method": "metadata_gate", "raw_difference_preserved": True}, message,
    )


def filter_illumination(request: IlluminationFilterRequest) -> IlluminationFilterResult:
    """Apply only a conservative metadata compatibility gate to 10.5 output."""
    difference = request.difference_result
    if not isinstance(difference, ImageDifferenceResult) or difference.status is not DifferenceStatus.SUCCESS:
        return _failure(request, IlluminationFilterStatus.INVALID_DIFFERENCE_INPUT, "invalid_difference_input", "A successful Phase 10.5 difference result is required.")
    if (difference.observation_a_id != request.pair.observation_a.observation_id or
            difference.observation_b_id != request.pair.observation_b.observation_id):
        return _failure(request, IlluminationFilterStatus.INVALID_DIFFERENCE_INPUT, "observation_pair_mismatch", "The difference result does not belong to the supplied observation pair.")
    references = (difference.signed_difference_reference, difference.absolute_difference_reference, difference.valid_mask_reference)
    if any(not reference for reference in references):
        return _failure(request, IlluminationFilterStatus.MISSING_DIFFERENCE_ARTIFACT, "missing_difference_artifact", "Phase 10.5 numerical artifacts are required.")
    try:
        signed = np.load(difference.signed_difference_reference, allow_pickle=False)
        absolute = np.load(difference.absolute_difference_reference, allow_pickle=False)
        valid = np.load(difference.valid_mask_reference, allow_pickle=False)
    except (OSError, ValueError, TypeError):
        return _failure(request, IlluminationFilterStatus.INVALID_DIFFERENCE_ARTIFACT, "invalid_difference_artifact", "Phase 10.5 artifacts could not be loaded.")
    if signed.shape != absolute.shape or signed.ndim not in (2, 3) or valid.shape != signed.shape[:2] or valid.dtype != np.bool_:
        return _failure(request, IlluminationFilterStatus.SHAPE_MISMATCH, "shape_mismatch", "Difference arrays and valid mask are not structurally compatible.")
    assessment = assess_illumination(request.pair, request.config)
    raw_values = signed[valid] if signed.ndim == 2 else signed[valid, :].reshape(-1)
    before = _stats(raw_values[np.isfinite(raw_values)])
    if assessment.status in (IlluminationAssessmentStatus.UNKNOWN, IlluminationAssessmentStatus.INSUFFICIENT_METADATA) or (
            assessment.status is IlluminationAssessmentStatus.DIFFERENT and not request.config.filter_different_geometry):
        return IlluminationFilterResult(
            difference.observation_a_id, difference.observation_b_id, difference.status.value,
            IlluminationFilterStatus.INSUFFICIENT_ILLUMINATION_MODEL, assessment,
            difference.signed_difference_reference, difference.absolute_difference_reference, difference.valid_mask_reference,
            None, None, None, before, {}, 0, 0, 0.0, difference.normalization_method,
            assessment.warnings + ("pixel_level_illumination_model_unavailable",), (),
            {"phase": "m4_10.6", "method": "metadata_gate", "raw_difference_preserved": True},
            "No defensible illumination filter was available; raw difference preserved.",
        )
    illumination_mask = np.zeros(valid.shape, dtype=bool) if assessment.status is not IlluminationAssessmentStatus.COMPARABLE else valid.copy()
    effective_valid = valid & illumination_mask
    filtered_signed = signed.astype(np.float64, copy=True)
    filtered_absolute = absolute.astype(np.float64, copy=True)
    filtered_signed[~effective_valid] = np.nan
    filtered_absolute[~effective_valid] = np.nan
    after_values = filtered_signed[effective_valid] if filtered_signed.ndim == 2 else filtered_signed[effective_valid, :].reshape(-1)
    if after_values.size and not np.all(np.isfinite(after_values)):
        return _failure(request, IlluminationFilterStatus.FILTERING_FAILED, "invalid_filtered_pixel_data", "Filtered valid pixels are non-finite.")
    output_dir = request.config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    signed_path = output_dir / "illumination_filtered_signed_difference.npy"
    absolute_path = output_dir / "illumination_filtered_absolute_difference.npy"
    mask_path = output_dir / "illumination_compatibility_mask.npy"
    np.save(signed_path, filtered_signed)
    np.save(absolute_path, filtered_absolute)
    np.save(mask_path, illumination_mask)
    compatible_count = int(np.count_nonzero(effective_valid))
    excluded_count = int(np.count_nonzero(valid & ~illumination_mask))
    result = IlluminationFilterResult(
        difference.observation_a_id, difference.observation_b_id, difference.status.value,
        IlluminationFilterStatus.SUCCESS, assessment,
        difference.signed_difference_reference, difference.absolute_difference_reference, difference.valid_mask_reference,
        str(signed_path), str(absolute_path), str(mask_path), before, _stats(after_values),
        compatible_count, excluded_count, compatible_count / int(np.count_nonzero(valid)) if np.count_nonzero(valid) else 0.0,
        difference.normalization_method,
        assessment.warnings + (("illumination_different_global_gate",) if assessment.status is IlluminationAssessmentStatus.DIFFERENT else ("metadata_gate_only",)),
        (), {"phase": "m4_10.6", "method": "metadata_gate", "raw_difference_preserved": True, "difference_orientation": "registered_A_minus_reference_B"},
        "Illumination metadata gate applied; no physical lunar change determination was performed.",
    )
    (output_dir / "illumination_filter_summary.json").write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result