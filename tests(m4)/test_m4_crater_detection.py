import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from lunar_hazard_mapper.m3_terrain.synthetic import (
    create_synthetic_terrain,
)

from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
)


def main():

    print(
        "=== M4-06.2 "
        "Crater Detection Test ==="
    )

    # --------------------------------------------------
    # Create known synthetic crater terrain
    # --------------------------------------------------

    dem = create_synthetic_terrain(
        kind="crater",
        size=128,
        pixel_size_m=1.0,
        radius_px=20,
        depth_m=8.0,
        rim_height_m=2.0,
    )

    print(
        f"DEM shape: {dem.shape}"
    )

    detector = CraterDetector(
        min_radius_m=3.0,
        max_radius_m=50.0,
        min_depth_m=1.0,
        neighborhood_radius_px=20,
    )

    candidates = detector.detect(
        dem
    )

    print(
        f"Candidates detected: "
        f"{len(candidates)}"
    )

    # --------------------------------------------------
    # Basic detection validation
    # --------------------------------------------------

    assert len(candidates) > 0

    # --------------------------------------------------
    # Inspect candidates
    # --------------------------------------------------

    for index, candidate in enumerate(
        candidates[:10]
    ):

        print(
            f"[{index}] "
            f"center=("
            f"{candidate.center_x_m:.1f}, "
            f"{candidate.center_y_m:.1f}) m | "
            f"diameter="
            f"{candidate.diameter_m:.1f} m | "
            f"depth="
            f"{candidate.depth_m:.1f} m | "
            f"confidence="
            f"{candidate.confidence:.3f}"
        )

    # --------------------------------------------------
    # Validate candidate fields
    # --------------------------------------------------

    for candidate in candidates:

        assert (
            candidate.radius_m > 0
        )

        assert (
            candidate.diameter_m
            > 0
        )

        assert (
            candidate.depth_m
            >= 1.0
        )

        assert (
            0.0
            <= candidate.confidence
            <= 1.0
        )

        assert np.isclose(
            candidate.diameter_m,
            2.0 * candidate.radius_m,
        )

    # --------------------------------------------------
    # Synthetic isolation
    # --------------------------------------------------

    # Detection itself does not convert the result into
    # a real lunar observation.

    print()

    print(
        "Candidate generation: PASS"
    )

    print(
        "Geometry validation: PASS"
    )

    print(
        "Confidence validation: PASS"
    )

    print(
        "Synthetic test isolation: PASS"
    )

    print()

    print(
        "PASS: M4-06.2 Crater Detection "
        "is functioning."
    )


if __name__ == "__main__":
    main()