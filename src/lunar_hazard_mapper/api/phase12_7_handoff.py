"""Typed, inactive boundary for future Phase 11 result consumers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .phase11_router import Phase11ApiResponse


@dataclass(frozen=True)
class Phase11ResultHandoff:
    """Unmodified Phase 11 result slots for a future downstream consumer.

    This is a transport boundary, not a registration or coordinate model. The
    result dictionaries are the exact objects supplied by Phase 11.
    """

    validation_request_id: str
    status: str
    source_image_id: str
    match_points: Optional[Dict[str, Any]]
    registration_metrics: Optional[Dict[str, Any]]
    localization: Optional[Dict[str, Any]]
    final_validation: Optional[Dict[str, Any]]
    provenance: Dict[str, Any]
    warnings: list[str]
    limitations: list[str]


def adapt_phase11_result(response: Phase11ApiResponse) -> Phase11ResultHandoff:
    """Preserve Phase 11 context, including blocked or empty results.

    This carries response context only; downstream adapters still decide
    whether a genuine registered output exists.
    """
    if not isinstance(response, Phase11ApiResponse):
        raise TypeError("response must be a Phase11ApiResponse")
    return Phase11ResultHandoff(
        validation_request_id=response.validation_request_id,
        status=response.status,
        source_image_id=response.source_image_id,
        match_points=response.match_points,
        registration_metrics=response.registration_metrics,
        localization=response.localization,
        final_validation=response.final_validation,
        provenance=response.provenance,
        warnings=response.warnings,
        limitations=response.limitations,
    )


__all__ = ["Phase11ResultHandoff", "adapt_phase11_result"]