"""M4-12.9 Replaceable Hazard Overlay Data Contract.

Bridges hazard information to the 3D Digital Twin viewer.
Spatially associated with the DEM-backed terrain.
No scientific hazard detection or ML inference is implemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation
from lunar_hazard_mapper.m4_terrain.provider import SyntheticTerrainProvider


class HazardDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    ESTIMATED = "estimated"
    REAL = "real"
    UNKNOWN = "unknown"


class HazardSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class HazardType(str, Enum):
    STEEP_SLOPE = "STEEP_SLOPE"
    BOULDER_FIELD = "BOULDER_FIELD"
    CRATER_RIM = "CRATER_RIM"
    SHADOW_ZONE = "SHADOW_ZONE"
    UNSTABLE_TERRAIN = "UNSTABLE_TERRAIN"


@dataclass(frozen=True)
class HazardItem:
    """Individual hazard element for 3D Digital Twin visualization.

    Coordinates follow Three.js render axes: X=local East, Y=local Up (elevation), Z=local North (metres).
    """

    hazard_id: str
    hazard_type: str
    severity: str
    risk_score: float
    position_m: Tuple[float, float, float]
    radius_m: Optional[float] = 50.0
    boundary_vertices_m: Optional[List[Tuple[float, float, float]]] = None
    confidence: Optional[float] = None
    description: str = ""
    data_status: HazardDataStatus = HazardDataStatus.SYNTHETIC
    provenance: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if not self.hazard_id:
            raise ValueError("hazard_id cannot be empty.")
        if len(self.position_m) != 3:
            raise ValueError("position_m must have 3 coordinates (x, y, z).")
        if not (0.0 <= self.risk_score <= 1.0):
            raise ValueError("risk_score must be between 0.0 and 1.0.")
        if self.radius_m is not None and self.radius_m <= 0:
            raise ValueError("radius_m must be positive.")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0.")

    def payload(self) -> Dict[str, Any]:
        res = {
            "hazard_id": self.hazard_id,
            "hazard_type": self.hazard_type,
            "severity": self.severity,
            "risk_score": float(self.risk_score),
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "description": self.description,
            "position_m": {
                "x": float(self.position_m[0]),
                "y": float(self.position_m[1]),
                "z": float(self.position_m[2]),
            },
            "radius_m": float(self.radius_m) if self.radius_m is not None else None,
            "data_status": self.data_status.value,
            "provenance": dict(self.provenance or {}),
        }
        if self.boundary_vertices_m:
            res["boundary_vertices_m"] = [
                {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])}
                for v in self.boundary_vertices_m
            ]
        else:
            res["boundary_vertices_m"] = None
        return res


HazardModel = HazardItem


@dataclass(frozen=True)
class HazardSetModel:
    """Collection of hazards returned by a HazardProvider."""

    hazards: List[HazardItem]
    data_status: HazardDataStatus
    provenance: Dict[str, Any]

    @property
    def display_label(self) -> str:
        if self.data_status is HazardDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT HAZARDS"
        if self.data_status is HazardDataStatus.ESTIMATED:
            return "MODEL ESTIMATED HAZARDS"
        if self.data_status is HazardDataStatus.REAL:
            return "REAL AUTHORITATIVE HAZARDS"
        return "HAZARD OVERLAYS"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "hazard_count": len(self.hazards),
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "hazards": [h.payload() for h in self.hazards],
            "provenance": dict(self.provenance),
        }


class HazardProvider(ABC):
    """Provider boundary between hazard datasets and the 3D viewer."""

    @abstractmethod
    def load_hazards(self, foundation: Optional[TerrainFoundation] = None) -> HazardSetModel:
        raise NotImplementedError


class SyntheticHazardProvider(HazardProvider):
    """Isolated, non-scientific development configuration supplying synthetic hazards for 3D visualization."""

    def load_hazards(self, foundation: Optional[TerrainFoundation] = None) -> HazardSetModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())

        elev = foundation.dem.elevation
        tr = foundation.dem.transform

        def sample_elev(east_m: float, north_m: float, offset: float = 1.5) -> float:
            col = int(round((east_m - tr.c) / tr.a - 0.5))
            row = int(round((north_m - tr.f) / tr.e - 0.5))
            if 0 <= row < elev.shape[0] and 0 <= col < elev.shape[1]:
                return float(elev[row, col]) + offset
            return 30.0 + offset

        # Hazard 1: Steep Slope Region around crater slope
        pos1 = (850.0, sample_elev(850.0, -1150.0), -1150.0)
        # Polygon boundary around slope region
        poly1 = [
            (800.0, sample_elev(800.0, -1100.0), -1100.0),
            (900.0, sample_elev(900.0, -1100.0), -1100.0),
            (920.0, sample_elev(920.0, -1200.0), -1200.0),
            (820.0, sample_elev(820.0, -1200.0), -1200.0),
        ]

        # Hazard 2: Boulder Field near landing area
        pos2 = (1450.0, sample_elev(1450.0, -1300.0), -1300.0)
        poly2 = [
            (1400.0, sample_elev(1400.0, -1250.0), -1250.0),
            (1500.0, sample_elev(1500.0, -1260.0), -1260.0),
            (1520.0, sample_elev(1520.0, -1350.0), -1350.0),
            (1420.0, sample_elev(1420.0, -1340.0), -1340.0),
        ]

        # Hazard 3: Crater Rim Sharp Incline
        pos3 = (1750.0, sample_elev(1750.0, -750.0), -750.0)

        hazards = [
            HazardItem(
                hazard_id="HAZARD_SYNTHETIC_001",
                hazard_type=HazardType.STEEP_SLOPE.value,
                severity=HazardSeverity.CRITICAL.value,
                risk_score=0.92,
                confidence=0.89,
                position_m=pos1,
                radius_m=75.0,
                boundary_vertices_m=poly1,
                description="Excessive terrain slope (> 15°). Severe touchdown tip-over hazard.",
                data_status=HazardDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_9_synthetic_hazard_provider",
                    "note": "Synthetic development hazard overlay. Not real lunar hazard observation.",
                },
            ),
            HazardItem(
                hazard_id="HAZARD_SYNTHETIC_002",
                hazard_type=HazardType.BOULDER_FIELD.value,
                severity=HazardSeverity.HIGH.value,
                risk_score=0.78,
                confidence=0.85,
                position_m=pos2,
                radius_m=60.0,
                boundary_vertices_m=poly2,
                description="Dense boulder cluster (> 0.5m rocks). Gear puncture and landing risk.",
                data_status=HazardDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_9_synthetic_hazard_provider",
                    "note": "Synthetic development hazard overlay. Not real lunar hazard observation.",
                },
            ),
            HazardItem(
                hazard_id="HAZARD_SYNTHETIC_003",
                hazard_type=HazardType.CRATER_RIM.value,
                severity=HazardSeverity.MODERATE.value,
                risk_score=0.55,
                confidence=0.91,
                position_m=pos3,
                radius_m=45.0,
                boundary_vertices_m=None,
                description="Crater rim elevation discontinuity and slope hazard.",
                data_status=HazardDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_9_synthetic_hazard_provider",
                    "note": "Synthetic development hazard overlay. Not real lunar hazard observation.",
                },
            ),
        ]

        return HazardSetModel(
            hazards=hazards,
            data_status=HazardDataStatus.SYNTHETIC,
            provenance={
                "source": "m4_12_9_synthetic_hazard_provider",
                "note": (
                    "Synthetic development visualization only. Values do not represent "
                    "real lunar hazard observations or mission safety maps."
                ),
            },
        )
