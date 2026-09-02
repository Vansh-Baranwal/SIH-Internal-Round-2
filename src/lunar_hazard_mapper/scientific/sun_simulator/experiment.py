"""
Counterfactual Sun-Angle Experiment.

Runs the Sun Simulator over multiple controlled Sun states
and records how the synthetic illumination and shadow geometry
change.

This module does NOT claim correspondence invariance.

That claim can only be made after the correspondence engine
has processed the generated variants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import DEM
from lunar_hazard_mapper.scientific.common.types import SunState

from .simulator import (
    CounterfactualSunSimulator,
    SunSimulationResult,
)


@dataclass
class SunExperimentRecord:
    """
    Summary of one simulated Sun state.
    """

    sun: SunState

    shadow_fraction: float

    mean_illumination: float

    mean_image_intensity: float

    shadow_pixels: int

    source_type: str

    label: str


@dataclass
class SunAngleExperiment:
    """
    Collection of counterfactual Sun simulations.
    """

    records: List[SunExperimentRecord]

    baseline_index: int = 0

    def baseline(self) -> SunExperimentRecord:
        """Return the baseline Sun state."""

        return self.records[self.baseline_index]

    def shadow_change_from_baseline(
        self,
        index: int,
    ) -> float:
        """
        Calculate absolute shadow-fraction change from baseline.
        """

        baseline = self.baseline()

        current = self.records[index]

        return abs(
            current.shadow_fraction
            -
            baseline.shadow_fraction
        )

    def summary(self) -> dict:
        """
        Return a JSON-friendly experiment summary.
        """

        baseline = self.baseline()

        return {
            "experiment_type":
                "counterfactual_sun_angle",

            "source_type":
                "synthetic",

            "label":
                "Simulated Data",

            "num_variants":
                len(self.records),

            "baseline_sun": {
                "azimuth_deg":
                    baseline.sun.azimuth_deg,

                "elevation_deg":
                    baseline.sun.elevation_deg,
            },

            "variants": [
                {
                    "azimuth_deg":
                        record.sun.azimuth_deg,

                    "elevation_deg":
                        record.sun.elevation_deg,

                    "shadow_fraction":
                        record.shadow_fraction,

                    "shadow_change_from_baseline":
                        self.shadow_change_from_baseline(
                            index
                        ),

                    "mean_illumination":
                        record.mean_illumination,

                    "mean_image_intensity":
                        record.mean_image_intensity,

                    "shadow_pixels":
                        record.shadow_pixels,
                }

                for index, record
                in enumerate(self.records)
            ],
        }


class SunAngleExperimentRunner:
    """
    Runs controlled multi-angle Sun simulations.
    """

    def __init__(
        self,
        simulator: CounterfactualSunSimulator | None = None,
    ) -> None:

        self.simulator = (
            simulator
            if simulator is not None
            else CounterfactualSunSimulator()
        )

    def run(
        self,
        dem: DEM,
        sun_states: List[SunState],
    ) -> SunAngleExperiment:
        """
        Run a controlled experiment across multiple Sun states.
        """

        if not sun_states:
            raise ValueError(
                "At least one Sun state is required."
            )

        simulation_results = [
            self.simulator.run(
                dem,
                sun,
            )
            for sun in sun_states
        ]

        records = [
            self._make_record(
                result
            )
            for result in simulation_results
        ]

        return SunAngleExperiment(
            records=records,
            baseline_index=0,
        )

    @staticmethod
    def _make_record(
        result: SunSimulationResult,
    ) -> SunExperimentRecord:
        """
        Convert a full simulation result into
        an experiment record.
        """

        return SunExperimentRecord(
            sun=result.sun,

            shadow_fraction=float(
                result.shadow_mask.mean()
            ),

            mean_illumination=float(
                result.illumination.mean()
            ),

            mean_image_intensity=float(
                result.image.mean()
            ),

            shadow_pixels=int(
                result.shadow_mask.sum()
            ),

            source_type=result.source_type,

            label=result.label,
        )