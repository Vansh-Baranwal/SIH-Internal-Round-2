"""
Visualization utilities for the Member 4 Sun Simulator.

These plots are for scientific inspection of synthetic
counterfactual observations.

All generated visualizations represent synthetic data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from .simulator import SunSimulationResult


def plot_simulation(
    result: SunSimulationResult,
    output_path: str | Path | None = None,
):
    """
    Visualize one synthetic Sun simulation.

    The figure contains three separate scientific views:

        1. Synthetic observation
        2. Shadow mask
        3. Direct illumination

    Parameters
    ----------
    result:
        Result returned by CounterfactualSunSimulator.

    output_path:
        Optional path where the figure should be saved.

    Returns
    -------
    matplotlib.figure.Figure
        Generated figure.
    """

    if result.source_type != "synthetic":
        raise ValueError(
            "Visualization is intended for synthetic "
            "Sun Simulator results."
        )

    figure = plt.figure(
        figsize=(15, 5)
    )

    # -----------------------------------------
    # Synthetic observation
    # -----------------------------------------

    axis_image = figure.add_subplot(
        1,
        3,
        1,
    )

    axis_image.imshow(
        result.image,
        cmap="gray",
        vmin=0.0,
        vmax=1.0,
    )

    axis_image.set_title(
        "Synthetic Observation"
    )

    axis_image.set_xlabel(
        "X / pixel"
    )

    axis_image.set_ylabel(
        "Y / pixel"
    )

    # -----------------------------------------
    # Shadow mask
    # -----------------------------------------

    axis_shadow = figure.add_subplot(
        1,
        3,
        2,
    )

    axis_shadow.imshow(
        result.shadow_mask,
        cmap="gray",
        interpolation="nearest",
    )

    axis_shadow.set_title(
        "Geometric Shadow Mask"
    )

    axis_shadow.set_xlabel(
        "X / pixel"
    )

    axis_shadow.set_ylabel(
        "Y / pixel"
    )

    # -----------------------------------------
    # Direct illumination
    # -----------------------------------------

    axis_illumination = figure.add_subplot(
        1,
        3,
        3,
    )

    axis_illumination.imshow(
        result.illumination,
        cmap="gray",
        vmin=0.0,
        vmax=1.0,
    )

    axis_illumination.set_title(
        "Direct Illumination"
    )

    axis_illumination.set_xlabel(
        "X / pixel"
    )

    axis_illumination.set_ylabel(
        "Y / pixel"
    )

    # -----------------------------------------
    # Overall title
    # -----------------------------------------

    figure.suptitle(
        (
            "Counterfactual Sun Simulation — "
            "Simulated Data\n"
            f"Azimuth: {result.sun.azimuth_deg:.1f}° | "
            f"Elevation: {result.sun.elevation_deg:.1f}°"
        )
    )

    figure.tight_layout()

    if output_path is not None:

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        figure.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight",
        )

    return figure


def plot_experiment(
    results: Sequence[SunSimulationResult],
    output_path: str | Path | None = None,
):
    """
    Visualize multiple counterfactual Sun observations.

    Each Sun state receives its own figure panel containing
    the corresponding synthetic observation.

    Parameters
    ----------
    results:
        Sequence of SunSimulationResult objects.

    output_path:
        Optional output image path.

    Returns
    -------
    matplotlib.figure.Figure
        Generated figure.
    """

    if not results:
        raise ValueError(
            "At least one simulation result is required."
        )

    if any(
        result.source_type != "synthetic"
        for result in results
    ):
        raise ValueError(
            "Experiment visualization accepts "
            "synthetic results only."
        )

    figure, axes = plt.subplots(
        1,
        len(results),
        figsize=(
            5 * len(results),
            5,
        ),
        squeeze=False,
    )

    axes = axes[0]

    for axis, result in zip(
        axes,
        results,
    ):

        axis.imshow(
            result.image,
            cmap="gray",
            vmin=0.0,
            vmax=1.0,
        )

        axis.set_title(
            (
                f"Az {result.sun.azimuth_deg:.0f}°\n"
                f"Elevation {result.sun.elevation_deg:.0f}°"
            )
        )

        axis.set_xlabel(
            "X / pixel"
        )

        axis.set_ylabel(
            "Y / pixel"
        )

    figure.suptitle(
        "Counterfactual Sun-Angle Experiment — Simulated Data"
    )

    figure.tight_layout()

    if output_path is not None:

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        figure.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight",
        )

    return figure