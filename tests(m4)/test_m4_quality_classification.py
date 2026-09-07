"""
M4-06.5.6 — Quality Classification Test.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.scientific.crater_landmarks import (
    classify_quality,
)


def main():

    print(
        "=== M4-06.5.6 "
        "Quality Classification Test ==="
    )

    # --------------------------------------------------
    # Representative classification
    # --------------------------------------------------

    test_score = 0.916

    classification = classify_quality(
        test_score
    )

    print(
        f"Combined score: "
        f"{test_score:.3f}"
    )

    print(
        f"Classification: "
        f"{classification}"
    )

    assert classification == "HIGH"

    print(
        "HIGH classification: PASS"
    )

    # --------------------------------------------------
    # MEDIUM classification
    # --------------------------------------------------

    medium_score = 0.700

    assert (
        classify_quality(medium_score)
        == "MEDIUM"
    )

    print(
        "MEDIUM classification: PASS"
    )

    # --------------------------------------------------
    # LOW classification
    # --------------------------------------------------

    low_score = 0.400

    assert (
        classify_quality(low_score)
        == "LOW"
    )

    print(
        "LOW classification: PASS"
    )

    # --------------------------------------------------
    # Boundary tests
    # --------------------------------------------------

    assert (
        classify_quality(0.80)
        == "HIGH"
    )

    assert (
        classify_quality(0.60)
        == "MEDIUM"
    )

    assert (
        classify_quality(0.599999)
        == "LOW"
    )

    print(
        "Threshold boundary validation: PASS"
    )

    # --------------------------------------------------
    # Absolute boundaries
    # --------------------------------------------------

    assert (
        classify_quality(0.0)
        == "LOW"
    )

    assert (
        classify_quality(1.0)
        == "HIGH"
    )

    print(
        "Score boundary validation: PASS"
    )

    # --------------------------------------------------
    # Invalid score rejection
    # --------------------------------------------------

    invalid_scores = [
        -0.01,
        1.01,
        -1.0,
        2.0,
    ]

    for score in invalid_scores:

        try:

            classify_quality(score)

        except ValueError:

            continue

        raise AssertionError(
            f"Invalid score was accepted: {score}"
        )

    print(
        "Invalid score rejection: PASS"
    )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()

    print(
        "PASS: M4-06.5.6 Quality Classification "
        "is functioning."
    )


if __name__ == "__main__":
    main()