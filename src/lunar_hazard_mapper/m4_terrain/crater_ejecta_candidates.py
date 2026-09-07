"""M4 Phase 10.10 deterministic crater/ejecta candidate screening."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import ndimage

from .change_candidate_detection import ChangeCandidateResult, ChangeCandidateStatus
from .change_classification import ChangeClassificationResult, ChangeClassificationStatus
from .noise_suppression import NoiseSuppressionResult, NoiseSuppressionStatus


class CraterEjectaCandidateStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_SPECIALIZED_CANDIDATES = "no_specialized_candidates"
    UNDETERMINED = "undetermined"
    INVALID_CLASSIFICATION_INPUT = "invalid_classification_input"
    MISSING_CANDIDATE_ARTIFACT = "missing_candidate_artifact"
    INVALID_CANDIDATE_ARTIFACT = "invalid_candidate_artifact"
    SHAPE_MISMATCH = "shape_mismatch"
    INVALID_PIXEL_DATA = "invalid_pixel_data"
    INSUFFICIENT_MORPHOLOGY = "insufficient_morphology"
    SCREENING_FAILED = "screening_failed"


class SpecializedCandidateType(str, Enum):
    NEW_CRATER_CANDIDATE = "NEW_CRATER_CANDIDATE"
    EJECTA_CANDIDATE = "EJECTA_CANDIDATE"
    CRATER_AND_EJECTA_CANDIDATE = "CRATER_AND_EJECTA_CANDIDATE"
    NON_SPECIALIZED_CANDIDATE = "NON_SPECIALIZED_CANDIDATE"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class CraterEjectaCandidateConfig:
    output_dir: Path
    minimum_morphology_pixels: int = 9
    crater_compactness_threshold: float = 0.65
    crater_max_aspect_ratio: float = 1.75
    crater_min_radial_bins: int = 3
    crater_min_radial_coverage: float = 0.60
    ejecta_min_area_pixels: int = 15
    ejecta_max_extent: float = 0.55
    ejecta_min_radial_bins: int = 3
    ejecta_min_radial_decline: float = 0.10
    radial_bin_count: int = 4
    analysis_window_margin: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.minimum_morphology_pixels < 1 or self.ejecta_min_area_pixels < 1:
            raise ValueError("minimum morphology and ejecta areas must be positive")
        for name in ("crater_compactness_threshold", "crater_min_radial_coverage", "ejecta_max_extent"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"{name} must be finite and between zero and one")
        for name in ("crater_max_aspect_ratio", "ejecta_min_radial_decline"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.crater_min_radial_bins < 1 or self.ejecta_min_radial_bins < 1 or self.radial_bin_count < 1 or self.analysis_window_margin < 0:
            raise ValueError("radial bins must be positive and window margin cannot be negative")


@dataclass(frozen=True)
class CraterEjectaCandidateRequest:
    classification_result: ChangeClassificationResult
    candidate_result: ChangeCandidateResult
    noise_result: NoiseSuppressionResult
    config: CraterEjectaCandidateConfig


@dataclass(frozen=True)
class SpecializedCandidate:
    source_candidate_id: str
    candidate_type: SpecializedCandidateType
    centroid: dict[str, float]
    bounding_box: dict[str, int]
    geometry: dict[str, Any]
    radial_descriptors: dict[str, Any]
    sign_response: dict[str, Any]
    intensity: dict[str, Any]
    supporting_indicators: tuple[str, ...]
    limitations: tuple[str, ...]
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.__dict__)
        result["candidate_type"] = self.candidate_type.value
        result["supporting_indicators"] = list(self.supporting_indicators)
        result["limitations"] = list(self.limitations)
        return result


@dataclass(frozen=True)
class CraterEjectaCandidateResult:
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    classification_status: Optional[str]
    candidate_status: Optional[str]
    status: CraterEjectaCandidateStatus
    candidate_list_reference: Optional[str]
    classified_candidates_reference: Optional[str]
    specialized_candidates_reference: Optional[str]
    summary_reference: Optional[str]
    candidate_count: int
    specialized_candidate_count: int
    candidates: tuple[SpecializedCandidate, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"observation_a_id": self.observation_a_id, "observation_b_id": self.observation_b_id, "classification_status": self.classification_status, "candidate_status": self.candidate_status, "status": self.status.value, "candidate_list_reference": self.candidate_list_reference, "classified_candidates_reference": self.classified_candidates_reference, "specialized_candidates_reference": self.specialized_candidates_reference, "summary_reference": self.summary_reference, "candidate_count": self.candidate_count, "specialized_candidate_count": self.specialized_candidate_count, "candidates": [item.to_dict() for item in self.candidates], "warnings": list(self.warnings), "failure_reasons": list(self.failure_reasons), "provenance": self.provenance, "message": self.message}


def _failure(request: CraterEjectaCandidateRequest, status: CraterEjectaCandidateStatus, reason: str, message: str) -> CraterEjectaCandidateResult:
    classification = request.classification_result
    candidate = request.candidate_result
    return CraterEjectaCandidateResult(classification.observation_a_id, classification.observation_b_id, getattr(classification.status, "value", None), getattr(candidate.status, "value", None), status, candidate.candidate_list_reference, classification.classified_candidates_reference, None, None, 0, 0, (), (), (reason,), {"phase": "m4_10.10", "upstream_phase": "m4_10.9", "scientific_interpretation": "algorithmically screened candidate only"}, message)


def _load(path: Optional[str]) -> np.ndarray:
    if not path:
        raise FileNotFoundError(path)
    return np.load(path, allow_pickle=False)


def _perimeter(component: np.ndarray) -> int:
    return int(np.count_nonzero(component & ~ndimage.binary_erosion(component, structure=np.ones((3, 3), dtype=bool))))


def _radial(values: np.ndarray, coordinates: np.ndarray, valid: np.ndarray, absolute: np.ndarray, config: CraterEjectaCandidateConfig) -> dict[str, Any]:
    centroid = coordinates.mean(axis=0)
    distances = np.sqrt(np.sum((coordinates - centroid) ** 2, axis=1))
    maximum = float(np.max(distances)) if distances.size else 0.0
    if maximum == 0 or distances.size < config.minimum_morphology_pixels:
        return {"available": False, "reason": "insufficient_radial_extent", "bin_count": 0}
    edges = np.linspace(0.0, maximum + np.finfo(float).eps, config.radial_bin_count + 1)
    means: list[Optional[float]] = []
    counts: list[int] = []
    for index in range(config.radial_bin_count):
        selected = (distances >= edges[index]) & (distances <= edges[index + 1] if index == config.radial_bin_count - 1 else distances < edges[index + 1])
        counts.append(int(np.count_nonzero(selected)))
        means.append(float(np.mean(values[selected])) if np.any(selected) else None)
    finite_means = np.asarray([value for value in means if value is not None], dtype=float)
    coverage = float(finite_means.size / config.radial_bin_count)
    decline = float((finite_means[0] - finite_means[-1]) / max(abs(finite_means[0]), np.finfo(float).eps)) if finite_means.size >= 2 else None
    return {"available": bool(finite_means.size >= config.crater_min_radial_bins), "bin_count": int(finite_means.size), "radial_mean_absolute_difference": means, "radial_pixel_counts": counts, "radial_coverage": coverage, "radial_decline": decline, "maximum_radius_pixels": maximum}


def screen_crater_ejecta_candidates(request: CraterEjectaCandidateRequest) -> CraterEjectaCandidateResult:
    """Screen existing classified candidates without creating new temporal candidates."""
    classification = request.classification_result
    candidate = request.candidate_result
    noise = request.noise_result
    config = request.config
    if not isinstance(classification, ChangeClassificationResult) or classification.status not in (ChangeClassificationStatus.SUCCESS, ChangeClassificationStatus.NO_CANDIDATES):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CLASSIFICATION_INPUT, "invalid_classification_input", "A successful or empty Phase 10.9 result is required.")
    if not isinstance(candidate, ChangeCandidateResult) or candidate.status not in (ChangeCandidateStatus.SUCCESS, ChangeCandidateStatus.NO_CANDIDATES):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CLASSIFICATION_INPUT, "invalid_candidate_input", "A successful or empty Phase 10.8 result is required.")
    if not isinstance(noise, NoiseSuppressionResult) or noise.status is not NoiseSuppressionStatus.SUCCESS:
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CLASSIFICATION_INPUT, "invalid_noise_input", "A successful Phase 10.7 result is required.")
    if (classification.observation_a_id, classification.observation_b_id) != (candidate.observation_a_id, candidate.observation_b_id) or (candidate.observation_a_id, candidate.observation_b_id) != (noise.observation_a_id, noise.observation_b_id):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CLASSIFICATION_INPUT, "observation_id_mismatch", "Observation IDs must match across upstream phases.")
    try:
        mask = _load(candidate.candidate_mask_reference)
        labels = _load(candidate.candidate_labels_reference)
        signed = _load(noise.suppressed_signed_difference_reference)
        absolute = _load(noise.suppressed_absolute_difference_reference)
        valid = _load(noise.propagated_valid_mask_reference)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return _failure(request, CraterEjectaCandidateStatus.MISSING_CANDIDATE_ARTIFACT, "missing_artifact", "Required Phase 10.7/10.8 artifacts could not be loaded.")
    if mask.ndim != 2 or any(array.shape != mask.shape for array in (labels, signed, absolute, valid)):
        return _failure(request, CraterEjectaCandidateStatus.SHAPE_MISMATCH, "shape_mismatch", "All candidate and upstream arrays must have one matching two-dimensional shape.")
    if mask.dtype != np.uint8 or labels.dtype.kind not in "iu" or valid.dtype != np.bool_ or signed.dtype.kind not in "fiu" or absolute.dtype.kind not in "fiu" or np.any(~np.isin(mask, [0, 1, 2])) or np.any(labels < 0):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CANDIDATE_ARTIFACT, "invalid_mask_or_labels", "Candidate artifacts violate the Phase 10.8 contract.")
    finite = valid & np.isfinite(signed) & np.isfinite(absolute)
    if np.any(absolute[finite] < 0) or np.any(mask[~valid] != 0) or np.any(mask[valid & ~finite] != 0) or np.any((mask == 2) & ~finite):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_PIXEL_DATA, "invalid_candidate_pixels", "Candidate pixels must be valid, finite, and have non-negative absolute differences.")
    if np.any((labels > 0) != (mask == 2)):
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CANDIDATE_ARTIFACT, "label_mask_inconsistency", "Positive labels must correspond exactly to candidate-mask value 2.")
    label_ids = sorted(int(value) for value in np.unique(labels) if value > 0)
    expected_ids = [f"candidate-{value:04d}" for value in label_ids]
    if label_ids != list(range(1, len(label_ids) + 1)) or len(label_ids) != candidate.candidate_count or [item.candidate_id for item in candidate.candidates] != expected_ids or [item.candidate_id for item in classification.classifications] != expected_ids:
        return _failure(request, CraterEjectaCandidateStatus.INVALID_CANDIDATE_ARTIFACT, "candidate_identity_integrity", "10.8 labels and 10.9 records do not agree.")
    if not label_ids:
        return _failure(request, CraterEjectaCandidateStatus.NO_CANDIDATES, "", "No authoritative temporal candidates were supplied.")
    specialized: list[SpecializedCandidate] = []
    for label_id in label_ids:
        component_pixels = labels == label_id
        coordinates = np.argwhere(component_pixels)
        values_signed, values_absolute = signed[component_pixels], absolute[component_pixels]
        rows, columns = coordinates[:, 0], coordinates[:, 1]
        min_row, max_row, min_col, max_col = map(int, (rows.min(), rows.max(), columns.min(), columns.max()))
        width, height = max_col - min_col + 1, max_row - min_row + 1
        area = len(coordinates)
        perimeter = _perimeter(component_pixels)
        compactness = float(4 * np.pi * area / perimeter ** 2) if perimeter else None
        aspect_ratio = float(max(width, height) / min(width, height))
        extent = float(area / (width * height))
        equivalent_diameter = float(np.sqrt(4 * area / np.pi))
        boundary = min_row == 0 or min_col == 0 or max_row == mask.shape[0] - 1 or max_col == mask.shape[1] - 1
        radial = _radial(values_absolute, coordinates, valid, absolute, config)
        crater_indicators = []
        if compactness is not None and compactness >= config.crater_compactness_threshold:
            crater_indicators.append("compact_circular_like_geometry")
        if aspect_ratio <= config.crater_max_aspect_ratio:
            crater_indicators.append("bounded_aspect_ratio")
        if area >= config.minimum_morphology_pixels:
            crater_indicators.append("sufficient_image_space_area")
        if radial.get("available") and radial.get("radial_coverage", 0.0) >= config.crater_min_radial_coverage:
            crater_indicators.append("measurable_radial_extent")
        ejecta_indicators = []
        if area >= config.ejecta_min_area_pixels and extent <= config.ejecta_max_extent:
            ejecta_indicators.append("broad_diffuse_extent")
        if radial.get("available") and radial.get("bin_count", 0) >= config.ejecta_min_radial_bins and radial.get("radial_decline") is not None and radial["radial_decline"] >= config.ejecta_min_radial_decline:
            ejecta_indicators.append("radial_absolute_difference_decline")
        limitations = []
        if boundary:
            limitations.append("boundary_truncation_limits_morphology")
        if not radial.get("available"):
            limitations.append("radial_analysis_insufficient")
        if boundary:
            crater_indicators = [item for item in crater_indicators if item not in ("compact_circular_like_geometry", "measurable_radial_extent")]
        crater_like = len(crater_indicators) >= 3 and not boundary
        ejecta_like = len(ejecta_indicators) >= 2 and not boundary
        if crater_like and ejecta_like:
            kind = SpecializedCandidateType.CRATER_AND_EJECTA_CANDIDATE
        elif crater_like:
            kind = SpecializedCandidateType.NEW_CRATER_CANDIDATE
        elif ejecta_like:
            kind = SpecializedCandidateType.EJECTA_CANDIDATE
        elif area < config.minimum_morphology_pixels:
            kind = SpecializedCandidateType.UNDETERMINED
            limitations.append("insufficient_morphology_pixels")
        else:
            kind = SpecializedCandidateType.NON_SPECIALIZED_CANDIDATE
        specialized.append(SpecializedCandidate(f"candidate-{label_id:04d}", kind, {"row": float(rows.mean()), "col": float(columns.mean())}, {"min_row": min_row, "min_col": min_col, "max_row": max_row, "max_col": max_col}, {"pixel_area": area, "perimeter_pixels": perimeter, "compactness": compactness, "aspect_ratio": aspect_ratio, "extent": extent, "equivalent_diameter_pixels": equivalent_diameter, "touches_image_boundary": boundary, "image_shape": list(mask.shape)}, radial, {"positive_pixel_count": int(np.count_nonzero(values_signed > 0)), "negative_pixel_count": int(np.count_nonzero(values_signed < 0)), "signed_mean": float(np.mean(values_signed)), "signed_median": float(np.median(values_signed))}, {"mean_absolute_difference": float(np.mean(values_absolute)), "median_absolute_difference": float(np.median(values_absolute)), "maximum_absolute_difference": float(np.max(values_absolute))}, tuple(crater_indicators + ejecta_indicators), tuple(dict.fromkeys(limitations)), classification.observation_a_id, classification.observation_b_id))
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    list_path, summary_path = output_dir / "crater_ejecta_candidates.json", output_dir / "crater_ejecta_candidate_summary.json"
    specialized_count = sum(item.candidate_type in (SpecializedCandidateType.NEW_CRATER_CANDIDATE, SpecializedCandidateType.EJECTA_CANDIDATE, SpecializedCandidateType.CRATER_AND_EJECTA_CANDIDATE) for item in specialized)
    status = CraterEjectaCandidateStatus.SUCCESS if specialized_count else CraterEjectaCandidateStatus.NO_SPECIALIZED_CANDIDATES
    provenance = {"phase": "m4_10.10", "upstream_phase": "m4_10.9", "phase_10_9_status": classification.status.value, "phase_10_8_status": candidate.status.value, "phase_10_7_provenance": noise.provenance, "input_artifacts": {"candidate_mask": candidate.candidate_mask_reference, "candidate_labels": candidate.candidate_labels_reference, "signed_difference": noise.suppressed_signed_difference_reference, "absolute_difference": noise.suppressed_absolute_difference_reference, "valid_mask": noise.propagated_valid_mask_reference}, "method": "deterministic multi-indicator image-space crater/ejecta screening", "thresholds": {name: getattr(config, name) for name in ("minimum_morphology_pixels", "crater_compactness_threshold", "crater_max_aspect_ratio", "crater_min_radial_bins", "crater_min_radial_coverage", "ejecta_min_area_pixels", "ejecta_max_extent", "ejecta_min_radial_bins", "ejecta_min_radial_decline", "radial_bin_count", "analysis_window_margin")}, "limitations": ["These are algorithmically screened crater/ejecta candidates based on observable temporal-difference morphology. They are not confirmed craters, ejecta deposits, impacts, or physical lunar changes.", "Geometry is image-space only and requires Phase 10.11 and 10.12 validation."]}
    result = CraterEjectaCandidateResult(classification.observation_a_id, classification.observation_b_id, classification.status.value, candidate.status.value, status, candidate.candidate_list_reference, classification.classified_candidates_reference, str(list_path), str(summary_path), len(label_ids), specialized_count, tuple(specialized), ("candidate_screening_is_not_confirmation", "signed_response_has_no_physical_interpretation"), (), provenance, "Algorithmically screened candidate morphology only; later validation is required.")
    list_path.write_text(json.dumps([item.to_dict() for item in specialized], indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result


class CraterEjectaCandidateError(ValueError):
    """Reserved public error type for invalid screening requests."""