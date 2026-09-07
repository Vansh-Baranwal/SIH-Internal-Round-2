"""Focused tests for M4 Phase 10.3 metadata-only pair selection.

All observations are test fixtures. They are explicitly marked as test data
and do not represent real lunar observations or scientific change.
"""

from pathlib import Path

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    ImageReferenceStatus,
    LunarObservation,
    ObservationContractError,
    PairEligibility,
    TemporalMetadataStatus,
    evaluate_pair,
    select_candidate_pairs,
)


def observation(identifier: str, timestamp: str | None = "2024-01-01T00:00:00Z", **overrides) -> LunarObservation:
    values = {
        "observation_id": identifier,
        "source": "TMC test fixture",
        "image_reference": f"https://example.test/{identifier}.tif",
        "acquisition_timestamp": timestamp,
        "provenance_source": "tests/test_m4_10_3_image_pair_selection.py",
        "provenance": DataProvenance.REAL,
        "is_real_data": True,
    }
    values.update(overrides)
    return LunarObservation(**values)


def overlapping_pair(**overrides):
    first_values = {
        "crs": "EPSG:4326",
        "footprint": {"bounds": {"west": 0, "south": 0, "east": 2, "north": 2}},
    }
    first_values.update(overrides.pop("first", {}))
    first = observation("a", "2024-01-01T00:00:00Z", **first_values)
    second_values = {
        "source": "OHRC test fixture",
        "crs": "EPSG:4326",
        "footprint": {"bounds": {"west": 1, "south": 1, "east": 3, "north": 3}},
    }
    second_values.update(overrides.pop("second", {}))
    second = observation("b", "2024-01-02T00:00:00Z", **second_values)
    return first, second


def test_valid_genuine_same_sensor_pair_is_eligible() -> None:
    result = evaluate_pair(observation("a"), observation("b", "2024-02-01T00:00:00Z"))
    assert result.eligibility is PairEligibility.ELIGIBLE
    assert result.hard_rejection_reasons == ()
    assert result.sensor_compatibility == "supported"
    assert result.candidate_selection_score is not None


def test_valid_genuine_cross_sensor_pair_is_eligible() -> None:
    first, second = overlapping_pair()
    result = evaluate_pair(first, second)
    assert result.eligible
    assert result.sensor_compatibility == "supported"
    assert result.footprint_compatibility == "compatible"


def test_synthetic_observation_is_rejected() -> None:
    result = evaluate_pair(
        observation("synthetic", provenance=DataProvenance.SYNTHETIC, is_real_data=False),
        observation("real", "2024-02-01T00:00:00Z"),
    )
    assert "non_real_provenance" in result.hard_rejection_reasons


def test_missing_provenance_is_rejected() -> None:
    result = evaluate_pair(
        observation("unknown", provenance=DataProvenance.UNAVAILABLE, is_real_data=False),
        observation("real", "2024-02-01T00:00:00Z"),
    )
    assert "non_real_provenance" in result.hard_rejection_reasons


def test_same_observation_is_rejected() -> None:
    first = observation("same")
    second = observation("same", "2024-02-01T00:00:00Z", image_reference="https://example.test/other.tif")
    result = evaluate_pair(first, second)
    assert "same_observation" in result.hard_rejection_reasons


def test_same_acquisition_instant_is_rejected() -> None:
    result = evaluate_pair(observation("a"), observation("b"))
    assert "same_acquisition_instant" in result.hard_rejection_reasons


def test_missing_temporal_metadata_is_rejected_without_fabrication() -> None:
    result = evaluate_pair(observation("a", None), observation("b", "2024-02-01T00:00:00Z"))
    assert "missing_temporal_metadata" in result.hard_rejection_reasons
    assert result.temporal_metadata is None


def test_date_only_metadata_is_ordered_without_exact_separation() -> None:
    result = evaluate_pair(observation("a", "2024-01-01"), observation("b", "2024-01-02"))
    assert result.eligible
    assert result.temporal_metadata.chronological_order == "a_before_b"
    assert result.temporal_metadata.temporal_separation_seconds is None
    assert "limited_temporal_precision" in result.warnings


def test_same_date_only_metadata_is_not_treated_as_distinct() -> None:
    result = evaluate_pair(observation("a", "2024-01-01"), observation("b", "2024-01-01"))
    assert "same_acquisition_date" in result.hard_rejection_reasons


def test_timezone_naive_metadata_does_not_claim_utc_separation() -> None:
    result = evaluate_pair(observation("a", "2024-01-01T00:00:00"), observation("b", "2024-01-02T00:00:00"))
    assert result.eligible
    assert result.temporal_metadata.temporal_separation_seconds is None
    assert "timezone_naive_temporal_metadata" in result.warnings


def test_same_crs_is_compatible() -> None:
    first, second = overlapping_pair()
    assert evaluate_pair(first, second).crs_compatibility == "compatible"


def test_missing_crs_is_unknown_warning() -> None:
    result = evaluate_pair(observation("a"), observation("b", "2024-02-01T00:00:00Z"))
    assert result.crs_compatibility == "unknown"
    assert "missing_crs" in result.warnings


def test_different_crs_remains_candidate_with_warning() -> None:
    first, second = overlapping_pair(second={"crs": "EPSG:3857"})
    result = evaluate_pair(first, second)
    assert result.eligible
    assert result.crs_compatibility == "different"
    assert "different_crs_requires_later_transform" in result.warnings


def test_non_overlapping_same_crs_footprints_are_rejected() -> None:
    first, second = overlapping_pair(second={"footprint": {"bounds": {"west": 10, "south": 10, "east": 11, "north": 11}}})
    result = evaluate_pair(first, second)
    assert "non_overlapping_footprints" in result.hard_rejection_reasons


def test_unknown_coordinate_only_overlap_is_not_fabricated() -> None:
    first, second = overlapping_pair(
        first={"footprint": {"coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
        second={"footprint": {"coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}
    )
    result = evaluate_pair(first, second)
    assert result.eligible
    assert result.footprint_compatibility == "unknown"
    assert "footprint_overlap_unknown" in result.warnings


def test_different_gsd_does_not_reject_pair() -> None:
    first, second = overlapping_pair(first={"gsd_m": 0.5}, second={"gsd_m": 5.0})
    result = evaluate_pair(first, second)
    assert result.eligible
    assert "different_gsd" in result.warnings


def test_missing_explicit_local_file_is_unavailable_warning() -> None:
    first = observation("a", file_path=str(Path("C:/missing/observation-a.tif")))
    result = evaluate_pair(first, observation("b", "2024-02-01T00:00:00Z"))
    assert result.eligible
    assert result.image_reference_a is ImageReferenceStatus.UNAVAILABLE
    assert "image_reference_unavailable" in result.warnings


@pytest.mark.parametrize("source", ["TMC", "OHRC", "IIRS", "LRO NAC", "SELENE"])
def test_known_sensor_combinations_are_supported(source: str) -> None:
    result = evaluate_pair(observation("a", source=source), observation("b", "2024-02-01T00:00:00Z", source="TMC"))
    assert result.sensor_compatibility == "supported"


def test_unknown_sensor_is_warning_not_automatic_rejection() -> None:
    result = evaluate_pair(observation("a", source="unknown test instrument"), observation("b", "2024-02-01T00:00:00Z"))
    assert result.eligible
    assert result.sensor_compatibility == "unknown"
    assert "unknown_sensor_combination" in result.warnings


def test_missing_illumination_is_soft_warning() -> None:
    result = evaluate_pair(observation("a"), observation("b", "2024-02-01T00:00:00Z"))
    assert result.eligible
    assert "optional_metadata_missing" in result.warnings


def test_missing_observation_is_rejected() -> None:
    result = evaluate_pair(None, observation("b", "2024-02-01T00:00:00Z"))
    assert "missing_observation" in result.hard_rejection_reasons
    assert result.image_reference_a is ImageReferenceStatus.INVALID


def test_blank_image_reference_is_rejected_by_phase_10_1_contract() -> None:
    with pytest.raises(ObservationContractError, match="image_reference"):
        observation("a", image_reference="")


def test_multiple_observations_are_unique_and_deterministic() -> None:
    records = [observation("c", "2024-03-01T00:00:00Z"), observation("a"), observation("b", "2024-02-01T00:00:00Z"), observation("b", "2024-02-01T00:00:00Z")]
    results = select_candidate_pairs(records)
    identities = [(result.observation_a_id, result.observation_b_id) for result in results]
    assert identities == [("a", "b"), ("a", "c"), ("b", "c")]


def test_result_serialization_exposes_machine_reasons_and_soft_warnings() -> None:
    result = evaluate_pair(observation("a"), observation("b"))
    payload = result.to_dict()
    assert "same_acquisition_instant" in payload["hard_rejection_reasons"]
    assert isinstance(payload["warnings"], list)
    assert payload["candidate_selection_score"] is None