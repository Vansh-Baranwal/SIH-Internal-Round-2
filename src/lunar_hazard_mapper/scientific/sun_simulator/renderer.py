"""
Counterfactual Sun Simulator rendering primitives.

Generates synthetic illumination from a DEM under
a controlled Sun position.

All outputs are synthetic evaluation data and must
never be represented as real lunar observations.
"""

from __future__ import annotations

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import (
    DEM,
    to_local_frame,
)

from lunar_hazard_mapper.m4_hazards.shadow import (
    detect_shadows,
)

from lunar_hazard_mapper.scientific.common.types import (
    SunState,
)


def _surface_normals(dem: DEM) -> np.ndarray:
    """
    Calculate unit surface normals from the DEM.

    Coordinate convention:
        x = east
        y = north
        z = up
    """

    elevation = np.asarray(
        dem.elevation,
        dtype=np.float64,
    )

    pixel_size = float(
        dem.pixel_size_m
    )

    dz_drow, dz_dcol = np.gradient(
        elevation,
        pixel_size,
        pixel_size,
    )

    # Raster rows increase downward.
    # North therefore corresponds to negative row direction.
    dz_dx = dz_dcol
    dz_dy = -dz_drow

    nx = -dz_dx
    ny = -dz_dy
    nz = np.ones_like(elevation)

    magnitude = np.sqrt(
        nx * nx +
        ny * ny +
        nz * nz
    )

    magnitude = np.maximum(
        magnitude,
        1e-12,
    )

    return np.stack(
        [
            nx / magnitude,
            ny / magnitude,
            nz / magnitude,
        ],
        axis=-1,
    )


def _sun_vector(
    sun: SunState,
) -> np.ndarray:
    """
    Convert Sun azimuth/elevation to a local
    ENU-style direction vector.

    Azimuth:
        0°  = north
        90° = east

    Elevation:
        0°  = horizon
        90° = zenith
    """

    azimuth = np.radians(
        sun.azimuth_deg
    )

    elevation = np.radians(
        sun.elevation_deg
    )

    return np.array(
        [
            np.sin(azimuth) *
            np.cos(elevation),

            np.cos(azimuth) *
            np.cos(elevation),

            np.sin(elevation),
        ],
        dtype=np.float64,
    )


def render_synthetic_observation(
    dem: DEM,
    sun: SunState,
    ambient: float = 0.15,
    diffuse: float = 0.85,
    shadow_floor: float = 0.08,
):
    """
    Render a synthetic grayscale observation.

    Returns:
        image:
            Float32 image normalized to [0, 1].

        shadow_mask:
            Boolean geometric shadow mask.

        illumination:
            Direct illumination before shadow compositing.
    """

    if not isinstance(dem, DEM):
        raise TypeError(
            "dem must be an instance of DEM."
        )

    if not 0.0 <= ambient <= 1.0:
        raise ValueError(
            "ambient must be between 0 and 1."
        )

    if not 0.0 <= diffuse <= 1.0:
        raise ValueError(
            "diffuse must be between 0 and 1."
        )

    if ambient + diffuse > 1.0:
        raise ValueError(
            "ambient + diffuse must not exceed 1."
        )

    if not 0.0 <= shadow_floor <= 1.0:
        raise ValueError(
            "shadow_floor must be between 0 and 1."
        )

    normals = _surface_normals(dem)

    sun_vector = _sun_vector(sun)

    direct_illumination = np.clip(
        np.sum(
            normals * sun_vector,
            axis=-1,
        ),
        0.0,
        1.0,
    )

    # Reuse the existing M4 geometric shadow engine.
    local = to_local_frame(dem)

    shadow_input = {
        "z": local["z"],
        "dx": float(dem.pixel_size_m),
        "dy": float(dem.pixel_size_m),
    }

    shadow_mask = detect_shadows(
        shadow_input,
        sun.elevation_deg,
        sun_azimuth_deg=sun.azimuth_deg,
    )

    image = (
        ambient +
        diffuse * direct_illumination
    )

    image = np.where(
        shadow_mask,
        shadow_floor +
        ambient * 0.25,
        image,
    )

    image = np.clip(
        image,
        0.0,
        1.0,
    ).astype(np.float32)

    return (
        image,
        shadow_mask,
        direct_illumination.astype(np.float32),
    )