"""Focused tests for M4 Phase 10.2 temporal metadata handling.

Fixtures are test-only records. They are not real lunar observations or
scientific temporal-change evidence.
"""

from datetime import datetime, timezone

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    LunarObservation,
    ObservationPair,
    TemporalMetadata,
    TemporalMetadataError,
    TemporalMetadataStatus,
    TemporalPrecision,
)


def observation(identifier: str, timestamp: str | None = "2024-01-01T00:00:00Z", **overrides) -> LunarObservation:
    values = {
        "observation_id": identifier,
        "source": "test fixture sensor",
        "image_reference": f"data/test-fixtures/{identifier}.tif",
        "acquisition_timestamp": timestamp,
        "provenance_source": "tests/test_m4_10_2_temporal_metadata.py",
        "provenance": DataProvenance.REAL,
        "is_real_data": True,
    }
    values.update(overrides)
    return LunarObservation(**values)


def test_valid_utc_timestamp_is_normalized() -> None:
    result = TemporalMetadata.from_value(
        "2024-01-01T12:30:45Z", source_field="test.utc", authoritative=True
    )
    assert result.normalized_timestamp == datetime(2024, 1, 1, 12, 30, 45, tzinfo=timezone.utc)
    assert result.metadata_quality is TemporalMetadataStatus.VALID
    assert result.precision is TemporalPrecision.SECOND
    assert result.timezone_aware is True
    assert result.authoritative is True


@pytest.mark.parametrize(
    ("value", "expected_hour"),
    [("2024-01-01T12:30:45+05:30", 7), ("2024-01-01T12:30:45-04:00", 16)],
)
def test_timezone_offsets_normalize_to_correct_instant(value: str, expected_hour: int) -> None:
    result = TemporalMetadata.from_value(value, source_field="test.offset")
    assert result.normalized_timestamp.hour == expected_hour
    assert result.normalized_timestamp.tzinfo is not None


def test_equivalent_timezone_representations_have_same_instant() -> None:
    utc = TemporalMetadata.from_value("2024-01-01T12:00:00Z", source_field="a")
    offset = TemporalMetadata.from_value("2024-01-01T13:00:00+01:00", source_field="b")
    assert utc.normalized_timestamp == offset.normalized_timestamp


def test_date_only_value_preserves_limited_precision() -> None:
    result = TemporalMetadata.from_value("2024-01-01", source_field="manifest.acquisition_date")
    assert result.original_timestamp == "2024-01-01"
    assert result.acquisition_date == "2024-01-01"
    assert result.precision is TemporalPrecision.DATE
    assert result.metadata_quality is TemporalMetadataStatus.LIMITED_PRECISION
    assert result.timezone_aware is False
    assert result.normalized_timestamp is None


def test_timezone_naive_value_does_not_claim_utc() -> None:
    result = TemporalMetadata.from_value("2024-01-01T12:30:00", source_field="header.date_time")
    assert result.normalized_timestamp.tzinfo is None
    assert result.timezone_aware is False
    assert result.metadata_quality is TemporalMetadataStatus.TIMEZONE_NAIVE
    assert result.usable_for_absolute_ordering is False


def test_missing_timestamp_is_explicit() -> None:
    result = TemporalMetadata.from_value(None, source_field="missing.field")
    assert result.metadata_quality is TemporalMetadataStatus.MISSING
    assert result.normalized_timestamp is None


def test_blank_timestamp_is_invalid() -> None:
    result = TemporalMetadata.from_value("", source_field="blank.field")
    assert result.metadata_quality is TemporalMetadataStatus.INVALID
    assert result.normalized_timestamp is None


def test_invalid_timestamp_is_explicit() -> None:
    result = TemporalMetadata.from_value("not-a-timestamp", source_field="bad.field")
    assert result.metadata_quality is TemporalMetadataStatus.INVALID
    assert result.original_timestamp == "not-a-timestamp"
    assert result.normalized_timestamp is None


def test_non_mapping_external_metadata_is_rejected() -> None:
    with pytest.raises(TemporalMetadataError, match="mapping"):
        TemporalMetadata.from_observation(observation("a"), metadata=[])


def test_observation_timestamp_takes_precedence_over_explicit_external_metadata() -> None:
    result = TemporalMetadata.from_observation(
        observation("a", "2024-01-01T00:00:00Z"),
        {"acquisition_timestamp": "2024-01-01T00:00:00Z"},
    )
    assert result.source_field == "observation.acquisition_timestamp"
    assert result.authoritative is True


def test_conflicting_explicit_temporal_metadata_is_reported() -> None:
    result = TemporalMetadata.from_observation(
        observation("a", "2024-01-01T00:00:00Z"),
        {"acquisition_timestamp": "2024-01-02T00:00:00Z"},
    )
    assert result.metadata_quality is TemporalMetadataStatus.CONFLICTING
    assert "Conflicting acquisition metadata" in result.notes


def test_acquisition_date_is_supported_when_observation_timestamp_is_missing() -> None:
    result = TemporalMetadata.from_observation(
        observation("a", None), {"acquisition_date": "2024-01-03"}
    )
    assert result.source_field == "metadata.acquisition_date"
    assert result.precision is TemporalPrecision.DATE


def test_pair_exposes_temporal_records_order_and_separation() -> None:
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00Z"),
        observation("b", "2024-01-02T12:00:00Z"),
    )
    view = pair.temporal_metadata
    assert view.observation_a.original_timestamp.endswith("Z")
    assert view.observation_b.original_timestamp.endswith("Z")
    assert view.chronological_order == "a_before_b"
    assert view.temporal_separation_seconds == 129600.0
    assert view.timestamps_available is True
    assert view.metadata_quality is TemporalMetadataStatus.VALID


def test_pair_temporal_view_supports_reverse_chronological_order() -> None:
    pair = ObservationPair(
        observation("a", "2024-01-02T00:00:00Z"),
        observation("b", "2024-01-01T00:00:00Z"),
    )
    assert pair.temporal_metadata.chronological_order == "b_before_a"


def test_timezone_naive_pair_has_clock_order_but_no_absolute_separation() -> None:
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00"),
        observation("b", "2024-01-02T00:00:00"),
    )
    view = pair.temporal_metadata
    assert view.chronological_order == "a_before_b"
    assert view.temporal_separation_seconds is None
    assert view.metadata_quality is TemporalMetadataStatus.TIMEZONE_NAIVE


def test_pair_temporal_view_retains_limited_precision() -> None:
    pair = ObservationPair(observation("a", "2024-01-01"), observation("b", "2024-01-03"))
    view = pair.temporal_metadata
    assert view.metadata_quality is TemporalMetadataStatus.LIMITED_PRECISION
    assert view.observation_a.precision is TemporalPrecision.DATE
    assert view.chronological_order == "a_before_b"
    assert view.temporal_separation_seconds is None


def test_simulated_provenance_remains_simulated_during_resolution() -> None:
    simulated = observation(
        "simulated-a",
        provenance=DataProvenance.SYNTHETIC,
        is_real_data=False,
    )
    result = TemporalMetadata.from_observation(simulated)
    assert simulated.provenance is DataProvenance.SYNTHETIC
    assert simulated.is_real_data is False
    assert result.source_field == "observation.acquisition_timestamp"


def test_temporal_metadata_serializes_without_fabricating_timezone() -> None:
    result = TemporalMetadata.from_value("2024-01-01T12:30:00", source_field="test.naive")
    payload = result.to_dict()
    assert payload["original_timestamp"] == "2024-01-01T12:30:00"
    assert payload["normalized_timestamp"] == "2024-01-01T12:30:00"
    assert payload["timezone_aware"] is False