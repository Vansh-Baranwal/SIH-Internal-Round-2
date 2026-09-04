"""M4 Phase 10.12 final temporal-change validation.

This stage is intentionally conservative: it consumes the authoritative 10.7-10.11
chain and only emits final validation when the full evidence chain is real,
consistent, and free of decisive false-positive evidence. It does not claim a
confirmed impact, crater, ejecta deposit, or geological interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .change_candidate_detection import ChangeCandidateResult, ChangeCandidateStatus
from .change_classification import ChangeClassificationResult, ChangeClassificationStatus
from .crater_ejecta_candidates import CraterEjectaCandidateResult, CraterEjectaCandidateStatus
from .false_positive_validation import (
    FalsePositiveValidationResult,
    FalsePositiveValidationStatus,
)
from .image_differencing import DifferenceStatus, ImageDifferenceResult
from .illumination_filtering import IlluminationAssessmentStatus, IlluminationFilterResult, IlluminationFilterStatus
from .image_pair_selection import PairEligibility, PairSelectionResult
from .multi_date_registration import RegistrationStatus, TemporalRegistrationResult
from .noise_suppression import NoiseSuppressionResult, NoiseSuppressionStatus
from .provenance import DataProvenance
from .temporal_observation import ObservationPair


class TemporalChangeValidationStatus(str, Enum):
    VALIDATED_TEMPORAL_CHANGE = "validated_temporal_change"
    REJECTED_FALSE_POSITIVE = "rejected_false_positive"
    NO_CANDIDATES = "no_candidates"
    INCONCLUSIVE = "inconclusive"
    VALIDATION_BLOCKED = "validation_blocked"


@dataclass(frozen=True)
class ValidationGate:
    name: str
    status: str
    passed: bool
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "passed": self.passed,
            "details": self.details,
        }


@dataclass(frozen=True)
class TemporalChangeValidationConfig:
    output_dir: Path
    minimum_inlier_ratio: float = 0.20
    minimum_spatial_coverage: float = 0.50
    maximum_rmse: float = 1.0
    minimum_valid_fraction: float = 0.85
    minimum_support_pixels: int = 9

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.minimum_inlier_ratio < 0.0 or self.minimum_inlier_ratio > 1.0:
            raise ValueError("minimum_inlier_ratio must be in [0, 1].")
        if self.minimum_spatial_coverage < 0.0 or self.minimum_spatial_coverage > 1.0:
            raise ValueError("minimum_spatial_coverage must be in [0, 1].")
        if self.maximum_rmse < 0.0:
            raise ValueError("maximum_rmse must be non-negative.")
        if self.minimum_valid_fraction < 0.0 or self.minimum_valid_fraction > 1.0:
            raise ValueError("minimum_valid_fraction must be in [0, 1].")
        if self.minimum_support_pixels < 1:
            raise ValueError("minimum_support_pixels must be positive.")


@dataclass(frozen=True)
class TemporalChangeValidationRequest:
    pair: ObservationPair
    config: TemporalChangeValidationConfig
    selection_result: Optional[PairSelectionResult] = None
    registration_result: Optional[TemporalRegistrationResult] = None
    difference_result: Optional[ImageDifferenceResult] = None
    illumination_result: Optional[IlluminationFilterResult] = None
    noise_result: Optional[NoiseSuppressionResult] = None
    candidate_result: Optional[ChangeCandidateResult] = None
    classification_result: Optional[ChangeClassificationResult] = None
    specialized_result: Optional[CraterEjectaCandidateResult] = None
    false_positive_result: Optional[FalsePositiveValidationResult] = None


@dataclass(frozen=True)
class TemporalChangeValidationResult:
    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    status: TemporalChangeValidationStatus
    gates: tuple[ValidationGate, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "status": self.status.value,
            "gates": [gate.to_dict() for gate in self.gates],
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }


def _status_name(value: Any) -> str:
    if value is None:
        return "none"
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _build_result(
    request: TemporalChangeValidationRequest,
    status: TemporalChangeValidationStatus,
    *,
    gates: tuple[ValidationGate, ...],
    warnings: tuple[str, ...] = (),
    failure_reasons: tuple[str, ...] = (),
    message: str,
) -> TemporalChangeValidationResult:
    pair = request.pair
    return TemporalChangeValidationResult(
        pair.observation_a.observation_id,
        pair.observation_b.observation_id,
        status,
        gates,
        warnings,
        failure_reasons,
        {
            "phase": "m4_10.12",
            "upstream_phase_chain": "m4_10.7_to_m4_10.11",
            "scientific_interpretation": "consistent evidence chain required; no confirmed crater, impact, ejecta, or geological interpretation is claimed.",
            "config": {"minimum_inlier_ratio": request.config.minimum_inlier_ratio, "minimum_spatial_coverage": request.config.minimum_spatial_coverage, "maximum_rmse": request.config.maximum_rmse, "minimum_valid_fraction": request.config.minimum_valid_fraction, "minimum_support_pixels": request.config.minimum_support_pixels},
        },
        message,
    )


def _candidate_count(value: Optional[ChangeCandidateResult]) -> int:
    if value is None:
        return 0
    return int(getattr(value, "candidate_count", 0) or 0)


def _matches_pair(value: Any, pair: ObservationPair) -> bool:
    if value is None:
        return True
    return (
        getattr(value, "observation_a_id", None) == pair.observation_a.observation_id
        and getattr(value, "observation_b_id", None) == pair.observation_b.observation_id
    )


def validate_temporal_change(request: TemporalChangeValidationRequest) -> TemporalChangeValidationResult:
    """Apply the final M4 temporal-change validation gate.

    The validation is intentionally conservative. A true-positive status is only
    returned when all required evidence gates are satisfied and the authoritative
    10.11 false-positive check did not expose decisive false-positive evidence.
    """
    if not isinstance(request, TemporalChangeValidationRequest):
        raise TypeError("TemporalChangeValidationRequest is required.")
    pair = request.pair
    if not isinstance(pair, ObservationPair):
        raise TypeError("request.pair must be an ObservationPair.")

    gates: list[ValidationGate] = []
    warnings: list[str] = []
    failure_reasons: list[str] = []

    real_chain = (
        pair.observation_a.is_real_data
        and pair.observation_b.is_real_data
        and pair.observation_a.provenance is DataProvenance.REAL
        and pair.observation_b.provenance is DataProvenance.REAL
    )
    if not real_chain:
        gates.append(ValidationGate("provenance_real_data", "failed", False, "Synthetic or non-real observations are not eligible for final temporal validation."))
        return _build_result(
            request,
            TemporalChangeValidationStatus.VALIDATION_BLOCKED,
            gates=tuple(gates),
            warnings=tuple(warnings),
            failure_reasons=("synthetic_or_non_real_data",),
            message="Final temporal validation is blocked: synthetic or non-real observations cannot support a real temporal-change claim.",
        )
    gates.append(ValidationGate("provenance_real_data", "passed", True, "Both observations are real-data provenance records."))

    if pair.observation_a.parsed_acquisition_time is None or pair.observation_b.parsed_acquisition_time is None:
        gates.append(ValidationGate("distinct_temporal_metadata", "failed", False, "Both observations require genuine acquisition timestamps."))
        return _build_result(
            request,
            TemporalChangeValidationStatus.VALIDATION_BLOCKED,
            gates=tuple(gates),
            warnings=tuple(warnings),
            failure_reasons=("missing_temporal_metadata",),
            message="Final temporal validation is blocked because the temporal metadata chain is incomplete.",
        )
    if pair.observation_a.parsed_acquisition_time == pair.observation_b.parsed_acquisition_time:
        gates.append(ValidationGate("distinct_temporal_metadata", "failed", False, "The pair does not contain distinct acquisition timestamps."))
        return _build_result(
            request,
            TemporalChangeValidationStatus.VALIDATION_BLOCKED,
            gates=tuple(gates),
            warnings=tuple(warnings),
            failure_reasons=("same_acquisition_timestamp",),
            message="Final temporal validation is blocked because the pair does not satisfy temporal distinctness.",
        )
    gates.append(ValidationGate("distinct_temporal_metadata", "passed", True, "The observation pair contains distinct real acquisition timestamps."))

    selection = request.selection_result
    if selection is not None:
        if not isinstance(selection, PairSelectionResult):
            gates.append(ValidationGate("pair_selection", "failed", False, "Selection result is malformed."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_pair_selection",), message="Final temporal validation is blocked because the pair-selection contract is invalid.")
        if selection.eligibility is not PairEligibility.ELIGIBLE:
            gates.append(ValidationGate("pair_selection", "failed", False, "The pair was not eligible for a temporal-change validation chain."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("ineligible_pair",) + tuple(selection.hard_rejection_reasons), message="Final temporal validation is blocked because the observation pair is not eligible for temporal comparison.")
        gates.append(ValidationGate("pair_selection", "passed", True, "The pair satisfies the Phase 10.3 eligibility contract."))
    else:
        gates.append(ValidationGate("pair_selection", "inconclusive", False, "No pair-selection result was supplied; validation cannot complete deterministically."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("pair_selection_not_supplied",), message="Final temporal validation is inconclusive because the pair-selection gate was not provided.")

    registration = request.registration_result
    if registration is not None:
        if not isinstance(registration, TemporalRegistrationResult):
            gates.append(ValidationGate("registration", "failed", False, "Registration output did not match the expected Phase 10.4 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_registration_result",), message="Final temporal validation is blocked because the registration result is invalid.")
        if not _matches_pair(registration, pair):
            gates.append(ValidationGate("registration", "failed", False, "Registration result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the registration result does not refer to the supplied pair.")
        if registration.status is not RegistrationStatus.SUCCESS:
            gates.append(ValidationGate("registration", "failed", False, f"Registration status was {registration.status.value} rather than success."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("registration_failed",), message="Final temporal validation is blocked because the registration stage did not succeed.")
        inlier_ratio = registration.inlier_ratio if registration.inlier_ratio is not None else 0.0
        spatial_coverage = registration.spatial_coverage if registration.spatial_coverage is not None else 0.0
        rmse = registration.registration_rmse if registration.registration_rmse is not None else float("inf")
        ok = inlier_ratio >= request.config.minimum_inlier_ratio and spatial_coverage >= request.config.minimum_spatial_coverage and rmse <= request.config.maximum_rmse
        if not ok:
            gates.append(ValidationGate("registration", "failed", False, f"Registration metrics were below the required thresholds: inlier_ratio={inlier_ratio}, coverage={spatial_coverage}, rmse={rmse}."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("registration_metrics_insufficient",), message="Final temporal validation is blocked because registration quality metrics do not satisfy the deterministic gate.")
        gates.append(ValidationGate("registration", "passed", True, f"Registration quality satisfied the thresholds: inlier_ratio={inlier_ratio}, coverage={spatial_coverage}, rmse={rmse}."))
    else:
        gates.append(ValidationGate("registration", "inconclusive", False, "No registration result was supplied; final validation cannot be accepted without it."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("registration_result_missing",), message="Final temporal validation is inconclusive because the registration gate was not supplied.")

    illumination = request.illumination_result
    if illumination is not None:
        if not isinstance(illumination, IlluminationFilterResult):
            gates.append(ValidationGate("illumination", "failed", False, "Illumination result did not match the expected Phase 10.6 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_illumination_result",), message="Final temporal validation is blocked because the illumination result is invalid.")
        if not _matches_pair(illumination, pair):
            gates.append(ValidationGate("illumination", "failed", False, "Illumination result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the illumination result does not describe the supplied pair.")
        status = illumination.status
        if status is IlluminationFilterStatus.INSUFFICIENT_ILLUMINATION_MODEL:
            gates.append(ValidationGate("illumination", "failed", False, "The illumination metadata gate did not permit a defensible comparison."))
            return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("illumination_metadata_incomplete",), message="Final temporal validation is inconclusive because illumination metadata was insufficient for a defensible comparison.")
        assessment = illumination.assessment
        if getattr(assessment, "status", None) is IlluminationAssessmentStatus.DIFFERENT:
            gates.append(ValidationGate("illumination", "failed", False, "The illumination gate reported a materially different geometry and therefore prevented acceptance."))
            return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("illumination_geometry_different",), message="Final temporal validation is inconclusive because the illumination gate reported incompatible geometry.")
        gates.append(ValidationGate("illumination", "passed", True, "The illumination gate did not find a material metadata incompatibility."))
    else:
        gates.append(ValidationGate("illumination", "inconclusive", False, "No illumination gate result was supplied; the final validation remains incomplete."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("illumination_result_missing",), message="Final temporal validation is inconclusive because the illumination gate was not supplied.")

    difference = request.difference_result
    if difference is not None:
        if not isinstance(difference, ImageDifferenceResult):
            gates.append(ValidationGate("differencing", "failed", False, "Difference result did not match the expected Phase 10.5 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_difference_result",), message="Final temporal validation is blocked because the differencing result is invalid.")
        if not _matches_pair(difference, pair):
            gates.append(ValidationGate("differencing", "failed", False, "Difference result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the differencing result does not describe the supplied pair.")
        if difference.status is not DifferenceStatus.SUCCESS:
            gates.append(ValidationGate("differencing", "failed", False, f"Difference stage did not succeed: {difference.status.value if hasattr(difference.status, 'value') else difference.status}."))
            return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("difference_result_unsuccessful",), message="Final temporal validation is inconclusive because the differencing stage did not produce a usable comparison.")
        valid_fraction = float(difference.valid_fraction if difference.valid_fraction is not None else 0.0)
        if valid_fraction < request.config.minimum_valid_fraction:
            gates.append(ValidationGate("differencing", "failed", False, f"Valid comparison fraction was too low: {valid_fraction} < {request.config.minimum_valid_fraction}."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("low_valid_fraction",), message="Final temporal validation is blocked because the differencing stage did not retain enough valid data.")
        gates.append(ValidationGate("differencing", "passed", True, f"Difference stage succeeded with valid_fraction={valid_fraction}."))
    else:
        gates.append(ValidationGate("differencing", "inconclusive", False, "No differencing result was supplied; no final acceptance is possible."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("difference_result_missing",), message="Final temporal validation is inconclusive because the differencing result was not supplied.")

    noise = request.noise_result
    if noise is not None:
        if not isinstance(noise, NoiseSuppressionResult):
            gates.append(ValidationGate("noise_suppression", "failed", False, "Noise result did not match the expected Phase 10.7 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_noise_result",), message="Final temporal validation is blocked because the noise-suppression result is invalid.")
        if not _matches_pair(noise, pair):
            gates.append(ValidationGate("noise_suppression", "failed", False, "Noise result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the noise-suppression result does not describe the supplied pair.")
        if noise.status is not NoiseSuppressionStatus.SUCCESS:
            gates.append(ValidationGate("noise_suppression", "failed", False, "Noise suppression did not succeed."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("noise_suppression_failed",), message="Final temporal validation is blocked because the noise-suppression stage did not succeed.")
        gates.append(ValidationGate("noise_suppression", "passed", True, "Noise suppression succeeded and preserved a viable valid mask."))
    else:
        gates.append(ValidationGate("noise_suppression", "inconclusive", False, "No noise-suppression result was supplied; the temporal-change chain remains incomplete."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("noise_result_missing",), message="Final temporal validation is inconclusive because the noise-suppression result was not supplied.")

    candidate = request.candidate_result
    if candidate is not None:
        if not isinstance(candidate, ChangeCandidateResult):
            gates.append(ValidationGate("candidate_detection", "failed", False, "Candidate result did not match the Phase 10.8 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_candidate_result",), message="Final temporal validation is blocked because the candidate-detection result is invalid.")
        if not _matches_pair(candidate, pair):
            gates.append(ValidationGate("candidate_detection", "failed", False, "Candidate result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the candidate result does not describe the supplied pair.")
        if candidate.status is ChangeCandidateStatus.NO_CANDIDATES or _candidate_count(candidate) == 0:
            gates.append(ValidationGate("candidate_detection", "no_candidates", False, "No temporal candidates were detected in the authoritative chain."))
            return _build_result(request, TemporalChangeValidationStatus.NO_CANDIDATES, gates=tuple(gates), warnings=("no_candidate_detected",), message="Final temporal validation returns NO_CANDIDATES because the chain did not produce an authoritative candidate.")
        if candidate.status not in (ChangeCandidateStatus.SUCCESS, ChangeCandidateStatus.NO_CANDIDATES):
            gates.append(ValidationGate("candidate_detection", "failed", False, f"Candidate detection failed with status {candidate.status.value}."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("candidate_detection_failed",), message="Final temporal validation is blocked because candidate detection failed.")
        gates.append(ValidationGate("candidate_detection", "passed", True, f"Candidate detection succeeded with {_candidate_count(candidate)} candidate(s)."))
    else:
        gates.append(ValidationGate("candidate_detection", "inconclusive", False, "No candidate-detection result was supplied; final validation cannot accept without it."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("candidate_result_missing",), message="Final temporal validation is inconclusive because the candidate-detection result was not supplied.")

    classification = request.classification_result
    if classification is not None:
        if not isinstance(classification, ChangeClassificationResult):
            gates.append(ValidationGate("classification", "failed", False, "Classification result did not match the Phase 10.9 contract."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_classification_result",), message="Final temporal validation is blocked because the classification result is invalid.")
        if not _matches_pair(classification, pair):
            gates.append(ValidationGate("classification", "failed", False, "Classification result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the classification result does not describe the supplied pair.")
        if classification.status is ChangeClassificationStatus.NO_CANDIDATES:
            gates.append(ValidationGate("classification", "no_candidates", False, "No authoritative classifications were produced."))
            return _build_result(request, TemporalChangeValidationStatus.NO_CANDIDATES, gates=tuple(gates), warnings=("no_classification_for_candidates",), message="Final temporal validation returns NO_CANDIDATES because the candidate chain did not produce a valid classification.")
        if classification.status is not ChangeClassificationStatus.SUCCESS:
            gates.append(ValidationGate("classification", "failed", False, f"Classification failed with status {classification.status.value}."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("classification_failed",), message="Final temporal validation is blocked because the classification stage did not succeed.")
        gates.append(ValidationGate("classification", "passed", True, f"Classification succeeded with {classification.candidate_count} record(s)."))
    else:
        gates.append(ValidationGate("classification", "inconclusive", False, "No classification result was supplied; final validation remains incomplete."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("classification_result_missing",), message="Final temporal validation is inconclusive because the classification result was not supplied.")

    if request.specialized_result is not None:
        if not isinstance(request.specialized_result, CraterEjectaCandidateResult):
            gates.append(ValidationGate("specialized_screening", "failed", False, "Specialized-candidate result was malformed."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_specialized_result",), message="Final temporal validation is blocked because the specialized-candidate result is invalid.")
        if not _matches_pair(request.specialized_result, pair):
            gates.append(ValidationGate("specialized_screening", "failed", False, "Specialized-candidate result does not match the supplied observation pair."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the specialized-candidate result does not describe the supplied pair.")
        if request.specialized_result.status in (CraterEjectaCandidateStatus.NO_CANDIDATES, CraterEjectaCandidateStatus.NO_SPECIALIZED_CANDIDATES):
            gates.append(ValidationGate("specialized_screening", "no_candidates", False, "The specialized screening did not produce a candidate that could be carried forward."))
            return _build_result(request, TemporalChangeValidationStatus.NO_CANDIDATES, gates=tuple(gates), warnings=("no_specialized_candidate",), message="Final temporal validation returns NO_CANDIDATES because no specialized candidate remained after the authoritative screening chain.")
        if request.specialized_result.status is not CraterEjectaCandidateStatus.SUCCESS:
            gates.append(ValidationGate("specialized_screening", "failed", False, f"Specialized screening failed with status {request.specialized_result.status.value}."))
            return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("specialized_screening_failed",), message="Final temporal validation is blocked because the specialized screening stage did not succeed.")
        gates.append(ValidationGate("specialized_screening", "passed", True, f"Specialized screening succeeded with {request.specialized_result.specialized_candidate_count} specialized candidate(s)."))

    false_positive = request.false_positive_result
    if false_positive is None:
        gates.append(ValidationGate("false_positive_validation", "inconclusive", False, "No Phase 10.11 false-positive validation result was supplied; final validation cannot be accepted without it."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("false_positive_result_missing",), message="Final temporal validation is inconclusive because the Phase 10.11 false-positive validation result was not supplied.")
    if not isinstance(false_positive, FalsePositiveValidationResult):
        gates.append(ValidationGate("false_positive_validation", "failed", False, "False-positive validation result is malformed."))
        return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("invalid_false_positive_result",), message="Final temporal validation is blocked because the false-positive validation artifact is invalid.")
    if not _matches_pair(false_positive, pair):
        gates.append(ValidationGate("false_positive_validation", "failed", False, "False-positive validation result does not match the supplied observation pair."))
        return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("observation_id_mismatch",), message="Final temporal validation is blocked because the false-positive validation result describes a different pair.")
    fp_status = false_positive.status
    if fp_status in (FalsePositiveValidationStatus.FALSE_POSITIVE, FalsePositiveValidationStatus.LIKELY_FALSE_POSITIVE):
        gates.append(ValidationGate("false_positive_validation", "rejected", False, "The authoritative 10.11 false-positive check found decisive artifact evidence and therefore rejected the temporal-change claim."))
        return _build_result(request, TemporalChangeValidationStatus.REJECTED_FALSE_POSITIVE, gates=tuple(gates), failure_reasons=("decisive_false_positive_evidence",), message="Final temporal validation rejects the candidate because decisive false-positive evidence remained in the authoritative chain; this is not confirmation of a physical lunar change.")
    if fp_status is FalsePositiveValidationStatus.NO_CANDIDATES:
        gates.append(ValidationGate("false_positive_validation", "no_candidates", False, "The false-positive validator reported no authoritative candidates to accept."))
        return _build_result(request, TemporalChangeValidationStatus.NO_CANDIDATES, gates=tuple(gates), warnings=("false_positive_no_candidates",), message="Final temporal validation returns NO_CANDIDATES because the false-positive validator did not retain an authoritative candidate for final acceptance.")
    if fp_status is FalsePositiveValidationStatus.INCONCLUSIVE:
        gates.append(ValidationGate("false_positive_validation", "inconclusive", False, "False-positive validation remained inconclusive and therefore did not permit final acceptance."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("false_positive_inconclusive",), message="Final temporal validation is inconclusive because the false-positive validation step did not reach a decisive negative result.")
    if fp_status is FalsePositiveValidationStatus.VALIDATION_BLOCKED:
        gates.append(ValidationGate("false_positive_validation", "blocked", False, "False-positive validation was blocked and therefore prevented final acceptance."))
        return _build_result(request, TemporalChangeValidationStatus.VALIDATION_BLOCKED, gates=tuple(gates), failure_reasons=("false_positive_validation_blocked",), message="Final temporal validation is blocked because the false-positive validation step was unable to evaluate the chain.")
    if fp_status is not FalsePositiveValidationStatus.NO_FALSE_POSITIVE_EVIDENCE:
        gates.append(ValidationGate("false_positive_validation", "inconclusive", False, f"False-positive validation reported an unexpected status: {fp_status.value}."))
        return _build_result(request, TemporalChangeValidationStatus.INCONCLUSIVE, gates=tuple(gates), warnings=("unexpected_false_positive_status",), message="Final temporal validation is inconclusive because the false-positive validation status was not decisive.")
    gates.append(ValidationGate("false_positive_validation", "passed", True, "False-positive validation did not identify decisive artifact evidence in the authoritative chain."))

    # Final acceptance is limited to a fully consistent real-data chain with no leak of false-positive evidence.
    gates.append(ValidationGate("final_acceptance", "passed", True, "The full chain is consistent and no decisive false-positive evidence remained; this does not claim a confirmed physical process."))
    return _build_result(
        request,
        TemporalChangeValidationStatus.VALIDATED_TEMPORAL_CHANGE,
        gates=tuple(gates),
        warnings=tuple(warnings),
        failure_reasons=tuple(failure_reasons),
        message="Final temporal validation accepted the evidence chain as a valid temporal-change candidate under the conservative Phase 10.12 gates. This is not confirmation of a crater, impact, ejecta deposit, or other physical geological interpretation.",
    )
