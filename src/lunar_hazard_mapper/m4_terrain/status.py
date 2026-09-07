"""
M4-12.1 terrain data status / provenance helpers.

The 3D terrain viewer MUST be able to show whether the terrain it renders is
synthetic development data, real georeferenced data, or of unknown provenance.
This module defines that explicit data-status concept and derives it from the
repository's established M3 DEM ``source_type`` labels, so provenance is always
explicit and never inferred from filenames or GLB naming.

CORE RULE (see the M4-12.1 task text): synthetic data must never be presented
as real scientific observation. That rule is enforced here by mapping
``source_type == "synthetic"`` to a distinct data-status whose UI label says
"Synthetic Development Data", and by never labeling synthetic data as measured
lunar terrain, spacecraft observation, or an authoritative lunar DEM.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class TerrainDataStatus(str, Enum):
    """Explicit provenance status a terrain provider can carry."""

    SYNTHETIC = "synthetic"
    REAL = "real"
    UNKNOWN = "unknown"


# Display labels used by the UI / debug metadata. Deliberately unambiguous so
# synthetic development data is never presented as measured lunar terrain and
# real data is never mislabeled as synthetic.
DATA_STATUS_LABELS = {
    TerrainDataStatus.SYNTHETIC: "SYNTHETIC DEVELOPMENT DATA",
    TerrainDataStatus.REAL: "REAL GEOREFERENCED DATA",
    TerrainDataStatus.UNKNOWN: "UNKNOWN / UNAVAILABLE",
}

# Established M3 source_type labels (see m3_terrain/dem.py). We reuse these
# rather than inventing competing vocabulary.
SOURCE_SYNTHETIC = "synthetic"
SOURCE_SR_ESTIMATED = "sr_estimated"
SOURCE_MEASURED = "measured"


def status_from_source_type(source_type: Optional[str]) -> TerrainDataStatus:
    """
    Map an M3 DEM ``source_type`` to an explicit data-status.

    - ``synthetic``  -> SYNTHETIC
    - ``measured``   -> REAL
    - ``sr_estimated`` and anything else -> UNKNOWN

    ``sr_estimated`` is deliberately mapped to UNKNOWN rather than REAL: it is
    an estimate derived from optical imagery, not independently validated
    measured elevation. It is neither confirmed synthetic nor confirmed
    real-measured terrain, so the honest status is UNKNOWN and the precise
    ``source_type`` is still carried alongside for display.
    """
    if source_type == SOURCE_SYNTHETIC:
        return TerrainDataStatus.SYNTHETIC
    if source_type == SOURCE_MEASURED:
        return TerrainDataStatus.REAL
    return TerrainDataStatus.UNKNOWN


def status_from_dem(dem) -> TerrainDataStatus:
    """Derive the data-status from a DEM object by reading its source_type."""
    return status_from_source_type(getattr(dem, "source_type", None))


def display_label_for_status(status: TerrainDataStatus) -> str:
    """Return the unambiguous UI/debug label for a data-status."""
    return DATA_STATUS_LABELS.get(
        status, DATA_STATUS_LABELS[TerrainDataStatus.UNKNOWN]
    )


def synthetic_status_label() -> str:
    """Convenience: the canonical 'synthetic development data' UI label."""
    return display_label_for_status(TerrainDataStatus.SYNTHETIC)
