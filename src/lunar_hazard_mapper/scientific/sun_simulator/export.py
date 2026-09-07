"""
Synthetic Sun Simulator export utilities.

All exported observations are explicitly marked as
synthetic evaluation data.

They must never be treated as real lunar observations.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .simulator import SunSimulationResult


def export_simulation_result(
    result: SunSimulationResult,
    output_dir: str | Path,
    variant_name: str,
) -> Path:
    """
    Export one synthetic Sun simulation.

    Files created:

        <variant_name>.npy
        <variant_name>_shadow.npy
        <variant_name>_metadata.json

    Returns:
        Path to the exported image.
    """

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not variant_name:
        raise ValueError(
            "variant_name cannot be empty."
        )

    # --------------------------------------------------
    # Safety guard
    # --------------------------------------------------

    if result.source_type != "synthetic":
        raise ValueError(
            "Only synthetic simulation results may "
            "be exported by this module."
        )

    if result.label != "Simulated Data":
        raise ValueError(
            "Simulation result must be labelled "
            "'Simulated Data'."
        )

    # --------------------------------------------------
    # Image
    # --------------------------------------------------

    image_path = (
        output_dir /
        f"{variant_name}.npy"
    )

    np.save(
        image_path,
        result.image,
    )

    # --------------------------------------------------
    # Shadow mask
    # --------------------------------------------------

    shadow_path = (
        output_dir /
        f"{variant_name}_shadow.npy"
    )

    np.save(
        shadow_path,
        result.shadow_mask,
    )

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    metadata = result.summary()

    metadata.update(
        {
            "export_type":
                "synthetic_evaluation",

            "synthetic_only":
                True,

            "real_observation":
                False,

            "image_file":
                image_path.name,

            "shadow_file":
                shadow_path.name,
        }
    )

    metadata_path = (
        output_dir /
        f"{variant_name}_metadata.json"
    )

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
        ),
        encoding="utf-8",
    )

    return image_path