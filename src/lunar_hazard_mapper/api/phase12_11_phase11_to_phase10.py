"""Typed Phase 11 to Phase 10 connection boundary.

The current Phase 11 handoff has no registered observation artifact. This
adapter therefore preserves the handoff context and stops before constructing
an observation for Phase 10.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .phase10_router import Phase10ObservationRequest
from .phase12_7_handoff import Phase11ResultHandoff, adapt_phase11_result
from .phase11_router import Phase11ApiResponse


class Phase11ToPhase10Status(str, Enum):
    UNAVAILABLE = "unavailable"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class Phase11ToPhase10Result:
    """The provenance-preserving result of the inactive integration boundary."""

    status: Phase11ToPhase10Status
    observation: Optional[Phase10ObservationRequest]
    validation_request_id: Optional[str]
    source_image_id: Optional[str]
    provenance: Dict[str, Any]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    reason: str


def adapt_phase11_to_phase10(
    handoff: Optional[Phase11ResultHandoff],
) -> Phase11ToPhase10Result:
    """Adapt a Phase 12.7 handoff without inventing a Phase 10 observation.

    The existing handoff contains nullable evidence slots, not a registered
    output contract. Even a non-blocked future handoff is therefore stopped
    here until Phase 11 exposes an explicit registered artifact and all
    mandatory Phase 10 observation metadata.
    """
    if handoff is not None and not isinstance(handoff, Phase11ResultHandoff):
        raise TypeError("handoff must be a Phase11ResultHandoff or None")

    if handoff is None:
        return Phase11ToPhase10Result(
            status=Phase11ToPhase10Status.UNAVAILABLE,
            observation=None,
            validation_request_id=None,
            source_image_id=None,
            provenance={},
            warnings=(),
            limitations=(
                "Phase 11 did not produce a supported result handoff.",
                "No Phase 10 observation was created.",
            ),
            reason="phase11_handoff_unavailable",
        )

    blocked = handoff.status.lower() == "blocked"
    limitations = tuple(handoff.limitations) + (
        "Phase 11 exposes no registered observation artifact/reference for Phase 10.",
        "Phase 11 match points, registration metrics, localization, and final validation are not registered-output metadata.",
        "No Phase 10 observation was created.",
    )
    reason = "phase11_handoff_unavailable" if blocked else "registered_output_unavailable"

    return Phase11ToPhase10Result(
        status=Phase11ToPhase10Status.UNAVAILABLE if blocked else Phase11ToPhase10Status.DEFERRED,
        observation=None,
        validation_request_id=handoff.validation_request_id,
        source_image_id=handoff.source_image_id,
        provenance=dict(handoff.provenance),
        warnings=tuple(handoff.warnings),
        limitations=limitations,
        reason=reason,
    )


def adapt_phase11_response_to_phase10(
    response: Phase11ApiResponse,
) -> Phase11ToPhase10Result:
    """Cross the Phase 12.7 boundary while retaining unavailable context."""
    if not isinstance(response, Phase11ApiResponse):
        raise TypeError("response must be a Phase11ApiResponse")

    handoff = adapt_phase11_result(response)
    if handoff is not None:
        return adapt_phase11_to_phase10(handoff)

    blocked = response.status.lower() == "blocked"
    return Phase11ToPhase10Result(
        status=Phase11ToPhase10Status.UNAVAILABLE if blocked else Phase11ToPhase10Status.DEFERRED,
        observation=None,
        validation_request_id=response.validation_request_id,
        source_image_id=response.source_image_id,
        provenance=dict(response.provenance),
        warnings=tuple(response.warnings),
        limitations=tuple(response.limitations) + (
            "Phase 11 did not expose a supported registered observation artifact/reference for Phase 10.",
            "No Phase 10 observation was created.",
        ),
        reason="phase11_blocked" if blocked else "registered_output_unavailable",
    )


__all__ = [
    "Phase11ToPhase10Result",
    "Phase11ToPhase10Status",
    "adapt_phase11_to_phase10",
    "adapt_phase11_response_to_phase10",
]
