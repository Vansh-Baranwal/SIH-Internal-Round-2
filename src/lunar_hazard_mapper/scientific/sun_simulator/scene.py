"""Scene-level contract combining a DEM and the solar illumination state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
from affine import Affine

from lunar_hazard_mapper.m3_terrain.dem import DEM
from lunar_hazard_mapper.scientific.common.types import SunState


@dataclass(frozen=True)
class SunScene:
    """Immutable scene contract carrying a DEM together with the SunState."""

    dem: DEM
    sun: SunState

    def __post_init__(self) -> None:
        if not isinstance(self.dem, DEM):
            raise TypeError("dem must be a DEM instance.")
        if not isinstance(self.sun, SunState):
            raise TypeError("sun must be a SunState instance.")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the scene into a deterministic, JSON-friendly payload."""
        return {
            "dem": {
                "elevation": np.asarray(self.dem.elevation, dtype=np.float32).tolist(),
                "pixel_size_m": float(self.dem.pixel_size_m),
                "transform": list(tuple(self.dem.transform)),
                "crs": self.dem.crs,
                "nodata": float(self.dem.nodata),
                "vertical_units": self.dem.vertical_units,
                "source_type": self.dem.source_type,
                "confidence": None
                if self.dem.confidence is None
                else np.asarray(self.dem.confidence, dtype=np.float32).tolist(),
                "notes": self.dem.notes,
                "extra": dict(self.dem.extra),
            },
            "sun": self.sun.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SunScene":
        """Reconstruct a SunScene from a serialized dictionary payload."""
        if not isinstance(payload, dict):
            raise TypeError("SunScene payload must be a dictionary.")
        if "dem" not in payload or "sun" not in payload:
            raise ValueError("SunScene payload must include 'dem' and 'sun'.")

        dem_payload = payload["dem"]
        sun_payload = payload["sun"]
        if not isinstance(dem_payload, dict):
            raise ValueError("Scene DEM payload must be a dictionary.")
        if not isinstance(sun_payload, dict):
            raise ValueError("Scene SunState payload must be a dictionary.")
        if "elevation" not in dem_payload or "pixel_size_m" not in dem_payload:
            raise ValueError("DEM payload must include elevation and pixel_size_m.")
        if "azimuth_deg" not in sun_payload or "elevation_deg" not in sun_payload:
            raise ValueError("SunState payload must include azimuth_deg and elevation_deg.")

        transform_data = dem_payload.get("transform")
        if transform_data is None:
            raise ValueError("DEM payload must include a transform.")
        try:
            transform = Affine(*transform_data)
        except Exception as exc:  # pragma: no cover - defensive validation
            raise ValueError("DEM payload transform is invalid.") from exc

        dem = DEM(
            elevation=np.asarray(dem_payload["elevation"], dtype=np.float32),
            pixel_size_m=float(dem_payload["pixel_size_m"]),
            transform=transform,
            crs=dem_payload.get("crs"),
            nodata=float(dem_payload.get("nodata", -9999.0)),
            vertical_units=str(dem_payload.get("vertical_units", "meters")),
            source_type=str(dem_payload.get("source_type", "synthetic")),
            confidence=None
            if dem_payload.get("confidence") is None
            else np.asarray(dem_payload["confidence"], dtype=np.float32),
            notes=str(dem_payload.get("notes", "")),
            extra=dict(dem_payload.get("extra", {})),
        )
        sun = SunState.from_dict(sun_payload)
        return cls(dem=dem, sun=sun)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SunScene):
            return NotImplemented
        if self.sun != other.sun:
            return False
        if self.dem is other.dem:
            return True

        return (
            self.dem.pixel_size_m == other.dem.pixel_size_m
            and self.dem.nodata == other.dem.nodata
            and self.dem.vertical_units == other.dem.vertical_units
            and self.dem.source_type == other.dem.source_type
            and self.dem.crs == other.dem.crs
            and self.dem.notes == other.dem.notes
            and self.dem.extra == other.dem.extra
            and np.array_equal(np.asarray(self.dem.elevation, dtype=np.float32),
                              np.asarray(other.dem.elevation, dtype=np.float32))
            and np.array_equal(np.asarray(self.dem.confidence) if self.dem.confidence is not None else None,
                              np.asarray(other.dem.confidence) if other.dem.confidence is not None else None)
            and tuple(self.dem.transform) == tuple(other.dem.transform)
        )

    def __hash__(self) -> int:
        return hash((
            self.sun.as_tuple(),
            float(self.dem.pixel_size_m),
            float(self.dem.nodata),
            self.dem.vertical_units,
            self.dem.source_type,
            self.dem.crs,
            self.dem.notes,
            tuple(sorted((str(k), repr(v)) for k, v in self.dem.extra.items())),
            tuple(np.asarray(self.dem.elevation, dtype=np.float32).ravel().tolist()),
            tuple(np.asarray(self.dem.confidence, dtype=np.float32).ravel().tolist()) if self.dem.confidence is not None else None,
            tuple(self.dem.transform),
        ))
