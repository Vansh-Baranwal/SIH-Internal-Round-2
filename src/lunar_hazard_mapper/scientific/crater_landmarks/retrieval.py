"""
Member 4 — Crater Landmark Retrieval.

Provides dedicated query and retrieval interfaces over a CraterLandmarkNetwork.
"""

from __future__ import annotations

from typing import List, Optional

from .network import CraterLandmarkNetwork
from .types import CraterLandmark


class CraterLandmarkRetriever:
    """
    Retrieval layer consuming a CraterLandmarkNetwork to execute validated,
    deterministic queries for CraterLandmark records.
    """

    def __init__(self, network: CraterLandmarkNetwork) -> None:
        if not isinstance(network, CraterLandmarkNetwork):
            raise TypeError("network must be an instance of CraterLandmarkNetwork.")
        self._network = network

    @property
    def network(self) -> CraterLandmarkNetwork:
        """Access the underlying CraterLandmarkNetwork."""
        return self._network

    def get_by_id(self, crater_id: str) -> Optional[CraterLandmark]:
        """
        Retrieve a single CraterLandmark by crater_id.

        Returns None if crater_id is missing, empty, or not found in the network.
        """
        if not isinstance(crater_id, str) or not crater_id.strip():
            return None
        return self._network.get_landmark(crater_id.strip())

    def get_all(self) -> List[CraterLandmark]:
        """
        Retrieve all landmarks in the network sorted deterministically by crater_id.
        """
        return self._network.landmarks()

    def get_by_classification(self, classification: str) -> List[CraterLandmark]:
        """
        Retrieve landmarks matching a quality classification ('HIGH', 'MEDIUM', 'LOW').

        Raises
        ------
        ValueError
            If classification is not one of 'HIGH', 'MEDIUM', or 'LOW'.
        """
        allowed = {"HIGH", "MEDIUM", "LOW"}
        if not isinstance(classification, str) or classification.upper() not in allowed:
            raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")

        return self._network.landmarks(classification=classification.upper())

    def get_by_min_quality(self, min_score: float) -> List[CraterLandmark]:
        """
        Retrieve landmarks with an overall quality score >= min_score.

        Raises
        ------
        ValueError
            If min_score is outside [0.0, 1.0].
        """
        if not isinstance(min_score, (int, float)) or not (0.0 <= float(min_score) <= 1.0):
            raise ValueError("min_score must be a float between 0.0 and 1.0.")

        return self._network.landmarks(min_quality_score=float(min_score))

    def query(
        self,
        min_quality_score: Optional[float] = None,
        classification: Optional[str] = None,
        min_diameter_m: Optional[float] = None,
        max_diameter_m: Optional[float] = None,
    ) -> List[CraterLandmark]:
        """
        Flexible deterministic query over the landmark network.

        Parameters
        ----------
        min_quality_score : float, optional
            Minimum overall quality score [0.0, 1.0].
        classification : str, optional
            Quality classification ('HIGH', 'MEDIUM', 'LOW').
        min_diameter_m : float, optional
            Minimum crater diameter in metres (> 0).
        max_diameter_m : float, optional
            Maximum crater diameter in metres (> 0).

        Returns
        -------
        list of CraterLandmark
            Filtered landmarks sorted deterministically by crater_id.
        """
        if min_quality_score is not None:
            if not isinstance(min_quality_score, (int, float)) or not (0.0 <= float(min_quality_score) <= 1.0):
                raise ValueError("min_quality_score must be between 0.0 and 1.0.")

        if classification is not None:
            allowed = {"HIGH", "MEDIUM", "LOW"}
            if not isinstance(classification, str) or classification.upper() not in allowed:
                raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")

        if min_diameter_m is not None:
            if not isinstance(min_diameter_m, (int, float)) or float(min_diameter_m) <= 0:
                raise ValueError("min_diameter_m must be positive.")

        if max_diameter_m is not None:
            if not isinstance(max_diameter_m, (int, float)) or float(max_diameter_m) <= 0:
                raise ValueError("max_diameter_m must be positive.")

        if min_diameter_m is not None and max_diameter_m is not None:
            if min_diameter_m > max_diameter_m:
                raise ValueError("min_diameter_m cannot be greater than max_diameter_m.")

        base_list = self._network.landmarks(
            min_quality_score=min_quality_score,
            classification=classification.upper() if classification else None,
        )

        if min_diameter_m is None and max_diameter_m is None:
            return base_list

        result: List[CraterLandmark] = []
        for lm in base_list:
            if min_diameter_m is not None and lm.diameter_m < min_diameter_m:
                continue
            if max_diameter_m is not None and lm.diameter_m > max_diameter_m:
                continue
            result.append(lm)

        return result


def retrieve_landmark_by_id(
    network: CraterLandmarkNetwork, crater_id: str
) -> Optional[CraterLandmark]:
    """
    Convenience function to retrieve a landmark by crater_id.
    """
    retriever = CraterLandmarkRetriever(network)
    return retriever.get_by_id(crater_id)


def retrieve_landmarks(
    network: CraterLandmarkNetwork,
    min_quality_score: Optional[float] = None,
    classification: Optional[str] = None,
) -> List[CraterLandmark]:
    """
    Convenience function to retrieve landmarks with quality filtering.
    """
    retriever = CraterLandmarkRetriever(network)
    return retriever.query(
        min_quality_score=min_quality_score,
        classification=classification,
    )
