"""
M4-07.5 — Counterfactual Crater Observation.

Creates deterministic synthetic crater observations under counterfactual
illumination conditions using DEM + SunState + SyntheticShadow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM
from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.scientific.sun_simulator.shadow import (
    SyntheticShadow,
    simulate_synthetic_shadow,
)
from lunar_hazard_mapper.scientific.sun_simulator.renderer import (
    render_synthetic_observation,
)


@dataclass(frozen=True)
class CounterfactualObservation:
    """
    Immutable synthetic crater observation under counterfactual illumination.

    Represents what terrain/craters would appear under a specified SunState
    using deterministic geometric simulation (no crater detection or matching).

    The observation is structured for downstream experimental pipeline
    consumption without embedding ground truth coordinates directly.
    """

    # Source terrain and illumination
    dem: DEM
    sun: SunState

    # Synthetic observation outputs
    image: np.ndarray  # Float32 grayscale [0, 1]
    shadow_mask: np.ndarray  # Boolean shadow mask

    # Derived metadata for consistency checking
    dem_shape: tuple  # Must match image shape
    pixel_size_m: float  # DEM pixel size
    elevation_deg: float  # SunState elevation reference
    azimuth_deg: float  # SunState azimuth reference

    # Observation parameters (reusable for consistent re-synthesis)
    ambient: float = 0.15
    diffuse: float = 0.85
    shadow_floor: float = 0.08

    def __post_init__(self) -> None:
        if not isinstance(self.dem, DEM):
            raise TypeError("dem must be a DEM instance.")
        if not isinstance(self.sun, SunState):
            raise TypeError("sun must be a SunState instance.")
        if not isinstance(self.image, np.ndarray):
            raise TypeError("image must be a numpy array.")
        if not isinstance(self.shadow_mask, np.ndarray):
            raise TypeError("shadow_mask must be a numpy array.")

        if not np.issubdtype(self.image.dtype, np.floating):
            raise TypeError("image must be floating-point array.")
        if not np.issubdtype(self.shadow_mask.dtype, np.bool_):
            raise TypeError("shadow_mask must be boolean array.")

        if self.image.shape != self.dem_shape:
            raise ValueError(
                f"image shape {self.image.shape} does not match "
                f"DEM shape {self.dem_shape}."
            )
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

        # Verify metadata consistency
        if abs(self.elevation_deg - self.sun.elevation_deg) > 1e-6:
            raise ValueError("elevation_deg must match sun.elevation_deg.")
        if abs(self.azimuth_deg - self.sun.azimuth_deg) > 1e-6:
            raise ValueError("azimuth_deg must match sun.azimuth_deg.")

        # Verify image range
        if not np.all((self.image >= 0.0) & (self.image <= 1.0)):
            raise ValueError("image values must be in [0, 1].")

        # Verify lighting parameters
        if not (0.0 <= self.ambient <= 1.0):
            raise ValueError("ambient must be in [0, 1].")
        if not (0.0 <= self.diffuse <= 1.0):
            raise ValueError("diffuse must be in [0, 1].")
        if not (0.0 <= self.shadow_floor <= 1.0):
            raise ValueError("shadow_floor must be in [0, 1].")

        # Enforce content immutability: the observation exposes its image and
        # shadow-mask arrays to callers, so mark the underlying buffers
        # read-only to prevent accidental in-place mutation (e.g. the standard
        # `obs.image[0, 0] = ...` / `obs.shadow_mask[0, 0] = ...` pattern).
        # Marking buffers read-only does not affect reads, copying, comparisons,
        # or JSON serialization; it only blocks in-place writes.
        self.image.flags.writeable = False
        self.shadow_mask.flags.writeable = False

    @property
    def shadow_fraction(self) -> float:
        """Fraction of pixels in shadow."""
        return float(np.mean(self.shadow_mask))

    @property
    def shadow_pixel_count(self) -> int:
        """Total number of shadowed pixels."""
        return int(np.sum(self.shadow_mask))

    @property
    def image_min(self) -> float:
        """Minimum image intensity."""
        return float(np.min(self.image))

    @property
    def image_max(self) -> float:
        """Maximum image intensity."""
        return float(np.max(self.image))

    @property
    def image_mean(self) -> float:
        """Mean image intensity."""
        return float(np.mean(self.image))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize observation to deterministic JSON-friendly format."""
        return {
            "dem_shape": list(self.dem_shape),
            "pixel_size_m": float(self.pixel_size_m),
            "sun": self.sun.to_dict(),
            "image": np.asarray(self.image, dtype=np.float32).tolist(),
            "shadow_mask": np.asarray(self.shadow_mask, dtype=bool).tolist(),
            "elevation_deg": float(self.elevation_deg),
            "azimuth_deg": float(self.azimuth_deg),
            "ambient": float(self.ambient),
            "diffuse": float(self.diffuse),
            "shadow_floor": float(self.shadow_floor),
            "shadow_fraction": self.shadow_fraction,
            "shadow_pixel_count": self.shadow_pixel_count,
            "image_min": self.image_min,
            "image_max": self.image_max,
            "image_mean": self.image_mean,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CounterfactualObservation":
        """Reconstruct observation from serialized dictionary."""
        if not isinstance(payload, dict):
            raise TypeError("Payload must be a dictionary.")

        required = {"dem_shape", "pixel_size_m", "sun", "image", "shadow_mask"}
        if not required.issubset(payload.keys()):
            raise ValueError(f"Payload must include {required}.")

        dem_shape = tuple(payload["dem_shape"])
        image = np.asarray(payload["image"], dtype=np.float32)
        shadow_mask = np.asarray(payload["shadow_mask"], dtype=bool)
        sun = SunState.from_dict(payload["sun"])

        # Note: from_dict does NOT reconstruct the DEM itself
        # Only the observation metadata and arrays
        return cls(
            dem=None,  # type: ignore - Will fail without a proper DEM instance
            sun=sun,
            image=image,
            shadow_mask=shadow_mask,
            dem_shape=dem_shape,
            pixel_size_m=float(payload["pixel_size_m"]),
            elevation_deg=float(payload.get("elevation_deg", sun.elevation_deg)),
            azimuth_deg=float(payload.get("azimuth_deg", sun.azimuth_deg)),
            ambient=float(payload.get("ambient", 0.15)),
            diffuse=float(payload.get("diffuse", 0.85)),
            shadow_floor=float(payload.get("shadow_floor", 0.08)),
        )


def generate_counterfactual_observation(
    dem: DEM,
    sun: SunState,
    ambient: float = 0.15,
    diffuse: float = 0.85,
    shadow_floor: float = 0.08,
) -> CounterfactualObservation:
    """
    Generate a deterministic synthetic crater observation under counterfactual
    illumination.

    Uses the established rendering pipeline (7.4 shadow + grayscale rendering)
    to produce a synthetic observation suitable for later crater detection
    and landmark extraction stages.

    Args:
        dem: Digital Elevation Model for the terrain.
        sun: Solar illumination state (azimuth and elevation).
        ambient: Ambient illumination component [0, 1].
        diffuse: Diffuse reflection component [0, 1].
        shadow_floor: Minimum brightness in shadowed areas [0, 1].

    Returns:
        CounterfactualObservation with synthetic grayscale image and shadow mask.

    Raises:
        TypeError: if dem or sun are not the expected types.
        ValueError: if inputs are invalid.
    """
    if not isinstance(dem, DEM):
        raise TypeError("dem must be a DEM instance.")
    if not isinstance(sun, SunState):
        raise TypeError("sun must be a SunState instance.")

    # Validate lighting parameters
    if not (0.0 <= ambient <= 1.0):
        raise ValueError("ambient must be in [0, 1].")
    if not (0.0 <= diffuse <= 1.0):
        raise ValueError("diffuse must be in [0, 1].")
    if not (0.0 <= shadow_floor <= 1.0):
        raise ValueError("shadow_floor must be in [0, 1].")
    if ambient + diffuse > 1.0:
        raise ValueError("ambient + diffuse must not exceed 1.")

    # Generate synthetic observation using existing rendering pipeline
    image, shadow_mask, _ = render_synthetic_observation(
        dem=dem,
        sun=sun,
        ambient=ambient,
        diffuse=diffuse,
        shadow_floor=shadow_floor,
    )

    # Ensure arrays are properly typed
    image = np.asarray(image, dtype=np.float32)
    shadow_mask = np.asarray(shadow_mask, dtype=bool)

    # Create immutable observation
    return CounterfactualObservation(
        dem=dem,
        sun=sun,
        image=image,
        shadow_mask=shadow_mask,
        dem_shape=dem.shape,
        pixel_size_m=float(dem.pixel_size_m),
        elevation_deg=float(sun.elevation_deg),
        azimuth_deg=float(sun.azimuth_deg),
        ambient=float(ambient),
        diffuse=float(diffuse),
        shadow_floor=float(shadow_floor),
    )
