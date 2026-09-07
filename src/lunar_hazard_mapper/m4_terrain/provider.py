"""
M4-12.1 replaceable terrain data provider contract.

A ``TerrainDataProvider`` is the single abstraction the 3D terrain foundation
depends on. Today it is backed by the synthetic DEM generator; tomorrow a real
georeferenced DEM provider can implement exactly the same contract and neither
the foundation nor the viewer needs to change.

The contract is defined in terms of the repository's existing M3 ``DEM`` object
(see ``m3_terrain/dem.py``) so we reuse established DEM semantics -- elevation,
pixel_size_m, Affine transform, CRS, nodata, vertical_units, source_type --
rather than inventing a competing representation.

Provenance is mandatory. Every provider must make its source state explicit so
the viewer never infers synthetic-vs-real from filenames or GLB naming, and so
synthetic development data is never presented as real scientific observation.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict

# ``synthetic/terrain`` lives at the repo root and ``m3_terrain`` under ``src``.
# Make both importable regardless of the current working directory.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
for _path in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from lunar_hazard_mapper.m3_terrain.dem import DEM
from lunar_hazard_mapper.m3_terrain.synthetic import create_synthetic_terrain
from lunar_hazard_mapper.m4_terrain.status import (
    SOURCE_SYNTHETIC,
    TerrainDataStatus,
    display_label_for_status,
    status_from_dem,
    synthetic_status_label,
)


class TerrainDataProvider(ABC):
    """
    Contract for any terrain data source feeding the 3D terrain foundation.

    Implementations must:

    - return an authoritative M3 ``DEM`` via :meth:`load_dem` (which carries the
      canonical elevation grid, transform, CRS, nodata, vertical units and
      source_type), and
    - make their provenance / source state explicit via :attr:`source_type`,
      :attr:`data_status` and :attr:`provenance`, so the viewer never guesses it
      and never claims a provenance the provider does not declare.
    """

    @abstractmethod
    def load_dem(self) -> DEM:
        """Return the authoritative elevation product as an M3 ``DEM``."""
        raise NotImplementedError

    @property
    @abstractmethod
    def source_type(self) -> str:
        """``'synthetic'`` | ``'sr_estimated'`` | ``'measured'`` (M3 labels)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def data_status(self) -> TerrainDataStatus:
        """Explicit data-status (synthetic / real / unknown)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def provenance(self) -> Dict[str, Any]:
        """Explicit provenance so the viewer never infers source from files."""
        raise NotImplementedError


class SyntheticTerrainProvider(TerrainDataProvider):
    """
    Exposes the currently available synthetic DEM, clearly tagged SYNTHETIC.

    This is a development / demo source only. It is NOT presented as real lunar
    terrain, a spacecraft observation, or an authoritative lunar DEM. The data
    status and UI label both say "synthetic", and the provenance note repeats
    that the terrain is not real lunar observations, so the distinction stays
    visible downstream.
    """

    def __init__(
        self,
        kind: str = "combined",
        size: int = 256,
        pixel_size_m: float = 10.0,
        generator_notes: str = "",
    ) -> None:
        self._kind = kind
        self._size = size
        self._pixel_size_m = pixel_size_m
        self._generator_notes = generator_notes
        self._dem: DEM | None = None
        self._provenance: Dict[str, Any] = {
            "data_status": TerrainDataStatus.SYNTHETIC.value,
            "display_label": synthetic_status_label(),
            "declared_type": SOURCE_SYNTHETIC,
            "generator": f"synthetic_terrain/{kind}",
            "note": (
                "Synthetic development/demo terrain. NOT real lunar "
                "observations, NOT spacecraft-derived, NOT an authoritative "
                "lunar DEM."
            ),
        }

    def load_dem(self) -> DEM:
        if self._dem is None:
            self._dem = create_synthetic_terrain(
                kind=self._kind,
                size=self._size,
                pixel_size_m=self._pixel_size_m,
            )
            if self._generator_notes:
                self._dem.notes = " ".join(
                    n for n in (self._dem.notes, self._generator_notes) if n
                ).strip()
            # Ensure the synthetic provenance note is always present so the DEM
            # itself carries the explicit "not real" declaration, not just the
            # provider.
            synthetic_note = self._provenance["note"]
            if synthetic_note and synthetic_note not in self._dem.notes:
                self._dem.notes = " ".join(
                    n for n in (self._dem.notes, synthetic_note) if n
                ).strip()
        return self._dem

    @property
    def source_type(self) -> str:
        return SOURCE_SYNTHETIC

    @property
    def data_status(self) -> TerrainDataStatus:
        return TerrainDataStatus.SYNTHETIC

    @property
    def provenance(self) -> Dict[str, Any]:
        return dict(self._provenance)


class DemDataProvider(TerrainDataProvider):
    """
    Generic adapter that wraps any existing M3 ``DEM`` object through the
    provider contract.

    This is the interchangeability bridge: today it can wrap a synthetic DEM,
    and a future real georeferenced DEM object (``source_type == "measured"``,
    a real CRS set) can be passed in through the exact same code path -- the
    foundation and viewer do not need to change. This provider never fabricates
    data; it only adapts the DEM it is given and transparently carries that DEM's
    provenance.

    Note: this is NOT an implementation of a real georeferenced DEM provider. No
    real lunar coordinates, CRS, or elevation values are generated here.
    """

    def __init__(self, dem: DEM, source: str = "wrapped_dem") -> None:
        if not isinstance(dem, DEM):
            raise TypeError(
                "DemDataProvider requires an M3 DEM instance "
                "(m3_terrain.dem.DEM)."
            )
        self._dem = dem
        self._source = source

    def load_dem(self) -> DEM:
        return self._dem

    @property
    def source_type(self) -> str:
        return self._dem.source_type

    @property
    def data_status(self) -> TerrainDataStatus:
        return status_from_dem(self._dem)

    @property
    def provenance(self) -> Dict[str, Any]:
        return {
            "data_status": self.data_status.value,
            "display_label": display_label_for_status(self.data_status),
            "declared_type": self._dem.source_type,
            "source": self._source,
            "note": (
                "Adapted from an existing M3 DEM object; provenance (source_type, "
                "notes) is carried from the DEM itself."
            ),
        }


