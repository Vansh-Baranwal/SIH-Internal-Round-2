"""
Member 4 — DEM Profile Generation.

Generates reproducible radial elevation profiles around
crater centres.

This module is M4-owned and does not modify the existing
terrain/DEM implementation.
"""

from __future__ import annotations

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM

from .types import DEMProfile


class DEMProfileGenerator:
    """
    Generate radial DEM elevation profiles.

    At each radial distance, multiple angular samples are
    collected and their median elevation is used.

    The median makes the profile less sensitive to isolated
    noisy DEM pixels.
    """

    def __init__(
        self,
        max_radius_m: float = 50.0,
        radial_step_m: float = 1.0,
        angular_samples: int = 72,
    ) -> None:

        if max_radius_m <= 0:
            raise ValueError(
                "max_radius_m must be positive."
            )

        if radial_step_m <= 0:
            raise ValueError(
                "radial_step_m must be positive."
            )

        if angular_samples < 8:
            raise ValueError(
                "angular_samples must be at least 8."
            )

        self.max_radius_m = max_radius_m
        self.radial_step_m = radial_step_m
        self.angular_samples = angular_samples

    def generate(
        self,
        dem: DEM,
        center_x_m: float,
        center_y_m: float,
    ) -> DEMProfile:
        """
        Generate a radial DEM profile.

        Parameters
        ----------
        dem:
            Existing DEM object.

        center_x_m:
            X coordinate of profile centre in metres.

        center_y_m:
            Y coordinate of profile centre in metres.

        Returns
        -------
        DEMProfile
            Radial distance/elevation profile.
        """

        elevation = np.asarray(
            dem.elevation,
            dtype=float,
        )

        pixel_size_m = float(
            dem.pixel_size_m
        )

        rows, cols = elevation.shape

        # Convert metric coordinates to DEM pixel coordinates.
        center_col = (
            center_x_m / pixel_size_m
        )

        center_row = (
            center_y_m / pixel_size_m
        )

        if not (
            0.0 <= center_row < rows
            and
            0.0 <= center_col < cols
        ):
            raise ValueError(
                "Profile centre lies outside the DEM."
            )

        # Maximum radius that remains inside the DEM.
        max_available_radius_m = (
            min(
                center_row,
                center_col,
                rows - 1 - center_row,
                cols - 1 - center_col,
            )
            * pixel_size_m
        )

        usable_radius_m = min(
            self.max_radius_m,
            max_available_radius_m,
        )

        radii = np.arange(
            0.0,
            usable_radius_m + self.radial_step_m,
            self.radial_step_m,
        )

        elevations = []

        angles = np.linspace(
            0.0,
            2.0 * np.pi,
            self.angular_samples,
            endpoint=False,
        )

        for radius_m in radii:

            radius_px = (
                radius_m / pixel_size_m
            )

            samples = []

            # At radius zero there is only one centre point.
            if radius_m == 0.0:

                samples.append(
                    self._bilinear_sample(
                        elevation,
                        center_row,
                        center_col,
                    )
                )

            else:

                for angle in angles:

                    row = (
                        center_row
                        +
                        radius_px
                        * np.sin(angle)
                    )

                    col = (
                        center_col
                        +
                        radius_px
                        * np.cos(angle)
                    )

                    if (
                        row < 0.0
                        or row >= rows - 1
                        or col < 0.0
                        or col >= cols - 1
                    ):
                        continue

                    samples.append(
                        self._bilinear_sample(
                            elevation,
                            row,
                            col,
                        )
                    )

            if samples:
                elevations.append(
                    float(
                        np.median(samples)
                    )
                )
            else:
                elevations.append(
                    float("nan")
                )

        # Remove invalid samples while preserving
        # distance/elevation correspondence.
        radii = np.asarray(
            radii,
            dtype=float,
        )

        elevations = np.asarray(
            elevations,
            dtype=float,
        )

        valid = np.isfinite(
            elevations
        )

        radii = radii[valid]
        elevations = elevations[valid]

        if len(radii) < 3:
            raise ValueError(
                "Insufficient valid DEM samples "
                "for radial profile."
            )

        return DEMProfile(
            distances_m=[
                float(value)
                for value in radii
            ],
            elevations_m=[
                float(value)
                for value in elevations
            ],
            sampling_interval_m=float(
                self.radial_step_m
            ),
        )

    @staticmethod
    def _bilinear_sample(
        elevation: np.ndarray,
        row: float,
        col: float,
    ) -> float:
        """
        Bilinear interpolation of the DEM.
        """

        row0 = int(
            np.floor(row)
        )

        col0 = int(
            np.floor(col)
        )

        row1 = min(
            row0 + 1,
            elevation.shape[0] - 1,
        )

        col1 = min(
            col0 + 1,
            elevation.shape[1] - 1,
        )

        dr = row - row0
        dc = col - col0

        value = (
            elevation[row0, col0]
            * (1.0 - dr)
            * (1.0 - dc)
            +
            elevation[row1, col0]
            * dr
            * (1.0 - dc)
            +
            elevation[row0, col1]
            * (1.0 - dr)
            * dc
            +
            elevation[row1, col1]
            * dr
            * dc
        )

        return float(value)