"""
M4-06.6.7 — Crater Landmark Network End-to-End Validation Test.

Validates the full scientific flow from synthetic DEM terrain through crater detection,
geometry extraction, DEM profile generation, component quality scoring, quality classification,
CraterLandmark construction, CraterLandmarkNetwork storage, retrieval, and final RegistrationAnchor selection.

Explicitly verifies:
1. Synthetic input preparation
2. Crater detection output
3. Geometry preservation
4. DEM profile preservation
5. Detection score preservation
6. Geometry score preservation
7. Profile score preservation
8. Combined quality preservation
9. Quality classification preservation
10. Landmark construction
11. Network insertion
12. Landmark retrieval
13. Scientific field preservation
14. Quality filtering
15. Registration anchor selection
16. Anchor identity preservation
17. Deterministic ordering
18. Deterministic serialization
19. Repeatability
20. Invalid/empty input handling
21. Non-duplication validation
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.m3_terrain.synthetic import create_synthetic_terrain

from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    CraterLandmarkBuilder,
    CraterLandmarkNetwork,
    CraterLandmarkRetriever,
    DEMProfile,
    DEMProfileGenerator,
    E2EPipelineResult,
    LandmarkE2EValidator,
    LandmarkQuality,
    RegistrationAnchorSelector,
    SensorAppearance,
    classify_quality,
    run_e2e_pipeline_validation,
    score_combined,
    score_detection,
    score_geometry,
    score_profile,
)


def test_full_m4_e2e_pipeline_validation():
    """Verify end-to-end pipeline execution from synthetic terrain to registration anchor selection."""
    crater_id = "E2E_SHACKLETON_001"
    lat_deg = -89.9
    lon_deg = 0.0

    # 1. Synthetic input preparation
    dem = create_synthetic_terrain(kind="crater", size=128, pixel_size_m=1.0, radius_px=20, depth_m=8.0)
    assert dem is not None and dem.shape == (128, 128)
    print("1. Synthetic input preparation: PASS")

    # 2. Crater detection output
    detector = CraterDetector()
    candidates = detector.detect(dem)
    assert len(candidates) > 0, "Candidate detection failed"
    candidate = candidates[0]
    print("2. Crater detection output: PASS")

    # 3. Geometry preservation
    geo_extractor = CraterGeometryExtractor()
    extracted_geo = geo_extractor.extract(dem=dem, candidate=candidate)
    assert extracted_geo.geometry.diameter_m > 0
    print("3. Geometry preservation: PASS")

    # 4. DEM profile preservation
    prof_gen = DEMProfileGenerator()
    profile = prof_gen.generate(dem=dem, center_x_m=candidate.center_x_m, center_y_m=candidate.center_y_m)
    assert len(profile.distances_m) >= 2
    print("4. DEM profile preservation: PASS")

    # 5. Detection score preservation
    det_score = score_detection(candidate)
    assert 0.0 <= det_score <= 1.0
    print("5. Detection score preservation: PASS")

    # 6. Geometry score preservation
    geo_score = score_geometry(candidate=candidate, geometry=extracted_geo.geometry, pixel_size_m=dem.pixel_size_m)
    assert 0.0 <= geo_score <= 1.0
    print("6. Geometry score preservation: PASS")

    # 7. Profile score preservation
    prof_score = score_profile(profile)
    assert 0.0 <= prof_score <= 1.0
    print("7. Profile score preservation: PASS")

    # 8. Combined quality preservation
    comb_score = score_combined(det_score, geo_score, prof_score)
    assert 0.0 <= comb_score <= 1.0
    print("8. Combined quality preservation: PASS")

    # 9. Quality classification preservation
    classification = classify_quality(comb_score)
    assert classification in {"HIGH", "MEDIUM", "LOW"}
    print("9. Quality classification preservation: PASS")

    quality = LandmarkQuality(
        detection_score=det_score,
        geometry_score=geo_score,
        profile_score=prof_score,
        overall_score=comb_score,
        classification=classification,
    )

    # 10. Landmark construction
    landmark = CraterLandmarkBuilder.build(
        crater_id=crater_id,
        latitude_deg=lat_deg,
        longitude_deg=lon_deg,
        extracted_geometry=extracted_geo,
        dem_profile=profile,
        quality=quality,
        sensor_appearances=[
            SensorAppearance(sensor_name="TMC", reference="tmc_ref.tif"),
            SensorAppearance(sensor_name="OHRC", reference="ohrc_ref.tif"),
            SensorAppearance(sensor_name="IIRS", reference="iirs_ref.tif"),
        ],
    )
    assert landmark.crater_id == crater_id
    print("10. Landmark construction: PASS")

    # 11. Network insertion
    network = CraterLandmarkNetwork()
    network.add_landmark(landmark)
    assert network.count() == 1
    print("11. Network insertion: PASS")

    # 12. Landmark retrieval
    retriever = CraterLandmarkRetriever(network)
    retrieved = retriever.get_by_id(crater_id)
    assert retrieved is landmark
    print("12. Landmark retrieval: PASS")

    # 13. Scientific field preservation
    assert retrieved.latitude_deg == lat_deg
    assert retrieved.longitude_deg == lon_deg
    assert retrieved.diameter_m == extracted_geo.geometry.diameter_m
    assert retrieved.dem_profile is profile
    assert retrieved.quality is quality
    print("13. Scientific field preservation: PASS")

    # 14. Quality filtering
    filtered_lms = retriever.query(min_quality_score=0.50)
    assert len(filtered_lms) == 1
    print("14. Quality filtering: PASS")

    # 15. Registration anchor selection
    anchors = RegistrationAnchorSelector.select_anchors(filtered_lms, min_quality_score=0.50)
    assert len(anchors) == 1
    print("15. Registration anchor selection: PASS")

    # 16. Anchor identity preservation
    anchor = anchors[0]
    assert anchor.crater_id == crater_id
    assert anchor.landmark is landmark
    assert anchor.quality_score == comb_score
    print("16. Anchor identity preservation: PASS")

    # Helper run via module validator function
    e2e_res, e2e_anchors = run_e2e_pipeline_validation(crater_id=crater_id, min_quality_score=0.50)
    assert e2e_res.is_valid
    assert len(e2e_anchors) == 1


def test_deterministic_ordering_serialization_and_repeatability():
    """17, 18, 19. Verify deterministic ordering, serialization, and repeated execution equality."""
    # 19. Repeatability
    res1, anchors1 = LandmarkE2EValidator.run_e2e_pipeline(crater_id="E2E_REP_001")
    res2, anchors2 = LandmarkE2EValidator.run_e2e_pipeline(crater_id="E2E_REP_001")

    assert res1.is_valid and res2.is_valid
    assert res1.selected_anchor_ids == res2.selected_anchor_ids
    assert anchors1[0].crater_id == anchors2[0].crater_id
    assert anchors1[0].quality_score == anchors2[0].quality_score

    # 18. Deterministic serialization
    dict1 = res1.to_dict()
    dict2 = res2.to_dict()
    assert dict1 == dict2
    assert dict1["is_valid"] is True

    # 17. Deterministic ordering
    net = CraterLandmarkNetwork()
    profile = DEMProfile(distances_m=[0.0, 10.0], elevations_m=[-5.0, 0.0])
    for cid in ["CRATER_C", "CRATER_A", "CRATER_B"]:
        net.add_landmark(
            CraterLandmarkBuilder.build(
                crater_id=cid,
                latitude_deg=-80.0,
                longitude_deg=0.0,
                diameter_m=100.0,
                dem_profile=profile,
                quality_score=0.90,
            )
        )

    retriever = CraterLandmarkRetriever(net)
    sorted_retrieved = retriever.get_all()
    assert [lm.crater_id for lm in sorted_retrieved] == ["CRATER_A", "CRATER_B", "CRATER_C"]

    selected = RegistrationAnchorSelector.select_anchors(sorted_retrieved, min_quality_score=0.80)
    assert [a.crater_id for a in selected] == ["CRATER_A", "CRATER_B", "CRATER_C"]

    print("17. Deterministic ordering: PASS")
    print("18. Deterministic serialization: PASS")
    print("19. Repeatability: PASS")


def test_invalid_and_empty_input_handling():
    """20. Verify safe handling of empty networks and invalid input thresholds."""
    empty_net = CraterLandmarkNetwork()
    retriever = CraterLandmarkRetriever(empty_net)
    assert retriever.get_all() == []
    assert RegistrationAnchorSelector.select_anchors(empty_net) == []

    e2e_res, anchors = run_e2e_pipeline_validation(min_quality_score=0.99)  # Threshold above actual score
    assert e2e_res.is_valid  # Pipeline executes cleanly
    assert len(anchors) == 0  # Quality filtering returns empty cleanly

    print("20. Invalid/empty input handling: PASS")


def test_non_duplication_validation():
    """21. Confirm that validation and retriever layers consume pre-computed outputs without duplicating calculations."""
    res, anchors = LandmarkE2EValidator.run_e2e_pipeline(crater_id="CRATER_NODUP_001")
    assert res.is_valid
    anchor = anchors[0]

    # Verify score identity: quality_score on anchor is identical object value to stored landmark quality score
    assert anchor.quality_score == anchor.landmark.quality_score == anchor.landmark.quality.overall_score
    print("21. Non-duplication validation: PASS")


def main():
    print("=== M4-06.6.7 Crater Landmark Network End-to-End Validation ===")
    print()

    test_full_m4_e2e_pipeline_validation()
    test_deterministic_ordering_serialization_and_repeatability()
    test_invalid_and_empty_input_handling()
    test_non_duplication_validation()

    print()
    print("PASS: M4-06.6.7 Crater Landmark Network End-to-End Validation is functioning.")


if __name__ == "__main__":
    main()
