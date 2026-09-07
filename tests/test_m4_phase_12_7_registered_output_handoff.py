"""Regression tests for the inactive Phase 12.7 handoff boundary."""

from fastapi.testclient import TestClient

from lunar_hazard_mapper.api.main import app
from lunar_hazard_mapper.api.phase11_router import Phase11ApiResponse, Phase11StageResponse
from lunar_hazard_mapper.api.phase12_7_handoff import Phase11ResultHandoff, adapt_phase11_result


client = TestClient(app)


def phase11_request(provenance: str = "unavailable") -> dict:
    return {
        "validation_request_id": "phase12-7-test-001",
        "image": {
            "image_id": "phase12-7-image",
            "image_reference": "external-image-reference",
            "image_reference_type": "external_reference",
            "provenance": provenance,
            "provenance_source": "tests/test_m4_phase_12_7_registered_output_handoff.py",
            "is_real_data": False,
            "validation_status": "unvalidated",
            "external_reference": "https://example.invalid/phase12-7.tif",
        },
    }


def test_blocked_phase11_result_cannot_create_downstream_output():
    response = client.post("/api/phase11/lunar-gps", json=phase11_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["match_points"] is None
    assert payload["registration_metrics"] is None
    assert payload["localization"] is None
    assert payload["final_validation"] is None
    assert payload["downstream_statuses"]["11.7_coordinate_estimation"] == "not_executed"
    assert payload["validation_request_id"] == "phase12-7-test-001"
    assert "registration_id" not in payload
    assert "registered_image_id" not in payload
    assert "output_id" not in payload


def test_synthetic_phase11_result_preserves_provenance_without_handoff():
    response = client.post(
        "/api/phase11/lunar-gps",
        json=phase11_request(provenance="synthetic"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["provenance"]["image_provenance"] == "synthetic"
    assert payload["provenance"]["synthetic"] is True
    assert payload["localization"] is None
    assert payload["registration_metrics"] is None


def test_blocked_phase11_context_preserves_source_warnings_and_limitations():
    response = client.post("/api/phase11/lunar-gps", json=phase11_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_image_id"] == "phase12-7-image"
    assert payload["warnings"]
    assert payload["limitations"]
    assert payload["provenance"]["image_provenance"] == "unavailable"
    assert payload["match_points"] is None
    assert payload["registration_metrics"] is None
    assert payload["localization"] is None


def test_phase12_7_does_not_use_the_m2_correspondence_route():
    paths = app.openapi()["paths"]

    assert "/api/v1/correspondence/register" not in paths
    assert "/api/phase11/lunar-gps" in paths


def test_null_phase11_slots_preserve_context_without_registered_output():
    response = client.post("/api/phase11/lunar-gps", json=phase11_request())

    handoff = adapt_phase11_result(Phase11ApiResponse.model_validate(response.json()))

    assert handoff.status == "blocked"
    assert handoff.validation_request_id == "phase12-7-test-001"
    assert handoff.source_image_id == "phase12-7-image"
    assert handoff.match_points is None
    assert handoff.registration_metrics is None
    assert handoff.localization is None


def test_future_supported_result_is_passed_without_modification():
    match_points = {"pairs": [{"source": {"x": 1, "y": 2}, "reference": {"x": 3, "y": 4}}]}
    registration_metrics = {"rmse": 0.25}
    localization = {
        "coordinate": [12.5, -4.0],
        "coordinate_system": "lunar_local",
        "reference_frame": "mission_frame",
        "units": "m",
        "axis_order": ["x", "y"],
    }
    provenance = {"source": "future-phase-11", "classification": "synthetic"}
    payload = {
        "validation_request_id": "future-result-001",
        "status": "available",
        "source_image_id": "future-image",
        "metadata_quality": {"status": "good", "result": {}},
        "landmark_retrieval": {"status": "success", "result": {}},
        "downstream_statuses": {},
        "match_points": match_points,
        "registration_metrics": registration_metrics,
        "localization": localization,
        "final_validation": None,
        "warnings": ["synthetic fixture"],
        "limitations": ["illustrative only"],
        "provenance": provenance,
    }

    handoff = adapt_phase11_result(Phase11ApiResponse.model_validate(payload))

    assert isinstance(handoff, Phase11ResultHandoff)
    assert handoff.match_points == match_points
    assert handoff.registration_metrics == registration_metrics
    assert handoff.localization == localization
    assert handoff.provenance == provenance
    assert handoff.validation_request_id == "future-result-001"
    assert not hasattr(handoff, "registration_id")


def test_blocked_response_preserves_context_even_if_slots_are_present():
    response = Phase11ApiResponse(
        validation_request_id="blocked-001",
        status="BLOCKED",
        source_image_id="blocked-image",
        metadata_quality=Phase11StageResponse(status="blocked", result={}),
        landmark_retrieval=Phase11StageResponse(status="blocked", result={}),
        downstream_statuses={},
        localization={"coordinate": [1, 2]},
    )

    handoff = adapt_phase11_result(response)

    assert handoff.status == "BLOCKED"
    assert handoff.validation_request_id == "blocked-001"
    assert handoff.source_image_id == "blocked-image"
    assert handoff.localization == {"coordinate": [1, 2]}