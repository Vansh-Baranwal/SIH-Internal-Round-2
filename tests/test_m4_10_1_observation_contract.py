"""Focused tests for M4 Phase 10.1 multi-date observation contract.

All records here are test-only fixtures. They are explicitly marked as real
data only to exercise the contract's provenance gate; they are not scientific
observations or evidence of lunar change.
"""

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    LunarObservation,
    ObservationContractError,
    ObservationPair,
)


def observation(identifier: str, timestamp: str | None = "2024-01-01T00:00:00Z", **overrides) -> LunarObservation:
    values = {
        "observation_id": identifier,
        "source": "TMC test fixture",
        "image_reference": f"data/test-fixtures/{identifier}.tif",
        "acquisition_timestamp": timestamp,
        "dimensions": (1024, 2048),
        "gsd_m": 5.0,
        "provenance_source": "tests/test_m4_10_1_observation_contract.py",
        "provenance": DataProvenance.REAL,
        "is_real_data": True,
    }
    values.update(overrides)
    return LunarObservation(**values)


def test_valid_genuine_observation_pair_round_trips() -> None:
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00Z"),
        observation("b", "2024-02-01T00:00:00Z", source="LRO NAC test fixture"),
        pair_id="test-pair",
    )

    restored = ObservationPair.from_dict(pair.to_dict())
    assert restored.pair_id == "test-pair"
    assert restored.temporally_distinct
    assert restored.observation_a.image_reference.endswith("a.tif")


def test_missing_identity_is_rejected() -> None:
    with pytest.raises(ObservationContractError, match="observation_id"):
        observation("",)


def test_invalid_acquisition_timestamp_is_rejected() -> None:
    with pytest.raises(ObservationContractError, match="ISO-8601"):
        observation("a", "not-a-date")


def test_same_observation_cannot_be_both_pair_members() -> None:
    first = observation("same", "2024-01-01T00:00:00Z")
    second = observation("same", "2024-02-01T00:00:00Z")
    with pytest.raises(ObservationContractError, match="same observation"):
        ObservationPair(first, second)


def test_missing_optional_illumination_is_valid() -> None:
    item = observation("a")
    assert item.sun_azimuth_deg is None
    assert item.sun_elevation_deg is None
    assert item.phase_angle_deg is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("dimensions", (0, 100)), ("dimensions", (100, -1)), ("gsd_m", 0), ("gsd_m", float("nan")),
     ("sun_elevation_deg", 91), ("sun_azimuth_deg", 360), ("phase_angle_deg", -1),
     ("incidence_angle_deg", 181), ("emission_angle_deg", float("inf"))],
)
def test_invalid_numeric_metadata_is_rejected(field_name: str, value) -> None:
    with pytest.raises(ObservationContractError, match=field_name):
        observation("a", **{field_name: value})


def test_unknown_metadata_is_serialized_as_null() -> None:
    payload = observation("a").to_dict()
    assert payload["sun_azimuth_deg"] is None
    assert payload["crs"] is None
    assert LunarObservation.from_dict(payload).crs is None


def test_pair_requires_both_acquisition_timestamps() -> None:
    with pytest.raises(ObservationContractError, match="timestamps"):
        ObservationPair(observation("a", None), observation("b", "2024-02-01"))


def test_pair_rejects_same_acquisition_instant_even_with_different_format() -> None:
    with pytest.raises(ObservationContractError, match="distinct acquisition"):
        ObservationPair(observation("a", "2024-01-01"), observation("b", "2024-01-01T00:00:00Z"))


def test_simulated_observations_cannot_be_temporal_pair() -> None:
    simulated = observation(
        "synthetic-a",
        "2024-01-01T00:00:00Z",
        provenance=DataProvenance.SYNTHETIC,
        is_real_data=False,
    )
    genuine = observation("real-b", "2024-02-01T00:00:00Z")
    with pytest.raises(ObservationContractError, match="is_real_data"):
        ObservationPair(simulated, genuine)


def test_real_claim_cannot_be_created_without_real_provenance() -> None:
    with pytest.raises(ObservationContractError, match="REAL provenance"):
        observation("a", provenance=DataProvenance.UNAVAILABLE, is_real_data=True)


def test_malformed_observation_payload_uses_contract_error() -> None:
    with pytest.raises(ObservationContractError, match="Malformed LunarObservation"):
        LunarObservation.from_dict({"observation_id": "missing-other-fields"})


def test_non_mapping_observation_payload_uses_contract_error() -> None:
    with pytest.raises(ObservationContractError, match="payload must be a dictionary"):
        LunarObservation.from_dict([])


def test_malformed_pair_payload_uses_contract_error() -> None:
    with pytest.raises(ObservationContractError, match="missing fields"):
        ObservationPair.from_dict({"observation_a": observation("a").to_dict()})


@pytest.mark.parametrize("field_name", ["crs", "geospatial_reference", "footprint", "view_geometry"])
def test_spatial_metadata_rejects_invalid_types(field_name: str) -> None:
    with pytest.raises(ObservationContractError, match=field_name):
        observation("a", **{field_name: []})


def test_empty_crs_is_rejected() -> None:
    with pytest.raises(ObservationContractError, match="crs"):
        observation("a", crs=" ")


def test_m1_style_footprint_bounds_are_validated() -> None:
    item = observation(
        "a",
        footprint={"bounds": {"west": -10.0, "south": -5.0, "east": 10.0, "north": 5.0}},
    )
    assert item.footprint["bounds"]["east"] == 10.0


@pytest.mark.parametrize(
    "footprint",
    [{}, {"type": "Polygon"}, {"bounds": {"west": 0, "south": 0, "east": 0, "north": 1}},
     {"coordinates": []}, {"coordinates": [["not", "numeric"]]}],
)
def test_malformed_footprint_structure_is_rejected(footprint) -> None:
    with pytest.raises(ObservationContractError, match="footprint"):
        observation("a", footprint=footprint)


def test_view_geometry_uses_existing_camera_vector_shape() -> None:
    item = observation(
        "a",
        view_geometry={"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}, "target_m": [0.0, 0.0, 0.0]},
    )
    assert item.view_geometry["position_m"]["z"] == 3.0


@pytest.mark.parametrize(
    "view_geometry",
    [{}, {"position_m": [1.0, 2.0]}, {"target_m": {"x": 0.0, "y": 0.0}},
     {"position_m": [0.0, 0.0, float("nan")]}],
)
def test_malformed_view_geometry_structure_is_rejected(view_geometry) -> None:
    with pytest.raises(ObservationContractError, match="view_geometry"):
        observation("a", view_geometry=view_geometry)


@pytest.mark.parametrize("field_name", ["metadata_quality", "validation_status"])
def test_blank_quality_or_status_is_rejected(field_name: str) -> None:
    with pytest.raises(ObservationContractError, match=field_name):
        observation("a", **{field_name: " "})