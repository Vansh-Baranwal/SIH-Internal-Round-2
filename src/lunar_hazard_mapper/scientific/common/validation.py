"""
Common validation helpers for Member 4.
"""

from typing import Optional

from .types import ValidationResult


def validate_rmse(
    rmse_px: Optional[float],
    threshold_px: float = 1.0,
) -> ValidationResult:

    result = ValidationResult(
        feature="registration_rmse",
        passed=False,
    )

    if rmse_px is None:

        result.message = "RMSE was not provided."

        result.add_check(
            "rmse_available",
            False,
        )

        return result

    result.add_check(
        "rmse_available",
        True,
    )

    passed = rmse_px < threshold_px

    result.add_check(
        "rmse_below_threshold",
        passed,
    )

    result.metrics["rmse_px"] = float(
        rmse_px
    )

    result.metrics["threshold_px"] = float(
        threshold_px
    )

    result.passed = passed

    if passed:

        result.message = (
            f"RMSE {rmse_px:.3f}px is below "
            f"the {threshold_px:.3f}px threshold."
        )

    else:

        result.message = (
            f"RMSE {rmse_px:.3f}px does not meet "
            f"the {threshold_px:.3f}px threshold."
        )

    return result


def validate_inlier_ratio(
    inlier_ratio: Optional[float],
    minimum_ratio: float = 0.85,
) -> ValidationResult:

    result = ValidationResult(
        feature="registration_inlier_ratio",
        passed=False,
    )

    if inlier_ratio is None:

        result.message = (
            "Inlier ratio was not provided."
        )

        result.add_check(
            "inlier_ratio_available",
            False,
        )

        return result

    result.add_check(
        "inlier_ratio_available",
        True,
    )

    passed = inlier_ratio >= minimum_ratio

    result.add_check(
        "inlier_ratio_above_threshold",
        passed,
    )

    result.metrics["inlier_ratio"] = float(
        inlier_ratio
    )

    result.metrics["minimum_ratio"] = float(
        minimum_ratio
    )

    result.passed = passed

    if passed:

        result.message = (
            f"Inlier ratio {inlier_ratio:.3f} "
            f"meets the {minimum_ratio:.3f} minimum."
        )

    else:

        result.message = (
            f"Inlier ratio {inlier_ratio:.3f} "
            f"is below the {minimum_ratio:.3f} minimum."
        )

    return result