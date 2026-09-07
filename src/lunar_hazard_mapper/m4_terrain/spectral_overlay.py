"""M4-12.10 Replaceable Spectral Overlay Data Contract.

Bridges spectral/band information to the 3D Digital Twin viewer.
Spatially associated with the DEM-backed terrain.
No scientific mineral classification or spectral inference is implemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation
from lunar_hazard_mapper.m4_terrain.provider import SyntheticTerrainProvider


class SpectralDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    ESTIMATED = "estimated"
    REAL = "real"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpectralBand:
    """Individual spectral band descriptor."""

    band_id: str
    name: str
    wavelength_um: Optional[float] = None
    unit: str = "Reflectance (I/F)"

    def payload(self) -> Dict[str, Any]:
        return {
            "band_id": self.band_id,
            "name": self.name,
            "wavelength_um": float(self.wavelength_um) if self.wavelength_um is not None else None,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class SpectralRegionItem:
    """Individual spatial region with associated spectral band values."""

    region_id: str
    display_label: str
    center_m: Tuple[float, float, float]
    boundary_vertices_m: List[Tuple[float, float, float]]
    band_values: Dict[str, float]
    scalar_index: float
    data_status: SpectralDataStatus = SpectralDataStatus.SYNTHETIC
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.region_id:
            raise ValueError("region_id cannot be empty.")
        if len(self.center_m) != 3:
            raise ValueError("center_m must have 3 coordinates (x, y, z).")
        if len(self.boundary_vertices_m) < 3:
            raise ValueError("boundary_vertices_m must have at least 3 vertices.")
        if not (0.0 <= self.scalar_index <= 1.0):
            raise ValueError("scalar_index must be between 0.0 and 1.0.")

    def payload(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "display_label": self.display_label,
            "center_m": {
                "x": float(self.center_m[0]),
                "y": float(self.center_m[1]),
                "z": float(self.center_m[2]),
            },
            "boundary_vertices_m": [
                {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])}
                for v in self.boundary_vertices_m
            ],
            "band_values": {k: float(v) for k, v in self.band_values.items()},
            "scalar_index": float(self.scalar_index),
            "data_status": self.data_status.value,
            "provenance": dict(self.provenance or {}),
        }


@dataclass(frozen=True)
class SpectralOverlayModel:
    """Viewer-facing spectral overlay dataset for the 3D Digital Twin."""

    regions: List[SpectralRegionItem]
    available_bands: List[SpectralBand]
    data_status: SpectralDataStatus
    colormap_name: str = "spectral"
    min_value: float = 0.0
    max_value: float = 1.0
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_label(self) -> str:
        if self.data_status is SpectralDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT SPECTRAL OVERLAY"
        if self.data_status is SpectralDataStatus.ESTIMATED:
            return "MODEL ESTIMATED SPECTRAL OVERLAY"
        if self.data_status is SpectralDataStatus.REAL:
            return "REAL AUTHORITATIVE SPECTRAL DATA"
        return "SPECTRAL OVERLAY"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "region_count": len(self.regions),
            "colormap_name": self.colormap_name,
            "min_value": float(self.min_value),
            "max_value": float(self.max_value),
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "available_bands": [b.payload() for b in self.available_bands],
            "regions": [r.payload() for r in self.regions],
            "provenance": dict(self.provenance),
        }


SpectralModel = SpectralOverlayModel


class SpectralProvider(ABC):
    """Provider boundary between spectral datasets and the 3D viewer."""

    @abstractmethod
    def load_spectral(self, foundation: Optional[TerrainFoundation] = None) -> SpectralOverlayModel:
        raise NotImplementedError


class SyntheticSpectralProvider(SpectralProvider):
    """Isolated, non-scientific development configuration supplying synthetic spectral regions for 3D visualization."""

    def load_spectral(self, foundation: Optional[TerrainFoundation] = None) -> SpectralOverlayModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())

        elev = foundation.dem.elevation
        tr = foundation.dem.transform

        def sample_elev(east_m: float, north_m: float, offset: float = 0.4) -> float:
            col = int(round((east_m - tr.c) / tr.a - 0.5))
            row = int(round((north_m - tr.f) / tr.e - 0.5))
            if 0 <= row < elev.shape[0] and 0 <= col < elev.shape[1]:
                return float(elev[row, col]) + offset
            return 30.0 + offset

        # Define 3 development spectral bands
        bands = [
            SpectralBand(
                band_id="BAND_950NM",
                name="0.95 µm Band (Reflectance)",
                wavelength_um=0.95,
                unit="Reflectance (I/F)",
            ),
            SpectralBand(
                band_id="BAND_1500NM",
                name="1.50 µm Band (Continuum)",
                wavelength_um=1.50,
                unit="Reflectance (I/F)",
            ),
            SpectralBand(
                band_id="BAND_2000NM",
                name="2.00 µm Band (Absorption)",
                wavelength_um=2.00,
                unit="Reflectance (I/F)",
            ),
        ]

        # Region 1: Central Crater Floor Spectral Patch
        c1 = (1150.0, sample_elev(1150.0, -1150.0), -1150.0)
        poly1 = [
            (1050.0, sample_elev(1050.0, -1050.0), -1050.0),
            (1250.0, sample_elev(1250.0, -1050.0), -1050.0),
            (1280.0, sample_elev(1280.0, -1250.0), -1250.0),
            (1080.0, sample_elev(1080.0, -1250.0), -1250.0),
        ]

        # Region 2: Northeast Ejecta Blanket Spectral Patch
        c2 = (1650.0, sample_elev(1650.0, -1000.0), -1000.0)
        poly2 = [
            (1550.0, sample_elev(1550.0, -900.0), -900.0),
            (1750.0, sample_elev(1750.0, -920.0), -920.0),
            (1780.0, sample_elev(1780.0, -1100.0), -1100.0),
            (1580.0, sample_elev(1580.0, -1080.0), -1080.0),
        ]

        # Region 3: Southwest Highland Incline Spectral Patch
        c3 = (750.0, sample_elev(750.0, -1500.0), -1500.0)
        poly3 = [
            (650.0, sample_elev(650.0, -1400.0), -1400.0),
            (850.0, sample_elev(850.0, -1420.0), -1420.0),
            (880.0, sample_elev(880.0, -1600.0), -1600.0),
            (680.0, sample_elev(680.0, -1580.0), -1580.0),
        ]

        regions = [
            SpectralRegionItem(
                region_id="SPEC_REGION_SYNTHETIC_001",
                display_label="Crater Floor Spectral Unit A",
                center_m=c1,
                boundary_vertices_m=poly1,
                band_values={"BAND_950NM": 0.14, "BAND_1500NM": 0.22, "BAND_2000NM": 0.18},
                scalar_index=0.72,
                data_status=SpectralDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_10_synthetic_spectral_provider",
                    "note": "Synthetic development spectral patch. Not real IIRS measurement.",
                },
            ),
            SpectralRegionItem(
                region_id="SPEC_REGION_SYNTHETIC_002",
                display_label="Ejecta Unit B",
                center_m=c2,
                boundary_vertices_m=poly2,
                band_values={"BAND_950NM": 0.18, "BAND_1500NM": 0.28, "BAND_2000NM": 0.24},
                scalar_index=0.88,
                data_status=SpectralDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_10_synthetic_spectral_provider",
                    "note": "Synthetic development spectral patch. Not real IIRS measurement.",
                },
            ),
            SpectralRegionItem(
                region_id="SPEC_REGION_SYNTHETIC_003",
                display_label="Highland Slope Unit C",
                center_m=c3,
                boundary_vertices_m=poly3,
                band_values={"BAND_950NM": 0.09, "BAND_1500NM": 0.15, "BAND_2000NM": 0.11},
                scalar_index=0.45,
                data_status=SpectralDataStatus.SYNTHETIC,
                provenance={
                    "source": "m4_12_10_synthetic_spectral_provider",
                    "note": "Synthetic development spectral patch. Not real IIRS measurement.",
                },
            ),
        ]

        return SpectralOverlayModel(
            regions=regions,
            available_bands=bands,
            data_status=SpectralDataStatus.SYNTHETIC,
            colormap_name="spectral",
            min_value=0.0,
            max_value=1.0,
            provenance={
                "source": "m4_12_10_synthetic_spectral_provider",
                "note": (
                    "Synthetic development spectral overlay. Values do not represent "
                    "real IIRS observations, mineralogical classifications, or calibrated reflectance spectra."
                ),
            },
        )
