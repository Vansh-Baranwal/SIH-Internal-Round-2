"""
Member 4 — Crater Landmark Quality Contract.

Defines the scientific data contract used by the crater
landmark quality-scoring system.

This module does not calculate quality scores yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QualityClass = Literal[
    "HIGH",
    "MEDIUM",
    "LOW",
]


@dataclass(frozen=True)
class LandmarkQuality:
    """
    Quality assessment for a detected crater landmark.

    All component scores use the normalized range [0, 1].

    Parameters
    ----------
    detection_score:
        Quality/reliability of the crater detection.

    geometry_score:
        Quality of the extracted crater geometry.

    profile_score:
        Quality of the supporting DEM radial profile.

    overall_score:
        Combined landmark quality score.

    classification:
        Human-readable quality category:
        HIGH, MEDIUM, or LOW.
    """

    detection_score: float
    geometry_score: float
    profile_score: float
    overall_score: float
    classification: QualityClass

    def __post_init__(self) -> None:
        """
        Validate the scientific contract.
        """

        scores = {
            "detection_score": self.detection_score,
            "geometry_score": self.geometry_score,
            "profile_score": self.profile_score,
            "overall_score": self.overall_score,
        }

        for name, value in scores.items():

            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0 and 1."
                )

        if self.classification not in {
            "HIGH",
            "MEDIUM",
            "LOW",
        }:
            raise ValueError(
                "classification must be "
                "HIGH, MEDIUM, or LOW."
            )