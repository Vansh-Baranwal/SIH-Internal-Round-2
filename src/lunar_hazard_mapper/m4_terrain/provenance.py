"""
M4 Phase 15.10 — Synthetic-vs-Real Separation Validation

Centralized data provenance registry and classification system for all M4 workspace outputs.

This module provides:
1. A unified classification vocabulary (SYNTHETIC, REAL, ESTIMATED, UNAVAILABLE)
2. A registry of all M4 data outputs and their provenance
3. Utilities to ensure synthetic data is never presented as real
4. Audit trails for data provenance across the application

PRINCIPLE: Synthetic development data must never be presented as real scientific
observation, measured lunar terrain, spacecraft observation, or authoritative data.
All M4 outputs MUST explicitly declare their provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone


class DataProvenance(str, Enum):
    """Unified provenance classification for all M4 data outputs."""

    # Real data: externally sourced, independently validated, scientifically authoritative
    REAL = "real"

    # Synthetic: development/demo data, not real lunar observations or measurements
    SYNTHETIC = "synthetic"

    # Estimated: derived from other data (e.g., super-resolution from optical imagery)
    ESTIMATED = "estimated"

    # Illustrative: conceptual/example data shown for UI/workflow purposes
    ILLUSTRATIVE = "illustrative"

    # Deferred: scientifically unvalidated or unimplemented capability
    DEFERRED = "deferred"

    # Unavailable: data missing, API not connected, or capability not implemented
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProvenanceMetadata:
    """Complete provenance classification for any M4 output."""

    classification: DataProvenance
    source_module: str  # e.g., "m4_12_1_terrain_foundation"
    data_type: str  # e.g., "DEM", "SPECTRAL_OVERLAY", "WATER_ICE_MARKERS"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    description: str = ""
    notes: str = ""
    is_cached: bool = False
    requires_backend_api: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "classification": self.classification.value,
            "source_module": self.source_module,
            "data_type": self.data_type,
            "created_at": self.created_at,
            "description": self.description,
            "notes": self.notes,
            "is_cached": self.is_cached,
            "requires_backend_api": self.requires_backend_api,
        }

    @property
    def ui_label(self) -> str:
        """Human-readable UI label for this provenance."""
        labels = {
            DataProvenance.REAL: "Calibrated Measurement",
            DataProvenance.SYNTHETIC: "Synthetic Development Data",
            DataProvenance.ESTIMATED: "Model Estimated Data",
            DataProvenance.ILLUSTRATIVE: "Illustrative Example",
            DataProvenance.DEFERRED: "Deferred / Unimplemented",
            DataProvenance.UNAVAILABLE: "Unavailable / Missing",
        }
        return labels.get(self.classification, "Unknown")


class M4DataProvenanceRegistry:
    """
    Centralized registry of all M4 workspace data outputs.

    Every output is classified and can be audited by consumers to ensure
    synthetic data is never presented as real-world validated results.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, ProvenanceMetadata] = {}
        self._initialize_registry()

    def _initialize_registry(self) -> None:
        """Populate the registry with all known M4 outputs."""

        # Terrain (Phase 12.1)
        self.register(
            key="terrain_dem",
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_1_terrain_foundation",
            data_type="DEM (Digital Elevation Model)",
            description="3D terrain foundation for the Digital Twin viewer",
            notes="Current implementation uses synthetic terrain generator. Not real lunar observations.",
            requires_backend_api=True,
        )

        # Cameras (Phase 12.3, 12.4, 12.5)
        for sensor, module in [
            ("tmc", "m4_12_3_tmc_camera"),
            ("ohrc", "m4_12_4_ohrc_camera"),
            ("iirs", "m4_12_5_iirs_footprint"),
        ]:
            self.register(
                key=f"camera_{sensor}",
                classification=DataProvenance.SYNTHETIC,
                source_module=module,
                data_type=f"{sensor.upper()} Camera Metadata",
                description=f"{sensor.upper()} camera pose and frustum for visualization",
                notes=f"Synthetic development configuration. Not real {sensor.upper()} metadata or observation.",
                requires_backend_api=True,
            )

        # Landmarks (Phase 12.6)
        self.register(
            key="landmarks",
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_6_landmark_visualization",
            data_type="Landmark Visualization",
            description="Crater landmarks for 3D Digital Twin inspection",
            notes="Synthetic development markers. Not real landmark detections or localizations.",
            requires_backend_api=True,
        )

        # Hazards (Phase 12.9)
        self.register(
            key="hazards",
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_9_hazard_overlay",
            data_type="Hazard Overlay",
            description="Hazard visualization overlays on 3D terrain",
            notes="Synthetic development hazard regions. Not real hazard detections or scientific classifications.",
            requires_backend_api=True,
        )

        # Spectral Intelligence (Phase 12.10)
        self.register(
            key="spectral_overlay",
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_10_spectral_overlay",
            data_type="Spectral Overlay",
            description="Spectral band visualization for IIRS imagery",
            notes="Synthetic development spectral regions. No mineral classification or spectral inference performed.",
            requires_backend_api=True,
        )

        # Water-Ice Intelligence (Phase 12.11)
        self.register(
            key="water_ice_overlay",
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_11_water_ice_overlay",
            data_type="Water-Ice Overlay",
            description="Water-ice marker visualization",
            notes="Synthetic development display markers. Not real water-ice detections or scientific observations.",
            requires_backend_api=True,
        )

        # Sun Simulation (Phase 12.7, 12.8)
        for key, desc in [
            ("sun_control", "Sun position and illumination control"),
            ("counterfactual_sun", "What-if sun angle simulation"),
        ]:
            self.register(
                key=key,
                classification=DataProvenance.ILLUSTRATIVE,
                source_module="m4_12_7_sun_control",
                data_type="Sun Simulation",
                description=desc,
                notes="Illustrative rendering. Not real ephemeris or observation predictions.",
            )

        # Registration (Phase 13.11)
        self.register(
            key="registration_engine",
            classification=DataProvenance.UNAVAILABLE,
            source_module="m4_13_11_registration_cockpit",
            data_type="Image Registration",
            description="Multi-sensor image correspondence and alignment",
            notes="Registration engine not available in this build. No match points or RMSE values are produced.",
        )

        # Temporal Change (Phase 13)
        self.register(
            key="temporal_change",
            classification=DataProvenance.DEFERRED,
            source_module="m4_13_temporal_change",
            data_type="Temporal Change Detection",
            description="Multi-date temporal analysis and change maps",
            notes="Temporal science pipeline is deferred and not implemented. No change values are real.",
        )

        # Mission Status (Phase 13.2)
        self.register(
            key="mission_status",
            classification=DataProvenance.UNAVAILABLE,
            source_module="m4_13_mission_control",
            data_type="Mission Status",
            description="System status and operational overview",
            notes="Mission export status depends on external pipeline execution.",
            requires_backend_api=True,
        )

    def register(
        self,
        key: str,
        classification: DataProvenance,
        source_module: str,
        data_type: str,
        description: str = "",
        notes: str = "",
        requires_backend_api: bool = False,
    ) -> None:
        """Register a data output with its provenance classification."""
        self._registry[key] = ProvenanceMetadata(
            classification=classification,
            source_module=source_module,
            data_type=data_type,
            description=description,
            notes=notes,
            requires_backend_api=requires_backend_api,
        )

    def get(self, key: str) -> Optional[ProvenanceMetadata]:
        """Retrieve provenance metadata for a data output."""
        return self._registry.get(key)

    def is_synthetic(self, key: str) -> bool:
        """Check if a data output is classified as synthetic."""
        meta = self.get(key)
        return meta is not None and meta.classification == DataProvenance.SYNTHETIC

    def is_real(self, key: str) -> bool:
        """Check if a data output is classified as real."""
        meta = self.get(key)
        return meta is not None and meta.classification == DataProvenance.REAL

    def is_available(self, key: str) -> bool:
        """Check if a data output is available."""
        meta = self.get(key)
        return meta is not None and meta.classification not in (
            DataProvenance.UNAVAILABLE,
            DataProvenance.DEFERRED,
        )

    def get_all_synthetic(self) -> Dict[str, ProvenanceMetadata]:
        """Get all data outputs classified as synthetic."""
        return {
            k: v
            for k, v in self._registry.items()
            if v.classification == DataProvenance.SYNTHETIC
        }

    def get_all_real(self) -> Dict[str, ProvenanceMetadata]:
        """Get all data outputs classified as real."""
        return {
            k: v
            for k, v in self._registry.items()
            if v.classification == DataProvenance.REAL
        }

    def get_all_unavailable(self) -> Dict[str, ProvenanceMetadata]:
        """Get all data outputs that are unavailable."""
        return {
            k: v
            for k, v in self._registry.items()
            if v.classification == DataProvenance.UNAVAILABLE
        }

    def get_all_deferred(self) -> Dict[str, ProvenanceMetadata]:
        """Get all data outputs that are deferred."""
        return {
            k: v
            for k, v in self._registry.items()
            if v.classification == DataProvenance.DEFERRED
        }

    def audit_report(self) -> str:
        """Generate an audit report of all registered data and their classifications."""
        lines = [
            "M4 Data Provenance Audit Report",
            "=" * 60,
            "",
            "REGISTRY SUMMARY",
            f"Total entries: {len(self._registry)}",
            f"Synthetic: {len(self.get_all_synthetic())}",
            f"Real: {len(self.get_all_real())}",
            f"Unavailable: {len(self.get_all_unavailable())}",
            f"Deferred: {len(self.get_all_deferred())}",
            "",
            "SYNTHETIC OUTPUTS (May NOT be presented as real)",
            "-" * 60,
        ]

        for key, meta in self.get_all_synthetic().items():
            lines.append(
                f"  {key}: {meta.data_type} ({meta.source_module})"
            )
            lines.append(f"    Note: {meta.notes}")

        lines.append("")
        lines.append("REAL OUTPUTS (May be presented as authoritative)")
        lines.append("-" * 60)

        real_outputs = self.get_all_real()
        if real_outputs:
            for key, meta in real_outputs.items():
                lines.append(f"  {key}: {meta.data_type} ({meta.source_module})")
        else:
            lines.append("  (None currently available)")

        lines.append("")
        lines.append("UNAVAILABLE OUTPUTS (Will not be presented)")
        lines.append("-" * 60)

        for key, meta in self.get_all_unavailable().items():
            lines.append(f"  {key}: {meta.data_type}")
            lines.append(f"    {meta.notes}")

        lines.append("")
        lines.append("DEFERRED OUTPUTS (Will not be presented as real)")
        lines.append("-" * 60)

        for key, meta in self.get_all_deferred().items():
            lines.append(f"  {key}: {meta.data_type}")
            lines.append(f"    {meta.notes}")

        lines.append("")

        return "\n".join(lines)


# Global registry instance
_global_registry: Optional[M4DataProvenanceRegistry] = None


def get_provenance_registry() -> M4DataProvenanceRegistry:
    """Get or create the global provenance registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = M4DataProvenanceRegistry()
    return _global_registry
