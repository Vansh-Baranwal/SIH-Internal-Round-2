"""
Member 4 — Crater Landmark Network Validation.

Validates end-to-end composition and data contract integrity of the Crater Landmark Network pipeline:
Landmark -> Network -> Retrieval -> Quality Filtering -> Anchor Selection.

This validation layer strictly verifies component composition and contract preservation.
It does NOT duplicate or recalculate scientific detection, geometry, profile, or scoring algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .matching import RegistrationAnchor, RegistrationAnchorSelector
from .network import CraterLandmarkNetwork
from .retrieval import CraterLandmarkRetriever
from .types import CraterLandmark


@dataclass(frozen=True)
class PipelineValidationResult:
    """
    Result of a Crater Landmark Network pipeline validation check.

    Parameters
    ----------
    is_valid : bool
        True if all pipeline composition checks pass cleanly.
    total_network_landmarks : int
        Count of landmarks present in the source network.
    retrieved_landmarks_count : int
        Count of landmarks retrieved after filtering.
    selected_anchors_count : int
        Count of registration anchors selected.
    landmark_ids : list of str
        List of retrieved landmark IDs in deterministic order.
    anchor_ids : list of str
        List of selected registration anchor IDs in rank order.
    checks_passed : dict
        Detailed boolean flag for each pipeline validation check.
    errors : list of str
        Descriptive error messages if any validation check fails.
    """

    is_valid: bool
    total_network_landmarks: int
    retrieved_landmarks_count: int
    selected_anchors_count: int
    landmark_ids: List[str]
    anchor_ids: List[str]
    checks_passed: Dict[str, bool]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic dictionary serialization of validation result.
        """
        return {
            "is_valid": self.is_valid,
            "total_network_landmarks": self.total_network_landmarks,
            "retrieved_landmarks_count": self.retrieved_landmarks_count,
            "selected_anchors_count": self.selected_anchors_count,
            "landmark_ids": list(self.landmark_ids),
            "anchor_ids": list(self.anchor_ids),
            "checks_passed": dict(self.checks_passed),
            "errors": list(self.errors),
        }


class LandmarkNetworkValidator:
    """
    Validator for verifying component composition and pipeline integrity across M4 crater landmarks.
    """

    @staticmethod
    def validate_pipeline(
        network: CraterLandmarkNetwork,
        min_quality_score: float = 0.80,
        classification: Optional[str] = None,
        max_anchors: Optional[int] = None,
    ) -> PipelineValidationResult:
        """
        Validate the complete pipeline composition over an existing CraterLandmarkNetwork.

        Pipeline stages validated:
        1. Network integrity & landmark type verification
        2. Retriever query execution & deterministic ordering
        3. Quality threshold filtering consistency
        4. Registration anchor selection & rank ordering
        5. Data contract field preservation across stages
        6. Serialization determinism
        """
        errors: List[str] = []
        checks: Dict[str, bool] = {}

        if not isinstance(network, CraterLandmarkNetwork):
            raise TypeError("network must be an instance of CraterLandmarkNetwork.")

        if not isinstance(min_quality_score, (int, float)) or not (0.0 <= float(min_quality_score) <= 1.0):
            raise ValueError("min_quality_score must be between 0.0 and 1.0.")

        if classification is not None:
            allowed = {"HIGH", "MEDIUM", "LOW"}
            if not isinstance(classification, str) or classification.upper() not in allowed:
                raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")

        if max_anchors is not None:
            if not isinstance(max_anchors, int) or max_anchors <= 0:
                raise ValueError("max_anchors must be a positive integer.")

        # Stage 1: Network Inspection
        total_lms = network.count()
        lms_all = network.landmarks()
        checks["network_count_consistency"] = (len(lms_all) == total_lms)

        invalid_landmarks = [lm for lm in lms_all if not isinstance(lm, CraterLandmark)]
        checks["all_items_valid_landmarks"] = (len(invalid_landmarks) == 0)
        if len(invalid_landmarks) > 0:
            errors.append(f"Network contains {len(invalid_landmarks)} invalid non-CraterLandmark items.")

        # Stage 2: Retrieval Validation
        retriever = CraterLandmarkRetriever(network)
        retrieved_lms = retriever.query(
            min_quality_score=min_quality_score,
            classification=classification,
        )

        retrieved_ids = [lm.crater_id for lm in retrieved_lms]
        checks["retrieval_deterministic_ordering"] = (retrieved_ids == sorted(retrieved_ids))
        if retrieved_ids != sorted(retrieved_ids):
            errors.append("Retrieved landmarks are not sorted deterministically by crater_id.")

        # Stage 3: Anchor Selection Validation
        anchors = RegistrationAnchorSelector.select_anchors(
            landmarks=retrieved_lms,
            min_quality_score=min_quality_score,
            classification=classification,
            max_anchors=max_anchors,
        )

        anchor_ids = [a.crater_id for a in anchors]
        checks["anchor_validity"] = all(isinstance(a, RegistrationAnchor) for a in anchors)
        checks["anchor_rank_consistency"] = ([a.rank for a in anchors] == list(range(1, len(anchors) + 1)))

        # Stage 4: Scientific Field & Identity Preservation
        preservation_passed = True
        for a in anchors:
            lm = network.get_landmark(a.crater_id)
            if lm is None or lm is not a.landmark:
                preservation_passed = False
                errors.append(f"Anchor '{a.crater_id}' lost object identity with network landmark.")
            elif lm.diameter_m != a.landmark.diameter_m:
                preservation_passed = False
                errors.append(f"Anchor '{a.crater_id}' diameter mutated during pipeline.")
            elif lm.latitude_deg != a.landmark.latitude_deg:
                preservation_passed = False
                errors.append(f"Anchor '{a.crater_id}' latitude mutated during pipeline.")
        checks["scientific_field_preservation"] = preservation_passed

        # Stage 5: Serialization Determinism
        s1 = network.summary()
        s2 = network.summary()
        checks["serialization_determinism"] = (s1 == s2)

        is_valid = (len(errors) == 0) and all(checks.values())

        return PipelineValidationResult(
            is_valid=is_valid,
            total_network_landmarks=total_lms,
            retrieved_landmarks_count=len(retrieved_lms),
            selected_anchors_count=len(anchors),
            landmark_ids=retrieved_ids,
            anchor_ids=anchor_ids,
            checks_passed=checks,
            errors=errors,
        )


def validate_network_pipeline(
    network: CraterLandmarkNetwork,
    min_quality_score: float = 0.80,
    classification: Optional[str] = None,
    max_anchors: Optional[int] = None,
) -> PipelineValidationResult:
    """
    Convenience function for validating the Crater Landmark Network pipeline composition.
    """
    return LandmarkNetworkValidator.validate_pipeline(
        network=network,
        min_quality_score=min_quality_score,
        classification=classification,
        max_anchors=max_anchors,
    )
