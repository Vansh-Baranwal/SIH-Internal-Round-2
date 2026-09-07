"""
M4-06.5.4 — DEM Profile Score Test.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.m3_terrain.synthetic import (
    create_synthetic_terrain,
)

from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    DEMProfileGenerator,
    score_profile,
)


def main():

    print(
        "=== M4-06.5.4 "
        "DEM Profile Score Test ==="
    )

    # --------------------------------------------------
    # Create controlled synthetic crater
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

    # --------------------------------------------------
    # Detect crater
    # --------------------------------------------------

    detector = CraterDetector(
        min_radius_m=3.0,
        max_radius_m=50.0,
        min_depth_m=1.0,
        neighborhood_radius_px=20,
    )

    candidates = detector.detect(
        dem
    )

    assert len(candidates) > 0

    candidate = candidates[0]

    print(
        f"Crater centre: "
        f"({candidate.center_x_m:.1f}, "
        f"{candidate.center_y_m:.1f}) m"
    )

    # --------------------------------------------------
    # Generate radial profile
    # --------------------------------------------------

    generator = DEMProfileGenerator(
        max_radius_m=50.0,
        radial_step_m=1.0,
        angular_samples=72,
    )

    profile = generator.generate(
        dem=dem,
        center_x_m=candidate.center_x_m,
        center_y_m=candidate.center_y_m,
    )

    print(
        f"Profile samples: "
        f"{len(profile.distances_m)}"
    )

    print(
        f"Sampling interval: "
        f"{profile.sampling_interval_m:.1f} m"
    )

    print(
        f"Centre elevation: "
        f"{profile.elevations_m[0]:.3f} m"
    )

    print(
        f"Minimum elevation: "
        f"{min(profile.elevations_m):.3f} m"
    )

    # --------------------------------------------------
    # Calculate profile score
    # --------------------------------------------------

    profile_score = score_profile(
        profile
    )

    print(
        f"Profile score: "
        f"{profile_score:.3f}"
    )

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    assert 0.0 <= profile_score <= 1.0

    print(
        "Score range validation: PASS"
    )

    # The controlled synthetic crater has a complete,
    # regular and measurable profile.
    assert profile_score >= 0.70

    print(
        "Synthetic profile quality: PASS"
    )

    # --------------------------------------------------
    # Validate profile structure
    # --------------------------------------------------

    assert (
        len(profile.distances_m)
        ==
        len(profile.elevations_m)
    )

    assert (
        len(profile.distances_m)
        >= 10
    )

    assert (
        profile.distances_m[0]
        == 0.0
    )

    print(
        "Profile structure validation: PASS"
    )

    # --------------------------------------------------
    # Invalid profile test
    # --------------------------------------------------

    class InvalidProfile:

        distances_m = [0.0, 1.0]

        elevations_m = [0.0]

        sampling_interval_m = 1.0

    try:

        score_profile(
            InvalidProfile()
        )

    except ValueError:

        print(
            "Invalid profile rejection: PASS"
        )

    else:

        raise AssertionError(
            "Invalid profile was accepted."
        )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()

    print(
        "PASS: M4-06.5.4 DEM Profile Score "
        "is functioning."
    )


if __name__ == "__main__":
    main()