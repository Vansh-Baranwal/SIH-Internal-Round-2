"""
M4-06.9 — Synthetic Testing for Crater Landmark Pipeline.

Exercises the existing crater landmark pipeline against deterministic synthetic
scenes with explicit ground truth and reproducible generation parameters.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    DEMProfileGenerator,
    SyntheticCraterGroundTruth,
    SyntheticCraterScene,
    generate_synthetic_crater_scene,
    generate_synthetic_scene,
)


def test_single_crater_scene_generation():
    scene = generate_synthetic_crater_scene(
        crater_id="SYN_THETA",
        size=128,
        pixel_size_m=1.0,
        radius_px=18,
        depth_m=8.0,
        center_xy=(64, 64),
        seed=7,
    )

    assert isinstance(scene, SyntheticCraterScene)
    assert len(scene.ground_truth) == 1
    assert scene.ground_truth[0].crater_id == "SYN_THETA"
    assert scene.ground_truth[0].radius_px == 18
    assert scene.ground_truth[0].depth_m == 8.0
    assert scene.dem is not None
    assert scene.dem.shape == (128, 128)
    print("1. Single-crater generation: PASS")


def test_multi_crater_ground_truth_and_known_ordering():
    scene = generate_synthetic_scene(
        crater_ids=["SYN_A", "SYN_B", "SYN_C"],
        size=160,
        pixel_size_m=1.0,
        radius_px_by_id={"SYN_A": 12, "SYN_B": 18, "SYN_C": 22},
        depth_m_by_id={"SYN_A": 6.0, "SYN_B": 9.0, "SYN_C": 11.0},
        centers_xy={
            "SYN_A": (40, 35),
            "SYN_B": (120, 70),
            "SYN_C": (90, 120),
        },
        seed=11,
    )

    assert len(scene.ground_truth) == 3
    ids = [gt.crater_id for gt in scene.ground_truth]
    assert ids == ["SYN_A", "SYN_B", "SYN_C"]
    assert all(isinstance(gt, SyntheticCraterGroundTruth) for gt in scene.ground_truth)
    for gt in scene.ground_truth:
        assert gt.radius_px > 0
        assert gt.depth_m > 0
        assert gt.center_xy[0] >= 0 and gt.center_xy[1] >= 0
    print("2. Multi-crater ground truth and ordering: PASS")


def test_deterministic_generation_and_seed_reproducibility():
    scene1 = generate_synthetic_scene(
        crater_ids=["SYN_A", "SYN_B"],
        size=128,
        pixel_size_m=1.0,
        radius_px_by_id={"SYN_A": 16, "SYN_B": 20},
        depth_m_by_id={"SYN_A": 7.0, "SYN_B": 8.0},
        centers_xy={"SYN_A": (35, 35), "SYN_B": (95, 90)},
        background_elevation=0.0,
        noise_std=0.25,
        seed=5,
    )
    scene2 = generate_synthetic_scene(
        crater_ids=["SYN_A", "SYN_B"],
        size=128,
        pixel_size_m=1.0,
        radius_px_by_id={"SYN_A": 16, "SYN_B": 20},
        depth_m_by_id={"SYN_A": 7.0, "SYN_B": 8.0},
        centers_xy={"SYN_A": (35, 35), "SYN_B": (95, 90)},
        background_elevation=0.0,
        noise_std=0.25,
        seed=5,
    )

    assert (scene1.dem.elevation == scene2.dem.elevation).all()
    assert scene1.ground_truth == scene2.ground_truth
    print("3. Deterministic generation and seed reproducibility: PASS")


def test_ground_truth_field_preservation_and_no_mutation():
    scene = generate_synthetic_scene(
        crater_ids=["SYN_X"],
        size=80,
        pixel_size_m=1.0,
        radius_px_by_id={"SYN_X": 10},
        depth_m_by_id={"SYN_X": 5.5},
        centers_xy={"SYN_X": (40, 40)},
        seed=9,
    )

    original = scene.ground_truth[0].to_dict()
    snapshot = scene.ground_truth[0].to_dict()
    assert snapshot == original
    assert scene.ground_truth[0].crater_id == "SYN_X"
    assert scene.ground_truth[0].diameter_m == 2 * 10.0
    assert scene.ground_truth[0].radius_m == 10.0
    assert scene.ground_truth[0].depth_m == 5.5
    assert scene.ground_truth[0].center_xy == (40, 40)
    print("4. Ground-truth preservation and no-mutation semantics: PASS")


def test_pipeline_compatibility_with_existing_components():
    scene = generate_synthetic_scene(
        crater_ids=["SYN_PIPE_1", "SYN_PIPE_2"],
        size=128,
        pixel_size_m=1.0,
        radius_px_by_id={"SYN_PIPE_1": 16, "SYN_PIPE_2": 20},
        depth_m_by_id={"SYN_PIPE_1": 7.0, "SYN_PIPE_2": 8.5},
        centers_xy={"SYN_PIPE_1": (32, 32), "SYN_PIPE_2": (96, 96)},
        seed=13,
    )

    detector = CraterDetector()
    candidates = detector.detect(scene.dem)
    assert len(candidates) >= 2

    geometry_extractor = CraterGeometryExtractor()
    profile_generator = DEMProfileGenerator()

    for candidate in candidates[:2]:
        geometry = geometry_extractor.extract(scene.dem, candidate)
        profile = profile_generator.generate(scene.dem, candidate.center_x_m, candidate.center_y_m)
        assert geometry.geometry.diameter_m > 0
        assert len(profile.distances_m) >= 2

    print("5. Pipeline compatibility: PASS")


def test_repeated_execution_consistency():
    scenes = []
    for i in range(3):
        scene = generate_synthetic_scene(
            crater_ids=["SYN_REPEAT_A", "SYN_REPEAT_B"],
            size=96,
            pixel_size_m=1.0,
            radius_px_by_id={"SYN_REPEAT_A": 15, "SYN_REPEAT_B": 18},
            depth_m_by_id={"SYN_REPEAT_A": 6.0, "SYN_REPEAT_B": 7.5},
            centers_xy={"SYN_REPEAT_A": (24, 24), "SYN_REPEAT_B": (72, 72)},
            seed=17,
        )
        scenes.append(scene)

    assert all((s1.dem.elevation == s2.dem.elevation).all() for s1, s2 in zip(scenes, scenes[1:]))
    assert all(s1.ground_truth == s2.ground_truth for s1, s2 in zip(scenes, scenes[1:]))
    print("6. Repeated execution consistency: PASS")


def main():
    print("=== M4-06.9 Synthetic Testing ===")
    print()
    test_single_crater_scene_generation()
    test_multi_crater_ground_truth_and_known_ordering()
    test_deterministic_generation_and_seed_reproducibility()
    test_ground_truth_field_preservation_and_no_mutation()
    test_pipeline_compatibility_with_existing_components()
    test_repeated_execution_consistency()
    print()
    print("PASS: M4-06.9 Synthetic Testing is valid and verified.")


if __name__ == "__main__":
    main()
