import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterCenter,
    CraterGeometry,
    DEMProfile,
    SensorAppearance,
    CraterLandmark,
)


def main():

    print(
        "=== M4-06.1 "
        "Crater Landmark Contract Test ==="
    )

    center = CraterCenter(
        latitude_deg=-89.0,
        longitude_deg=0.5,
        x_m=100.0,
        y_m=200.0,
    )

    geometry = CraterGeometry(
        diameter_m=50.0,
        depth_m=8.0,
        radius_m=25.0,
        circularity=0.94,
        rim_height_m=2.0,
    )

    profile = DEMProfile(
        distances_m=[
            0.0,
            5.0,
            10.0,
            15.0,
            20.0,
        ],
        elevations_m=[
            -8.0,
            -7.0,
            -4.0,
            -1.0,
            0.0,
        ],
        sampling_interval_m=5.0,
    )

    landmark = CraterLandmark(
        crater_id="CRATER_TEST_001",

        center=center,

        geometry=geometry,

        dem_profile=profile,

        quality_score=0.93,

        detection_method="synthetic_test",

        source_type="synthetic",

        label="Simulated Data",
    )

    landmark.add_sensor_appearance(
        SensorAppearance(
            sensor_name="TMC",
            reference="future_tmc_reference",
        )
    )

    landmark.add_sensor_appearance(
        SensorAppearance(
            sensor_name="OHRC",
            reference="future_ohrc_reference",
        )
    )

    landmark.add_sensor_appearance(
        SensorAppearance(
            sensor_name="IIRS",
            reference="future_iirs_reference",
        )
    )

    # -----------------------------------------
    # Validation
    # -----------------------------------------

    assert (
        landmark.crater_id
        == "CRATER_TEST_001"
    )

    assert (
        landmark.geometry.diameter_m
        == 50.0
    )

    assert (
        landmark.geometry.circularity
        == 0.94
    )

    assert (
        len(landmark.dem_profile.distances_m)
        == 5
    )

    assert (
        landmark.quality_score
        == 0.93
    )

    assert (
        landmark.source_type
        == "synthetic"
    )

    assert (
        landmark.label
        == "Simulated Data"
    )

    sensors = {
        appearance.sensor_name
        for appearance
        in landmark.sensor_appearances
    }

    assert sensors == {
        "TMC",
        "OHRC",
        "IIRS",
    }

    summary = landmark.summary()

    assert (
        summary["crater_id"]
        == "CRATER_TEST_001"
    )

    assert (
        summary["dem_profile_samples"]
        == 5
    )

    print()

    print(
        "Crater identity: PASS"
    )

    print(
        "Geometry contract: PASS"
    )

    print(
        "DEM profile contract: PASS"
    )

    print(
        "Quality score: PASS"
    )

    print(
        "Multi-sensor contract: PASS"
    )

    print(
        "Synthetic isolation: PASS"
    )

    print()

    print(
        "PASS: M4-06.1 Crater Landmark "
        "Data Contract is valid."
    )


if __name__ == "__main__":
    main()