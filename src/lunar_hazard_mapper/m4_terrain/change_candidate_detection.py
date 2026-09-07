"""M4 Phase 10.8 deterministic change-candidate detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import ndimage

from .noise_suppression import NoiseSuppressionResult, NoiseSuppressionStatus


class ChangeCandidateStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_VALID_DATA = "no_valid_data"
    INVALID_NOISE_INPUT = "invalid_noise_input"
    MISSING_SUPPRESSED_ARTIFACT = "missing_suppressed_artifact"
    INVALID_SUPPRESSED_ARTIFACT = "invalid_suppressed_artifact"
    SHAPE_MISMATCH = "shape_mismatch"
    INVALID_PIXEL_DATA = "invalid_pixel_data"
    DETECTION_FAILED = "detection_failed"


@dataclass(frozen=True)
class ChangeCandidateConfig:
    """Explicit engineering criteria for candidate detection."""

    output_dir: Path
    absolute_difference_threshold: float
    minimum_component_size: int = 3
    minimum_valid_neighbors: int = 2
    connectivity: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if isinstance(self.absolute_difference_threshold, bool) or not isinstance(self.absolute_difference_threshold, (int, float)) or not np.isfinite(self.absolute_difference_threshold) or self.absolute_difference_threshold <= 0:
            raise ValueError("absolute_difference_threshold must be a finite positive number")
        if self.minimum_component_size < 1:
            raise ValueError("minimum_component_size must be positive")
        if self.minimum_valid_neighbors < 1:
            raise ValueError("minimum_valid_neighbors must be positive")
        if self.connectivity not in (4, 8):
            raise ValueError("connectivity must be 4 or 8")


@dataclass(frozen=True)
class ChangeCandidateRequest:
    """Input boundary consuming only a Phase 10.7 result."""

    noise_result: NoiseSuppressionResult
    config: ChangeCandidateConfig


@dataclass(frozen=True)
class ChangeCandidate:
    candidate_id: str
    bounding_box: dict[str, int]
    pixel_count: int
    valid_pixel_count: int
    centroid: dict[str, float]
    detection_threshold: float
    peak_absolute_difference: float
    mean_absolute_difference: float
    median_absolute_difference: float
    signed_mean: float
    signed_median: float
    sign_characterization: str
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ChangeCandidateResult:
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    noise_suppression_status: Optional[str]
    status: ChangeCandidateStatus
    threshold: Optional[float]
    connectivity: int
    minimum_component_size: int
    minimum_valid_neighbors: int
    candidate_mask_reference: Optional[str]
    candidate_labels_reference: Optional[str]
    candidate_list_reference: Optional[str]
    valid_input_mask_reference: Optional[str]
    candidate_count: int
    valid_pixel_count: int
    invalid_pixel_count: int
    candidates: tuple[ChangeCandidate, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "noise_suppression_status": self.noise_suppression_status,
            "status": self.status.value,
            "threshold": self.threshold,
            "connectivity": self.connectivity,
            "minimum_component_size": self.minimum_component_size,
            "minimum_valid_neighbors": self.minimum_valid_neighbors,
            "candidate_mask_reference": self.candidate_mask_reference,
            "candidate_labels_reference": self.candidate_labels_reference,
            "candidate_list_reference": self.candidate_list_reference,
            "valid_input_mask_reference": self.valid_input_mask_reference,
            "candidate_count": self.candidate_count,
            "valid_pixel_count": self.valid_pixel_count,
            "invalid_pixel_count": self.invalid_pixel_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }


def _failure(request: ChangeCandidateRequest, status: ChangeCandidateStatus, reason: str, message: str) -> ChangeCandidateResult:
    upstream = request.noise_result
    return ChangeCandidateResult(
        upstream.observation_a_id, upstream.observation_b_id,
        getattr(upstream.status, "value", None), status,
        request.config.absolute_difference_threshold, request.config.connectivity,
        request.config.minimum_component_size, request.config.minimum_valid_neighbors,
        None, None, None, upstream.propagated_valid_mask_reference,
        0, 0, 0, (), (), (reason,),
        {"phase": "m4_10.8", "upstream_phase": "m4_10.7", "scientific_interpretation": "algorithmic candidate only"}, message,
    )


def _sign_characterization(values: np.ndarray) -> str:
    positive = bool(np.any(values > 0))
    negative = bool(np.any(values < 0))
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "zero"


def detect_change_candidates(request: ChangeCandidateRequest) -> ChangeCandidateResult:
    """Detect coherent above-threshold regions in Phase 10.7 output."""
    upstream = request.noise_result
    config = request.config
    if not isinstance(upstream, NoiseSuppressionResult) or upstream.status is not NoiseSuppressionStatus.SUCCESS:
        return _failure(request, ChangeCandidateStatus.INVALID_NOISE_INPUT, "invalid_noise_input", "A successful Phase 10.7 result is required; earlier products are not fallback inputs.")
    references = (upstream.suppressed_signed_difference_reference, upstream.suppressed_absolute_difference_reference, upstream.propagated_valid_mask_reference)
    if any(not reference for reference in references):
        return _failure(request, ChangeCandidateStatus.MISSING_SUPPRESSED_ARTIFACT, "missing_suppressed_artifact", "Phase 10.7 suppressed artifacts are required.")
    try:
        signed = np.load(upstream.suppressed_signed_difference_reference, allow_pickle=False)
        absolute = np.load(upstream.suppressed_absolute_difference_reference, allow_pickle=False)
        valid = np.load(upstream.propagated_valid_mask_reference, allow_pickle=False)
    except (OSError, ValueError, TypeError):
        return _failure(request, ChangeCandidateStatus.INVALID_SUPPRESSED_ARTIFACT, "invalid_suppressed_artifact", "Phase 10.7 artifacts could not be loaded.")
    if signed.ndim != 2 or absolute.ndim != 2 or signed.shape != absolute.shape:
        return _failure(request, ChangeCandidateStatus.SHAPE_MISMATCH, "shape_mismatch", "Phase 10.7 candidate inputs must be matching two-dimensional arrays.")
    if valid.dtype != np.bool_ or valid.shape != signed.shape:
        return _failure(request, ChangeCandidateStatus.SHAPE_MISMATCH, "mask_mismatch", "The Phase 10.7 valid mask does not match the difference shape.")
    finite = valid & np.isfinite(signed) & np.isfinite(absolute)
    if np.any(absolute[finite] < 0):
        return _failure(request, ChangeCandidateStatus.INVALID_PIXEL_DATA, "negative_absolute_difference", "Absolute difference contains negative valid values.")
    valid_count = int(np.count_nonzero(finite))
    invalid_count = int(finite.size - valid_count)
    if valid_count == 0:
        return ChangeCandidateResult(upstream.observation_a_id, upstream.observation_b_id, upstream.status.value, ChangeCandidateStatus.NO_VALID_DATA, config.absolute_difference_threshold, config.connectivity, config.minimum_component_size, config.minimum_valid_neighbors, None, None, None, upstream.propagated_valid_mask_reference, 0, 0, invalid_count, (), (), (), {"phase": "m4_10.8", "upstream_phase": "m4_10.7", "scientific_interpretation": "algorithmic candidate only"}, "No valid Phase 10.7 pixels were available; no candidates were fabricated.")
    structure = ndimage.generate_binary_structure(2, 1 if config.connectivity == 4 else 2)
    above = finite & (absolute >= config.absolute_difference_threshold)
    neighbor_count = ndimage.convolve(finite.astype(np.uint8), structure, mode="constant", cval=0)
    supported = above & (neighbor_count >= config.minimum_valid_neighbors)
    labels, component_count = ndimage.label(supported, structure=structure)
    candidates: list[ChangeCandidate] = []
    candidate_labels = np.zeros(signed.shape, dtype=np.int32)
    candidate_mask = np.where(~finite, 0, 1).astype(np.uint8)
    next_id = 1
    for component in range(1, component_count + 1):
        coordinates = np.argwhere(labels == component)
        if coordinates.shape[0] < config.minimum_component_size:
            continue
        rows, columns = coordinates[:, 0], coordinates[:, 1]
        values_signed = signed[rows, columns]
        values_absolute = absolute[rows, columns]
        candidate_labels[rows, columns] = next_id
        candidate_mask[rows, columns] = 2
        candidates.append(ChangeCandidate(
            candidate_id=f"candidate-{next_id:04d}",
            bounding_box={"min_row": int(rows.min()), "min_col": int(columns.min()), "max_row": int(rows.max()), "max_col": int(columns.max())},
            pixel_count=int(coordinates.shape[0]), valid_pixel_count=int(coordinates.shape[0]),
            centroid={"row": float(np.mean(rows)), "col": float(np.mean(columns))},
            detection_threshold=float(config.absolute_difference_threshold),
            peak_absolute_difference=float(np.max(values_absolute)),
            mean_absolute_difference=float(np.mean(values_absolute)),
            median_absolute_difference=float(np.median(values_absolute)),
            signed_mean=float(np.mean(values_signed)), signed_median=float(np.median(values_signed)),
            sign_characterization=_sign_characterization(values_signed),
            observation_a_id=upstream.observation_a_id, observation_b_id=upstream.observation_b_id,
        ))
        next_id += 1
    status = ChangeCandidateStatus.SUCCESS if candidates else ChangeCandidateStatus.NO_CANDIDATES
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    mask_path = output_dir / "change_candidate_mask.npy"
    labels_path = output_dir / "candidate_labels.npy"
    list_path = output_dir / "change_candidates.json"
    summary_path = output_dir / "change_candidate_summary.json"
    np.save(mask_path, candidate_mask)
    np.save(labels_path, candidate_labels)
    result = ChangeCandidateResult(
        upstream.observation_a_id, upstream.observation_b_id, upstream.status.value, status,
        config.absolute_difference_threshold, config.connectivity, config.minimum_component_size,
        config.minimum_valid_neighbors, str(mask_path), str(labels_path), str(list_path),
        upstream.propagated_valid_mask_reference, len(candidates), valid_count, invalid_count,
        tuple(candidates), ("candidate_threshold_is_engineering_criterion", "candidate_is_not_confirmed_change"), (),
        {"phase": "m4_10.8", "upstream_phase": "m4_10.7", "threshold_population": "finite_pixels_marked_valid_by_phase_10.7", "candidate_mask_semantics": "0_invalid_1_valid_non_candidate_2_candidate", "scientific_interpretation": "algorithmic candidate only"},
        "Algorithmic candidate detection only; no physical lunar change determination was performed.",
    )
    list_path.write_text(json.dumps([candidate.to_dict() for candidate in candidates], indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result