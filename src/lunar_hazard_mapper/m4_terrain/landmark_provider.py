"""M4-12.6 Replaceable Landmark Visualization Data Contract.

Consumes Phase 11 crater landmark / localization outputs and bridges them to the 3D viewer.
Preserves strict separation between estimated/localized coordinates and metadata/reference coordinates.
No landmark localization algorithms are reimplemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation
from lunar_hazard_mapper.m4_terrain.provider import SyntheticTerrainProvider


class LandmarkDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    ESTIMATED = "estimated"
    REAL = "real"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LandmarkItem:
    """Individual landmark entry for 3D Digital Twin visualization.

    Coordinates use Three.js render axes: X=local East, Y=local Up (elevation), Z=local North (metres).
    """

    landmark_id: str
    display_label: str
    estimated_position_m: Tuple[float, float, float]
    reference_position_m: Optional[Tuple[float, float, float]] = None
    diameter_m: float = 100.0
    depth_m: Optional[float] = None
    confidence: Optional[float] = None
    quality_score: Optional[float] = None
    localization_status: str = "ESTIMATED"
    data_status: LandmarkDataStatus = LandmarkDataStatus.SYNTHETIC
    provenance: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if not self.landmark_id:
            raise ValueError("landmark_id cannot be empty.")
        if len(self.estimated_position_m) != 3:
            raise ValueError("estimated_position_m must have 3 coordinates (x, y, z).")
        if self.reference_position_m is not None and len(self.reference_position_m) != 3:
            raise ValueError("reference_position_m must have 3 coordinates (x, y, z).")
        if self.diameter_m <= 0:
            raise ValueError("diameter_m must be positive.")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0.")
        if self.quality_score is not None and not (0.0 <= self.quality_score <= 1.0):
            raise ValueError("quality_score must be between 0.0 and 1.0.")

    def payload(self) -> Dict[str, Any]:
        res = {
            "landmark_id": self.landmark_id,
            "display_label": self.display_label,
            "estimated_position_m": {
                "x": float(self.estimated_position_m[0]),
                "y": float(self.estimated_position_m[1]),
                "z": float(self.estimated_position_m[2]),
            },
            "diameter_m": float(self.diameter_m),
            "depth_m": float(self.depth_m) if self.depth_m is not None else None,
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "quality_score": float(self.quality_score) if self.quality_score is not None else None,
            "localization_status": self.localization_status,
            "data_status": self.data_status.value,
            "provenance": dict(self.provenance or {}),
        }
        if self.reference_position_m is not None:
            res["reference_position_m"] = {
                "x": float(self.reference_position_m[0]),
                "y": float(self.reference_position_m[1]),
                "z": float(self.reference_position_m[2]),
            }
        else:
            res["reference_position_m"] = None
        return res


LandmarkModel = LandmarkItem


@dataclass(frozen=True)
class LandmarkSetModel:
    """Collection of landmarks returned by a LandmarkProvider."""

    landmarks: List[LandmarkItem]
    data_status: LandmarkDataStatus
    provenance: Dict[str, Any]

    @property
    def display_label(self) -> str:
        if self.data_status is LandmarkDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT LANDMARKS"
        if self.data_status is LandmarkDataStatus.ESTIMATED:
            return "PHASE 11 LOCALIZED LANDMARKS"
        if self.data_status is LandmarkDataStatus.REAL:
            return "REAL AUTHORITATIVE LANDMARKS"
        return "LANDMARKS UNAVAILABLE"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "landmark_count": len(self.landmarks),
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "landmarks": [lm.payload() for lm in self.landmarks],
            "provenance": dict(self.provenance),
        }


class LandmarkProvider(ABC):
    """Provider boundary between Phase 11 / landmark metadata and the 3D viewer."""

    @abstractmethod
    def load_landmarks(self, foundation: Optional[TerrainFoundation] = None) -> LandmarkSetModel:
        raise NotImplementedError


class SyntheticLandmarkProvider(LandmarkProvider):
    """Isolated, non-scientific development configuration supplying synthetic landmarks for 3D visualization."""

    def load_landmarks(self, foundation: Optional[TerrainFoundation] = None) -> LandmarkSetModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())

        elev = foundation.dem.elevation
        tr = foundation.dem.transform

        def sample_elev(east_m: float, north_m: float) -> float:
            col = int(round((east_m - tr.c) / tr.a - 0.5))
            row = int(round((north_m - tr.f) / tr.e - 0.5))
            if 0 <= row < elev.shape[0] and 0 <= col < elev.shape[1]:
                return float(elev[row, col])
            return 30.0

        # Sample synthetic landmarks distributed on the DEM grid
        lm1_est = (1000.0, sample_elev(1000.0, -1000.0), -1000.0)
        lm1_ref = (1005.0, sample_elev(1005.0, -995.0), -995.0)

        lm2_est = (1600.0, sample_elev(1600.0, -1400.0), -1400.0)
        lm2_ref = (1598.0, sample_elev(1598.0, -1402.0), -1402.0)

        lm3_est = (1280.0, sample_elev(1280.0, -800.0), -800.0)

        landmarks = [
            LandmarkItem(
                landmark_id="CRATER_LUNAR_SYNTHETIC_001",
                display_label="Landmark Crater Alpha",
                estimated_position_m=lm1_est,
                reference_position_m=lm1_ref,
                diameter_m=180.0,
                depth_m=35.0,
                confidence=0.94,
                quality_score=0.91,
                localization_status="ESTIMATED_VS_REFERENCE",
                data_status=LandmarkDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_6_synthetic_landmark_provider",
                    "note": "Synthetic development landmark. Estimated position is distinct from reference position.",
                },
            ),
            LandmarkItem(
                landmark_id="CRATER_LUNAR_SYNTHETIC_002",
                display_label="Landmark Crater Beta",
                estimated_position_m=lm2_est,
                reference_position_m=lm2_ref,
                diameter_m=220.0,
                depth_m=42.0,
                confidence=0.88,
                quality_score=0.85,
                localization_status="ESTIMATED_VS_REFERENCE",
                data_status=LandmarkDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_6_synthetic_landmark_provider",
                    "note": "Synthetic development landmark. Estimated position is distinct from reference position.",
                },
            ),
            LandmarkItem(
                landmark_id="CRATER_LUNAR_SYNTHETIC_003",
                display_label="Landmark Crater Gamma",
                estimated_position_m=lm3_est,
                reference_position_m=None,
                diameter_m=140.0,
                depth_m=25.0,
                confidence=0.96,
                quality_score=0.93,
                localization_status="ESTIMATED_ONLY",
                data_status=LandmarkDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_6_synthetic_landmark_provider",
                    "note": "Synthetic development landmark with estimated position only.",
                },
            ),
        ]

        return LandmarkSetModel(
            landmarks=landmarks,
            data_status=LandmarkDataStatus.SYNTHETIC,
            provenance={
                "source": "m4_12_6_synthetic_landmark_provider",
                "note": (
                    "Synthetic development visualization only. Values do not represent "
                    "real lunar observations, historical crater catalogs, or real mission landmarks."
                ),
            },
        )
