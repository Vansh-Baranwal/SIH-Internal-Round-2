"""M4 Phase 10.4 orchestration around the existing M2 registration pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .image_pair_selection import (
    ImageReferenceStatus,
    PairSelectionResult,
    evaluate_pair,
)
from .temporal_observation import ObservationPair


class RegistrationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RegistrationConfig:
    """Configuration passed through to M2 without changing its algorithms."""

    output_dir: Path
    matcher: str = "sift"
    geo_model: str = "affine"
    source_gsd_m: float = 0.3
    reference_gsd_m: float = 5.0
    apply_scale_matching: bool = False
    apply_uniform_filter: bool = True
    max_per_cell: int = 3
    apply_illumination_invariant: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.matcher not in ("sift", "akaze", "superpoint_lightglue", "loftr"):
            raise ValueError(f"unsupported registration matcher: {self.matcher}")
        if self.geo_model not in ("affine", "homography", "tps"):
            raise ValueError(f"unsupported registration model: {self.geo_model}")
        if self.source_gsd_m <= 0 or self.reference_gsd_m <= 0:
            raise ValueError("registration GSD values must be positive")
        if self.max_per_cell <= 0:
            raise ValueError("max_per_cell must be positive")


@dataclass(frozen=True)
class TemporalRegistrationRequest:
    """Phase 10.4 input: an eligible Phase 10.3 pair and M2 config."""

    pair: ObservationPair
    selection: PairSelectionResult
    config: RegistrationConfig

    def __post_init__(self) -> None:
        if not self.selection.eligible:
            raise ValueError("TemporalRegistrationRequest requires an eligible pair selection.")
        if (self.selection.observation_a_id != self.pair.observation_a.observation_id or
                self.selection.observation_b_id != self.pair.observation_b.observation_id):
            raise ValueError("pair selection does not describe the supplied observation pair.")


@dataclass(frozen=True)
class TemporalRegistrationResult:
    """M4-normalized registration result; absent M2 values remain unavailable."""

    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    status: RegistrationStatus
    registration_engine: str
    backend_used: Optional[str]
    transformation_model: Optional[str]
    transformation_parameters: Optional[Any]
    initial_match_count: Optional[int]
    verified_inlier_count: Optional[int]
    inlier_ratio: Optional[float]
    spatial_coverage: Optional[float]
    registration_rmse: Optional[float]
    subpixel_refinement_available: bool
    subpixel_refinement_status: str
    registered_output_reference: Optional[str]
    match_point_output_reference: Optional[str]
    registration_quality_status: str
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance_status: str
    message: str = ""
    reference_image_reference: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status is RegistrationStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "status": self.status.value,
            "registration_engine": self.registration_engine,
            "backend_used": self.backend_used,
            "transformation_model": self.transformation_model,
            "transformation_parameters": self.transformation_parameters,
            "initial_match_count": self.initial_match_count,
            "verified_inlier_count": self.verified_inlier_count,
            "inlier_ratio": self.inlier_ratio,
            "spatial_coverage": self.spatial_coverage,
            "registration_rmse": self.registration_rmse,
            "subpixel_refinement_available": self.subpixel_refinement_available,
            "subpixel_refinement_status": self.subpixel_refinement_status,
            "registered_output_reference": self.registered_output_reference,
            "match_point_output_reference": self.match_point_output_reference,
            "registration_quality_status": self.registration_quality_status,
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance_status": self.provenance_status,
            "message": self.message,
            "reference_image_reference": self.reference_image_reference,
        }


def _base_result(pair: ObservationPair, status: RegistrationStatus, *, reasons: tuple[str, ...] = (), message: str = "") -> TemporalRegistrationResult:
    return TemporalRegistrationResult(
        pair.observation_a.observation_id,
        pair.observation_b.observation_id,
        status,
        "m2_correspondence_engine",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        False,
        "unavailable",
        None,
        None,
        "unavailable",
        (),
        reasons,
        "real_observation_pair",
        message,
        None,
    )


def _resolve_local_reference(observation) -> tuple[Optional[str], Optional[str]]:
    reference = observation.file_path or observation.image_reference
    if not isinstance(reference, str) or not reference.strip():
        return None, "invalid_image_reference"
    is_windows_path = len(reference) >= 3 and reference[1] == ":" and reference[2] in "\\/"
    parsed = urlparse(reference)
    if not is_windows_path and parsed.scheme and parsed.scheme != "file":
        return None, "external_image_reference_unsupported_by_m2"
    path = Path(parsed.path if parsed.scheme == "file" else reference)
    if not path.is_file():
        return None, "missing_image_input"
    return str(path), None


def _valid_metric(value: Any, field_name: str, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"invalid_registration_metrics:{field_name}")
    numeric = float(value)
    if minimum is not None and numeric < minimum or maximum is not None and numeric > maximum:
        raise ValueError(f"invalid_registration_metrics:{field_name}")
    return numeric


def _optional_metric(value: Any, field_name: str, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> Optional[float]:
    return None if value is None else _valid_metric(value, field_name, minimum=minimum, maximum=maximum)


def register_observation_pair(
    pair: ObservationPair,
    config: RegistrationConfig,
    selection: Optional[PairSelectionResult] = None,
) -> TemporalRegistrationResult:
    """Register an eligible pair through M2's existing path-based pipeline."""
    selection = selection or evaluate_pair(pair.observation_a, pair.observation_b)
    if not selection.eligible:
        return _base_result(
            pair,
            RegistrationStatus.BLOCKED,
            reasons=("ineligible_pair",) + selection.hard_rejection_reasons,
            message="Pair selection did not produce an eligible candidate.",
        )
    try:
        source_path, source_error = _resolve_local_reference(pair.observation_a)
        reference_path, reference_error = _resolve_local_reference(pair.observation_b)
    except (OSError, ValueError, TypeError):
        return _base_result(pair, RegistrationStatus.BLOCKED, reasons=("invalid_image_reference",), message="Image references could not be resolved.")
    reference_errors = tuple(error for error in (source_error, reference_error) if error)
    if reference_errors:
        return _base_result(pair, RegistrationStatus.BLOCKED, reasons=reference_errors, message="M2 requires existing local filesystem image inputs.")

    from lunar_hazard_mapper.correspondence_engine.registration import pipeline as m2_pipeline

    warnings = ["m2_backend_not_exposed", "transformation_parameters_unavailable"]
    try:
        metrics = m2_pipeline.run_pipeline(
            source_path,
            reference_path,
            str(config.output_dir),
            matcher=config.matcher,
            geo_model=config.geo_model,
            source_gsd_m=config.source_gsd_m,
            reference_gsd_m=config.reference_gsd_m,
            apply_scale_matching=config.apply_scale_matching,
            apply_uniform_filter=config.apply_uniform_filter,
            max_per_cell=config.max_per_cell,
            apply_illumination_invariant=config.apply_illumination_invariant,
        )
    except ValueError as exc:
        return _base_result(pair, RegistrationStatus.FAILED, reasons=("unsupported_registration_backend",), message=str(exc))
    except Exception as exc:
        return _base_result(pair, RegistrationStatus.FAILED, reasons=("registration_execution_failed",), message=str(exc))
    if metrics is None:
        return _base_result(pair, RegistrationStatus.FAILED, reasons=("insufficient_matches",), message="M2 returned no registration metrics.")

    try:
        total_matches = int(metrics.total_matches)
        inlier_count = int(metrics.inlier_count)
        if total_matches < 0 or inlier_count < 0 or inlier_count > total_matches:
            raise ValueError("invalid_registration_metrics:match_counts")
        inlier_ratio = _optional_metric(metrics.inlier_ratio, "inlier_ratio", minimum=0.0, maximum=1.0)
        rmse = _optional_metric(metrics.rmse, "rmse", minimum=0.0)
        coverage = _optional_metric(metrics.spatial_coverage, "spatial_coverage", minimum=0.0, maximum=1.0)
        if total_matches < 3 or inlier_count < 1:
            return _base_result(pair, RegistrationStatus.FAILED, reasons=("insufficient_matches",), message="M2 did not return enough verified matches for a registered output.")
    except (AttributeError, TypeError, ValueError) as exc:
        return _base_result(pair, RegistrationStatus.FAILED, reasons=("invalid_registration_metrics",), message=str(exc))

    output_dir = Path(config.output_dir)
    registered_output = output_dir / "warped_source.png"
    match_output = output_dir / "matches.json"
    if not registered_output.is_file():
        return _base_result(pair, RegistrationStatus.FAILED, reasons=("missing_registered_output",), message="M2 metrics were returned but warped_source.png is unavailable.")
    return TemporalRegistrationResult(
        pair.observation_a.observation_id,
        pair.observation_b.observation_id,
        RegistrationStatus.SUCCESS,
        "m2_correspondence_engine",
        None,
        config.geo_model,
        None,
        total_matches,
        inlier_count,
        inlier_ratio,
        coverage,
        rmse,
        True,
        "executed",
        str(registered_output),
        str(match_output) if match_output.is_file() else None,
        "metrics_available" if rmse is not None and coverage is not None and inlier_ratio is not None else "partial_metrics",
        tuple(warnings),
        (),
        "real_observation_pair",
        "M2 registration completed; this result establishes alignment only.",
        str(reference_path),
    )