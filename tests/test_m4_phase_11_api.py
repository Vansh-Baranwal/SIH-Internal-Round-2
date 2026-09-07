"""Focused tests for the thin Phase 11 HTTP boundary."""

from fastapi.testclient import TestClient

from lunar_hazard_mapper.api.main import app


client = TestClient(app)


def valid_request() -> dict:
    return {
        "validation_request_id": "api-test-001",
        "image": {
            "image_id": "unknown-api-image",
            "image_reference": "external-image-reference",
            "image_reference_type": "external_reference",
            "provenance": "unavailable",
            "provenance_source": "tests/test_m4_phase_11_api.py",
            "is_real_data": False,
            "validation_status": "unvalidated",
            "external_reference": "https://example.invalid/unknown.tif",
        },
    }


def test_phase11_route_is_registered_without_repurposing_m2_route():
    paths = app.openapi()["paths"]
    response_schema = app.openapi()["components"]["schemas"]["Phase11ApiResponse"]["properties"]
    assert "/api/phase11/lunar-gps" in paths
    assert "post" in paths["/api/phase11/lunar-gps"]
    assert "/api/v1/correspondence/register" not in paths
    assert "/api/mission/status" in paths
    assert {"match_points", "registration_metrics", "localization"}.issubset(response_schema)


def test_valid_request_runs_available_prefix_and_preserves_blocked_state():
    response = client.post("/api/phase11/lunar-gps", json=valid_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["validation_request_id"] == "api-test-001"
    assert payload["source_image_id"] == "unknown-api-image"
    assert payload["metadata_quality"]["result"]["image_id"] == "unknown-api-image"
    assert payload["landmark_retrieval"]["status"] == "landmark_source_unavailable"
    assert "match_points" in payload
    assert "registration_metrics" in payload
    assert "localization" in payload
    assert payload["match_points"] is None
    assert payload["registration_metrics"] is None
    assert payload["localization"] is None
    assert payload["final_validation"] is None
    assert payload["provenance"]["image_provenance"] == "unavailable"
    assert payload["provenance"]["synthetic"] is False
    assert payload["downstream_statuses"]["11.7_coordinate_estimation"] == "not_executed"


def test_required_and_blank_identifiers_are_rejected():
    missing = client.post("/api/phase11/lunar-gps", json={"image": valid_request()["image"]})
    blank = client.post(
        "/api/phase11/lunar-gps",
        json={**valid_request(), "validation_request_id": ""},
    )

    assert missing.status_code == 422
    assert blank.status_code == 422


def test_contradictory_real_provenance_is_rejected_without_fabrication():
    request = valid_request()
    request["image"]["provenance"] = "real"
    request["image"]["is_real_data"] = False

    response = client.post("/api/phase11/lunar-gps", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "invalid_input"


def test_unknown_request_fields_are_rejected():
    request = valid_request()
    request["invented_coordinate"] = [1.0, 2.0]

    response = client.post("/api/phase11/lunar-gps", json=request)

    assert response.status_code == 422


def test_malformed_numeric_values_are_rejected():
    request = valid_request()
    request["image"]["gsd_m"] = "5.0"

    response = client.post("/api/phase11/lunar-gps", json=request)

    assert response.status_code == 422


def test_synthetic_provenance_survives_and_does_not_create_localization():
    request = valid_request()
    request["image"]["provenance"] = "synthetic"
    request["image"]["provenance_source"] = "controlled-api-test-fixture"

    response = client.post("/api/phase11/lunar-gps", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["provenance"]["image_provenance"] == "synthetic"
    assert payload["provenance"]["synthetic"] is True
    assert payload["final_validation"] is None
    assert "estimated_coordinate" not in payload
