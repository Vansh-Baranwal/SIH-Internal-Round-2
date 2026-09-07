"""
M4-06.5.2 — Detection Score Test.
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
    score_detection,
)


def main():

    print(
        "=== M4-06.5.2 "
        "Detection Score Test ==="
    )

    # --------------------------------------------------
    # Create the same controlled synthetic crater
    # used by the previous M4 tests.
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
    # Run the existing M4 detector.
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
        f"Detection confidence: "
        f"{candidate.confidence:.3f}"
    )

    # --------------------------------------------------
    # Calculate detection quality.
    # --------------------------------------------------

    detection_score = score_detection(
        candidate
    )

    print(
        f"Detection score: "
        f"{detection_score:.3f}"
    )

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    assert 0.0 <= detection_score <= 1.0

    print(
        "Score range validation: PASS"
    )

    # The current M4 scoring contract intentionally
    # preserves the detector's normalized confidence.
    assert abs(
        detection_score
        - candidate.confidence
    ) < 1e-12

    print(
        "Confidence preservation: PASS"
    )

    # --------------------------------------------------
    # Test invalid confidence rejection.
    # --------------------------------------------------

    original_confidence = (
        candidate.confidence
    )

    try:

        # CraterCandidate is expected to be immutable,
        # so create a lightweight test object instead.
        class InvalidCandidate:
            confidence = 1.5

        score_detection(
            InvalidCandidate()
        )

    except ValueError:

        print(
            "Invalid confidence rejection: PASS"
        )

    else:

        raise AssertionError(
            "Invalid confidence was accepted."
        )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()
    print(
        "PASS: M4-06.5.2 Detection Score "
        "is functioning."
    )


if __name__ == "__main__":
    main()