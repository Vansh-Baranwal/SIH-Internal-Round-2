"""
M4-07.4 — Synthetic Shadow Simulation.

Deterministic synthetic shadow generation from terrain DEM and solar illumination state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM, to_local_frame
from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.m4_hazards.shadow import detect_shadows


@dataclass(frozen=True)
class SyntheticShadow:
    """
    Immutable result of synthetic shadow simulation.

    Represents geometric shadows cast on terrain by the Sun at a specific position
    and elevation. The shadow is deterministic: identical DEM + SunState always
    produces identical shadow_mask.
    """

    shadow_mask: np.ndarray  # Boolean array, True = shadowed, shape matches DEM
    sun: SunState  # Immutable SunState used for simulation
    dem_shape: tuple  # Original DEM shape for validation
    pixel_size_m: float  # Original DEM pixel size for reference
    elevation_deg: float  # For quick reference (redundant with sun.elevation_deg)
    azimuth_deg: float  # For quick reference (redundant with sun.azimuth_deg)

    def __post_init__(self) -> None:
        if not isinstance(self.shadow_mask, np.ndarray):
            raise TypeError("shadow_mask must be a numpy array.")
        if not np.issubdtype(self.shadow_mask.dtype, np.bool_):
            raise TypeError("shadow_mask must have dtype bool.")
        if not isinstance(self.sun, SunState):
            raise TypeError("sun must be a SunState instance.")
        if self.shadow_mask.shape != self.dem_shape:
            raise ValueError(
                f"shadow_mask shape {self.shadow_mask.shape} does not match "
                f"DEM shape {self.dem_shape}."
            )
        if self.pixel_size_m <= 0.0:
            raise ValueError("pixel_size_m must be positive.")
        if not (0.0 <= self.elevation_deg <= 90.0):
            raise ValueError("elevation_deg must be in [0, 90].")
        if not (0.0 <= self.azimuth_deg < 360.0):
            raise ValueError("azimuth_deg must be in [0, 360).")
        # Verify reference values match sun state
        if abs(self.elevation_deg - self.sun.elevation_deg) > 1e-6:
            raise ValueError(
                "elevation_deg must match sun.elevation_deg."
            )
        if abs(self.azimuth_deg - self.sun.azimuth_deg) > 1e-6:
            raise ValueError(
                "azimuth_deg must match sun.azimuth_deg."
            )

    @property
    def shadow_fraction(self) -> float:
        """Fraction of terrain pixels in shadow."""
        return float(np.mean(self.shadow_mask))

    @property
    def shadow_pixel_count(self) -> int:
        """Total number of shadowed pixels."""
        return int(np.sum(self.shadow_mask))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize shadow to deterministic JSON-friendly dict."""
        return {
            "shadow_mask": self.shadow_mask.astype(bool).tolist(),
            "sun": self.sun.to_dict(),
            "dem_shape": list(self.dem_shape),
            "pixel_size_m": float(self.pixel_size_m),
            "elevation_deg": float(self.elevation_deg),
            "azimuth_deg": float(self.azimuth_deg),
            "shadow_fraction": self.shadow_fraction,
            "shadow_pixel_count": self.shadow_pixel_count,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SyntheticShadow":
        """Reconstruct SyntheticShadow from serialized dictionary."""
        if not isinstance(payload, dict):
            raise TypeError("Payload must be a dictionary.")

        required_keys = {"shadow_mask", "sun", "dem_shape", "pixel_size_m"}
        if not required_keys.issubset(payload.keys()):
            raise ValueError(
                f"Payload must include {required_keys}."
            )

        shadow_array = np.asarray(payload["shadow_mask"], dtype=bool)
        sun = SunState.from_dict(payload["sun"])
        dem_shape = tuple(payload["dem_shape"])

        return cls(
            shadow_mask=shadow_array,
            sun=sun,
            dem_shape=dem_shape,
            pixel_size_m=float(payload["pixel_size_m"]),
            elevation_deg=float(payload.get("elevation_deg", sun.elevation_deg)),
            azimuth_deg=float(payload.get("azimuth_deg", sun.azimuth_deg)),
        )


def simulate_synthetic_shadow(
    dem: DEM,
    sun: SunState,
    max_search_px: int = 40,
) -> SyntheticShadow:
    """
    Generate synthetic geometric shadow from DEM and SunState.

    Uses horizon ray-casting: for each terrain cell, marches toward the Sun
    and checks whether upstream terrain occludes it. This is deterministic
    and consistent with the project's coordinate conventions.

    Args:
        dem: Digital Elevation Model (must be a DEM instance).
        sun: Solar illumination state (must be a SunState instance).
        max_search_px: Maximum distance (in pixels) to search upstream
                       for occluding terrain. Default 40 pixels.

    Returns:
        SyntheticShadow with boolean shadow mask and metadata.

    Raises:
        TypeError: if dem or sun are not the expected types.
        ValueError: if inputs are invalid.
    """
    if not isinstance(dem, DEM):
        raise TypeError("dem must be a DEM instance.")
    if not isinstance(sun, SunState):
        raise TypeError("sun must be a SunState instance.")

    if max_search_px <= 0:
        raise ValueError("max_search_px must be positive.")

    # Convert DEM to local frame for shadow detection
    local = to_local_frame(dem)

    # Prepare input for detect_shadows
    shadow_input = {
        "z": np.asarray(local["z"], dtype=np.float64),
        "dx": float(dem.pixel_size_m),
        "dy": float(dem.pixel_size_m),
    }

    # Compute shadow mask using existing geometric horizon ray-casting
    shadow_mask = detect_shadows(
        shadow_input,
        sun.elevation_deg,
        sun_azimuth_deg=sun.azimuth_deg,
        max_search_px=max_search_px,
    )

    # Ensure shadow_mask is bool type
    shadow_mask = np.asarray(shadow_mask, dtype=bool)

    # Create immutable shadow result
    return SyntheticShadow(
        shadow_mask=shadow_mask,
        sun=sun,
        dem_shape=dem.shape,
        pixel_size_m=float(dem.pixel_size_m),
        elevation_deg=float(sun.elevation_deg),
        azimuth_deg=float(sun.azimuth_deg),
    )
