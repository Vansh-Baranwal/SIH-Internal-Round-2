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
    CraterGeometryExtractor,
)


def main():

    print(
        "=== M4-06.3 "
        "Crater Geometry Extraction Test ==="
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

    # --------------------------------------------------
    # Detect candidate
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
        f"Detected centre: "
        f"({candidate.center_x_m:.1f}, "
        f"{candidate.center_y_m:.1f}) m"
    )

    print(
        f"Detection diameter: "
        f"{candidate.diameter_m:.1f} m"
    )

    # --------------------------------------------------
    # Geometry extraction
    # --------------------------------------------------

    extractor = CraterGeometryExtractor(
        max_radius_m=50.0,
        radial_step_m=1.0,
        angular_samples=72,
    )

    result = extractor.extract(
        dem,
        candidate,
    )

    center = result.center
    geometry = result.geometry
    profile = result.dem_profile

    print()

    print(
        f"Extracted centre: "
        f"({center.x_m:.1f}, "
        f"{center.y_m:.1f}) m"
    )

    print(
        f"Extracted radius: "
        f"{geometry.radius_m:.1f} m"
    )

    print(
        f"Extracted diameter: "
        f"{geometry.diameter_m:.1f} m"
    )

    print(
        f"Extracted depth: "
        f"{geometry.depth_m:.1f} m"
    )

    print(
        f"Circularity: "
        f"{geometry.circularity:.3f}"
    )

    print(
        f"Rim height: "
        f"{geometry.rim_height_m:.1f} m"
    )

    print(
        f"DEM profile samples: "
        f"{len(profile.distances_m)}"
    )

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    assert center.x_m is not None
    assert center.y_m is not None

    assert abs(
        center.x_m - 64.0
    ) <= 2.0

    assert abs(
        center.y_m - 64.0
    ) <= 2.0

    assert (
        geometry.radius_m > 0
    )

    assert (
        geometry.diameter_m > 0
    )

    assert (
        geometry.depth_m > 0
    )

    assert (
        0.0
        <= geometry.circularity
        <= 1.0
    )

    assert (
        len(profile.distances_m)
        ==
        len(profile.elevations_m)
    )

    assert (
        len(profile.distances_m)
        >= 10
    )

    print()

    print(
        "Centre extraction: PASS"
    )

    print(
        "Radius extraction: PASS"
    )

    print(
        "Diameter extraction: PASS"
    )

    print(
        "Depth extraction: PASS"
    )

    print(
        "Circularity extraction: PASS"
    )

    print(
        "DEM radial profile: PASS"
    )

    print()

    print(
        "PASS: M4-06.3 Crater Geometry "
        "Extraction is functioning."
    )


if __name__ == "__main__":
    main()