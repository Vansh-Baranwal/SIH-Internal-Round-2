"""M4-12.5 replaceable IIRS observation footprint data contract.

No authoritative IIRS observation metadata or georeferencing is available in this repository.
The default provider exposes only an explicitly labelled synthetic development
visualization where the footprint is computed from modeled sensor viewing geometry
intersected with the DEM-backed terrain foundation.

A future provider with real georeferenced metadata can implement the same
``IirsProvider`` contract; the 3D viewer remains unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation
from lunar_hazard_mapper.m4_terrain.provider import SyntheticTerrainProvider


class IirsDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    REAL = "real"
    UNKNOWN = "unknown"


# Alias for naming consistency
IirsCameraDataStatus = IirsDataStatus
IIRSCameraDataStatus = IirsDataStatus


@dataclass(frozen=True)
class IirsCameraModel:
    """IIRS sensor viewing geometry parameters in Three.js render axes.

    ``position_m`` and ``target_m`` use X=local East, Y=local Up, Z=local North (metres).
    """

    position_m: Tuple[float, float, float]
    target_m: Tuple[float, float, float]
    fov_across_track_degrees: float
    fov_along_track_degrees: float
    near_m: float
    far_m: float
    data_status: IirsDataStatus
    provenance: Dict[str, Any]

    def __post_init__(self) -> None:
        if not 0 < self.fov_across_track_degrees < 180:
            raise ValueError("fov_across_track_degrees must be in (0, 180).")
        if not 0 < self.fov_along_track_degrees < 180:
            raise ValueError("fov_along_track_degrees must be in (0, 180).")
        if self.near_m <= 0 or self.far_m <= self.near_m:
            raise ValueError("Clip planes are invalid.")
        if len(self.position_m) != 3 or len(self.target_m) != 3:
            raise ValueError("Position and target must have three coordinates.")

    @property
    def display_label(self) -> str:
        if self.data_status is IirsDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT CAMERA GEOMETRY"
        if self.data_status is IirsDataStatus.REAL:
            return "IIRS Sensor Telemetry"
        return "IIRS CAMERA METADATA UNAVAILABLE"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "position_m": {"x": self.position_m[0], "y": self.position_m[1], "z": self.position_m[2]},
            "target_m": {"x": self.target_m[0], "y": self.target_m[1], "z": self.target_m[2]},
            "fov_across_track_degrees": self.fov_across_track_degrees,
            "fov_along_track_degrees": self.fov_along_track_degrees,
            "near_m": self.near_m,
            "far_m": self.far_m,
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class IirsFootprintModel:
    """Computed footprint from sensor viewing geometry intersected with DEM terrain."""

    camera: IirsCameraModel
    boundary_vertices: List[Tuple[float, float, float]]  # (x=East, y=Up, z=North) in metres
    surface_area_m2: float
    is_within_dem_bounds: bool
    has_nodata_intersection: bool
    data_status: IirsDataStatus
    provenance: Dict[str, Any]

    @property
    def display_label(self) -> str:
        if self.data_status is IirsDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT DATA"
        if self.data_status is IirsDataStatus.REAL:
            return "IIRS Observation Footprint"
        return "IIRS FOOTPRINT UNAVAILABLE"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "sensor_type": "IIRS",
            "camera": self.camera.payload(),
            "footprint": {
                "boundary_vertices": [
                    {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])}
                    for v in self.boundary_vertices
                ],
                "vertex_count": len(self.boundary_vertices),
                "surface_area_m2": float(self.surface_area_m2),
                "is_within_dem_bounds": bool(self.is_within_dem_bounds),
                "has_nodata_intersection": bool(self.has_nodata_intersection),
            },
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "provenance": dict(self.provenance),
        }


def intersect_ray_with_dem(
    origin: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    foundation: TerrainFoundation,
    max_steps: int = 15,
) -> Tuple[Optional[Tuple[float, float, float]], bool]:
    """Find intersection of a 3D ray with the DEM surface.

    Origin and direction use Three.js coordinates: (East, Up, North).
    Returns (intersection_point_or_none, is_nodata).
    """
    ox, oy, oz = origin
    dx, dy, dz = direction

    # Ray must point downward toward terrain
    if abs(dy) < 1e-6:
        return None, False

    dem = foundation.dem
    tr = dem.transform
    elev = dem.elevation
    height, width = elev.shape
    vmask = foundation.valid_mask()

    # Initial elevation estimate: mean/center elevation
    t = -oy / dy if dy < 0 else 100.0
    if t <= 0:
        return None, False

    has_nodata = False
    last_pt = None

    for _ in range(max_steps):
        curr_x = ox + t * dx
        curr_z = oz + t * dz
        curr_y = oy + t * dy

        # Convert East (curr_x) and North (curr_z) to raster row/col
        col = (curr_x - tr.c) / tr.a - 0.5
        row = (curr_z - tr.f) / tr.e - 0.5

        r = int(round(row))
        c = int(round(col))

        if 0 <= r < height and 0 <= c < width:
            if vmask[r, c]:
                dem_elev = float(elev[r, c])
                diff = curr_y - dem_elev
                if abs(diff) < 0.05:
                    return (curr_x, dem_elev, curr_z), has_nodata
                last_pt = (curr_x, dem_elev, curr_z)
                # Secant step along ray
                t = t - diff / dy
            else:
                has_nodata = True
                return (curr_x, curr_y, curr_z), has_nodata
        else:
            # Outside DEM grid bounds
            return (curr_x, curr_y, curr_z), has_nodata

    return last_pt or (ox + t * dx, oy + t * dy, oz + t * dz), has_nodata


def compute_iirs_footprint(
    camera: IirsCameraModel,
    foundation: TerrainFoundation,
    samples_per_edge: int = 10,
) -> IirsFootprintModel:
    """Compute the surface footprint polygon by intersecting viewing geometry with the DEM."""
    pos = camera.position_m
    target = camera.target_m

    # Forward direction
    fwd = np.array([target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]], dtype=np.float64)
    fwd_norm = np.linalg.norm(fwd)
    if fwd_norm < 1e-6:
        raise ValueError("Camera position and target coincide.")
    fwd /= fwd_norm

    # Camera coordinate system
    up_ref = np.array([0.0, 0.0, 1.0] if abs(fwd[1]) > 0.99 else [0.0, 1.0, 0.0], dtype=np.float64)
    right = np.cross(fwd, up_ref)
    right /= np.linalg.norm(right)
    cam_up = np.cross(right, fwd)
    cam_up /= np.linalg.norm(cam_up)

    half_fov_x = math.radians(camera.fov_across_track_degrees / 2.0)
    half_fov_z = math.radians(camera.fov_along_track_degrees / 2.0)

    # Parametric edges along normalized camera plane [-1, 1]
    # Edge 1: top (-1, 1) -> (1, 1)
    # Edge 2: right (1, 1) -> (1, -1)
    # Edge 3: bottom (1, -1) -> (-1, -1)
    # Edge 4: left (-1, -1) -> (-1, 1)
    boundary_points: List[Tuple[float, float, float]] = []
    has_nodata = False
    all_within_bounds = True

    dem_bounds = foundation.bounds

    edge_segments = [
        ((-1.0, 1.0), (1.0, 1.0)),
        ((1.0, 1.0), (1.0, -1.0)),
        ((1.0, -1.0), (-1.0, -1.0)),
        ((-1.0, -1.0), (-1.0, 1.0)),
    ]

    for start, end in edge_segments:
        for step in range(samples_per_edge):
            alpha = step / float(samples_per_edge)
            u = start[0] + alpha * (end[0] - start[0])
            v = start[1] + alpha * (end[1] - start[1])

            tan_x = math.tan(half_fov_x) * u
            tan_z = math.tan(half_fov_z) * v

            ray_dir = fwd + tan_x * right + tan_z * cam_up
            ray_dir /= np.linalg.norm(ray_dir)

            pt, pt_nodata = intersect_ray_with_dem(
                pos,
                (float(ray_dir[0]), float(ray_dir[1]), float(ray_dir[2])),
                foundation,
            )

            if pt_nodata:
                has_nodata = True

            if pt is not None:
                # Check if within DEM bounds
                if not (dem_bounds["min_x"] <= pt[0] <= dem_bounds["max_x"] and
                        dem_bounds["min_y"] <= pt[2] <= dem_bounds["max_y"]):
                    all_within_bounds = False
                boundary_points.append(pt)

    # Calculate approximate polygon surface area on horizontal plane
    if len(boundary_points) >= 3:
        xs = [p[0] for p in boundary_points]
        zs = [p[2] for p in boundary_points]
        # Shoelace formula
        area = 0.5 * abs(sum(xs[i] * zs[i + 1] - xs[i + 1] * zs[i] for i in range(-1, len(boundary_points) - 1)))
    else:
        area = 0.0

    return IirsFootprintModel(
        camera=camera,
        boundary_vertices=boundary_points,
        surface_area_m2=area,
        is_within_dem_bounds=all_within_bounds,
        has_nodata_intersection=has_nodata,
        data_status=camera.data_status,
        provenance=dict(camera.provenance),
    )


class IirsProvider(ABC):
    """Provider boundary between IIRS metadata/geometry and the 3D footprint renderer."""

    @abstractmethod
    def load_camera(self) -> IirsCameraModel:
        raise NotImplementedError

    @abstractmethod
    def load_footprint(self, foundation: Optional[TerrainFoundation] = None) -> IirsFootprintModel:
        raise NotImplementedError


class SyntheticIirsProvider(IirsProvider):
    """Isolated, non-scientific development configuration for the 3D footprint viewer."""

    def load_camera(self) -> IirsCameraModel:
        return IirsCameraModel(
            position_m=(1280.0, 800.0, -1280.0),
            target_m=(1280.0, 0.0, -1280.0),
            fov_across_track_degrees=14.0,
            fov_along_track_degrees=10.0,
            near_m=1.0,
            far_m=1500.0,
            data_status=IirsDataStatus.SYNTHETIC,
            provenance={
                "source": "m4_12_5_synthetic_development_configuration",
                "note": (
                    "Synthetic development visualization only. Values are not real "
                    "IIRS calibration, spacecraft pose, observation metadata, or "
                    "proof of historical observation coverage."
                ),
            },
        )

    def load_footprint(self, foundation: Optional[TerrainFoundation] = None) -> IirsFootprintModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())
        camera = self.load_camera()
        return compute_iirs_footprint(camera, foundation)


# Alias for case variants
SyntheticIIRSProvider = SyntheticIirsProvider
IIRSProvider = IirsProvider
IIRSCameraModel = IirsCameraModel
IIRSFootprintModel = IirsFootprintModel
