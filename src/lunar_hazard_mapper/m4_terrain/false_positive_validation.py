"""M4 Phase 10.11 validation for measurable false-positive evidence.

This stage does not confirm change. It only determines whether the authoritative
candidate chain contains evidence that a candidate may be explained by an artifact
or other non-change mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import numpy as np
from scipy import ndimage

from .change_candidate_detection import ChangeCandidateResult
from .change_classification import ChangeClassificationResult
from .crater_ejecta_candidates import CraterEjectaCandidateResult
from .illumination_filtering import IlluminationFilterResult
from .multi_date_registration import TemporalRegistrationResult
from .noise_suppression import NoiseSuppressionResult


class ValidationCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNAVAILABLE = "UNAVAILABLE"


class FalsePositiveCategory(str, Enum):
    REGISTRATION_ARTIFACT = "REGISTRATION_ARTIFACT"
    BOUNDARY_ARTIFACT = "BOUNDARY_ARTIFACT"
    MASK_ARTIFACT = "MASK_ARTIFACT"
    ILLUMINATION_ARTIFACT = "ILLUMINATION_ARTIFACT"
    NOISE_ARTIFACT = "NOISE_ARTIFACT"
    SENSOR_ARTIFACT = "SENSOR_ARTIFACT"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
    METADATA_LIMITATION = "METADATA_LIMITATION"
    PROCESSING_ARTIFACT = "PROCESSING_ARTIFACT"
    NO_FALSE_POSITIVE_EVIDENCE = "NO_FALSE_POSITIVE_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"


class FalsePositiveValidationStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_FALSE_POSITIVE_EVIDENCE = "no_false_positive_evidence"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"
    VALIDATION_BLOCKED = "validation_blocked"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class FalsePositiveValidationConfig:
    output_dir: Path
    inlier_ratio_threshold: float = 0.20
    rmse_threshold: float = 1.0
    spatial_coverage_threshold: float = 0.50
    minimum_support_pixels: int = 9
    minimum_valid_fraction: float = 0.85
    noise_residual_std_threshold: float = 1.0
    boundary_margin: int = 1
    minimum_mask_support_fraction: float = 0.80

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        for name in ("inlier_ratio_threshold", "rmse_threshold", "spatial_coverage_threshold", "minimum_valid_fraction", "noise_residual_std_threshold", "minimum_mask_support_fraction"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if self.minimum_support_pixels < 1:
            raise ValueError("minimum_support_pixels must be positive")
        if self.boundary_margin < 0:
            raise ValueError("boundary_margin must be non-negative")


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: ValidationCheckStatus
    evidence: Any
    threshold: Optional[float] = None
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {"name": self.name, "status": self.status.value, "evidence": self.evidence}
        if self.threshold is not None:
            payload["threshold"] = self.threshold
        payload["interpretation"] = self.interpretation
        return payload


@dataclass(frozen=True)
class CandidateValidationResult:
    source_candidate_id: str
    classification: Optional[str]
    specialized_type: Optional[str]
    overall_status: FalsePositiveValidationStatus
    detected_categories: tuple[FalsePositiveCategory, ...]
    validation_checks: tuple[ValidationCheck, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_candidate_id": self.source_candidate_id,
            "classification": self.classification,
            "specialized_type": self.specialized_type,
            "overall_status": self.overall_status.value,
            "detected_categories": [item.value for item in self.detected_categories],
            "validation_checks": [check.to_dict() for check in self.validation_checks],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "provenance": self.provenance,
            "message": self.message,
        }


@dataclass(frozen=True)
class FalsePositiveValidationRequest:
    specialized_result: CraterEjectaCandidateResult
    classification_result: ChangeClassificationResult
    candidate_result: ChangeCandidateResult
    noise_result: NoiseSuppressionResult
    config: FalsePositiveValidationConfig
    registration_result: Optional[TemporalRegistrationResult] = None
    illumination_result: Optional[IlluminationFilterResult] = None


@dataclass(frozen=True)
class FalsePositiveValidationResult:
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    status: FalsePositiveValidationStatus
    candidate_count: int
    candidates: tuple[CandidateValidationResult, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    summary_reference: Optional[str]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "status": self.status.value,
            "candidate_count": self.candidate_count,
            "candidates": [item.to_dict() for item in self.candidates],
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "summary_reference": self.summary_reference,
            "provenance": self.provenance,
            "message": self.message,
        }


def _safe_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _load(path: Optional[str]) -> np.ndarray:
    if not path:
        raise FileNotFoundError(path)
    return np.load(path, allow_pickle=False)


def _as_bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _candidate_shape(candidate: Any) -> Optional[tuple[int, int]]:
    geometry = getattr(candidate, "geometry", None) or {}
    image_shape = geometry.get("image_shape")
    if isinstance(image_shape, (list, tuple)) and len(image_shape) >= 2:
        return int(image_shape[0]), int(image_shape[1])
    return None


def _touches_image_boundary(candidate: Any, image_shape: Optional[tuple[int, int]]) -> bool:
    geometry = getattr(candidate, "geometry", {}) or {}
    box = geometry.get("bounding_box") or {}
    if not box:
        bounding_box = getattr(candidate, "bounding_box", None)
        if isinstance(bounding_box, dict):
            box = bounding_box
    if image_shape is None:
        min_row = box.get("min_row")
        max_row = box.get("max_row")
        min_col = box.get("min_col")
        max_col = box.get("max_col")
        if min_row is None or max_row is None or min_col is None or max_col is None:
            return False
        return min_row == 0 or min_col == 0 or max_row == max_row or max_col == max_col
    min_row = int(box.get("min_row", 0))
    max_row = int(box.get("max_row", image_shape[0] - 1))
    min_col = int(box.get("min_col", 0))
    max_col = int(box.get("max_col", image_shape[1] - 1))
    return min_row == 0 or min_col == 0 or max_row == image_shape[0] - 1 or max_col == image_shape[1] - 1


def _current_thresholds(config: FalsePositiveValidationConfig) -> dict[str, Any]:
    return {
        "inlier_ratio_threshold": config.inlier_ratio_threshold,
        "rmse_threshold": config.rmse_threshold,
        "spatial_coverage_threshold": config.spatial_coverage_threshold,
        "minimum_support_pixels": config.minimum_support_pixels,
        "minimum_valid_fraction": config.minimum_valid_fraction,
        "noise_residual_std_threshold": config.noise_residual_std_threshold,
        "minimum_mask_support_fraction": config.minimum_mask_support_fraction,
    }


def _assess_registration(registration: Optional[TemporalRegistrationResult], config: FalsePositiveValidationConfig) -> tuple[list[ValidationCheck], list[FalsePositiveCategory], list[str], list[str], bool]:
    checks: list[ValidationCheck] = []
    categories: list[FalsePositiveCategory] = []
    warnings: list[str] = []
    limits: list[str] = []
    if registration is None:
        checks.append(ValidationCheck("registration_quality", ValidationCheckStatus.UNAVAILABLE, "registration_result unavailable", None, "No registration result was supplied for this candidate validation pass."))
        return checks, categories, warnings, limits, False
    if registration.status is not registration.status.SUCCESS:
        checks.append(ValidationCheck("registration_quality", ValidationCheckStatus.UNAVAILABLE, {"status": _safe_status(registration.status), "failure_reasons": list(registration.failure_reasons)}, None, "Registration result not successful; no registration-quality evidence available."))
        return checks, categories, warnings, limits, False
    ratio = registration.inlier_ratio
    if ratio is not None:
        status = ValidationCheckStatus.PASS if ratio >= config.inlier_ratio_threshold else ValidationCheckStatus.FAIL
        evidence = {"inlier_ratio": ratio, "threshold": config.inlier_ratio_threshold}
        threshold = config.inlier_ratio_threshold
        item = ValidationCheck("registration_inlier_ratio", status, evidence, threshold, "Lower inlier ratios indicate weaker alignment and may elevate false-positive risk.")
        checks.append(item)
        if ratio < config.inlier_ratio_threshold:
            categories.append(FalsePositiveCategory.REGISTRATION_ARTIFACT)
            warnings.append("poor_global_registration_quality")
    rmse = registration.registration_rmse
    if rmse is not None:
        status = ValidationCheckStatus.PASS if rmse <= config.rmse_threshold else ValidationCheckStatus.FAIL
        evidence = {"rmse": rmse, "threshold": config.rmse_threshold}
        threshold = config.rmse_threshold
        checks.append(ValidationCheck("registration_rmse", status, evidence, threshold, "Large RMSE indicates registration residuals that may create spurious candidate structure."))
        if rmse > config.rmse_threshold:
            categories.append(FalsePositiveCategory.REGISTRATION_ARTIFACT)
            warnings.append("registration_rmse_above_threshold")
    coverage = registration.spatial_coverage
    if coverage is not None:
        status = ValidationCheckStatus.PASS if coverage >= config.spatial_coverage_threshold else ValidationCheckStatus.FAIL
        evidence = {"spatial_coverage": coverage, "threshold": config.spatial_coverage_threshold}
        checks.append(ValidationCheck("registration_spatial_coverage", status, evidence, config.spatial_coverage_threshold, "Sparse spatial coverage can make local candidate interpretation less reliable."))
        if coverage < config.spatial_coverage_threshold:
            categories.append(FalsePositiveCategory.REGISTRATION_ARTIFACT)
            warnings.append("registration_spatial_coverage_low")
    if getattr(registration, "subpixel_refinement_available", False):
        sub_status = getattr(registration, "subpixel_refinement_status", "unavailable")
        checks.append(ValidationCheck("subpixel_refinement", ValidationCheckStatus.PASS if str(sub_status).lower() in {"executed", "success", "available"} else ValidationCheckStatus.WARN, {"subpixel_refinement_status": str(sub_status)}, None, "Sub-pixel refinement is supporting evidence only and does not guarantee perfect alignment."))
    if not checks:
        checks.append(ValidationCheck("registration_quality", ValidationCheckStatus.UNAVAILABLE, {"status": registration.status.value}, None, "Registration metric fields were not exposed by the upstream contract."))
    return checks, list(dict.fromkeys(categories)), warnings, limits, bool(categories)


def _assess_illumination(illumination: Optional[Any], config: FalsePositiveValidationConfig) -> tuple[list[ValidationCheck], list[FalsePositiveCategory], list[str], list[str], bool]:
    checks: list[ValidationCheck] = []
    categories: list[FalsePositiveCategory] = []
    warnings: list[str] = []
    limits: list[str] = []
    if illumination is None:
        checks.append(ValidationCheck("illumination_metadata", ValidationCheckStatus.UNAVAILABLE, "illumination_result unavailable", None, "No illumination result was supplied."))
        return checks, categories, warnings, limits, False
    status = getattr(illumination, "status", None)
    assessment = getattr(illumination, "assessment", illumination)
    if isinstance(assessment, dict):
        assessment_status = assessment.get("status")
        warnings_list = tuple(assessment.get("warnings", ()))
        missing_fields = tuple(assessment.get("missing_fields", ()))
        available = tuple(assessment.get("available_fields", ()))
    else:
        assessment_status = getattr(assessment, "status", None)
        warnings_list = tuple(getattr(assessment, "warnings", ()))
        missing_fields = tuple(getattr(assessment, "missing_fields", ()))
        available = tuple(getattr(assessment, "available_fields", ()))
    status_label = str(assessment_status) if assessment_status is not None else str(status)
    if status_label in {"unknown", "insufficient_metadata", "INSUFFICIENT_METADATA", "UNKNOWN"}:
        checks.append(ValidationCheck("illumination_metadata", ValidationCheckStatus.WARN, {"status": status_label, "missing_fields": list(missing_fields), "available_fields": list(available)}, None, "Illumination metadata is incomplete or incompatible; candidate validity remains uncertain."))
        categories.append(FalsePositiveCategory.METADATA_LIMITATION)
        warnings.append("illumination_metadata_incomplete")
        limits.append("illumination_metadata_limitations")
        return checks, categories, warnings, limits, True
    if status_label in {"different", "DIFFERENT"}:
        checks.append(ValidationCheck("illumination_geometry", ValidationCheckStatus.FAIL, {"status": status_label, "warnings": list(warnings_list)}, None, "Illumination geometry differs materially and may explain apparent change."))
        categories.append(FalsePositiveCategory.ILLUMINATION_ARTIFACT)
        warnings.append("illumination_geometry_different")
        return checks, categories, warnings, limits, True
    checks.append(ValidationCheck("illumination_geometry", ValidationCheckStatus.PASS, {"status": status_label}, None, "Illumination metadata was sufficiently comparable for this stage."))
    return checks, categories, warnings, limits, False


def _load_valid_mask(noise_result: NoiseSuppressionResult) -> np.ndarray:
    return _load(noise_result.propagated_valid_mask_reference)


def _mask_data_checks(candidate: Any, image_shape: tuple[int, int], valid_mask: np.ndarray, config: FalsePositiveValidationConfig) -> tuple[list[ValidationCheck], list[FalsePositiveCategory], list[str], list[str], bool]:
    checks: list[ValidationCheck] = []
    categories: list[FalsePositiveCategory] = []
    warnings: list[str] = []
    limits: list[str] = []
    geometry = getattr(candidate, "geometry", {}) or {}
    box = geometry.get("bounding_box") or {}
    min_row = int(box.get("min_row", 0))
    max_row = int(box.get("max_row", image_shape[0] - 1))
    min_col = int(box.get("min_col", 0))
    max_col = int(box.get("max_col", image_shape[1] - 1))
    y0, y1 = max(0, min_row - config.boundary_margin), min(image_shape[0], max_row + config.boundary_margin + 1)
    x0, x1 = max(0, min_col - config.boundary_margin), min(image_shape[1], max_col + config.boundary_margin + 1)
    window = valid_mask[y0:y1, x0:x1]
    if window.size == 0:
        checks.append(ValidationCheck("valid_mask_support", ValidationCheckStatus.UNAVAILABLE, {"bounding_box": box}, None, "No valid-mask support was available within the candidate bounding box."))
        return checks, categories, warnings, limits, False
    valid_fraction = float(np.count_nonzero(window)) / float(window.size)
    if valid_fraction < config.minimum_mask_support_fraction:
        categories.append(FalsePositiveCategory.MASK_ARTIFACT)
        warnings.append("candidate_adjoins_invalid_or_masked_pixels")
        checks.append(ValidationCheck("valid_mask_support", ValidationCheckStatus.FAIL, {"valid_fraction": valid_fraction, "threshold": config.minimum_mask_support_fraction}, config.minimum_mask_support_fraction, "Candidate support is dominated by invalid or masked pixels."))
        limits.append("mask_boundary_dependent_support")
        return checks, categories, warnings, limits, True
    checks.append(ValidationCheck("valid_mask_support", ValidationCheckStatus.PASS, {"valid_fraction": valid_fraction, "threshold": config.minimum_mask_support_fraction}, config.minimum_mask_support_fraction, "Candidate lies on predominantly valid support and is not dominated by invalid data."))
    return checks, categories, warnings, limits, False


def _candidate_noise_and_support(candidate: Any, noise_result: NoiseSuppressionResult, config: FalsePositiveValidationConfig) -> tuple[list[ValidationCheck], list[FalsePositiveCategory], list[str], list[str], bool]:
    checks: list[ValidationCheck] = []
    categories: list[FalsePositiveCategory] = []
    warnings: list[str] = []
    limits: list[str] = []
    metric = getattr(candidate, "geometry", {}) or {}
    area = 0
    if isinstance(metric, dict):
        pixel_area = metric.get("pixel_area")
        if pixel_area is not None:
            try:
                area = int(pixel_area)
            except (TypeError, ValueError):
                area = 0
    if area == 0:
        area = int(getattr(candidate, "pixel_count", 0) or 0)
    if area == 0:
        area = int(getattr(candidate, "area", 0) or 0)
    if area < config.minimum_support_pixels:
        checks.append(ValidationCheck("candidate_support", ValidationCheckStatus.FAIL, {"pixel_area": area, "threshold": config.minimum_support_pixels}, config.minimum_support_pixels, "Candidate support is too small to distinguish from residual noise or isolated artifacts."))
        categories.append(FalsePositiveCategory.INSUFFICIENT_SUPPORT)
        warnings.append("insufficient_spatial_support")
        limits.append("candidate_support_below_threshold")
        return checks, categories, warnings, limits, True
    checks.append(ValidationCheck("candidate_support", ValidationCheckStatus.PASS, {"pixel_area": area, "threshold": config.minimum_support_pixels}, config.minimum_support_pixels, "Candidate has adequate spatial support for a local validation check."))
    residual_std = getattr(noise_result, "high_frequency_residual_std", None)
    if residual_std is not None and float(residual_std) > config.noise_residual_std_threshold:
        checks.append(ValidationCheck("noise_residual_std", ValidationCheckStatus.WARN, {"high_frequency_residual_std": residual_std, "threshold": config.noise_residual_std_threshold}, config.noise_residual_std_threshold, "Residual local variation remains high and may explain a small or weak candidate."))
        categories.append(FalsePositiveCategory.NOISE_ARTIFACT)
        warnings.append("residual_noise_suspicious")
    else:
        checks.append(ValidationCheck("noise_residual_std", ValidationCheckStatus.PASS, {"high_frequency_residual_std": residual_std}, None, "Residual noise is not elevated beyond the configured engineering threshold."))
    return checks, categories, warnings, limits, bool(categories)


def _classify_candidate(candidate: Any, *, categories: set[FalsePositiveCategory], checks: list[ValidationCheck]) -> FalsePositiveValidationStatus:
    if not categories:
        return FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE
    strong = {FalsePositiveCategory.REGISTRATION_ARTIFACT, FalsePositiveCategory.BOUNDARY_ARTIFACT, FalsePositiveCategory.MASK_ARTIFACT, FalsePositiveCategory.NOISE_ARTIFACT, FalsePositiveCategory.INSUFFICIENT_SUPPORT, FalsePositiveCategory.PROCESSING_ARTIFACT, FalsePositiveCategory.SENSOR_ARTIFACT}
    if categories.intersection(strong):
        return FalsePositiveValidationStatus.FALSE_POSITIVE if len(categories.intersection(strong)) >= 2 else FalsePositiveValidationStatus.LIKELY_FALSE_POSITIVE
    if categories.intersection({FalsePositiveCategory.METADATA_LIMITATION, FalsePositiveCategory.INCONCLUSIVE, FalsePositiveCategory.UNAVAILABLE}):
        return FalsePositiveValidationStatus.INCONCLUSIVE
    return FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE


def _fallback_candidate_records(candidate_result: ChangeCandidateResult, noise_result: NoiseSuppressionResult) -> tuple[Any, ...]:
    if getattr(candidate_result, "candidates", ()):
        return tuple(candidate_result.candidates)
    try:
        absolute = np.load(noise_result.suppressed_absolute_difference_reference, allow_pickle=False)
        valid = np.load(noise_result.propagated_valid_mask_reference, allow_pickle=False)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return ()
    if absolute.size == 0 or valid.shape != absolute.shape:
        return ()
    threshold = float(getattr(candidate_result, "threshold", 0.0) or 0.0)
    if threshold <= 0:
        finite = np.isfinite(absolute)
        if not np.any(finite):
            return ()
        threshold = float(np.nanmax(np.abs(absolute[finite]))) * 0.5 if np.any(finite) else 0.0
    signal = np.abs(absolute) >= max(threshold, 1e-9)
    if not np.any(signal):
        return ()
    labels, count = ndimage.label(signal, structure=np.ones((3, 3), dtype=bool))
    if count == 0:
        return ()
    records: list[Any] = []
    for label_id in range(1, count + 1):
        coords = np.argwhere(labels == label_id)
        if coords.size == 0:
            continue
        rows, cols = coords[:, 0], coords[:, 1]
        records.append(SimpleNamespace(
            source_candidate_id=f"candidate-{label_id:04d}",
            candidate_id=f"candidate-{label_id:04d}",
            candidate_type=None,
            geometry={
                "bounding_box": {
                    "min_row": int(rows.min()),
                    "min_col": int(cols.min()),
                    "max_row": int(rows.max()),
                    "max_col": int(cols.max()),
                },
                "image_shape": list(absolute.shape),
            },
            supporting_indicators=(),
            limitations=(),
            pixel_count=int(coords.shape[0]),
        ))
    return tuple(records)


def _build_request_failure(status: FalsePositiveValidationStatus, reason: str, message: str, *, candidate_result: Optional[ChangeCandidateResult] = None, classification_result: Optional[ChangeClassificationResult] = None, specialized_result: Optional[CraterEjectaCandidateResult] = None, noise_result: Optional[NoiseSuppressionResult] = None) -> FalsePositiveValidationResult:
    obs_a = getattr(candidate_result, "observation_a_id", None) or getattr(classification_result, "observation_a_id", None) or getattr(specialized_result, "observation_a_id", None) or getattr(noise_result, "observation_a_id", None)
    obs_b = getattr(candidate_result, "observation_b_id", None) or getattr(classification_result, "observation_b_id", None) or getattr(specialized_result, "observation_b_id", None) or getattr(noise_result, "observation_b_id", None)
    return FalsePositiveValidationResult(
        observation_a_id=obs_a,
        observation_b_id=obs_b,
        status=status,
        candidate_count=0,
        candidates=(),
        warnings=(reason,),
        failure_reasons=(reason,),
        summary_reference=None,
        provenance={"phase": "m4_10.11", "upstream_phase": "m4_10.10", "scientific_interpretation": "false-positive validation only; later final validation remains required."},
        message=message,
    )


def validate_false_positives(request: FalsePositiveValidationRequest) -> FalsePositiveValidationResult:
    """Validate authoritative Phase 10.8-10.10 candidates for measurable false-positive evidence."""
    specialized = request.specialized_result
    classification = request.classification_result
    candidate = request.candidate_result
    noise = request.noise_result
    config = request.config
    if not isinstance(specialized, CraterEjectaCandidateResult):
        return _build_request_failure(FalsePositiveValidationStatus.INVALID_INPUT, "invalid_specialized_result", "A valid Phase 10.10 result is required.")
    if not isinstance(classification, ChangeClassificationResult):
        return _build_request_failure(FalsePositiveValidationStatus.INVALID_INPUT, "invalid_classification_result", "A valid Phase 10.9 result is required.", candidate_result=candidate, specialized_result=specialized, noise_result=noise)
    if not isinstance(candidate, ChangeCandidateResult):
        return _build_request_failure(FalsePositiveValidationStatus.INVALID_INPUT, "invalid_candidate_result", "A valid Phase 10.8 result is required.", classification_result=classification, specialized_result=specialized, noise_result=noise)
    if not isinstance(noise, NoiseSuppressionResult):
        return _build_request_failure(FalsePositiveValidationStatus.INVALID_INPUT, "invalid_noise_result", "A valid Phase 10.7 result is required.", candidate_result=candidate, classification_result=classification, specialized_result=specialized)
    if specialized.observation_a_id != candidate.observation_a_id or specialized.observation_b_id != candidate.observation_b_id or specialized.observation_a_id != noise.observation_a_id or specialized.observation_b_id != noise.observation_b_id:
        return _build_request_failure(FalsePositiveValidationStatus.INVALID_INPUT, "observation_id_mismatch", "Observation IDs must match across the authoritative candidate chain.", candidate_result=candidate, classification_result=classification, specialized_result=specialized, noise_result=noise)
    fallback_records = _fallback_candidate_records(candidate, noise)
    if specialized.candidate_count == 0 and getattr(candidate, "candidate_count", 0) == 0 and not fallback_records:
        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "false_positive_validation_summary.json"
        summary = FalsePositiveValidationResult(
            observation_a_id=specialized.observation_a_id,
            observation_b_id=specialized.observation_b_id,
            status=FalsePositiveValidationStatus.NO_CANDIDATES,
            candidate_count=0,
            candidates=(),
            warnings=("no_authoritative_candidates",),
            failure_reasons=(),
            summary_reference=str(summary_path),
            provenance={"phase": "m4_10.11", "upstream_phase": "m4_10.10", "scientific_interpretation": "false-positive validation only; later final validation remains required.", "input_artifacts": {"candidate_mask": candidate.candidate_mask_reference, "candidate_labels": candidate.candidate_labels_reference, "noise_signed": noise.suppressed_signed_difference_reference, "noise_absolute": noise.suppressed_absolute_difference_reference, "valid_mask": noise.propagated_valid_mask_reference}, "thresholds": _current_thresholds(config)},
            message="No authoritative temporal candidates were supplied for false-positive validation.",
        )
        summary_path.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
        return summary
    results: list[CandidateValidationResult] = []
    valid_mask = _load(valid_mask_path) if (valid_mask_path := noise.propagated_valid_mask_reference) else np.array([], dtype=bool)
    image_shape = tuple(noise.image_shape) if noise.image_shape else None
    candidate_records = tuple(specialized.candidates) if specialized.candidates else tuple(candidate.candidates) if getattr(candidate, "candidates", ()) else fallback_records
    for candidate_record in candidate_records:
        source_id = candidate_record.source_candidate_id
        categories: set[FalsePositiveCategory] = set()
        checks: list[ValidationCheck] = []
        warnings: list[str] = []
        limits: list[str] = []
        if not source_id:
            source_id = "candidate-0000"
        try:
            candidate_array = _load(candidate.candidate_labels_reference)
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return _build_request_failure(FalsePositiveValidationStatus.VALIDATION_BLOCKED, "missing_candidate_artifacts", "Required candidate artifacts were missing during validation.", candidate_result=candidate, classification_result=classification, specialized_result=specialized, noise_result=noise)
        if candidate_array.shape != valid_mask.shape:
            return _build_request_failure(FalsePositiveValidationStatus.VALIDATION_BLOCKED, "shape_mismatch", "Candidate and valid-mask arrays must match for false-positive validation.", candidate_result=candidate, classification_result=classification, specialized_result=specialized, noise_result=noise)
        label_id = int(source_id.split("-")[-1]) if source_id and source_id.startswith("candidate-") else 0
        local_mask = candidate_array == label_id if label_id > 0 else np.zeros_like(candidate_array, dtype=bool)
        if not np.any(local_mask):
            local_mask = candidate_array == int(source_id.split("-")[-1]) if source_id.startswith("candidate-") else np.zeros_like(candidate_array, dtype=bool)
        reg_checks, reg_cats, reg_warnings, reg_limits, _ = _assess_registration(request.registration_result, config)
        checks.extend(reg_checks)
        categories.update(reg_cats)
        warnings.extend(reg_warnings)
        limits.extend(reg_limits)
        illum_checks, illum_cats, illum_warnings, illum_limits, _ = _assess_illumination(request.illumination_result, config)
        checks.extend(illum_checks)
        categories.update(illum_cats)
        warnings.extend(illum_warnings)
        limits.extend(illum_limits)
        boundary = _touches_image_boundary(candidate_record, image_shape)
        if boundary or "boundary_truncation_limits_morphology" in candidate_record.limitations:
            checks.append(ValidationCheck("boundary_touch", ValidationCheckStatus.FAIL, {"touches_image_boundary": boundary, "limitations": list(candidate_record.limitations)}, None, "The candidate contacts an image boundary or masked edge, which can create incomplete morphology and false-positive evidence."))
            categories.add(FalsePositiveCategory.BOUNDARY_ARTIFACT)
            warnings.append("candidate_boundary_truncation")
            limits.append("boundary_truncation_limits_morphology")
        else:
            checks.append(ValidationCheck("boundary_touch", ValidationCheckStatus.PASS, {"touches_image_boundary": False}, None, "Candidate geometry is not visibly truncated by the image boundary."))
        support_checks, support_cats, support_warnings, support_limits, _ = _mask_data_checks(candidate_record, image_shape or (0, 0), valid_mask, config)
        checks.extend(support_checks)
        categories.update(support_cats)
        warnings.extend(support_warnings)
        limits.extend(support_limits)
        noise_checks, noise_cats, noise_warnings, noise_limits, _ = _candidate_noise_and_support(candidate_record, noise, config)
        checks.extend(noise_checks)
        categories.update(noise_cats)
        warnings.extend(noise_warnings)
        limits.extend(noise_limits)
        if candidate_record.candidate_type is None:
            candidate_type = None
        else:
            candidate_type = candidate_record.candidate_type.value if hasattr(candidate_record.candidate_type, "value") else str(candidate_record.candidate_type)
        if candidate_record.supporting_indicators and isinstance(candidate_record.supporting_indicators, tuple):
            if any(indicator.lower().endswith("boundary") for indicator in candidate_record.supporting_indicators):
                pass
        if not categories:
            categories.add(FalsePositiveCategory.NO_FALSE_POSITIVE_EVIDENCE)
        detected = tuple(dict.fromkeys(categories))
        overall = _classify_candidate(candidate_record, categories=set(categories), checks=checks)
        result = CandidateValidationResult(
            source_candidate_id=source_id,
            classification=(getattr(classification.classifications, "__iter__", None) and next((item.primary_classification for item in classification.classifications if item.candidate_id == source_id), None)) if classification.classifications else None,
            specialized_type=candidate_type,
            overall_status=overall,
            detected_categories=detected,
            validation_checks=tuple(checks),
            warnings=tuple(dict.fromkeys(warnings)),
            limitations=tuple(dict.fromkeys(limits)),
            observation_a_id=specialized.observation_a_id,
            observation_b_id=specialized.observation_b_id,
            provenance={"phase": "m4_10.11", "upstream_phase": "m4_10.10", "input_artifacts": {"candidate_mask": candidate.candidate_mask_reference, "candidate_labels": candidate.candidate_labels_reference, "noise_signed": noise.suppressed_signed_difference_reference, "noise_absolute": noise.suppressed_absolute_difference_reference, "valid_mask": noise.propagated_valid_mask_reference}, "registration": getattr(request.registration_result, "to_dict", lambda: {})(), "illumination": getattr(request.illumination_result, "to_dict", lambda: {})() if request.illumination_result is not None else None, "thresholds": _current_thresholds(config), "scientific_interpretation": "false-positive validation only; later final validation remains required."},
            message=("Measured false-positive evidence was detected; this does not confirm a physical lunar change." if overall in {FalsePositiveValidationStatus.FALSE_POSITIVE, FalsePositiveValidationStatus.LIKELY_FALSE_POSITIVE} else "No measurable false-positive mechanism was detected in the authoritative input chain; this is not confirmation of physical change." if overall is FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE else "The false-positive validation was inconclusive because available evidence remains incomplete."),
        )
        results.append(result)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "false_positive_validation_summary.json"
    batch_status = FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE
    if not results:
        batch_status = FalsePositiveValidationStatus.NO_CANDIDATES
    elif any(item.overall_status in {FalsePositiveValidationStatus.FALSE_POSITIVE, FalsePositiveValidationStatus.LIKELY_FALSE_POSITIVE} for item in results):
        batch_status = FalsePositiveValidationStatus.FALSE_POSITIVE
    elif any(item.overall_status is FalsePositiveValidationStatus.INCONCLUSIVE for item in results):
        batch_status = FalsePositiveValidationStatus.INCONCLUSIVE
    elif any(item.overall_status is FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE for item in results):
        batch_status = FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE
    result = FalsePositiveValidationResult(
        observation_a_id=specialized.observation_a_id,
        observation_b_id=specialized.observation_b_id,
        status=batch_status,
        candidate_count=len(results),
        candidates=tuple(results),
        warnings=tuple(dict.fromkeys(item for candidate in results for item in candidate.warnings)),
        failure_reasons=(),
        summary_reference=str(summary_path),
        provenance={"phase": "m4_10.11", "upstream_phase": "m4_10.10", "scientific_interpretation": "false-positive validation only; later final validation remains required.", "input_artifacts": {"candidate_mask": candidate.candidate_mask_reference, "candidate_labels": candidate.candidate_labels_reference, "noise_signed": noise.suppressed_signed_difference_reference, "noise_absolute": noise.suppressed_absolute_difference_reference, "valid_mask": noise.propagated_valid_mask_reference}, "thresholds": _current_thresholds(config), "warnings": [warning for candidate in results for warning in candidate.warnings], "limitations": [limitation for candidate in results for limitation in candidate.limitations]},
        message="False-positive validation identifies measurable evidence that may explain a temporal candidate as an artifact. A candidate with no detected false-positive evidence is not thereby confirmed as a physical lunar change. Final validation remains the responsibility of Phase 10.12.",
    )
    summary_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result
