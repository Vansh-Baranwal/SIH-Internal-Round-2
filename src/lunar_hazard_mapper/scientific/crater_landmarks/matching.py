"""
Member 4 — Crater Landmark Matching & Registration Anchor Selection.

Provides deterministic selection, ranking, and validation of CraterLandmark registration anchors
from validated CraterLandmarkNetwork outputs.
"""

from __future__ import annotations

import numpy as np

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .network import CraterLandmarkNetwork
from .retrieval import CraterLandmarkRetriever
from .types import CraterLandmark


@dataclass(frozen=True)
class RegistrationAnchor:
    """
    Selected registration anchor record derived from a validated CraterLandmark.

    Parameters
    ----------
    crater_id : str
        Unique crater identifier of the anchor.
    landmark : CraterLandmark
        Underlying M4 CraterLandmark object.
    quality_score : float
        Combined quality score [0.0, 1.0].
    classification : str
        Quality classification ('HIGH', 'MEDIUM', 'LOW').
    rank : int
        Deterministic 1-indexed selection rank.
    selection_reason : str
        Scientific rationale for anchor selection.
    metadata : dict
        Auxiliary metadata for the anchor.
    """

    crater_id: str
    landmark: CraterLandmark
    quality_score: float
    classification: str
    rank: int
    selection_reason: str = "High quality stable crater landmark"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.crater_id, str) or not self.crater_id.strip():
            raise ValueError("crater_id cannot be empty.")
        if not isinstance(self.landmark, CraterLandmark):
            raise TypeError("landmark must be an instance of CraterLandmark.")
        if not (0.0 <= float(self.quality_score) <= 1.0):
            raise ValueError("quality_score must be between 0.0 and 1.0.")
        if self.rank <= 0:
            raise ValueError("rank must be a positive integer.")

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic dictionary serialization of the anchor.
        """
        return {
            "crater_id": self.crater_id,
            "rank": self.rank,
            "quality_score": self.quality_score,
            "classification": self.classification,
            "selection_reason": self.selection_reason,
            "landmark": self.landmark.to_dict(),
            "metadata": self.metadata,
        }

    def summary(self) -> Dict[str, Any]:
        """
        Summary representation of the registration anchor.
        """
        return {
            "crater_id": self.crater_id,
            "rank": self.rank,
            "quality_score": self.quality_score,
            "classification": self.classification,
            "latitude_deg": self.landmark.latitude_deg,
            "longitude_deg": self.landmark.longitude_deg,
            "diameter_m": self.landmark.diameter_m,
        }


class RegistrationAnchorSelector:
    """
    Deterministic selector for identifying and ranking stable crater registration anchors.
    """

    @staticmethod
    def select_anchors(
        landmarks: Union[List[CraterLandmark], CraterLandmarkNetwork, CraterLandmarkRetriever],
        min_quality_score: float = 0.80,
        classification: Optional[str] = None,
        max_anchors: Optional[int] = None,
    ) -> List[RegistrationAnchor]:
        """
        Select and rank registration anchors from landmark candidates.

        Sorting strategy:
        1. Primary: quality_score DESC (highest quality first)
        2. Secondary (tie-breaker): crater_id ASC (alphabetical)

        Parameters
        ----------
        landmarks : list of CraterLandmark, CraterLandmarkNetwork, or CraterLandmarkRetriever
            Candidates to select anchors from.
        min_quality_score : float
            Minimum quality score threshold [0.0, 1.0]. Default is 0.80.
        classification : str, optional
            Optional classification filter ('HIGH', 'MEDIUM', 'LOW').
        max_anchors : int, optional
            Maximum number of anchors to return.

        Returns
        -------
        list of RegistrationAnchor
            Ranked registration anchors.
        """
        # Validate min_quality_score
        if not isinstance(min_quality_score, (int, float)) or not (0.0 <= float(min_quality_score) <= 1.0):
            raise ValueError("min_quality_score must be a float between 0.0 and 1.0.")

        # Validate classification
        if classification is not None:
            allowed = {"HIGH", "MEDIUM", "LOW"}
            if not isinstance(classification, str) or classification.upper() not in allowed:
                raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")

        # Validate max_anchors
        if max_anchors is not None:
            if not isinstance(max_anchors, int) or max_anchors <= 0:
                raise ValueError("max_anchors must be a positive integer.")

        # Resolve candidate list
        if isinstance(landmarks, CraterLandmarkNetwork):
            candidate_list = landmarks.landmarks()
        elif isinstance(landmarks, CraterLandmarkRetriever):
            candidate_list = landmarks.get_all()
        elif isinstance(landmarks, list):
            candidate_list = landmarks
        else:
            raise TypeError(
                "landmarks must be a list of CraterLandmark, CraterLandmarkNetwork, or CraterLandmarkRetriever."
            )

        # Filter & validate individual candidates
        filtered: List[CraterLandmark] = []
        for item in candidate_list:
            if not isinstance(item, CraterLandmark):
                raise TypeError("Each candidate item must be an instance of CraterLandmark.")

            score = item.quality_score if item.quality_score is not None else 0.0
            if score < min_quality_score:
                continue

            if classification is not None:
                item_cls = item.quality.classification if item.quality is not None else None
                if item_cls != classification.upper():
                    continue

            filtered.append(item)

        # Deterministic sorting:
        # Primary: score descending (-score)
        # Secondary: crater_id ascending
        sorted_candidates = sorted(
            filtered,
            key=lambda lm: (-(lm.quality_score if lm.quality_score is not None else 0.0), lm.crater_id),
        )

        if max_anchors is not None:
            sorted_candidates = sorted_candidates[:max_anchors]

        anchors: List[RegistrationAnchor] = []
        for idx, lm in enumerate(sorted_candidates, start=1):
            score = lm.quality_score if lm.quality_score is not None else 0.0
            cls_str = (
                lm.quality.classification
                if lm.quality is not None
                else ("HIGH" if score >= 0.80 else ("MEDIUM" if score >= 0.60 else "LOW"))
            )
            anchors.append(
                RegistrationAnchor(
                    crater_id=lm.crater_id,
                    landmark=lm,
                    quality_score=score,
                    classification=cls_str,
                    rank=idx,
                    selection_reason=f"Selected anchor rank #{idx} with quality score {score:.3f}",
                )
            )

        return anchors


def select_registration_anchors(
    landmarks: Union[List[CraterLandmark], CraterLandmarkNetwork, CraterLandmarkRetriever],
    min_quality_score: float = 0.80,
    classification: Optional[str] = None,
    max_anchors: Optional[int] = None,
) -> List[RegistrationAnchor]:
    """
    Convenience function to select and rank registration anchors.
    """
    return RegistrationAnchorSelector.select_anchors(
        landmarks=landmarks,
        min_quality_score=min_quality_score,
        classification=classification,
        max_anchors=max_anchors,
    )


# ---------------------------------------------------------------------------
# M4-07.7 — Landmark matching across Sun conditions.
#
# The matcher below operates on the existing CraterLandmark representation
# (geometry + radial DEM profile). It is intentionally independent from
# crater_id and from any registration/pose/transform logic: it only decides
# whether two landmark records correspond. Ground truth is never consumed here.
# ---------------------------------------------------------------------------

# Default match threshold. Same-crater landmark signatures are essentially
# identical (similarity = 1.0) because crater geometry is derived from the
# illumination-independent DEM. Distinct synthetic craters of clearly different
# size and depth-to-radius ratio measured at most ~0.825 similarity, so 0.85
# separates true matches from distinct craters with margin.
DEFAULT_MATCH_THRESHOLD = 0.85


@dataclass(frozen=True)
class LandmarkMatch:
    """
    Result of matching a query landmark against a set of candidate landmarks.

    This is the matcher's own output. It does NOT contain any registration,
    pose, coordinate-transform, or geographic information: only the queried
    landmark identity, the best candidate identity, a similarity score, and a
    boolean match decision.
    """

    query_id: str
    candidate_id: Optional[str]
    similarity: float
    matched: bool
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic JSON-friendly serialization."""
        return {
            "query_id": self.query_id,
            "candidate_id": self.candidate_id,
            "similarity": float(self.similarity),
            "matched": bool(self.matched),
            "reason": self.reason,
        }


def _rel_close(first: float, second: float) -> float:
    """Relative closeness in [0, 1]; 1.0 when both values are equal (incl. 0)."""
    first = float(first)
    second = float(second)
    magnitude = max(abs(first), abs(second))
    if magnitude <= 1e-9:
        return 1.0
    return float(np.clip(1.0 - abs(first - second) / magnitude, 0.0, 1.0))


def _profile_vector(
    landmark: CraterLandmark,
    bins: int = 16,
) -> np.ndarray:
    """
    Normalize a landmark's radial DEM profile into a fixed-length shape vector.

    Distances are scaled to [0, 1] and elevations are normalized to a [0, 1]
    shape curve, so the vector is a scale-invariant crater-shape descriptor.
    """
    if landmark.dem_profile is None:
        return np.full(bins, np.nan)
    distances = np.asarray(landmark.dem_profile.distances_m, dtype=float)
    elevations = np.asarray(landmark.dem_profile.elevations_m, dtype=float)
    if len(distances) < 2 or float(np.max(distances)) <= 0.0:
        return np.zeros(bins)

    t = distances / float(np.max(distances))
    low = float(np.min(elevations))
    high = float(np.max(elevations))
    if (high - low) <= 1e-9:
        shape = np.zeros_like(elevations)
    else:
        shape = (elevations - low) / (high - low)

    grid = np.linspace(0.0, 1.0, bins)
    return np.interp(grid, t, shape)


def landmark_signature(landmark: CraterLandmark, profile_bins: int = 16) -> Dict[str, Any]:
    """
    Build a deterministic, illumination-invariant landmark descriptor.

    The signature is derived only from the existing CraterLandmark geometry and
    radial DEM profile (both originate from the DEM, not the rendered image), so
    it does not change with SunState for the same physical crater.

    Raises:
        TypeError: if ``landmark`` is not a CraterLandmark.
        ValueError: if the landmark has no geometry (required for matching).
    """
    if not isinstance(landmark, CraterLandmark):
        raise TypeError("landmark must be an instance of CraterLandmark.")
    geometry = landmark.geometry
    if geometry is None:
        raise ValueError("Landmark geometry is required for matching.")

    radius_m = float(geometry.radius_m) if geometry.radius_m is not None else 0.0
    depth_m = float(geometry.depth_m) if geometry.depth_m is not None else 0.0
    circularity = float(geometry.circularity) if geometry.circularity is not None else 0.0
    depth_to_radius = (depth_m / radius_m) if radius_m > 0.0 else 0.0

    return {
        "diameter_m": float(geometry.diameter_m),
        "depth_m": depth_m,
        "circularity": circularity,
        "depth_to_radius": depth_to_radius,
        "profile": _profile_vector(landmark, profile_bins),
    }


def landmark_similarity(first: CraterLandmark, second: CraterLandmark) -> float:
    """
    Compute a deterministic geometric similarity in [0, 1] between two landmarks.

    The score combines scale (diameter), depth, circularity, a scale-invariant
    depth-to-radius ratio, and a normalized radial-profile shape comparison.
    It is based on the existing crater-geometry representation (illumination
    independent), never on crater_id.

    Raises:
        TypeError: if either input is not a CraterLandmark.
    """
    if not isinstance(first, CraterLandmark) or not isinstance(second, CraterLandmark):
        raise TypeError("Both inputs must be CraterLandmark instances.")

    sig_a = landmark_signature(first)
    sig_b = landmark_signature(second)

    diameter_sim = _rel_close(sig_a["diameter_m"], sig_b["diameter_m"])
    depth_sim = _rel_close(sig_a["depth_m"], sig_b["depth_m"])
    circularity_sim = _rel_close(sig_a["circularity"], sig_b["circularity"])
    depth_ratio_sim = _rel_close(sig_a["depth_to_radius"], sig_b["depth_to_radius"])

    profile_a = sig_a["profile"]
    profile_b = sig_b["profile"]
    if np.isnan(profile_a).any() or np.isnan(profile_b).any():
        profile_sim = 0.0
    else:
        profile_sim = float(np.clip(1.0 - np.mean(np.abs(profile_a - profile_b)), 0.0, 1.0))

    score = (
        0.30 * diameter_sim
        + 0.25 * depth_sim
        + 0.10 * circularity_sim
        + 0.15 * depth_ratio_sim
        + 0.20 * profile_sim
    )
    return float(np.clip(score, 0.0, 1.0))


def match_landmarks(
    query: CraterLandmark,
    candidates: Union[List[CraterLandmark], CraterLandmarkNetwork],
    match_threshold: Optional[float] = None,
) -> LandmarkMatch:
    """
    Match a query landmark against a set of candidate landmarks.

    The best candidate (highest geometric similarity) is reported; it is
    considered a match only if its similarity is at least ``match_threshold``.
    The decision is based solely on the landmark representation, never on
    crater_id and never on ground truth.

    Args:
        query: The query landmark.
        candidates: Candidate landmarks (list/tuple or a CraterLandmarkNetwork).
        match_threshold: Minimum similarity to count as a match. Default 0.80.

    Returns:
        LandmarkMatch.

    Raises:
        TypeError: if inputs have the wrong types.
        ValueError: if the threshold is outside [0, 1].
    """
    if not isinstance(query, CraterLandmark):
        raise TypeError("query must be an instance of CraterLandmark.")

    if isinstance(candidates, CraterLandmarkNetwork):
        candidate_list = candidates.landmarks()
    elif isinstance(candidates, (list, tuple)):
        candidate_list = list(candidates)
    else:
        raise TypeError(
            "candidates must be a list/tuple of CraterLandmark or a CraterLandmarkNetwork."
        )

    if not candidate_list:
        return LandmarkMatch(
            query_id=query.crater_id,
            candidate_id=None,
            similarity=0.0,
            matched=False,
            reason="no candidates provided",
        )

    for candidate in candidate_list:
        if not isinstance(candidate, CraterLandmark):
            raise TypeError("Each candidate must be an instance of CraterLandmark.")

    threshold = DEFAULT_MATCH_THRESHOLD if match_threshold is None else float(match_threshold)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("match_threshold must be between 0.0 and 1.0.")

    best_candidate: Optional[CraterLandmark] = None
    best_similarity = -1.0
    for candidate in candidate_list:
        similarity = landmark_similarity(query, candidate)
        if similarity > best_similarity:
            best_similarity = similarity
            best_candidate = candidate

    matched = best_candidate is not None and best_similarity >= threshold
    return LandmarkMatch(
        query_id=query.crater_id,
        candidate_id=best_candidate.crater_id if best_candidate is not None else None,
        similarity=best_similarity,
        matched=matched,
        reason=(
            "best candidate similarity meets threshold" if matched
            else "no candidate meets match threshold"
        ),
    )

