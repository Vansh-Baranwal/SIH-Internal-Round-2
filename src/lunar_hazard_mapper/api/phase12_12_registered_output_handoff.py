"""Minimal Phase 12.12 boundary for future registered-output consumers.

The current Phase 11 contract exposes no registered artifact. This module
therefore carries supported context only and keeps downstream availability
explicitly unavailable until Phase 11 defines that artifact.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .phase12_7_handoff import Phase11ResultHandoff


class RegisteredOutputHandoffStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RegisteredOutputHandoff:
    """Canonical downstream boundary carrying only genuine Phase 11 context."""

    status: RegisteredOutputHandoffStatus
    validation_request_id: Optional[str]
    source_image_id: Optional[str]
    registered_output_reference: Optional[str]
    provenance: Dict[str, Any]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


def adapt_phase11_to_registered_output(
    handoff: Optional[Phase11ResultHandoff],
) -> RegisteredOutputHandoff:
    """Build a downstream handoff without promoting nullable evidence slots.

    Phase 12.7 currently has no registered-output field. Consequently this
    adapter never creates an available handoff, and it never copies source
    image identity into the registered-output reference.
    """
    if handoff is not None and not isinstance(handoff, Phase11ResultHandoff):
        raise TypeError("handoff must be a Phase11ResultHandoff or None")

    if handoff is None:
        return RegisteredOutputHandoff(
            status=RegisteredOutputHandoffStatus.UNAVAILABLE,
            validation_request_id=None,
            source_image_id=None,
            registered_output_reference=None,
            provenance={},
            warnings=(),
            limitations=(
                "Phase 11 did not produce a supported result handoff.",
                "No registered output was supplied to Phase 12.12.",
            ),
        )

    blocked = handoff.status.lower() == "blocked"
    return RegisteredOutputHandoff(
        status=(
            RegisteredOutputHandoffStatus.BLOCKED
            if blocked
            else RegisteredOutputHandoffStatus.UNAVAILABLE
        ),
        validation_request_id=handoff.validation_request_id,
        source_image_id=handoff.source_image_id,
        registered_output_reference=None,
        provenance=dict(handoff.provenance),
        warnings=tuple(handoff.warnings),
        limitations=tuple(handoff.limitations)
        + (
            "Phase 11 does not expose a genuine registered output reference.",
            "Nullable match points, registration metrics, localization, and final validation are not registered output.",
            "No M4, M5, or M6 downstream consumer was invoked.",
        ),
    )


def downstream_invocation_allowed(handoff: RegisteredOutputHandoff) -> bool:
    """Return whether an existing downstream consumer may be called."""
    if not isinstance(handoff, RegisteredOutputHandoff):
        raise TypeError("handoff must be a RegisteredOutputHandoff")
    return (
        handoff.status is RegisteredOutputHandoffStatus.AVAILABLE
        and handoff.registered_output_reference is not None
    )


__all__ = [
    "RegisteredOutputHandoff",
    "RegisteredOutputHandoffStatus",
    "adapt_phase11_to_registered_output",
    "downstream_invocation_allowed",
]