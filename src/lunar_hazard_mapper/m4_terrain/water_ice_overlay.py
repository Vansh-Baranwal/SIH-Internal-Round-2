"""M4-12.11 replaceable water-ice visualization data contract.

This module carries spatially associated water-ice *development markers* to
the viewer.  It intentionally contains no detection, abundance, confidence,
spectral, shadow, hazard, or scientific inference logic.  A future real
georeferenced provider can implement the same ``WaterIceProvider`` contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation
from lunar_hazard_mapper.m4_terrain.provider import SyntheticTerrainProvider


class WaterIceDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    ESTIMATED = "estimated"
    REAL = "real"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WaterIceItem:
    """A spatial marker/region with explicit provenance.

    Positions use viewer coordinates: X=east, Y=up/elevation, Z=north, metres.
    Only spatial identity and display metadata are supported by this contract.
    """

    water_ice_id: str
    display_label: str
    position_m: Tuple[float, float, float]
    boundary_vertices_m: Optional[List[Tuple[float, float, float]]] = None
    data_status: WaterIceDataStatus = WaterIceDataStatus.SYNTHETIC
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return self.water_ice_id

    def __post_init__(self) -> None:
        if not self.water_ice_id:
            raise ValueError("water_ice_id cannot be empty.")
        if len(self.position_m) != 3:
            raise ValueError("position_m must have 3 coordinates (x, y, z).")
        if self.boundary_vertices_m is not None and len(self.boundary_vertices_m) < 3:
            raise ValueError("boundary_vertices_m must have at least 3 vertices.")

    def payload(self) -> Dict[str, Any]:
        return {
            "water_ice_id": self.water_ice_id,
            "display_label": self.display_label,
            "position_m": {"x": float(self.position_m[0]), "y": float(self.position_m[1]), "z": float(self.position_m[2])},
            "boundary_vertices_m": ([
                {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])}
                for v in self.boundary_vertices_m
            ] if self.boundary_vertices_m is not None else None),
            "data_status": self.data_status.value,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class WaterIceOverlayModel:
    items: List[WaterIceItem]
    data_status: WaterIceDataStatus
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_label(self) -> str:
        return {
            WaterIceDataStatus.SYNTHETIC: "SYNTHETIC DEVELOPMENT WATER-ICE OVERLAY",
            WaterIceDataStatus.ESTIMATED: "MODEL ESTIMATED WATER-ICE OVERLAY",
            WaterIceDataStatus.REAL: "REAL AUTHORITATIVE WATER-ICE DATA",
        }.get(self.data_status, "WATER-ICE OVERLAY")

    @property
    def regions(self) -> List[WaterIceItem]:
        return self.items

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "item_count": len(self.items),
            "region_count": len(self.items),
            "coordinate_convention": {"x": "local_east_meters", "y": "local_up_meters", "z": "local_north_meters"},
            "items": [item.payload() for item in self.items],
            "regions": [item.payload() for item in self.items],
            "provenance": dict(self.provenance),
        }


WaterIceRegionItem = WaterIceItem
WaterIceModel = WaterIceOverlayModel


class WaterIceProvider(ABC):
    @abstractmethod
    def load_water_ice(self, foundation: Optional[TerrainFoundation] = None) -> WaterIceOverlayModel:
        raise NotImplementedError


class SyntheticWaterIceProvider(WaterIceProvider):
    """Deterministic display-only locations; not observations or detections."""

    def load_water_ice(self, foundation: Optional[TerrainFoundation] = None) -> WaterIceOverlayModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())
        elev = foundation.dem.elevation
        tr = foundation.dem.transform

        def surface(east: float, north: float, offset: float = 1.0) -> float:
            col = int(round((east - tr.c) / tr.a - 0.5))
            row = int(round((north - tr.f) / tr.e - 0.5))
            if 0 <= row < elev.shape[0] and 0 <= col < elev.shape[1]:
                return float(elev[row, col]) + offset
            return offset

        def item(identifier: str, label: str, east: float, north: float, half: float) -> WaterIceItem:
            vertices = [(east-half, surface(east-half, north-half), north-half),
                        (east+half, surface(east+half, north-half), north-half),
                        (east+half, surface(east+half, north+half), north+half),
                        (east-half, surface(east-half, north+half), north+half)]
            return WaterIceItem(identifier, label, (east, surface(east, north), north), vertices,
                                provenance={"source": "m4_12_11_synthetic_water_ice_provider",
                                            "note": "Synthetic development visualization marker; not a real lunar water-ice observation."})

        return WaterIceOverlayModel(
            items=[item("WATER_ICE_SYNTHETIC_001", "Development region A", 900.0, -900.0, 90.0),
                   item("WATER_ICE_SYNTHETIC_002", "Development region B", 1050.0, -1050.0, 75.0),
                   item("WATER_ICE_SYNTHETIC_003", "Development region C", 700.0, -700.0, 65.0)],
            data_status=WaterIceDataStatus.SYNTHETIC,
            provenance={"source": "m4_12_11_synthetic_water_ice_provider",
                        "note": "Synthetic development data for overlay validation only. It does not represent deposits, abundance, concentration, probability, confidence, or mission observations."},
        )
