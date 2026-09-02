import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from lunar_hazard_mapper.scientific.common.types import (
    SunState,
    RegistrationMetrics,
    RegistrationResult,
    ScientificResult,
)

from lunar_hazard_mapper.scientific.common.validation import (
    validate_rmse,
    validate_inlier_ratio,
)

def main():

    print(
        "=== M4 Scientific Foundation Test ==="
    )

    sun = SunState(
        azimuth_deg=135.0,
        elevation_deg=30.0,
    )

    print(
        f"Sun: azimuth={sun.azimuth_deg}°, "
        f"elevation={sun.elevation_deg}°"
    )

    metrics = RegistrationMetrics(
        rmse_px=0.73,
        inlier_count=1842,
        inlier_ratio=0.91,
    )

    registration = RegistrationResult(
        registration_id="reg_test_001",
        source_sensor="OHRC",
        reference_sensor="TMC",
        metrics=metrics,
        success=True,
    )

    print(
        f"Registration: "
        f"{registration.registration_id}"
    )

    print(
        f"RMSE: "
        f"{registration.metrics.rmse_px}px"
    )

    print(
        f"Inlier ratio: "
        f"{registration.metrics.inlier_ratio}"
    )

    rmse_result = validate_rmse(
        registration.metrics.rmse_px
    )

    ratio_result = validate_inlier_ratio(
        registration.metrics.inlier_ratio
    )

    print()
    print("Validation:")

    print(
        f"RMSE test: "
        f"{rmse_result.passed}"
    )

    print(
        f"  {rmse_result.message}"
    )

    print(
        f"Inlier test: "
        f"{ratio_result.passed}"
    )

    print(
        f"  {ratio_result.message}"
    )

    scientific = ScientificResult(
        feature="sun_simulator",
        success=True,
        source_type="synthetic",
    )

    scientific.add_warning(
        "Synthetic result — not a real lunar observation."
    )

    print()

    print(
        f"Scientific feature: "
        f"{scientific.feature}"
    )

    print(
        f"Source type: "
        f"{scientific.source_type}"
    )

    print(
        f"Warnings: "
        f"{scientific.warnings}"
    )


if __name__ == "__main__":
    main()