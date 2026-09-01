"""Counterfactual Sun Simulator: DEM-based synthetic shadow/illumination generator."""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


@dataclass
class SunSimResult:
    illumination_map: np.ndarray    # float32 [0,1]
    shadow_mask: np.ndarray         # bool
    sun_azimuth_deg: float
    sun_elevation_deg: float
    synthetic_image: Optional[np.ndarray] = None


class SunSimulator:
    """
    Simulate illumination and cast shadows from a DEM for a given sun position.
    Strictly isolated — synthetic outputs must NOT feed back into registered products.
    """

    def __init__(self, moon_radius_km: float = 1737.4):
        self.moon_radius_km = moon_radius_km

    def simulate(
        self,
        dem: np.ndarray,
        sun_azimuth_deg: float,
        sun_elevation_deg: float,
        pixel_scale_m: float = 5.0,
        base_image: Optional[np.ndarray] = None,
    ) -> SunSimResult:
        """
        Compute illumination map and shadow mask from DEM.
        dem: 2D float32 elevation in metres.
        """
        dem_f = dem.astype(np.float32)
        illumination, shadow = self._raycast_shadows(
            dem_f, sun_azimuth_deg, sun_elevation_deg, pixel_scale_m
        )

        synthetic = None
        if base_image is not None:
            synthetic = self._apply_illumination(base_image, illumination, shadow)

        return SunSimResult(
            illumination_map=illumination,
            shadow_mask=shadow,
            sun_azimuth_deg=sun_azimuth_deg,
            sun_elevation_deg=sun_elevation_deg,
            synthetic_image=synthetic,
        )

    def _raycast_shadows(
        self,
        dem: np.ndarray,
        azimuth: float,
        elevation: float,
        pixel_scale: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simplified horizon-scan shadow casting."""
        h, w = dem.shape
        illumination = np.ones((h, w), dtype=np.float32)
        shadow = np.zeros((h, w), dtype=bool)

        if elevation <= 0:
            # Below horizon: full shadow
            shadow[:] = True
            illumination[:] = 0.0
            return illumination, shadow

        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        dx = math.sin(az_rad)
        dy = -math.cos(az_rad)
        dz_per_px = math.tan(el_rad) * pixel_scale

        # At zenith, no terrain can occlude the sun and the incidence is full.
        if elevation >= 90:
            return illumination, shadow

        steps = max(h, w)
        for yi in range(h):
            for xi in range(w):
                # Cast ray toward the sun
                horizon_tan = -float("inf")
                for step in range(1, steps):
                    # Scan toward the sun; occlusion is cast on the opposite side.
                    sx = xi + dx * step
                    sy = yi + dy * step
                    if sx < 0 or sx >= w or sy < 0 or sy >= h:
                        break
                    sx_i, sy_i = int(sx), int(sy)
                    elev_diff = dem[sy_i, sx_i] - dem[yi, xi]
                    ray_tan = elev_diff / (step * pixel_scale)
                    if ray_tan > horizon_tan:
                        horizon_tan = ray_tan

                required_tan = math.tan(el_rad)
                if horizon_tan > required_tan:
                    shadow[yi, xi] = True
                    illumination[yi, xi] = 0.0
                else:
                    cos_inc = max(0.0, math.cos(math.atan(horizon_tan) - el_rad))
                    illumination[yi, xi] = cos_inc

        return illumination, shadow

    def simulate_batch(
        self,
        dem: np.ndarray,
        sun_angles: list,
        pixel_scale_m: float = 5.0,
    ) -> list:
        """Run simulation for multiple sun positions (for benchmark/comparison)."""
        return [
            self.simulate(dem, az, el, pixel_scale_m)
            for az, el in sun_angles
        ]

    def _apply_illumination(
        self, base: np.ndarray, illumination: np.ndarray, shadow: np.ndarray
    ) -> np.ndarray:
        """Multiply base image by illumination map and darken shadowed regions."""
        img = base.astype(np.float32)
        if img.ndim == 3:
            for c in range(img.shape[2]):
                img[:, :, c] *= illumination
        else:
            img *= illumination
        img[shadow] *= 0.05  # ambient light in shadow
        return np.clip(img, 0, 255).astype(np.uint8)


_simulator = SunSimulator()


def simulate_sun(
    dem: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    pixel_scale_m: float = 5.0,
    base_image: Optional[np.ndarray] = None,
) -> SunSimResult:
    return _simulator.simulate(dem, sun_azimuth_deg, sun_elevation_deg, pixel_scale_m, base_image)
