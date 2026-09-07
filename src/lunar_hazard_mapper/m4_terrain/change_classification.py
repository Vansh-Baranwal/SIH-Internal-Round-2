"""M4 Phase 10.9 deterministic, observational change classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import ndimage

from .change_candidate_detection import ChangeCandidateResult, ChangeCandidateStatus
from .noise_suppression import NoiseSuppressionResult, NoiseSuppressionStatus


class ChangeClassificationStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    INVALID_CANDIDATE_INPUT = "invalid_candidate_input"
    MISSING_CANDIDATE_ARTIFACT = "missing_candidate_artifact"
    INVALID_CANDIDATE_ARTIFACT = "invalid_candidate_artifact"
    SHAPE_MISMATCH = "shape_mismatch"
    INVALID_PIXEL_DATA = "invalid_pixel_data"
    UNDETERMINED_CLASSIFICATION = "undetermined_classification"
    CLASSIFICATION_FAILED = "classification_failed"


@dataclass(frozen=True)
class ChangeClassificationConfig:
    output_dir: Path
    sign_dominance_fraction: float = 0.75
    neutral_sign_fraction: float = 0.20
    minimum_classifiable_pixels: int = 3
    compactness_threshold: float = 0.65
    elongated_aspect_ratio: float = 3.0
    diffuse_extent_threshold: float = 0.45

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        for name in ("sign_dominance_fraction", "neutral_sign_fraction", "compactness_threshold", "diffuse_extent_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"{name} must be finite and between zero and one")
        if self.sign_dominance_fraction <= 0.5:
            raise ValueError("sign_dominance_fraction must exceed 0.5")
        if self.minimum_classifiable_pixels < 1:
            raise ValueError("minimum_classifiable_pixels must be positive")
        if self.elongated_aspect_ratio < 1 or not np.isfinite(self.elongated_aspect_ratio):
            raise ValueError("elongated_aspect_ratio must be finite and at least one")


@dataclass(frozen=True)
class ChangeClassificationRequest:
    candidate_result: ChangeCandidateResult
    noise_result: NoiseSuppressionResult
    config: ChangeClassificationConfig


@dataclass(frozen=True)
class ChangeClassification:
    candidate_id: str
    primary_classification: str
    secondary_characteristics: tuple[str, ...]
    sign_response: dict[str, Any]
    morphology: dict[str, Any]
    intensity: dict[str, Any]
    geometry: dict[str, Any]
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.__dict__)
        result["secondary_characteristics"] = list(self.secondary_characteristics)
        return result


@dataclass(frozen=True)
class ChangeClassificationResult:
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    upstream_candidate_status: Optional[str]
    status: ChangeClassificationStatus
    candidate_mask_reference: Optional[str]
    candidate_labels_reference: Optional[str]
    classified_candidates_reference: Optional[str]
    summary_reference: Optional[str]
    candidate_count: int
    classifications: tuple[ChangeClassification, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "upstream_candidate_status": self.upstream_candidate_status,
            "status": self.status.value,
            "candidate_mask_reference": self.candidate_mask_reference,
            "candidate_labels_reference": self.candidate_labels_reference,
            "classified_candidates_reference": self.classified_candidates_reference,
            "summary_reference": self.summary_reference,
            "candidate_count": self.candidate_count,
            "classifications": [item.to_dict() for item in self.classifications],
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }


def _result(request: ChangeClassificationRequest, status: ChangeClassificationStatus, reason: str = "", message: str = "") -> ChangeClassificationResult:
    candidate = request.candidate_result
    return ChangeClassificationResult(
        candidate.observation_a_id, candidate.observation_b_id,
        getattr(candidate.status, "value", None), status, candidate.candidate_mask_reference,
        candidate.candidate_labels_reference, None, None, 0, (), (), (reason,) if reason else (),
        {"phase": "m4_10.9", "upstream_phase": "m4_10.8", "scientific_interpretation": "observable algorithmic classification only"}, message,
    )


def _load(path: Optional[str]) -> np.ndarray:
    if not path:
        raise FileNotFoundError(path)
    return np.load(path, allow_pickle=False)


def _classify_sign(values: np.ndarray, config: ChangeClassificationConfig) -> tuple[str, dict[str, Any]]:
    positive = int(np.count_nonzero(values > 0))
    negative = int(np.count_nonzero(values < 0))
    zero = int(values.size - positive - negative)
    positive_fraction = positive / values.size
    negative_fraction = negative / values.size
    if positive_fraction >= config.sign_dominance_fraction:
        label = "POSITIVE_DOMINANT"
    elif negative_fraction >= config.sign_dominance_fraction:
        label = "NEGATIVE_DOMINANT"
    elif positive_fraction >= config.neutral_sign_fraction and negative_fraction >= config.neutral_sign_fraction:
        label = "MIXED_SIGN"
    else:
        label = "NEUTRAL_LOW_SIGN"
    return label, {
        "positive_pixel_count": positive, "negative_pixel_count": negative, "zero_pixel_count": zero,
        "positive_fraction": float(positive_fraction), "negative_fraction": float(negative_fraction),
        "signed_mean": float(np.mean(values)), "signed_median": float(np.median(values)),
        "signed_minimum": float(np.min(values)), "signed_maximum": float(np.max(values)),
    }


def _geometry(coordinates: np.ndarray, shape: tuple[int, int], config: ChangeClassificationConfig) -> tuple[str, tuple[str, ...], dict[str, Any], dict[str, Any]]:
    rows, columns = coordinates[:, 0], coordinates[:, 1]
    min_row, max_row, min_col, max_col = map(int, (rows.min(), rows.max(), columns.min(), columns.max()))
    width, height = max_col - min_col + 1, max_row - min_row + 1
    component = np.zeros(shape, dtype=bool)
    component[rows, columns] = True
    perimeter = int(np.count_nonzero(component & ~ndimage.binary_erosion(component, structure=np.ones((3, 3), dtype=bool))))
    compactness = float(4 * np.pi * len(rows) / perimeter ** 2) if perimeter else None
    extent = float(len(rows) / (width * height))
    aspect_ratio = float(max(width, height) / min(width, height))
    touches = min_row == 0 or min_col == 0 or max_row == shape[0] - 1 or max_col == shape[1] - 1
    if compactness is None:
        morphology_class = "UNKNOWN"
    elif aspect_ratio >= config.elongated_aspect_ratio:
        morphology_class = "ELONGATED"
    elif extent <= config.diffuse_extent_threshold:
        morphology_class = "DIFFUSE"
    elif compactness >= config.compactness_threshold:
        morphology_class = "COMPACT"
    else:
        morphology_class = "IRREGULAR"
    secondary = [morphology_class]
    if touches:
        secondary.append("EDGE_LIKE")
    if len(rows) >= 3:
        secondary.append("SPATIAL_CLUSTER")
    morphology = {"classification": morphology_class, "pixel_area": len(rows), "perimeter_pixels": perimeter, "compactness": compactness, "extent": extent, "aspect_ratio": aspect_ratio}
    geometry = {"bounding_box": {"min_row": min_row, "min_col": min_col, "max_row": max_row, "max_col": max_col}, "centroid": {"row": float(np.mean(rows)), "col": float(np.mean(columns))}, "image_shape": list(shape), "touches_image_boundary": touches}
    return morphology_class, tuple(secondary), morphology, geometry


def classify_change_candidates(request: ChangeClassificationRequest) -> ChangeClassificationResult:
    """Classify only the components supplied by Phase 10.8."""
    candidate = request.candidate_result
    noise = request.noise_result
    config = request.config
    if not isinstance(candidate, ChangeCandidateResult) or candidate.status not in (ChangeCandidateStatus.SUCCESS, ChangeCandidateStatus.NO_CANDIDATES):
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_INPUT, "invalid_candidate_input", "A successful or empty Phase 10.8 result is required.")
    if not isinstance(noise, NoiseSuppressionResult) or noise.status is not NoiseSuppressionStatus.SUCCESS:
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_INPUT, "invalid_noise_input", "A successful Phase 10.7 result is required for classification inputs.")
    if candidate.observation_a_id != noise.observation_a_id or candidate.observation_b_id != noise.observation_b_id:
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_INPUT, "observation_id_mismatch", "Observation IDs must match across phases.")
    try:
        mask = _load(candidate.candidate_mask_reference)
        labels = _load(candidate.candidate_labels_reference)
        signed = _load(noise.suppressed_signed_difference_reference)
        absolute = _load(noise.suppressed_absolute_difference_reference)
        valid = _load(noise.propagated_valid_mask_reference)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return _result(request, ChangeClassificationStatus.MISSING_CANDIDATE_ARTIFACT, "missing_artifact", "Required Phase 10.7/10.8 artifacts could not be loaded.")
    if mask.ndim != 2 or labels.shape != mask.shape or signed.shape != mask.shape or absolute.shape != mask.shape or valid.shape != mask.shape:
        return _result(request, ChangeClassificationStatus.SHAPE_MISMATCH, "shape_mismatch", "Candidate and upstream arrays must have identical two-dimensional shapes.")
    if mask.dtype != np.uint8 or labels.dtype.kind not in "iu" or valid.dtype != np.bool_ or signed.dtype.kind not in "fiu" or absolute.dtype.kind not in "fiu" or np.any(~np.isin(mask, [0, 1, 2])) or np.any(labels < 0):
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_ARTIFACT, "invalid_mask_or_labels", "Candidate mask and labels violate the Phase 10.8 representation.")
    finite = valid & np.isfinite(signed) & np.isfinite(absolute)
    if np.any(absolute[finite] < 0) or np.any(mask[~valid] != 0) or np.any(mask[valid & ~finite] != 0) or np.any((mask == 2) & (~finite)):
        return _result(request, ChangeClassificationStatus.INVALID_PIXEL_DATA, "invalid_candidate_pixels", "Candidate pixels must be valid and finite with non-negative absolute differences.")
    candidate_pixels = mask == 2
    if np.any((labels > 0) != candidate_pixels) or np.any(labels[candidate_pixels] == 0):
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_ARTIFACT, "label_mask_inconsistency", "Positive labels must correspond exactly to mask value 2.")
    label_ids = sorted(int(value) for value in np.unique(labels) if value > 0)
    if label_ids != list(range(1, len(label_ids) + 1)) or len(label_ids) != candidate.candidate_count:
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_ARTIFACT, "candidate_label_integrity", "Candidate labels must be contiguous and match the Phase 10.8 candidate count.")
    if len(candidate.candidates) != len(label_ids) or [item.candidate_id for item in candidate.candidates] != [f"candidate-{value:04d}" for value in label_ids]:
        return _result(request, ChangeClassificationStatus.INVALID_CANDIDATE_ARTIFACT, "candidate_record_integrity", "Candidate records do not match authoritative label IDs.")
    classifications: list[ChangeClassification] = []
    for label_id in label_ids:
        coordinates = np.argwhere(labels == label_id)
        if len(coordinates) < config.minimum_classifiable_pixels:
            sign_label, sign_stats = "UNDETERMINED", {"valid_pixel_count": int(len(coordinates))}
            morphology_class, secondary, morphology, geometry = "UNKNOWN", ("UNKNOWN",), {}, {}
            intensity = {}
        else:
            sign_values, absolute_values = signed[labels == label_id], absolute[labels == label_id]
            sign_label, sign_stats = _classify_sign(sign_values, config)
            morphology_class, secondary, morphology, geometry = _geometry(coordinates, mask.shape, config)
            intensity = {"mean_absolute_difference": float(np.mean(absolute_values)), "median_absolute_difference": float(np.median(absolute_values)), "std_absolute_difference": float(np.std(absolute_values)), "minimum_absolute_difference": float(np.min(absolute_values)), "maximum_absolute_difference": float(np.max(absolute_values)), "percentile_90_absolute_difference": float(np.percentile(absolute_values, 90))}
        classifications.append(ChangeClassification(f"candidate-{label_id:04d}", sign_label, secondary, sign_stats, morphology, intensity, geometry, candidate.observation_a_id, candidate.observation_b_id))
    status = ChangeClassificationStatus.SUCCESS if classifications else ChangeClassificationStatus.NO_CANDIDATES
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    classified_path, summary_path = output_dir / "classified_candidates.json", output_dir / "change_classification_summary.json"
    provenance = {"phase": "m4_10.9", "upstream_phase": "m4_10.8", "upstream_provenance": candidate.provenance, "input_artifacts": {"candidate_mask": candidate.candidate_mask_reference, "candidate_labels": candidate.candidate_labels_reference, "signed_difference": noise.suppressed_signed_difference_reference, "absolute_difference": noise.suppressed_absolute_difference_reference, "valid_mask": noise.propagated_valid_mask_reference}, "method": "deterministic sign response and image-space morphology", "thresholds": {"sign_dominance_fraction": config.sign_dominance_fraction, "neutral_sign_fraction": config.neutral_sign_fraction, "minimum_classifiable_pixels": config.minimum_classifiable_pixels, "compactness_threshold": config.compactness_threshold, "elongated_aspect_ratio": config.elongated_aspect_ratio, "diffuse_extent_threshold": config.diffuse_extent_threshold}, "limitations": ["Classification describes observable temporal-difference characteristics and does not confirm physical lunar change.", "Thresholds are engineering descriptors, not scientific calibration."]}
    result = ChangeClassificationResult(candidate.observation_a_id, candidate.observation_b_id, candidate.status.value, status, candidate.candidate_mask_reference, candidate.candidate_labels_reference, str(classified_path), str(summary_path), len(classifications), tuple(classifications), ("signed_response_is_not_physical_interpretation",), (), provenance, "Observable algorithmic classification only; no physical lunar change determination was performed.")
    classified_path.write_text(json.dumps([item.to_dict() for item in classifications], indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result


class ChangeClassificationError(ValueError):
    """Reserved public error type for invalid classification requests."""