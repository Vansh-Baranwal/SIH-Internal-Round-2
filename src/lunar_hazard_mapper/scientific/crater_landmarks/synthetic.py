"""
Member 4 — Synthetic crater-scene generation for deterministic testing.

This module provides a controlled synthetic data layer for M4 crater landmark
validation. It does not replace the scientific crater detection, geometry
extraction, quality scoring, network, or database logic; it only creates known
scene ground truth for reproducible testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM, generate_dem


@dataclass(frozen=True)
class LocalizationAccuracyResult:
    """
    Comparison between the pipeline-estimated crater centre and the independently
    retained synthetic ground truth.
    """

    crater_id: str
    ground_truth_center_x_m: float
    ground_truth_center_y_m: float
    estimated_center_x_m: float
    estimated_center_y_m: float
    center_error_m: float
    center_error_px: float
    max_error_m: float
    passed: bool

    @classmethod
    def from_estimate(
        cls,
        crater_id: str,
        ground_truth_center_x_m: float,
        ground_truth_center_y_m: float,
        estimated_center_x_m: float,
        estimated_center_y_m: float,
        max_error_m: float = 1.5,
        pixel_size_m: float = 1.0,
        geometry: Any = None,
    ) -> "LocalizationAccuracyResult":
        """
        Compute the localization error in both metric and pixel-space units.

        The optional `geometry` argument is accepted for pipeline-call compatibility
        and is intentionally unused here; the evaluation is based on the retained
        independent ground truth and the estimated crater centre only.
        """
        dx_m = float(estimated_center_x_m) - float(ground_truth_center_x_m)
        dy_m = float(estimated_center_y_m) - float(ground_truth_center_y_m)
        error_m = float(hypot(dx_m, dy_m))
        px_per_m = 1.0 / float(pixel_size_m) if pixel_size_m > 0 else 1.0
        error_px = error_m * px_per_m
        return cls(
            crater_id=str(crater_id),
            ground_truth_center_x_m=float(ground_truth_center_x_m),
            ground_truth_center_y_m=float(ground_truth_center_y_m),
            estimated_center_x_m=float(estimated_center_x_m),
            estimated_center_y_m=float(estimated_center_y_m),
            center_error_m=error_m,
            center_error_px=error_px,
            max_error_m=float(max_error_m),
            passed=error_m <= float(max_error_m),
        )


def strip_location_metadata(scene: "SyntheticCraterScene") -> "SyntheticCraterScene":
    """
    Return a scene copy that strips the independent ground-truth coordinate metadata
    from the evaluated object while preserving the retained truth separately on the
    original scene. This ensures validation uses the pipeline output against an
    independently retained reference rather than direct metadata passed into the
    detector/input pipeline.
    """
    if not isinstance(scene, SyntheticCraterScene):
        raise TypeError("scene must be a SyntheticCraterScene instance.")

    dem_copy = DEM(
        elevation=np.array(scene.dem.elevation, copy=True, dtype=np.float32),
        pixel_size_m=float(scene.dem.pixel_size_m),
        transform=scene.dem.transform,
        crs=None,
        nodata=float(scene.dem.nodata),
        vertical_units=scene.dem.vertical_units,
        source_type=scene.dem.source_type,
        confidence=None if scene.dem.confidence is None else np.array(scene.dem.confidence, copy=True),
        notes="Location metadata stripped for M4-06.10 pipeline evaluation; ground truth retained separately.",
        extra={},
    )

    return SyntheticCraterScene(
        dem=dem_copy,
        ground_truth=[],
        background_elevation=float(scene.background_elevation),
        noise_std=float(scene.noise_std),
        seed=int(scene.seed),
    )


@dataclass(frozen=True)
class SyntheticCraterGroundTruth:
    """
    Explicit ground truth for a synthetic crater placed in a controlled DEM.
    """

    crater_id: str
    center_px: Tuple[int, int]
    center_xy_m: Tuple[float, float]
    radius_px: float
    radius_m: float
    diameter_m: float
    depth_m: float
    rim_height_m: float
    latitude_deg: Optional[float] = None
    longitude_deg: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.crater_id, str) or not self.crater_id.strip():
            raise ValueError("crater_id cannot be empty.")
        if self.radius_px <= 0:
            raise ValueError("radius_px must be positive.")
        if self.radius_m <= 0:
            raise ValueError("radius_m must be positive.")
        if self.diameter_m <= 0:
            raise ValueError("diameter_m must be positive.")
        if self.depth_m <= 0:
            raise ValueError("depth_m must be positive.")

    @property
    def center_xy(self) -> Tuple[int, int]:
        """
        Return the crater centre in pixel-space as (x, y) = (column, row).
        """
        return (int(self.center_px[1]), int(self.center_px[0]))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crater_id": self.crater_id,
            "center_px": [int(self.center_px[0]), int(self.center_px[1])],
            "center_xy_m": [float(self.center_xy_m[0]), float(self.center_xy_m[1])],
            "radius_px": float(self.radius_px),
            "radius_m": float(self.radius_m),
            "diameter_m": float(self.diameter_m),
            "depth_m": float(self.depth_m),
            "rim_height_m": float(self.rim_height_m),
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
        }

    def summary(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass(frozen=True)
class SyntheticCraterScene:
    """
    Synthetic DEM scene with explicit ground truth provided separately from the
    detection/extraction outputs produced by the scientific pipeline.
    """

    dem: DEM
    ground_truth: List[SyntheticCraterGroundTruth]
    background_elevation: float
    noise_std: float
    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.dem, DEM):
            raise TypeError("dem must be an instance of DEM.")
        if not isinstance(self.ground_truth, list):
            raise TypeError("ground_truth must be provided as a list.")

    def get_ground_truth_by_id(self, crater_id: str) -> Optional[SyntheticCraterGroundTruth]:
        for gt in self.ground_truth:
            if gt.crater_id == crater_id:
                return gt
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "background_elevation": self.background_elevation,
            "noise_std": self.noise_std,
            "ground_truth": [gt.to_dict() for gt in self.ground_truth],
        }


def _validate_crater_ids(crater_ids: Sequence[str]) -> List[str]:
    if not isinstance(crater_ids, Sequence) or not crater_ids:
        raise ValueError("crater_ids must be a non-empty sequence of crater IDs.")
    ids = list(crater_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("crater_ids must be unique.")
    for crater_id in ids:
        if not isinstance(crater_id, str) or not crater_id.strip():
            raise ValueError("Each crater_id must be a non-empty string.")
    return ids


def generate_synthetic_scene(
    crater_ids: Sequence[str],
    size: int = 128,
    pixel_size_m: float = 1.0,
    radius_px_by_id: Optional[Dict[str, float]] = None,
    depth_m_by_id: Optional[Dict[str, float]] = None,
    centers_xy: Optional[Dict[str, Tuple[int, int]]] = None,
    background_elevation: float = 0.0,
    noise_std: float = 0.0,
    seed: Optional[int] = None,
    rim_height_scale: float = 0.25,
) -> SyntheticCraterScene:
    """
    Generate a deterministic synthetic terrain scene containing one or more known
    crater features with explicit ground truth that is intentionally separate from
    the detection/extraction pipeline outputs.
    """
    if not isinstance(size, int) or size <= 0:
        raise ValueError("size must be a positive integer.")
    if not isinstance(pixel_size_m, (int, float)) or float(pixel_size_m) <= 0:
        raise ValueError("pixel_size_m must be positive.")

    ids = _validate_crater_ids(crater_ids)
    rng = np.random.default_rng(seed)

    radius_px_by_id = radius_px_by_id or {}
    depth_m_by_id = depth_m_by_id or {}
    centers_xy = centers_xy or {}

    base = np.full((size, size), float(background_elevation), dtype=np.float32)
    if noise_std > 0:
        base = base + rng.normal(0.0, float(noise_std), size=(size, size)).astype(np.float32)

    ground_truth: List[SyntheticCraterGroundTruth] = []

    for crater_id in ids:
        if crater_id in centers_xy:
            cy, cx = centers_xy[crater_id]
        else:
            # Deterministic default placement: spread along a diagonal while staying inside bounds.
            offset = len(ground_truth)
            cy = int((size * 0.25) + (offset * size * 0.15)) % size
            cx = int((size * 0.75) - (offset * size * 0.10)) % size

        if not (0 <= cy < size and 0 <= cx < size):
            raise ValueError(f"Center for crater '{crater_id}' is outside the synthetic DEM bounds.")

        radius_px = float(radius_px_by_id.get(crater_id, 12.0))
        if radius_px <= 0:
            raise ValueError(f"radius_px for crater '{crater_id}' must be positive.")

        depth_m = float(depth_m_by_id.get(crater_id, 5.0))
        if depth_m <= 0:
            raise ValueError(f"depth_m for crater '{crater_id}' must be positive.")

        rim_height_m = max(0.1, depth_m * float(rim_height_scale))

        yy, xx = np.mgrid[0:size, 0:size]
        dist_px = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        norm_dist = dist_px / radius_px

        bowl = -depth_m * np.clip(1.0 - norm_dist ** 2, 0.0, None)
        rim = rim_height_m * np.exp(-((norm_dist - 1.0) ** 2) / (2.0 * 0.15 ** 2))
        rim = np.where(norm_dist >= 1.0, rim, 0.0)
        base = base + (bowl + rim).astype(np.float32)

        center_x_m = float(cx) * float(pixel_size_m)
        center_y_m = float(cy) * float(pixel_size_m)
        radius_m = float(radius_px * pixel_size_m)
        diameter_m = float(2.0 * radius_m)

        ground_truth.append(
            SyntheticCraterGroundTruth(
                crater_id=crater_id,
                center_px=(int(cy), int(cx)),
                center_xy_m=(center_x_m, center_y_m),
                radius_px=radius_px,
                radius_m=radius_m,
                diameter_m=diameter_m,
                depth_m=depth_m,
                rim_height_m=rim_height_m,
            )
        )

    dem = generate_dem(
        {"elevation": base.astype(np.float32), "pixel_size_m": float(pixel_size_m), "source_type": "synthetic"},
        notes=(
            "Synthetic crater scene generated for deterministic M4 crater-landmark testing. "
            "Ground truth is stored separately from detection outputs."
        ),
    )

    return SyntheticCraterScene(
        dem=dem,
        ground_truth=ground_truth,
        background_elevation=float(background_elevation),
        noise_std=float(noise_std),
        seed=int(seed) if seed is not None else 0,
    )


def generate_synthetic_crater_scene(
    crater_id: str,
    size: int = 128,
    pixel_size_m: float = 1.0,
    radius_px: float = 20.0,
    depth_m: float = 8.0,
    center_xy: Optional[Tuple[int, int]] = None,
    background_elevation: float = 0.0,
    noise_std: float = 0.0,
    seed: Optional[int] = None,
    rim_height_m: Optional[float] = None,
) -> SyntheticCraterScene:
    """
    Convenience wrapper for generating a single known crater scene.
    """
    if center_xy is None:
        center_xy = (size // 2, size // 2)
    if rim_height_m is None:
        rim_height_m = max(0.1, depth_m * 0.25)
    return generate_synthetic_scene(
        crater_ids=[crater_id],
        size=size,
        pixel_size_m=pixel_size_m,
        radius_px_by_id={crater_id: float(radius_px)},
        depth_m_by_id={crater_id: float(depth_m)},
        centers_xy={crater_id: center_xy},
        background_elevation=background_elevation,
        noise_std=noise_std,
        seed=seed,
    )
