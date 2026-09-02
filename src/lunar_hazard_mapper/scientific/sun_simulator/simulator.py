"""
Counterfactual Sun Simulator.

Generates controlled synthetic observations from a DEM
under different solar illumination states.

This is strictly an evaluation tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM

from lunar_hazard_mapper.scientific.common.types import (
    ScientificResult,
    SunState,
)

from .renderer import (
    render_synthetic_observation,
)


@dataclass
class SunSimulationResult:
    """
    Result of one counterfactual illumination simulation.
    """

    sun: SunState

    image: np.ndarray

    shadow_mask: np.ndarray

    illumination: np.ndarray

    source_type: str = "synthetic"

    label: str = "Simulated Data"

    metadata: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        """
        Return JSON-friendly simulation metadata.
        """

        return {
            "source_type": self.source_type,

            "label": self.label,

            "sun_azimuth_deg":
                self.sun.azimuth_deg,

            "sun_elevation_deg":
                self.sun.elevation_deg,

            "image_shape":
                list(self.image.shape),

            "shadow_pixels":
                int(self.shadow_mask.sum()),

            "shadow_fraction":
                float(self.shadow_mask.mean()),

            "image_min":
                float(self.image.min()),

            "image_max":
                float(self.image.max()),

            "image_mean":
                float(self.image.mean()),

            "metadata":
                self.metadata or {},
        }


class CounterfactualSunSimulator:
    """
    Evaluation-only simulator for generating synthetic
    observations under controlled Sun positions.
    """

    def __init__(
        self,
        ambient: float = 0.15,
        diffuse: float = 0.85,
        shadow_floor: float = 0.08,
    ) -> None:

        self.ambient = ambient
        self.diffuse = diffuse
        self.shadow_floor = shadow_floor

    def run(
        self,
        dem: DEM,
        sun: SunState,
    ) -> SunSimulationResult:
        """
        Generate one synthetic observation.
        """

        if dem.source_type not in {
            "synthetic",
            "measured",
        }:
            raise ValueError(
                "Sun Simulator requires a synthetic or measured DEM. "
                "SR-estimated terrain is not accepted."
            )

        (
            image,
            shadow_mask,
            illumination,
        ) = render_synthetic_observation(
            dem=dem,
            sun=sun,
            ambient=self.ambient,
            diffuse=self.diffuse,
            shadow_floor=self.shadow_floor,
        )

        return SunSimulationResult(
            sun=sun,
            image=image,
            shadow_mask=shadow_mask,
            illumination=illumination,

            metadata={
                "dem_source_type":
                    dem.source_type,

                "pixel_size_m":
                    float(dem.pixel_size_m),

                "shape":
                    list(dem.shape),

                "purpose":
                    "counterfactual_illumination_evaluation",
            },
        )

    @staticmethod
    def as_scientific_result(
        result: SunSimulationResult,
    ) -> ScientificResult:
        """
        Convert simulation output into the shared
        Member 4 scientific-result representation.
        """

        return ScientificResult(
            feature="counterfactual_sun_simulator",

            success=True,

            source_type=result.source_type,

            metadata=result.summary(),
        )