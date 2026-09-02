"""
M4-06.6.6 — Crater Landmark Network Validation Test.

Validates end-to-end composition and integrity of the M4 Crater Landmark Network pipeline:
Landmark -> Network -> Retrieval -> Quality Filtering -> Anchor Selection -> Validated Anchor Set

Explicitly verifies:
1. Insertion of valid landmarks into network
2. Landmark retrieval from network
3. Quality filtering subset correctness
4. Integration with RegistrationAnchorSelector
5. Preservation of crater_id across all pipeline stages
6. Preservation of scientific fields (latitude, longitude, diameter, DEM profile)
7. Deterministic ordering across the full pipeline
8. Consistent validation of quality threshold parameters
9. Safe empty-network pipeline execution
10. Safe handling of insufficient candidates relative to max_anchors
11. Rejection of invalid non-landmark objects
12. Deterministic and compatible serialization (to_dict)
13. Re-running identical pipelines yields identical output
14. Scientific calculations are non-duplicated (validates composition only)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterLandmark,
    CraterLandmarkBuilder,
    CraterLandmarkNetwork,
    CraterLandmarkRetriever,
    DEMProfile,
    LandmarkNetworkValidator,
    LandmarkQuality,
    PipelineValidationResult,
    RegistrationAnchorSelector,
    SensorAppearance,
    validate_network_pipeline,
)


def _make_landmark(
    crater_id: str,
    score: float,
    classification: str = "HIGH",
    lat: float = -80.0,
    lon: float = 15.0,
    diameter_m: float = 250.0,
) -> CraterLandmark:
    profile = DEMProfile(distances_m=[0.0, 20.0, 40.0], elevations_m=[-15.0, -8.0, 0.0])
    quality = LandmarkQuality(
        detection_score=score,
        geometry_score=score,
        profile_score=score,
        overall_score=score,
        classification=classification,  # type: ignore
    )
    return CraterLandmarkBuilder.build(
        crater_id=crater_id,
        latitude_deg=lat,
        longitude_deg=lon,
        diameter_m=diameter_m,
        dem_profile=profile,
        quality=quality,
        sensor_appearances=[
            SensorAppearance(sensor_name="TMC", reference=f"tmc_{crater_id}.tif"),
        ],
    )


def test_full_pipeline_composition_and_field_preservation():
    """1 to 7. Verify insertion, retrieval, filtering, anchor selection, field preservation, and ordering."""
    network = CraterLandmarkNetwork()
    lm1 = _make_landmark("CRATER_85S_001", 0.95, "HIGH", lat=-85.0, lon=10.0, diameter_m=1200.0)
    lm2 = _make_landmark("CRATER_85S_002", 0.88, "HIGH", lat=-85.2, lon=12.0, diameter_m=800.0)
    lm3 = _make_landmark("CRATER_85S_003", 0.65, "MEDIUM", lat=-85.4, lon=14.0, diameter_m=500.0)

    # 1. Insertion
    network.add_landmark(lm1)
    network.add_landmark(lm2)
    network.add_landmark(lm3)
    assert network.count() == 3

    # 2. Retrieval
    retriever = CraterLandmarkRetriever(network)
    retrieved = retriever.get_by_id("CRATER_85S_001")
    assert retrieved is lm1

    # 3. Quality Filtering
    high_lms = retriever.query(min_quality_score=0.80)
    assert len(high_lms) == 2
    assert [lm.crater_id for lm in high_lms] == ["CRATER_85S_001", "CRATER_85S_002"]

    # 4 & 5. Anchor selection & ID preservation
    anchors = RegistrationAnchorSelector.select_anchors(high_lms, min_quality_score=0.80)
    assert len(anchors) == 2
    assert anchors[0].crater_id == "CRATER_85S_001"
    assert anchors[1].crater_id == "CRATER_85S_002"

    # 6. Scientific field preservation
    assert anchors[0].landmark.latitude_deg == -85.0
    assert anchors[0].landmark.diameter_m == 1200.0
    assert anchors[0].landmark.dem_profile is lm1.dem_profile

    # 7. Pipeline validator test
    val_res = validate_network_pipeline(network, min_quality_score=0.80)
    assert isinstance(val_res, PipelineValidationResult)
    assert val_res.is_valid, f"Validation failed with errors: {val_res.errors}"
    assert val_res.total_network_landmarks == 3
    assert val_res.retrieved_landmarks_count == 2
    assert val_res.selected_anchors_count == 2

    print("1. Network insertion: PASS")
    print("2. Landmark retrieval: PASS")
    print("3. Quality filtering: PASS")
    print("4. Registration anchor selection integration: PASS")
    print("5. Crater ID preservation: PASS")
    print("6. Scientific field preservation: PASS")
    print("7. Deterministic ordering: PASS")


def test_quality_threshold_validation_and_rejection():
    """8 & 11. Verify consistent parameter validation and invalid object rejection."""
    network = CraterLandmarkNetwork()
    network.add_landmark(_make_landmark("CRATER_VAL_001", 0.90))

    # 8. Invalid quality threshold rejection
    for bad_threshold in [-0.1, 1.1, 5.0]:
        try:
            validate_network_pipeline(network, min_quality_score=bad_threshold)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Failed to reject invalid min_quality_score: {bad_threshold}")

    # 11. Invalid object rejection
    try:
        network.add_landmark("invalid_landmark_string")  # type: ignore
    except TypeError:
        pass
    else:
        raise AssertionError("Failed to reject non-CraterLandmark insertion.")

    print("8. Quality threshold validation: PASS")
    print("11. Invalid landmark object rejection: PASS")


def test_empty_and_insufficient_candidate_pipeline():
    """9 & 10. Verify pipeline safety on empty network and insufficient candidates."""
    # 9. Empty network behavior
    empty_net = CraterLandmarkNetwork()
    res_empty = validate_network_pipeline(empty_net)
    assert res_empty.is_valid
    assert res_empty.total_network_landmarks == 0
    assert res_empty.selected_anchors_count == 0

    # 10. Insufficient candidates relative to max_anchors
    net = CraterLandmarkNetwork()
    net.add_landmark(_make_landmark("CRATER_SINGLE", 0.92))
    res_insuff = validate_network_pipeline(net, max_anchors=10)
    assert res_insuff.is_valid
    assert res_insuff.selected_anchors_count == 1

    print("9. Empty-network behavior: PASS")
    print("10. Insufficient-candidate behavior: PASS")


def test_serialization_and_pipeline_reproducibility():
    """12, 13 & 14. Verify deterministic serialization and exact pipeline reproducibility without score recalculation."""
    net = CraterLandmarkNetwork()
    net.add_landmark(_make_landmark("CRATER_REP_A", 0.95))
    net.add_landmark(_make_landmark("CRATER_REP_B", 0.85))

    # 13. Re-running identical pipelines yields identical results
    val_res_1 = validate_network_pipeline(net, min_quality_score=0.80)
    val_res_2 = validate_network_pipeline(net, min_quality_score=0.80)

    assert val_res_1.is_valid == val_res_2.is_valid
    assert val_res_1.anchor_ids == val_res_2.anchor_ids
    assert val_res_1.checks_passed == val_res_2.checks_passed

    # 12. Serialization compatibility
    dict_1 = val_res_1.to_dict()
    dict_2 = val_res_2.to_dict()
    assert dict_1 == dict_2
    assert dict_1["is_valid"] is True
    assert dict_1["selected_anchors_count"] == 2

    # 14. Confirm scientific score preservation (no recalculation)
    anchor_a = RegistrationAnchorSelector.select_anchors(net, min_quality_score=0.80)[0]
    lm_a = net.get_landmark("CRATER_REP_A")
    assert lm_a is not None
    assert anchor_a.quality_score == lm_a.quality_score == 0.95

    print("12. Serialization determinism: PASS")
    print("13. Pipeline reproducibility: PASS")
    print("14. Non-duplication of scientific calculations: PASS")


def main():
    print("=== M4-06.6.6 Crater Landmark Network Validation Test ===")
    print()

    test_full_pipeline_composition_and_field_preservation()
    test_quality_threshold_validation_and_rejection()
    test_empty_and_insufficient_candidate_pipeline()
    test_serialization_and_pipeline_reproducibility()

    print()
    print("PASS: M4-06.6.6 Crater Landmark Network Validation is successful.")


if __name__ == "__main__":
    main()
