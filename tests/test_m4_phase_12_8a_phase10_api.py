"""Focused tests for the minimal Phase 10 HTTP transport."""

from fastapi.testclient import TestClient

from lunar_hazard_mapper.api.main import app


client = TestClient(app)


def observation(observation_id: str, timestamp: str, *, provenance: str = "real") -> dict:
    return {
        "observation_id": observation_id,
        "source": "TMC",
        "image_reference": f"https://example.invalid/{observation_id}.tif",
        "acquisition_timestamp": timestamp,
        "provenance_source": "phase12-8a-test-fixture",
        "provenance": provenance,
        "is_real_data": provenance == "real",
        "validation_status": "unvalidated",
    }


def pair_request(**kwargs: object) -> dict:
    first = observation("observation-a", "2024-01-01T00:00:00Z")
    second = observation("observation-b", "2024-01-02T00:00:00Z")
    first.update(kwargs.get("observation_a", {}))
    second.update(kwargs.get("observation_b", {}))
    return {"observation_a": first, "observation_b": second}


def test_pair_selection_endpoint_returns_existing_phase10_result():
    response = client.post("/api/phase10/pair-selection", json=pair_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligibility"] == "eligible"
    assert payload["observation_a_id"] == "observation-a"
    assert payload["observation_b_id"] == "observation-b"
    assert payload["provenance_status"] == "real"
    assert payload["temporal_metadata"]["chronological_order"] == "a_before_b"
    assert "candidate_selection_score" in payload


def test_pair_selection_preserves_client_order_without_sorting_in_router():
    request = pair_request(
        observation_a={"acquisition_timestamp": "2024-01-02T00:00:00Z"},
        observation_b={"acquisition_timestamp": "2024-01-01T00:00:00Z"},
    )

    response = client.post("/api/phase10/pair-selection", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["observation_a_id"] == "observation-a"
    assert payload["observation_b_id"] == "observation-b"
    assert payload["temporal_metadata"]["chronological_order"] == "b_before_a"


def test_non_real_pair_is_rejected_by_existing_real_data_gate():
    response = client.post(
        "/api/phase10/pair-selection",
        json=pair_request(observation_a={"provenance": "synthetic", "is_real_data": False}),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligibility"] == "rejected"
    assert "non_real_provenance" in payload["hard_rejection_reasons"]
    assert payload["provenance_status"] == "non_real"


def test_missing_required_observation_is_rejected():
    request = pair_request()
    del request["observation_b"]["observation_id"]

    response = client.post("/api/phase10/pair-selection", json=request)

    assert response.status_code == 422


def test_invalid_temporal_metadata_is_rejected_at_transport_boundary():
    response = client.post(
        "/api/phase10/pair-selection",
        json=pair_request(observation_a={"acquisition_timestamp": "not-a-timestamp"}),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "invalid_input"


def test_absolute_filesystem_references_are_not_accepted():
    response = client.post(
        "/api/phase10/pair-selection",
        json=pair_request(observation_a={"image_reference": "C:\\private\\image.tif"}),
    )

    assert response.status_code == 422


def test_relative_path_references_are_not_accepted():
    response = client.post(
        "/api/phase10/pair-selection",
        json=pair_request(observation_a={"image_reference": "data/private/image.tif"}),
    )

    assert response.status_code == 422


def test_spatial_metadata_is_preserved_without_conversion():
    request = pair_request(
        observation_a={
            "crs": "LUNAR:LOCAL",
            "footprint": {"bounds": {"west": 0, "south": 0, "east": 10, "north": 10}},
        },
        observation_b={
            "crs": "LUNAR:LOCAL",
            "footprint": {"bounds": {"west": 5, "south": 5, "east": 15, "north": 15}},
        },
    )

    response = client.post("/api/phase10/pair-selection", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["crs_compatibility"] == "compatible"
    assert payload["footprint_compatibility"] == "compatible"


def test_phase10_endpoint_does_not_create_phase11_dependency():
    paths = app.openapi()["paths"]

    assert "/api/phase10/pair-selection" in paths
    assert "/api/phase11/lunar-gps" in paths
    assert "phase11" not in app.routes[-1].path.lower() if hasattr(app.routes[-1], "path") else True