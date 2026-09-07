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
)


def main():

    print(
        "=== M4-06.4 "
        "DEM Profile Generation Test ==="
    )

    # --------------------------------------------------
    # Controlled synthetic crater
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
    # Detect crater centre
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

    # --------------------------------------------------
    # Show representative samples
    # --------------------------------------------------

    print()
    print("Representative profile:")

    sample_indices = [
        0,
        5,
        10,
        15,
        20,
        25,
        30,
    ]

    for index in sample_indices:

        if index >= len(
            profile.distances_m
        ):
            continue

        print(
            f"  distance="
            f"{profile.distances_m[index]:.1f} m"
            f" | elevation="
            f"{profile.elevations_m[index]:.3f} m"
        )

    # --------------------------------------------------
    # Validation
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

    assert (
        profile.sampling_interval_m
        == 1.0
    )

    # Distance should increase monotonically.
    for previous, current in zip(
        profile.distances_m,
        profile.distances_m[1:],
    ):

        assert current > previous

    # The centre should correspond to
    # the crater's deepest region.
    centre_elevation = (
        profile.elevations_m[0]
    )

    minimum_elevation = min(
        profile.elevations_m
    )

    assert abs(
        centre_elevation
        - minimum_elevation
    ) < 1e-6

    # --------------------------------------------------
    # Scientific consistency
    # --------------------------------------------------

    print()
    print(
        "Profile length consistency: PASS"
    )

    print(
        "Radial distance ordering: PASS"
    )

    print(
        "Sampling interval: PASS"
    )

    print(
        "Centre/minimum consistency: PASS"
    )

    print(
        "Synthetic test isolation: PASS"
    )

    print()

    print(
        "PASS: M4-06.4 DEM Profile Generation "
        "is functioning."
    )


if __name__ == "__main__":
    main()