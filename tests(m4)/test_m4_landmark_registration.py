"""
M4-07.8 — Landmark Registration (registration-anchor layer).

Verifies the existing RegistrationAnchor / RegistrationAnchorSelector /
select_registration_anchors(...) contract used to prepare stable, high-quality
crater landmarks as registration anchors. It is intentionally a verification
+ orchestration-level test over the existing anchors API:

- no geometric/map/image registration, transform estimation, or warping
- no reimplementation of detection/geometry/quality/matching logic
- no new registration API is invented
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
    LandmarkQuality,
    RegistrationAnchor,
    RegistrationAnchorSelector,
    match_landmarks,
    select_registration_anchors,
)


def _make_landmark(crater_id: str, quality_score: float, classification: str = "HIGH") -> CraterLandmark:
    profile = DEMProfile(distances_m=[0.0, 10.0], elevations_m=[-5.0, 0.0])
    quality = LandmarkQuality(
        detection_score=quality_score,
        geometry_score=quality_score,
        profile_score=quality_score,
        overall_score=quality_score,
        classification=classification,  # type: ignore
    )
    return CraterLandmarkBuilder.build(
        crater_id=crater_id,
        latitude_deg=-82.0,
        longitude_deg=15.0,
        diameter_m=200.0,
        dem_profile=profile,
        quality=quality,
    )


def test_valid_anchor_selection():
    """1. Valid high-quality landmark is selected as a registration anchor."""
    lm = _make_landmark("REG_A1", 0.92, "HIGH")
    anchors = select_registration_anchors([lm], min_quality_score=0.80)
    assert len(anchors) == 1
    assert isinstance(anchors[0], RegistrationAnchor)
    assert anchors[0].crater_id == "REG_A1"
    assert anchors[0].quality_score == 0.92
    assert anchors[0].classification == "HIGH"
    assert anchors[0].rank == 1


def test_minimum_quality_filtering():
    """2. Landmarks below the minimum quality threshold are excluded."""
    lms = [
        _make_landmark("REG_HIGH", 0.95, "HIGH"),
        _make_landmark("REG_MED", 0.70, "MEDIUM"),
        _make_landmark("REG_LOW", 0.40, "LOW"),
    ]
    anchors = select_registration_anchors(lms, min_quality_score=0.80)
    assert [a.crater_id for a in anchors] == ["REG_HIGH"]


def test_classification_filtering():
    """3. Classification filter restricts selection to the requested class."""
    lms = [
        _make_landmark("REG_HIGH1", 0.90, "HIGH"),
        _make_landmark("REG_HIGH2", 0.82, "HIGH"),
        _make_landmark("REG_MED1", 0.85, "MEDIUM"),
    ]
    anchors = select_registration_anchors(lms, classification="HIGH")
    assert [a.crater_id for a in anchors] == ["REG_HIGH1", "REG_HIGH2"]


def test_deterministic_ordering_and_tie_break():
    """4. Deterministic ordering: score desc, then crater_id asc for ties."""
    lms = [
        _make_landmark("REG_Z", 0.90, "HIGH"),
        _make_landmark("REG_A", 0.90, "HIGH"),
        _make_landmark("REG_M", 0.85, "HIGH"),
    ]
    anchors = select_registration_anchors(lms, min_quality_score=0.80)
    assert [a.crater_id for a in anchors] == ["REG_A", "REG_Z", "REG_M"]


def test_deterministic_repeated_execution():
    """5. Repeated execution yields identical selection and ordering."""
    lms = [
        _make_landmark("REG_R1", 0.93, "HIGH"),
        _make_landmark("REG_R2", 0.88, "HIGH"),
        _make_landmark("REG_R3", 0.81, "HIGH"),
    ]
    a1 = select_registration_anchors(lms, min_quality_score=0.80)
    a2 = select_registration_anchors(lms, min_quality_score=0.80)
    assert [x.to_dict() for x in a1] == [x.to_dict() for x in a2]


def test_max_anchor_limiting_when_many_qualify():
    """6. When more landmarks qualify than max_anchors, only the top are kept."""
    lms = [
        _make_landmark("REG_M1", 0.90, "HIGH"),
        _make_landmark("REG_M2", 0.88, "HIGH"),
        _make_landmark("REG_M3", 0.86, "HIGH"),
        _make_landmark("REG_M4", 0.84, "HIGH"),
        _make_landmark("REG_M5", 0.82, "HIGH"),
    ]
    anchors = select_registration_anchors(lms, min_quality_score=0.80, max_anchors=2)
    assert len(anchors) == 2
    assert [a.rank for a in anchors] == [1, 2]
    assert [a.crater_id for a in anchors] == ["REG_M1", "REG_M2"]


def test_correct_crater_ids_and_rank_info():
    """7 & 8. Correct crater IDs, quality scores, and 1-indexed rankings."""
    lms = [
        _make_landmark("REG_Q1", 0.91, "HIGH"),
        _make_landmark("REG_Q2", 0.87, "HIGH"),
        _make_landmark("REG_Q3", 0.83, "HIGH"),
    ]
    anchors = select_registration_anchors(lms, min_quality_score=0.80)
    ids = [a.crater_id for a in anchors]
    assert ids == ["REG_Q1", "REG_Q2", "REG_Q3"]
    assert [a.rank for a in anchors] == [1, 2, 3]
    assert [a.quality_score for a in anchors] == [0.91, 0.87, 0.83]


def test_selection_reason_and_metadata():
    """9. Selection reason and metadata are populated by the contract."""
    lm = _make_landmark("REG_REASON", 0.94, "HIGH")
    anchor = RegistrationAnchorSelector.select_anchors([lm], min_quality_score=0.80)[0]
    assert "rank #1" in anchor.selection_reason
    assert f"{0.94:.3f}" in anchor.selection_reason
    assert isinstance(anchor.metadata, dict)


def test_empty_and_no_qualified_behavior():
    """10. Empty or entirely-below-threshold candidate sets return no anchors."""
    assert select_registration_anchors([]) == []

    below_threshold = [
        _make_landmark("REG_LOW1", 0.55, "MEDIUM"),
        _make_landmark("REG_LOW2", 0.30, "LOW"),
    ]
    assert select_registration_anchors(below_threshold, min_quality_score=0.80) == []


def test_input_landmark_immutability():
    """11. Selection does not mutate input landmark objects."""
    lm = _make_landmark("REG_IMM", 0.90, "HIGH")
    before = lm.to_dict()
    select_registration_anchors([lm], min_quality_score=0.80)
    assert lm.to_dict() == before
    assert lm.crater_id == "REG_IMM"
    assert lm.quality_score == 0.90


def test_landmark_reference_preservation():
    """12. Anchors preserve the original landmark object reference."""
    lm = _make_landmark("REG_REF", 0.91, "HIGH")
    anchors = select_registration_anchors([lm], min_quality_score=0.80)
    assert anchors[0].landmark is lm
    assert anchors[0].landmark.crater_id == lm.crater_id


def test_network_and_retriever_compatibility():
    """Anchors can be selected from a network and its retriever."""
    lms = [
        _make_landmark("REG_N1", 0.90, "HIGH"),
        _make_landmark("REG_N2", 0.60, "MEDIUM"),
    ]
    network = CraterLandmarkNetwork()
    for lm in lms:
        network.add_landmark(lm)

    from_network = select_registration_anchors(network, min_quality_score=0.80)
    assert [a.crater_id for a in from_network] == ["REG_N1"]

    retriever = CraterLandmarkRetriever(network)
    from_retriever = select_registration_anchors(retriever, min_quality_score=0.80)
    assert [a.crater_id for a in from_retriever] == ["REG_N1"]


def test_integration_with_matching_layer():
    """13. A landmark validated by the matching layer becomes a registration anchor."""
    stable = _make_landmark("REG_MATCHED", 0.93, "HIGH")
    unstable = _make_landmark("REG_OTHER", 0.40, "LOW")

    # M4-07.7 matching identifies the stable crater as its own best match.
    match = match_landmarks(stable, [stable, unstable])
    assert match.matched is True
    assert match.candidate_id == "REG_MATCHED"

    # M4-07.8 promotes the matched/stable landmark to a registration anchor.
    anchors = select_registration_anchors([stable, unstable], min_quality_score=0.80)
    assert [a.crater_id for a in anchors] == ["REG_MATCHED"]
    assert anchors[0].landmark is stable


def main():
    print("=== M4-07.8 Landmark Registration (Anchor Layer) ===")
    test_valid_anchor_selection()
    test_minimum_quality_filtering()
    test_classification_filtering()
    test_deterministic_ordering_and_tie_break()
    test_deterministic_repeated_execution()
    test_max_anchor_limiting_when_many_qualify()
    test_correct_crater_ids_and_rank_info()
    test_selection_reason_and_metadata()
    test_empty_and_no_qualified_behavior()
    test_input_landmark_immutability()
    test_landmark_reference_preservation()
    test_network_and_retriever_compatibility()
    test_integration_with_matching_layer()
    print("PASS: M4-07.8 Landmark Registration is valid and verified.")


if __name__ == "__main__":
    main()
