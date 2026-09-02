"""
M4-06.10 — Localization Accuracy Testing.

Validates the existing detector/geometry pipeline against retained synthetic
ground truth while the evaluated input is stripped of location metadata.
"""

import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    LocalizationAccuracyResult,
    generate_synthetic_scene,
    strip_location_metadata,
)


def _evaluate_localization_case(name, scene, tolerance_m=1.5):
    assert scene.ground_truth, f"{name}: ground truth is missing."
    retained_ground_truth = scene.ground_truth[0]
    stripped_scene = strip_location_metadata(scene)

    assert stripped_scene.ground_truth == [], f"{name}: stripped evaluation input must not retain ground truth."
    assert scene.ground_truth[0].crater_id == retained_ground_truth.crater_id
    assert retained_ground_truth.latitude_deg is None
    assert retained_ground_truth.longitude_deg is None

    candidates = CraterDetector().detect(stripped_scene.dem)
    assert candidates, f"{name}: no crater candidates detected after metadata stripping."
    candidate = candidates[0]
    geometry = CraterGeometryExtractor().extract(stripped_scene.dem, candidate)

    result = LocalizationAccuracyResult.from_estimate(
        crater_id=retained_ground_truth.crater_id,
        ground_truth_center_x_m=retained_ground_truth.center_xy_m[0],
        ground_truth_center_y_m=retained_ground_truth.center_xy_m[1],
        estimated_center_x_m=candidate.center_x_m,
        estimated_center_y_m=candidate.center_y_m,
        max_error_m=tolerance_m,
        pixel_size_m=scene.dem.pixel_size_m,
        geometry=geometry.geometry,
    )

    summary = {
        "scenario": name,
        "crater_id": retained_ground_truth.crater_id,
        "ground_truth_center": (retained_ground_truth.center_xy_m[0], retained_ground_truth.center_xy_m[1]),
        "estimated_center": (candidate.center_x_m, candidate.center_y_m),
        "pixel_error": result.center_error_px,
        "metric_error": result.center_error_m,
        "tolerance": tolerance_m,
        "passed": result.passed,
    }
    print(
        f"SCENARIO={name} | crater_id={retained_ground_truth.crater_id} | "
        f"gt_center={summary['ground_truth_center']} | "
        f"est_center={summary['estimated_center']} | "
        f"pixel_error={summary['pixel_error']:.6f} | metric_error={summary['metric_error']:.6f} | "
        f"tolerance={tolerance_m:.3f} | PASS={result.passed}"
    )
    assert result.passed, f"{name}: localization error exceeded tolerance."
    assert geometry.geometry.diameter_m > 0
    return summary


def test_single_crater_localization_accuracy_and_metadata_stripping():
    scene = generate_synthetic_scene(
        crater_ids=["LOC_S1"],
        size=128,
        pixel_size_m=1.0,
        radius_px_by_id={"LOC_S1": 18},
        depth_m_by_id={"LOC_S1": 10.0},
        centers_xy={"LOC_S1": (64, 64)},
        seed=21,
    )
    _evaluate_localization_case("single_crater", scene, tolerance_m=1.5)


def test_multi_crater_localization_accuracy_with_position_and_size_variation():
    scene = generate_synthetic_scene(
        crater_ids=["LOC_M1", "LOC_M2", "LOC_M3"],
        size=160,
        pixel_size_m=1.0,
        radius_px_by_id={"LOC_M1": 12, "LOC_M2": 16, "LOC_M3": 23},
        depth_m_by_id={"LOC_M1": 6.5, "LOC_M2": 8.0, "LOC_M3": 9.5},
        centers_xy={"LOC_M1": (30, 35), "LOC_M2": (96, 70), "LOC_M3": (120, 120)},
        seed=17,
    )

    for crater in scene.ground_truth:
        single_scene = generate_synthetic_scene(
            crater_ids=[crater.crater_id],
            size=160,
            pixel_size_m=1.0,
            radius_px_by_id={crater.crater_id: crater.radius_px},
            depth_m_by_id={crater.crater_id: crater.depth_m},
            centers_xy={crater.crater_id: crater.center_xy},
            seed=17,
        )
        _evaluate_localization_case(f"multi_crater_{crater.crater_id}", single_scene, tolerance_m=1.5)


def test_repeated_execution_is_deterministic_and_ground_truth_immutable():
    params = {
        "crater_ids": ["LOC_R1"],
        "size": 128,
        "pixel_size_m": 1.0,
        "radius_px_by_id": {"LOC_R1": 20},
        "depth_m_by_id": {"LOC_R1": 11.0},
        "centers_xy": {"LOC_R1": (48, 52)},
        "seed": 33,
    }
    scene1 = generate_synthetic_scene(**params)
    scene2 = generate_synthetic_scene(**params)

    assert (scene1.dem.elevation == scene2.dem.elevation).all()
    assert scene1.ground_truth == scene2.ground_truth
    assert scene1.ground_truth[0].center_xy_m == (52.0, 48.0)
    assert scene1.ground_truth[0].center_xy_m == scene2.ground_truth[0].center_xy_m

    summary1 = _evaluate_localization_case("repeatability_first", scene1, tolerance_m=1.5)
    summary2 = _evaluate_localization_case("repeatability_second", scene2, tolerance_m=1.5)
    assert summary1["pixel_error"] == summary2["pixel_error"]
    assert summary1["metric_error"] == summary2["metric_error"]


def test_invalid_input_handling_and_metadata_isolation():
    try:
        strip_location_metadata("not-a-scene")
    except TypeError:
        pass
    else:
        raise AssertionError("strip_location_metadata should reject non-scene input.")

    try:
        generate_synthetic_scene(crater_ids=[], seed=5)
    except ValueError:
        pass
    else:
        raise AssertionError("generate_synthetic_scene should reject empty crater_ids.")

    scene = generate_synthetic_scene(
        crater_ids=["LOC_I1"],
        size=96,
        pixel_size_m=1.0,
        radius_px_by_id={"LOC_I1": 10},
        depth_m_by_id={"LOC_I1": 5.0},
        centers_xy={"LOC_I1": (48, 48)},
        seed=7,
    )
    retained = scene.ground_truth[0]
    stripped = strip_location_metadata(scene)
    assert retained.crater_id == "LOC_I1"
    assert stripped.ground_truth == []
    assert retained.latitude_deg is None and retained.longitude_deg is None
    assert not hasattr(stripped.dem, "latitude_deg") and not hasattr(stripped.dem, "longitude_deg")


def main():
    print("=== M4-06.10 Localization Accuracy ===")
    test_single_crater_localization_accuracy_and_metadata_stripping()
    test_multi_crater_localization_accuracy_with_position_and_size_variation()
    test_repeated_execution_is_deterministic_and_ground_truth_immutable()
    test_invalid_input_handling_and_metadata_isolation()
    print("PASS: M4-06.10 localization validation coverage is complete and verified.")


if __name__ == "__main__":
    main()
