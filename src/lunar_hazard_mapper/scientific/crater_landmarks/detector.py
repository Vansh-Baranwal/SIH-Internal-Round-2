"""
Member 4 — Crater Detection.

Detects candidate crater-like structures from a DEM.

This is an M4-owned scientific component and does not modify
the existing M3 terrain implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM


@dataclass(frozen=True)
class CraterCandidate:
    """
    Candidate crater detected from terrain geometry.

    This is deliberately a detection-stage object.
    It is not yet a fully validated CraterLandmark.
    """

    center_x_m: float
    center_y_m: float

    radius_m: float
    diameter_m: float

    depth_m: float

    confidence: float

    local_minimum_elevation_m: float


class CraterDetector:
    """
    Detect crater-like depressions in a DEM.

    The initial implementation uses a deterministic
    local-depression approach suitable for synthetic
    terrain validation.

    It is intentionally conservative: detection candidates
    are returned without claiming final scientific validity.
    """

    def __init__(
        self,
        min_radius_m: float = 3.0,
        max_radius_m: float = 100.0,
        min_depth_m: float = 1.0,
        neighborhood_radius_px: int = 20,
    ) -> None:

        if min_radius_m <= 0:
            raise ValueError(
                "min_radius_m must be positive."
            )

        if max_radius_m <= min_radius_m:
            raise ValueError(
                "max_radius_m must exceed min_radius_m."
            )

        if min_depth_m <= 0:
            raise ValueError(
                "min_depth_m must be positive."
            )

        if neighborhood_radius_px < 1:
            raise ValueError(
                "neighborhood_radius_px must be >= 1."
            )

        self.min_radius_m = min_radius_m
        self.max_radius_m = max_radius_m
        self.min_depth_m = min_depth_m
        self.neighborhood_radius_px = (
            neighborhood_radius_px
        )

    def detect(
        self,
        dem: DEM,
    ) -> List[CraterCandidate]:
        """
        Detect candidate crater depressions.

        Returns
        -------
        list[CraterCandidate]
            Candidate crater structures.
        """

        elevation = np.asarray(
            dem.elevation,
            dtype=float,
        )

        rows, cols = elevation.shape

        candidates: List[
            CraterCandidate
        ] = []

        radius_px = (
            self.neighborhood_radius_px
        )

        # --------------------------------------------------
        # Local-minimum detection
        # --------------------------------------------------

        for row in range(
            radius_px,
            rows - radius_px,
        ):

            for col in range(
                radius_px,
                cols - radius_px,
            ):

                center_elevation = (
                    elevation[row, col]
                )

                window = elevation[
                    row - radius_px :
                    row + radius_px + 1,

                    col - radius_px :
                    col + radius_px + 1,
                ]

                # A crater centre should be a local depression.
                if center_elevation != np.min(
                    window
                ):
                    continue

                # --------------------------------------------------
                # Estimate surrounding terrain elevation
                # --------------------------------------------------

                outer_values = self._outer_ring(
                    elevation,
                    row,
                    col,
                    radius_px,
                )

                if outer_values.size == 0:
                    continue

                surrounding_elevation = float(
                    np.median(
                        outer_values
                    )
                )

                depth = (
                    surrounding_elevation
                    - center_elevation
                )

                if depth < self.min_depth_m:
                    continue

                # --------------------------------------------------
                # Estimate crater radius
                # --------------------------------------------------

                estimated_radius = (
                    self._estimate_radius(
                        elevation,
                        row,
                        col,
                        surrounding_elevation,
                        dem.pixel_size_m,
                    )
                )

                if not (
                    self.min_radius_m
                    <= estimated_radius
                    <= self.max_radius_m
                ):
                    continue

                diameter = (
                    2.0 * estimated_radius
                )

                confidence = (
                    self._confidence(
                        depth,
                        estimated_radius,
                    )
                )

                center_x = (
                    col * dem.pixel_size_m
                )

                center_y = (
                    row * dem.pixel_size_m
                )

                candidates.append(
                    CraterCandidate(
                        center_x_m=float(
                            center_x
                        ),

                        center_y_m=float(
                            center_y
                        ),

                        radius_m=float(
                            estimated_radius
                        ),

                        diameter_m=float(
                            diameter
                        ),

                        depth_m=float(
                            depth
                        ),

                        confidence=float(
                            confidence
                        ),

                        local_minimum_elevation_m=float(
                            center_elevation
                        ),
                    )
                )

        return self._deduplicate(
            candidates
        )

    @staticmethod
    def _outer_ring(
        elevation: np.ndarray,
        row: int,
        col: int,
        radius_px: int,
    ) -> np.ndarray:
        """
        Extract the boundary pixels surrounding
        the local-minimum window.
        """

        top = elevation[
            row - radius_px,
            col - radius_px :
            col + radius_px + 1,
        ]

        bottom = elevation[
            row + radius_px,
            col - radius_px :
            col + radius_px + 1,
        ]

        left = elevation[
            row - radius_px :
            row + radius_px + 1,
            col - radius_px,
        ]

        right = elevation[
            row - radius_px :
            row + radius_px + 1,
            col + radius_px,
        ]

        return np.concatenate(
            (
                top,
                bottom,
                left,
                right,
            )
        )

    @staticmethod
    def _estimate_radius(
        elevation: np.ndarray,
        row: int,
        col: int,
        surrounding_elevation: float,
        pixel_size_m: float,
    ) -> float:
        """
        Estimate radius by finding the distance at which
        the terrain rises back toward the surrounding level.

        This is a deliberately simple deterministic estimate
        for the first detector stage.
        """

        max_radius_px = min(
            row,
            col,
            elevation.shape[0] - row - 1,
            elevation.shape[1] - col - 1,
        )

        if max_radius_px < 1:
            return pixel_size_m

        center = elevation[
            row,
            col,
        ]

        target = (
            center
            + 0.5
            * (
                surrounding_elevation
                - center
            )
        )

        for radius_px in range(
            1,
            max_radius_px + 1,
        ):

            samples = []

            if row - radius_px >= 0:
                samples.append(
                    elevation[
                        row - radius_px,
                        col,
                    ]
                )

            if row + radius_px < elevation.shape[0]:
                samples.append(
                    elevation[
                        row + radius_px,
                        col,
                    ]
                )

            if col - radius_px >= 0:
                samples.append(
                    elevation[
                        row,
                        col - radius_px,
                    ]
                )

            if col + radius_px < elevation.shape[1]:
                samples.append(
                    elevation[
                        row,
                        col + radius_px,
                    ]
                )

            if not samples:
                continue

            radial_elevation = float(
                np.mean(samples)
            )

            if radial_elevation >= target:
                return (
                    radius_px
                    * pixel_size_m
                )

        return (
            max_radius_px
            * pixel_size_m
        )

    @staticmethod
    def _confidence(
        depth_m: float,
        radius_m: float,
    ) -> float:
        """
        Compute a bounded detection confidence.

        This is a structural detection score, not a
        scientifically calibrated probability.
        """

        depth_component = min(
            depth_m / 10.0,
            1.0,
        )

        size_component = min(
            radius_m / 25.0,
            1.0,
        )

        confidence = (
            0.6 * depth_component
            +
            0.4 * size_component
        )

        return float(
            np.clip(
                confidence,
                0.0,
                1.0,
            )
        )

    @staticmethod
    def _deduplicate(
        candidates: List[
            CraterCandidate
        ],
    ) -> List[
        CraterCandidate
    ]:
        """
        Remove candidates that are spatially redundant.
        """

        accepted: List[
            CraterCandidate
        ] = []

        for candidate in sorted(
            candidates,
            key=lambda item:
                item.confidence,
            reverse=True,
        ):

            duplicate = False

            for existing in accepted:

                distance = np.hypot(
                    candidate.center_x_m
                    -
                    existing.center_x_m,

                    candidate.center_y_m
                    -
                    existing.center_y_m,
                )

                minimum_separation = (
                    0.5
                    * min(
                        candidate.radius_m,
                        existing.radius_m,
                    )
                )

                if (
                    distance
                    < minimum_separation
                ):
                    duplicate = True
                    break

            if not duplicate:
                accepted.append(
                    candidate
                )

        return accepted