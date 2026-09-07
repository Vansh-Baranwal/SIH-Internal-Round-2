"""Focused guardrails for the inactive Phase 12.12 handoff boundary."""

from lunar_hazard_mapper.api.phase11_router import Phase11ApiResponse, Phase11StageResponse
from lunar_hazard_mapper.api.phase12_7_handoff import adapt_phase11_result
from lunar_hazard_mapper.api.phase12_12_registered_output_handoff import (
    RegisteredOutputHandoffStatus,
    adapt_phase11_to_registered_output,
    downstream_invocation_allowed,
)


def response(**overrides: object) -> Phase11ApiResponse:
    payload = {
        "validation_request_id": "phase12-12-test-001",
        "status": "blocked",
        "source_image_id": "source-image-001",
        "metadata_quality": Phase11StageResponse(status="blocked", result={}),
        "landmark_retrieval": Phase11StageResponse(status="blocked", result={}),
        "downstream_statuses": {},
        "warnings": ["metadata warning"],
        "limitations": ["registration not executed"],
        "provenance": {"image_provenance": "synthetic", "source": "test-source"},
    }
    payload.update(overrides)
    return Phase11ApiResponse(**payload)


def adapt(response_value: Phase11ApiResponse):
    return adapt_phase11_to_registered_output(adapt_phase11_result(response_value))


def test_blocked_phase11_is_blocked_and_unavailable_to_downstream():
    handoff = adapt(response())

    assert handoff.status is RegisteredOutputHandoffStatus.BLOCKED
    assert handoff.registered_output_reference is None
    assert not downstream_invocation_allowed(handoff)


def test_null_registered_output_and_all_nullable_slots_remain_unavailable():
    handoff = adapt(response(status="available"))

    assert handoff.status is RegisteredOutputHandoffStatus.UNAVAILABLE
    assert handoff.registered_output_reference is None
    assert not downstream_invocation_allowed(handoff)


def test_source_image_alone_is_not_a_registered_output():
    handoff = adapt(response(status="available"))

    assert handoff.source_image_id == "source-image-001"
    assert handoff.registered_output_reference is None


def test_nullable_match_points_metrics_localization_and_validation_do_not_activate():
    handoff = adapt(
        response(
            status="available",
            match_points={"pairs": []},
            registration_metrics={"rmse": 0.2},
            localization={"coordinate": [1, 2]},
            final_validation={"status": "validated"},
        )
    )

    assert handoff.status is RegisteredOutputHandoffStatus.UNAVAILABLE
    assert not downstream_invocation_allowed(handoff)


def test_provenance_warnings_limitations_and_source_identity_are_preserved():
    handoff = adapt(response())

    assert handoff.validation_request_id == "phase12-12-test-001"
    assert handoff.source_image_id == "source-image-001"
    assert handoff.provenance == {"image_provenance": "synthetic", "source": "test-source"}
    assert handoff.warnings == ("metadata warning",)
    assert handoff.limitations[0] == "registration not executed"


def test_none_handoff_has_no_generated_identifiers_or_spatial_values():
    handoff = adapt_phase11_to_registered_output(None)

    assert handoff.status is RegisteredOutputHandoffStatus.UNAVAILABLE
    assert handoff.validation_request_id is None
    assert handoff.source_image_id is None
    assert handoff.registered_output_reference is None
    assert handoff.provenance == {}
    assert not hasattr(handoff, "coordinates")
    assert not hasattr(handoff, "crs")
    assert not hasattr(handoff, "transform")