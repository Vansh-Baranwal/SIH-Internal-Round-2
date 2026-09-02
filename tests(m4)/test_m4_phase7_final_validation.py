"""
M4-07.10 — Phase 7 Final Validation.

Validation-only harness for the completed Phase 7 pipeline. It reuses the public
M4-07.1–M4-07.9 APIs and checks that the whole chain executes consistently on a
single fixed scene, is deterministic, does not mutate source data, satisfies the
documented result contracts, and that cross-stage outputs are compatible.

No new scientific algorithm is introduced; this stage only validates existing
behaviour (it is the intended purpose of M4-07.10).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterCandidate,
    CraterDetector,
    CraterGeometryExtractor,
    CraterLandmark,
    DEMProfileGenerator,
    LandmarkMatch,
    RegistrationAnchor,
    generate_synthetic_scene,
    match_landmarks,
    select_registration_anchors,
)
from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.scientific.sun_simulator import (
    CounterfactualObservation,
    SunInvarianceExperimentResult,
    SunLandmarkMatchingResult,
    SunScene,
    SunSensitivityResult,
    generate_counterfactual_observation,
    generate_counterfactual_sun_states,
    match_landmarks_across_sun_conditions,
    run_sun_invariance_experiment,
    run_sun_position_sensitivity_experiment,
)
from lunar_hazard_mapper.scientific.sun_simulator.landmark_matching import _build_landmarks


def _make_scene(size=128, radius_px=18, depth_m=10.0, center=(64, 64), seed=21):
    return generate_synthetic_scene(
        crater_ids=["PV_S1"],
        size=size,
        pixel_size_m=1.0,
        radius_px_by_id={"PV_S1": radius_px},
        depth_m_by_id={"PV_S1": depth_m},
        centers_xy={"PV_S1": center},
        seed=seed,
    )


def test_sun_state_and_scene_contracts():
    """7.1 + 7.2: SunState serialization and DEM+Sun scene contract."""
    sun = SunState(azimuth_deg=90.0, elevation_deg=30.0)
    assert sun.as_tuple() == (90.0, 30.0)
    assert SunState.from_dict(sun.to_dict()) == sun

    scene = _make_scene()
    scene_obj = SunScene(dem=scene.dem, sun=sun)
    assert scene_obj.dem is scene.dem
    assert scene_obj.sun == sun


def test_counterfactual_sun_and_observation_contracts():
    """7.3 + 7.4 + 7.5: counterfactual Sun states and immutable observations."""
    base = SunState(90.0, 30.0)
    states = generate_counterfactual_sun_states(base, elevation_offsets=[15.0, 30.0])
    assert len(states) == 2
    assert all(isinstance(s, SunState) for s in states)

    scene = _make_scene()
    obs = generate_counterfactual_observation(scene.dem, base)
    assert isinstance(obs, CounterfactualObservation)
    assert obs.dem is scene.dem
    assert obs.image.shape == scene.dem.shape
    assert obs.shadow_mask.shape == scene.dem.shape
    # M4-07.5 immutability contract
    assert obs.image.flags.writeable is False
    assert obs.shadow_mask.flags.writeable is False


def test_phase7_chain_cross_stage_consistency_and_integrity():
    """7.6–7.9 run end-to-end on one scene and are mutually consistent."""
    scene = _make_scene()
    base = SunState(90.0, 30.0)
    dem_before = np.array(scene.dem.elevation, copy=True)
    gt_before = list(scene.ground_truth)

    # 7.6 invariance
    inv = run_sun_invariance_experiment(scene, base, elevation_offsets=[15.0])
    assert isinstance(inv, SunInvarianceExperimentResult)
    assert inv.status == "PASS"
    assert inv.dem_unchanged is True
    assert inv.ground_truth_unchanged is True

    # 7.7 landmark matching
    match = match_landmarks_across_sun_conditions(scene, base, elevation_offsets=[15.0])
    assert isinstance(match, SunLandmarkMatchingResult)
    assert match.metrics["match_rate"] == 1.0

    # 7.8 registration-anchor selection
    landmarks = _build_landmarks(
        scene.dem, CraterDetector(), CraterGeometryExtractor(), DEMProfileGenerator(), "BASE"
    )
    anchors = select_registration_anchors(landmarks, min_quality_score=0.80)
    assert len(anchors) >= 1
    assert all(isinstance(a, RegistrationAnchor) for a in anchors)

    # 7.9 sun-position sensitivity
    sens = run_sun_position_sensitivity_experiment(scene, base, elevation_offsets=[15.0])
    assert isinstance(sens, SunSensitivityResult)
    assert sens.metrics["match_rate"] == 1.0
    assert sens.metrics["anchor_count"] >= 1
    assert sens.metrics["detection_consistency"] == 1.0

    # Cross-stage input integrity
    assert np.array_equal(scene.dem.elevation, dem_before)
    assert scene.ground_truth == gt_before
    assert base.as_tuple() == (90.0, 30.0)
    assert sens.dem_unchanged is True
    assert sens.ground_truth_unchanged is True


def test_phase7_determinism():
    """7.6–7.9 produce identical results on repeated execution."""
    scene = _make_scene()
    base = SunState(90.0, 30.0)

    s1 = run_sun_position_sensitivity_experiment(scene, base, elevation_offsets=[15.0, 30.0])
    s2 = run_sun_position_sensitivity_experiment(scene, base, elevation_offsets=[15.0, 30.0])
    assert s1.to_dict() == s2.to_dict()

    m1 = match_landmarks_across_sun_conditions(scene, base, elevation_offsets=[15.0])
    m2 = match_landmarks_across_sun_conditions(scene, base, elevation_offsets=[15.0])
    assert m1.to_dict() == m2.to_dict()

    lms = _build_landmarks(
        scene.dem, CraterDetector(), CraterGeometryExtractor(), DEMProfileGenerator(), "BASE"
    )
    a1 = select_registration_anchors(lms)
    a2 = select_registration_anchors(lms)
    assert [a.to_dict() for a in a1] == [a.to_dict() for a in a2]


def test_phase7_sun_position_behavior():
    """7.9: Sun position changes the observation and is not ignored."""
    scene = _make_scene()
    sens = run_sun_position_sensitivity_experiment(
        scene, SunState(90.0, 30.0), elevation_offsets=[15.0, 30.0, 45.0]
    )
    assert sens.metrics["observation_is_sensitive"] is True
    assert sens.metrics["max_observation_difference"] > 0.0
    assert sens.metrics["detection_consistency"] == 1.0
    assert sens.metrics["max_center_error_m"] <= 1.5
    for c in sens.conditions:
        if not c.is_baseline:
            assert c.image_diff_from_baseline > 0.0


def test_phase7_cross_stage_contract_types():
    """Outputs of one stage are consumed by the next without new representations."""
    scene = _make_scene()
    base = SunState(90.0, 30.0)
    obs = generate_counterfactual_observation(scene.dem, base)
    assert isinstance(obs, CounterfactualObservation)

    # observation.dem is consumed directly by the detector
    candidates = CraterDetector().detect(obs.dem)
    assert len(candidates) >= 1
    assert all(isinstance(c, CraterCandidate) for c in candidates)

    landmarks = _build_landmarks(
        scene.dem, CraterDetector(), CraterGeometryExtractor(), DEMProfileGenerator(), "BASE"
    )
    assert len(landmarks) >= 1
    assert all(isinstance(lm, CraterLandmark) for lm in landmarks)

    match = match_landmarks(landmarks[0], landmarks)
    assert isinstance(match, LandmarkMatch)

    anchors = select_registration_anchors(landmarks)
    assert all(isinstance(a, RegistrationAnchor) for a in anchors)


def main():
    print("=== M4-07.10 Phase 7 Final Validation ===")
    test_sun_state_and_scene_contracts()
    test_counterfactual_sun_and_observation_contracts()
    test_phase7_chain_cross_stage_consistency_and_integrity()
    test_phase7_determinism()
    test_phase7_sun_position_behavior()
    test_phase7_cross_stage_contract_types()
    print("PASS: M4-07.10 Phase 7 Final Validation is valid and verified.")


if __name__ == "__main__":
    main()
