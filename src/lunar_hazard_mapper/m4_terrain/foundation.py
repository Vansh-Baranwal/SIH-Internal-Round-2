"""
M4-12.1 3D terrain foundation.

``TerrainFoundation`` is the seam between the replaceable terrain data provider
and the 3D viewer. It depends only on the ``TerrainDataProvider`` contract --
never on synthetic specifics -- and produces a uniform, provenance-carrying
description of the terrain in the repository's established local coordinate
convention (x = local East, y = local North, z = local Up, all metres).

A future real georeferenced DEM provider can be injected here without changing
this class or the viewer that consumes its output. Only provenance/display state
differs between a synthetic and a real provider.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import to_local_frame
from lunar_hazard_mapper.m4_terrain.provider import TerrainDataProvider
from lunar_hazard_mapper.m4_terrain.status import (
    TerrainDataStatus,
    display_label_for_status,
)


class TerrainFoundation:
    """
    Bridges a ``TerrainDataProvider`` to the 3D viewer as a uniform terrain view.

    This class holds no knowledge of whether the provider is synthetic or real.
    It only consumes the provider contract (``load_dem``, ``data_status``,
    ``provenance``) and exposes the resulting terrain together with explicit
    provenance/status metadata.
    """

    # Established local coordinate convention (configs/coordinate_convention.yaml).
    COORDINATE_CONVENTION = {
        "x": "local_east_meters",
        "y": "local_north_meters",
        "z": "local_up_meters",
    }

    def __init__(self, provider: TerrainDataProvider) -> None:
        if not isinstance(provider, TerrainDataProvider):
            raise TypeError(
                "TerrainFoundation requires a TerrainDataProvider instance."
            )
        self.provider = provider
        self._dem = None
        self._local_frame = None

    # ------------------------------------------------------------------ #
    # Lazy access to the authoritative DEM via the provider contract
    # ------------------------------------------------------------------ #
    @property
    def dem(self):
        """The authoritative M3 DEM from the provider (loaded lazily)."""
        if self._dem is None:
            self._dem = self.provider.load_dem()
        return self._dem

    @property
    def source_type(self) -> str:
        return self.dem.source_type

    @property
    def is_georeferenced(self) -> bool:
        return bool(self.dem.is_georeferenced)

    @property
    def data_status(self) -> TerrainDataStatus:
        return self.provider.data_status

    @property
    def display_label(self) -> str:
        return display_label_for_status(self.data_status)


    # ------------------------------------------------------------------ #
    # Derived terrain views (all preserved from the DEM semantics)
    # ------------------------------------------------------------------ #
    @property
    def width(self) -> int:
        return int(self.dem.shape[1])

    @property
    def height(self) -> int:
        return int(self.dem.shape[0])

    @property
    def pixel_size_m(self) -> float:
        return float(self.dem.pixel_size_m)

    @property
    def nodata(self) -> float:
        return self.dem.nodata

    @property
    def vertical_units(self) -> str:
        return self.dem.vertical_units

    @property
    def crs(self) -> Optional[str]:
        return self.dem.crs

    def local_frame(self) -> Dict[str, np.ndarray]:
        """
        Local simulation-frame coordinates for every pixel center, using the
        DEM's affine transform. Returns ``x`` (east, m), ``y`` (north, m),
        ``z`` (up, m == elevation). Reuses ``m3_terrain.dem.to_local_frame``.
        """
        if self._local_frame is None:
            self._local_frame = to_local_frame(self.dem)
        return self._local_frame

    def valid_mask(self) -> np.ndarray:
        """
        Boolean valid-mask (True = valid cell) derived from the DEM's nodata
        sentinel and finite-value check. Preserves nodata semantics.
        """
        elev = self.dem.elevation
        return (elev != self.dem.nodata) & np.isfinite(elev)

    @property
    def bounds(self) -> Dict[str, float]:
        """
        Bounding box (metres, local East/North) derived from the DEM's affine
        transform and grid extent, using pixel-corner coordinates so the full
        raster extent is captured. No real-world CRS is assumed.
        """
        tr = self.dem.transform
        width = self.width
        height = self.height
        min_x = float(tr.c)
        max_x = float(tr.c + tr.a * width)
        min_y = float(tr.f + tr.e * height)
        max_y = float(tr.f)
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width_m": float(abs(max_x - min_x)),
            "height_m": float(abs(max_y - min_y)),
        }

    def metadata(self) -> Dict[str, Any]:
        """
        Plain, JSON-friendly descriptive metadata for the terrain. Includes the
        explicit data-status / provenance so the viewer can label the terrain
        synthetic vs real without ever guessing from filenames.
        """
        dem = self.dem
        return {
            "source_type": dem.source_type,
            "data_status": self.data_status.value,
            "display_label": self.display_label,
            "is_georeferenced": self.is_georeferenced,
            "crs": dem.crs,
            "pixel_size_m": float(dem.pixel_size_m),
            "width": self.width,
            "height": self.height,
            "nodata": dem.nodata,
            "vertical_units": dem.vertical_units,
            "bounds": self.bounds,
            "coordinate_convention": dict(self.COORDINATE_CONVENTION),
            "provenance": dict(self.provider.provenance),
            "notes": dem.notes,
        }

    def grid(self) -> Dict[str, Any]:
        """
        Viewer-ready grid arrays: the elevation grid plus local-frame x/y/z
        (east/north/up, metres) and a valid-mask. The 3D viewer (task 12.2+)
        builds its mesh from this via the foundation -- not from synthetic
        implementation details.
        """
        lf = self.local_frame()
        return {
            "width": self.width,
            "height": self.height,
            "pixel_size_m": self.pixel_size_m,
            "elevation": self.dem.elevation,
            "x": lf["x"],
            "y": lf["y"],
            "z": lf["z"],
            "valid_mask": self.valid_mask(),
            "nodata": self.nodata,
            "coordinate_convention": dict(self.COORDINATE_CONVENTION),
        }

    def describe(self) -> Dict[str, Any]:
        """Combined metadata + a compact grid summary for inspection/UI."""
        elev = self.dem.elevation
        vmask = self.valid_mask()
        valid = elev[vmask] if vmask.any() else np.array([], dtype=elev.dtype)
        return {
            "metadata": self.metadata(),
            "grid_summary": {
                "elevation_min_m": float(valid.min()) if valid.size else None,
                "elevation_max_m": float(valid.max()) if valid.size else None,
                "valid_pixels": int(vmask.sum()),
                "total_pixels": int(vmask.size),
                "valid_fraction": float(vmask.mean()) if vmask.size else 0.0,
            },
        }


