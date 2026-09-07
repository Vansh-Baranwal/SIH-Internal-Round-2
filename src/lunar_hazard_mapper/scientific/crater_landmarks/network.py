"""
Member 4 — Crater Landmark Network.

In-memory collection and indexing infrastructure for CraterLandmark registration anchors.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .types import CraterLandmark


class CraterLandmarkNetwork:
    """
    In-memory scientific network of stable crater landmarks.

    Maintains a collection of CraterLandmark objects indexed by unique crater_id,
    providing deterministic ordering, retrieval, and quality-aware filtering.
    """

    def __init__(
        self,
        landmarks: Optional[List[CraterLandmark]] = None,
    ) -> None:
        self._landmarks: Dict[str, CraterLandmark] = {}
        if landmarks is not None:
            for landmark in landmarks:
                self.add_landmark(landmark)

    def add_landmark(self, landmark: CraterLandmark) -> None:
        """
        Add a valid CraterLandmark to the network.

        Parameters
        ----------
        landmark : CraterLandmark
            The landmark object to register.

        Raises
        ------
        TypeError
            If landmark is not an instance of CraterLandmark.
        ValueError
            If a landmark with the same crater_id already exists in the network.
        """
        if not isinstance(landmark, CraterLandmark):
            raise TypeError(
                "landmark must be an instance of CraterLandmark."
            )

        cid = landmark.crater_id
        if cid in self._landmarks:
            raise ValueError(
                f"Landmark with crater_id '{cid}' already exists in the network."
            )

        self._landmarks[cid] = landmark

    def get_landmark(self, crater_id: str) -> Optional[CraterLandmark]:
        """
        Retrieve a landmark by crater_id. Returns None if not found.
        """
        return self._landmarks.get(crater_id)

    def remove_landmark(self, crater_id: str) -> Optional[CraterLandmark]:
        """
        Remove and return a landmark by crater_id. Returns None if not present.
        """
        return self._landmarks.pop(crater_id, None)

    def contains(self, crater_id: str) -> bool:
        """
        Check if a landmark with the given crater_id exists in the network.
        """
        return crater_id in self._landmarks

    def count(self) -> int:
        """
        Return the total number of landmarks stored in the network.
        """
        return len(self._landmarks)

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, crater_id: str) -> bool:
        return self.contains(crater_id)

    def landmarks(
        self,
        min_quality_score: Optional[float] = None,
        classification: Optional[str] = None,
    ) -> List[CraterLandmark]:
        """
        Return stored landmarks in deterministic order (sorted by crater_id).

        Parameters
        ----------
        min_quality_score : float, optional
            Filter landmarks with quality score >= min_quality_score.
        classification : str, optional
            Filter landmarks matching quality classification ('HIGH', 'MEDIUM', 'LOW').

        Returns
        -------
        list of CraterLandmark
            Filtered landmarks sorted by crater_id.
        """
        sorted_ids = sorted(self._landmarks.keys())
        result: List[CraterLandmark] = []

        for cid in sorted_ids:
            lm = self._landmarks[cid]
            if min_quality_score is not None:
                if lm.quality_score is None or lm.quality_score < min_quality_score:
                    continue
            if classification is not None:
                lm_cls = (
                    lm.quality.classification
                    if lm.quality is not None
                    else None
                )
                if lm_cls != classification:
                    continue
            result.append(lm)

        return result

    def get_high_quality_landmarks(self) -> List[CraterLandmark]:
        """
        Return all landmarks classified as HIGH quality (or overall quality score >= 0.80).
        """
        return self.landmarks(classification="HIGH")

    def clear(self) -> None:
        """
        Remove all landmarks from the network.
        """
        self._landmarks.clear()

    def summary(self) -> Dict[str, Any]:
        """
        Return a deterministic summary of the landmark network state.
        """
        ordered_lms = self.landmarks()
        class_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNCLASSIFIED": 0}

        for lm in ordered_lms:
            if lm.quality is not None:
                cls_name = lm.quality.classification
                if cls_name in class_counts:
                    class_counts[cls_name] += 1
                else:
                    class_counts["UNCLASSIFIED"] += 1
            elif lm.quality_score is not None:
                if lm.quality_score >= 0.80:
                    class_counts["HIGH"] += 1
                elif lm.quality_score >= 0.60:
                    class_counts["MEDIUM"] += 1
                else:
                    class_counts["LOW"] += 1
            else:
                class_counts["UNCLASSIFIED"] += 1

        return {
            "total_landmarks": len(ordered_lms),
            "landmark_ids": [lm.crater_id for lm in ordered_lms],
            "quality_classification_counts": class_counts,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic serialization of the entire landmark network.
        """
        ordered_lms = self.landmarks()
        return {
            "total_landmarks": len(ordered_lms),
            "landmarks": {lm.crater_id: lm.to_dict() for lm in ordered_lms},
        }

    def __repr__(self) -> str:
        return f"CraterLandmarkNetwork(count={self.count()})"
