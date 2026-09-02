"""
M4-06.5.5 — Combined Landmark Quality Score Test.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.scientific.crater_landmarks import (
    score_combined,
)


def main():

    print(
        "=== M4-06.5.5 "
        "Combined Landmark Quality Score Test ==="
    )

    # --------------------------------------------------
    # Representative component scores
    # --------------------------------------------------

    detection_score = 0.824
    geometry_score = 0.962
    profile_score = 1.000

    print(
        f"Detection score: {detection_score:.3f}"
    )

    print(
        f"Geometry score:  {geometry_score:.3f}"
    )

    print(
        f"Profile score:   {profile_score:.3f}"
    )

    # --------------------------------------------------
    # Calculate combined score
    # --------------------------------------------------

    combined_score = score_combined(
        detection_score=detection_score,
        geometry_score=geometry_score,
        profile_score=profile_score,
    )

    print(
        f"Combined score:  {combined_score:.3f}"
    )

    # --------------------------------------------------
    # Expected weighted result
    # --------------------------------------------------

    expected = (
        0.40 * detection_score
        +
        0.35 * geometry_score
        +
        0.25 * profile_score
    )

    assert abs(
        combined_score - expected
    ) < 1e-12

    print(
        "Weighted combination validation: PASS"
    )

    # --------------------------------------------------
    # Range validation
    # --------------------------------------------------

    assert 0.0 <= combined_score <= 1.0

    print(
        "Score range validation: PASS"
    )

    # --------------------------------------------------
    # Boundary tests
    # --------------------------------------------------

    assert (
        score_combined(
            0.0,
            0.0,
            0.0,
        )
        == 0.0
    )

    assert (
        score_combined(
            1.0,
            1.0,
            1.0,
        )
        == 1.0
    )

    print(
        "Boundary validation: PASS"
    )

    # --------------------------------------------------
    # Invalid score rejection
    # --------------------------------------------------

    invalid_cases = [
        (1.1, 0.5, 0.5),
        (0.5, -0.1, 0.5),
        (0.5, 0.5, 1.2),
    ]

    for values in invalid_cases:

        try:

            score_combined(*values)

        except ValueError:

            continue

        raise AssertionError(
            f"Invalid scores were accepted: {values}"
        )

    print(
        "Invalid score rejection: PASS"
    )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()

    print(
        "PASS: M4-06.5.5 Combined Landmark "
        "Quality Score is functioning."
    )


if __name__ == "__main__":
    main()