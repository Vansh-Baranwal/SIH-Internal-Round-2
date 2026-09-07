"""Phase 11.5 anchor selection for correspondence candidates.

This module consumes an existing Phase 11.4 `LandmarkCorrespondenceResult` and
selects a subset of candidate landmark IDs to pass into downstream geometric
verification. It does not estimate coordinates, perform geometric verification,
or localize the unknown image.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

from lunar_hazard_mapper.m4_terrain.landmark_correspondence import (
    LandmarkCorrespondenceRecord,
    LandmarkCorrespondenceResult,
)


class AnchorSelectionStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_CORRESPONDENCE = "no_correspondence"
    NO_ELIGIBLE_ANCHORS = "no_eligible_anchors"
    SINGLE_ANCHOR_SELECTED = "single_anchor_selected"
    MULTIPLE_ANCHORS_SELECTED = "multiple_anchors_selected"
    AMBIGUOUS_ANCHORS = "ambiguous_anchors"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_INPUT = "invalid_input"
    PROVENANCE_BLOCKED = "provenance_blocked"
    ANCHOR_SELECTION_FAILED = "anchor_selection_failed"


@dataclass(frozen=True)
class AnchorSelectionConfig:
    min_surviving_matches: int = 1
    min_tentative_matches: int = 1
    min_survival_ratio: float = 0.0
    max_anchors: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.min_surviving_matches, int) or self.min_surviving_matches < 1:
            raise ValueError("min_surviving_matches must be a positive integer.")
        if not isinstance(self.min_tentative_matches, int) or self.min_tentative_matches < 1:
            raise ValueError("min_tentative_matches must be a positive integer.")
        if not isinstance(self.max_anchors, int) or self.max_anchors < 1:
            raise ValueError("max_anchors must be a positive integer.")
        if not isinstance(self.min_survival_ratio, (int, float)):
            raise ValueError("min_survival_ratio must be a finite numeric value.")
        ratio = float(self.min_survival_ratio)
        if not np.isfinite(ratio) or not (0.0 <= ratio <= 1.0):
            raise ValueError("min_survival_ratio must be between 0.0 and 1.0.")
        object.__setattr__(self, "min_survival_ratio", ratio)


@dataclass(frozen=True)
class AnchorCandidateEvidence:
    candidate_id: str
    surviving_match_count: int
    tentative_match_count: int
    survival_ratio: float
    mean_descriptor_distance: float
    mean_similarity: float
    feature_coverage: float
    selection_score: float
    eligibility_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "surviving_match_count": self.surviving_match_count,
            "tentative_match_count": self.tentative_match_count,
            "survival_ratio": self.survival_ratio,
            "mean_descriptor_distance": self.mean_descriptor_distance,
            "mean_similarity": self.mean_similarity,
            "feature_coverage": self.feature_coverage,
            "selection_score": self.selection_score,
            "eligibility_reason": self.eligibility_reason,
        }


@dataclass(frozen=True)
class AnchorSelectionResult:
    status: AnchorSelectionStatus
    selected_anchor_ids: List[str]
    rejected_anchor_ids: List[str]
    ambiguous_anchor_ids: List[str]
    ranking: Tuple[Tuple[str, float], ...]
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    claims_localization: bool = False
    claims_geometric_verification: bool = False
    claims_localization_confidence: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "selected_anchor_ids": list(self.selected_anchor_ids),
            "rejected_anchor_ids": list(self.rejected_anchor_ids),
            "ambiguous_anchor_ids": list(self.ambiguous_anchor_ids),
            "ranking": [
                {"candidate_id": candidate_id, "selection_score": score}
                for candidate_id, score in self.ranking
            ],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
            "claims_localization": self.claims_localization,
            "claims_geometric_verification": self.claims_geometric_verification,
            "claims_localization_confidence": self.claims_localization_confidence,
        }


def _safe_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    numeric = [float(v) for v in values if np.isfinite(v)]
    if not numeric:
        return 0.0
    return float(mean(numeric))


def _selection_score(record: LandmarkCorrespondenceRecord, *, min_surviving_matches: int, min_tentative_matches: int) -> Tuple[float, str]:
    tentative = int(record.tentative_match_count)
    surviving = int(record.surviving_match_count)
    if tentative < min_tentative_matches:
        return 0.0, "insufficient_tentative_matches"
    if surviving < min_surviving_matches:
        return 0.0, "insufficient_surviving_matches"
    if tentative == 0:
        return 0.0, "no_tentative_matches"
    survival_ratio = float(surviving) / float(tentative)
    similarity_values = tuple(float(v) for v in record.similarity_scores if np.isfinite(v))
    distance_values = tuple(float(v) for v in record.descriptor_distances if np.isfinite(v))
    mean_similarity = _safe_mean(similarity_values)
    mean_distance = _safe_mean(distance_values)
    feature_coverage = float(min(1.0, surviving / max(1, record.reference_feature_count, record.unknown_feature_count)))
    distance_component = 1.0 / (1.0 + mean_distance) if mean_distance > 0.0 else 1.0
    score = (
        float(surviving) * 100.0
        + survival_ratio * 20.0
        + mean_similarity * 10.0
        + distance_component * 5.0
        + feature_coverage * 10.0
    )
    return float(score), "eligible"


def _normalize_result(result: LandmarkCorrespondenceResult) -> List[LandmarkCorrespondenceRecord]:
    if not isinstance(result, LandmarkCorrespondenceResult):
        raise TypeError("result must be a LandmarkCorrespondenceResult instance.")
    if result.records is None:
        return []
    return list(result.records)


def select_anchors(
    correspondence_result: LandmarkCorrespondenceResult,
    *,
    config: AnchorSelectionConfig | None = None,
) -> AnchorSelectionResult:
    """Select candidate anchors from a frozen Phase 11.4 correspondence result.

    The selection is based only on evidence produced by Phase 11.4 and the
    configuration values supplied for this phase. Anchor selection is not a
    geometric verification step and does not estimate spatial coordinates.
    """
    if not isinstance(correspondence_result, LandmarkCorrespondenceResult):
        raise TypeError("correspondence_result must be a LandmarkCorrespondenceResult instance.")

    config = config or AnchorSelectionConfig()
    if not isinstance(config, AnchorSelectionConfig):
        raise TypeError("config must be an AnchorSelectionConfig instance.")

    records = _normalize_result(correspondence_result)
    candidate_ids = list(correspondence_result.candidate_ids)
    if not candidate_ids:
        return AnchorSelectionResult(
            status=AnchorSelectionStatus.NO_CANDIDATES,
            selected_anchor_ids=[],
            rejected_anchor_ids=[],
            ambiguous_anchor_ids=[],
            ranking=(),
            warnings=("no_candidate_landmarks",),
            limitations=("No candidate landmark IDs were supplied by the upstream retrieval result.",),
            provenance={**dict(correspondence_result.provenance), "selection_config": config.__dict__},
            claims_localization=False,
            claims_geometric_verification=False,
            claims_localization_confidence=False,
        )

    record_by_id = {record.candidate_id: record for record in records}
    ranked: List[AnchorCandidateEvidence] = []
    rejected: List[str] = []
    for candidate_id in candidate_ids:
        record = record_by_id.get(candidate_id)
        if record is None:
            rejected.append(candidate_id)
            continue
        if record.status in {
            record.status.REFERENCE_FEATURES_UNAVAILABLE,
            record.status.IMAGE_UNAVAILABLE,
            record.status.INVALID_INPUT,
            record.status.INCOMPATIBLE_FEATURES,
            record.status.NO_CORRESPONDENCES,
            record.status.CORRESPONDENCE_FAILED,
        }:
            rejected.append(candidate_id)
            continue
        score, reason = _selection_score(
            record,
            min_surviving_matches=config.min_surviving_matches,
            min_tentative_matches=config.min_tentative_matches,
        )
        if score <= 0.0:
            rejected.append(candidate_id)
            continue
        if record.tentative_match_count > 0:
            survival_ratio = float(record.surviving_match_count) / float(record.tentative_match_count)
        else:
            survival_ratio = 0.0
        if survival_ratio < float(config.min_survival_ratio):
            rejected.append(candidate_id)
            continue
        mean_similarity = _safe_mean(tuple(float(v) for v in record.similarity_scores if np.isfinite(v)))
        mean_distance = _safe_mean(tuple(float(v) for v in record.descriptor_distances if np.isfinite(v)))
        feature_coverage = min(1.0, float(record.surviving_match_count) / max(1, record.reference_feature_count, record.unknown_feature_count))
        ranked.append(
            AnchorCandidateEvidence(
                candidate_id=candidate_id,
                surviving_match_count=int(record.surviving_match_count),
                tentative_match_count=int(record.tentative_match_count),
                survival_ratio=survival_ratio,
                mean_descriptor_distance=mean_distance,
                mean_similarity=mean_similarity,
                feature_coverage=feature_coverage,
                selection_score=score,
                eligibility_reason=reason,
            )
        )

    qualified = sorted(ranked, key=lambda item: (-item.selection_score, item.candidate_id))
    selected = [item.candidate_id for item in qualified[: config.max_anchors]]
    ambiguous = [item.candidate_id for item in qualified[config.max_anchors:]]

    if not selected:
        warnings = ("no_eligible_anchors",)
        limitations = (
            "No candidate satisfied the configured surviving-match and ratio thresholds for anchor selection.",
            "Anchor selection does not constitute geometric verification or localization.",
        )
        final_status = AnchorSelectionStatus.NO_ELIGIBLE_ANCHORS
        if not records:
            final_status = AnchorSelectionStatus.NO_CORRESPONDENCE
        return AnchorSelectionResult(
            status=final_status,
            selected_anchor_ids=[],
            rejected_anchor_ids=sorted(set(candidate_ids) - set(selected)) if candidate_ids else [],
            ambiguous_anchor_ids=[],
            ranking=tuple((item.candidate_id, item.selection_score) for item in qualified),
            warnings=warnings,
            limitations=limitations,
            provenance={
                **dict(correspondence_result.provenance),
                "selection_config": config.__dict__,
                "selection_method": "surviving_match_count_then_similarity_then_candidate_id",
                "geometric_verification_performed": False,
            },
            claims_localization=False,
            claims_geometric_verification=False,
            claims_localization_confidence=False,
        )

    if len(selected) == 1:
        status = AnchorSelectionStatus.SINGLE_ANCHOR_SELECTED
    elif len(selected) > 1:
        status = AnchorSelectionStatus.MULTIPLE_ANCHORS_SELECTED
    else:
        status = AnchorSelectionStatus.SUCCESS

    warnings = tuple()
    limitations = (
        "Anchor selection is a downstream preparation step only and does not confirm a geometric transformation or localization.",
    )
    if ambiguous:
        warnings = ("ambiguous_anchor_selection",)
        limitations = limitations + ("Multiple eligible anchor candidates remain ambiguous under the current deterministic selection rule.",)
        status = AnchorSelectionStatus.AMBIGUOUS_ANCHORS if len(selected) == 1 else status

    return AnchorSelectionResult(
        status=status,
        selected_anchor_ids=selected,
        rejected_anchor_ids=sorted(set(candidate_ids) - set(selected) - set(ambiguous)),
        ambiguous_anchor_ids=ambiguous,
        ranking=tuple((item.candidate_id, item.selection_score) for item in qualified),
        warnings=warnings,
        limitations=limitations,
        provenance={
            **dict(correspondence_result.provenance),
            "selection_config": config.__dict__,
            "selection_method": "surviving_match_count_then_similarity_then_candidate_id",
            "unknown_image_provenance": correspondence_result.provenance.get("unknown_image_provenance"),
            "candidate_provenance": correspondence_result.provenance.get("candidate_provenance"),
            "geometric_verification_performed": False,
        },
        claims_localization=False,
        claims_geometric_verification=False,
        claims_localization_confidence=False,
    )


__all__ = [
    "AnchorCandidateEvidence",
    "AnchorSelectionConfig",
    "AnchorSelectionResult",
    "AnchorSelectionStatus",
    "select_anchors",
]
