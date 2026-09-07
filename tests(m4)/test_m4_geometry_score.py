"""
M4-06.5.3 — Geometry Score Test.
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
    CraterGeometryExtractor,
    score_geometry,
)


def main():

    print(
        "=== M4-06.5.3 "
        "Geometry Score Test ==="
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
        f"Detection diameter: "
        f"{candidate.diameter_m:.1f} m"
    )

    # --------------------------------------------------
    # Extract geometry
    # --------------------------------------------------

    extractor = CraterGeometryExtractor(
        max_radius_m=50.0,
        radial_step_m=1.0,
        angular_samples=72,
    )

    extracted = extractor.extract(
        dem=dem,
        candidate=candidate,
    )

    geometry = extracted.geometry

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

    # --------------------------------------------------
    # Calculate geometry score
    # --------------------------------------------------

    geometry_score = score_geometry(
        candidate=candidate,
        geometry=geometry,
        pixel_size_m=dem.pixel_size_m,
    )

    print(
        f"Geometry score: "
        f"{geometry_score:.3f}"
    )

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    assert 0.0 <= geometry_score <= 1.0

    print(
        "Score range validation: PASS"
    )

    # The synthetic crater should have strong
    # geometric quality.
    assert geometry_score >= 0.70

    print(
        "Synthetic crater quality: PASS"
    )

    # --------------------------------------------------
    # Validate individual geometry fields
    # --------------------------------------------------

    assert (
        0.0
        <= geometry.circularity
        <= 1.0
    )

    assert (
        geometry.diameter_m > 0.0
    )

    assert (
        geometry.radius_m > 0.0
    )

    assert (
        geometry.depth_m >= 0.0
    )

    print(
        "Geometry field validation: PASS"
    )

    # --------------------------------------------------
    # Invalid pixel-size rejection
    # --------------------------------------------------

    try:

        score_geometry(
            candidate=candidate,
            geometry=geometry,
            pixel_size_m=0.0,
        )

    except ValueError:

        print(
            "Invalid pixel-size rejection: PASS"
        )

    else:

        raise AssertionError(
            "Invalid pixel size was accepted."
        )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()
    print(
        "PASS: M4-06.5.3 Geometry Score "
        "is functioning."
    )


if __name__ == "__main__":
    main()