"""Focused tests for the inactive Phase 12.11 connection boundary."""

from lunar_hazard_mapper.api.phase11_router import Phase11ApiResponse, Phase11StageResponse
from lunar_hazard_mapper.api.phase12_11_phase11_to_phase10 import (
    Phase11ToPhase10Status,
    adapt_phase11_to_phase10,
    adapt_phase11_response_to_phase10,
)


def response(**overrides: object) -> Phase11ApiResponse:
    payload = {
        "validation_request_id": "phase12-11-test-001",
        "status": "blocked",
        "source_image_id": "source-image-001",
        "metadata_quality": Phase11StageResponse(status="blocked", result={}),
        "landmark_retrieval": Phase11StageResponse(status="blocked", result={}),
        "downstream_statuses": {"11.7_coordinate_estimation": "not_executed"},
        "warnings": ["metadata warning"],
        "limitations": ["registration not executed"],
        "provenance": {"image_provenance": "synthetic", "source": "test-source"},
    }
    payload.update(overrides)
    return Phase11ApiResponse(**payload)


def test_blocked_phase11_result_is_unavailable_without_observation() -> None:
    result = adapt_phase11_response_to_phase10(response())

    assert result.status is Phase11ToPhase10Status.UNAVAILABLE
    assert result.observation is None
    assert result.reason == "phase11_handoff_unavailable"


def test_null_phase11_slots_do_not_infer_registration() -> None:
    result = adapt_phase11_response_to_phase10(response(status="available"))

    assert result.status is Phase11ToPhase10Status.DEFERRED
    assert result.observation is None
    assert "registered observation artifact" in " ".join(result.limitations)


def test_null_localization_and_metrics_do_not_create_observation() -> None:
    result = adapt_phase11_response_to_phase10(
        response(status="available", match_points={"pairs": []}, final_validation={"status": "not_executed"})
    )

    assert result.observation is None
    assert "match points" in " ".join(result.limitations)


def test_handoff_context_provenance_warnings_and_limitations_are_preserved() -> None:
    result = adapt_phase11_response_to_phase10(response())

    assert result.validation_request_id == "phase12-11-test-001"
    assert result.source_image_id == "source-image-001"
    assert result.provenance == {"image_provenance": "synthetic", "source": "test-source"}
    assert result.warnings == ("metadata warning",)
    assert result.limitations[0] == "registration not executed"


def test_none_handoff_is_explicitly_unavailable_without_generated_values() -> None:
    result = adapt_phase11_to_phase10(None)

    assert result.status is Phase11ToPhase10Status.UNAVAILABLE
    assert result.observation is None
    assert result.validation_request_id is None
    assert result.source_image_id is None
    assert result.provenance == {}
