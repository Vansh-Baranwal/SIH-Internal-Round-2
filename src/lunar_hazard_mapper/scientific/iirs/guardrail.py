"""M4-08.10 Scientific Guardrails for IIRS spectral outputs.

This module provides an immutable scientific-status qualification contract
that explicitly declares the epistemic status of IIRS classification and
overlay results.

It does NOT modify any upstream scientific computation.  It qualifies
existing outputs with metadata that makes their illustrative/engineering
nature explicit, preventing them from being silently treated as
publication-grade mineral identification.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict


class IIRSScientificStatus(enum.Enum):
    """Scientific validation status for IIRS spectral interpretation outputs.

    ILLUSTRATIVE
        The output uses lightweight, engineering/illustrative rules.
        It has NOT been independently validated and must NOT be treated
        as publication-grade mineral identification.

    VALIDATED
        Reserved for a future independent validation workflow that
        supplies externally verified evidence.  Current Phase 8 code
        must NEVER produce this status automatically.
    """

    ILLUSTRATIVE = "ILLUSTRATIVE"
    VALIDATED = "VALIDATED"


# Canonical limitation statement — deterministic constant.
_DEFAULT_LIMITATION_STATEMENT: str = (
    "This classification is lightweight and illustrative. "
    "Thresholds and rules are engineering/illustrative and have NOT been "
    "scientifically validated. Results must NOT be treated as "
    "publication-grade mineral identification. No USGS or independent "
    "laboratory/mission validation has been performed."
)


@dataclass(frozen=True)
class IIRSScientificGuardrail:
    """Immutable scientific-status qualification for IIRS spectral outputs.

    This contract is adjacent to the existing IIRS result contracts
    (``IIRSMaterialClassificationResult``, ``IIRSSpectralResult``,
    ``SpectralOverlayResult``).  It does not modify those contracts; it
    qualifies them with explicit epistemic metadata.

    Parameters
    ----------
    status:
        The scientific validation status.  Defaults to ``ILLUSTRATIVE``.
    limitation_statement:
        A deterministic, human-readable statement declaring the
        limitations of the current output.
    """

    status: IIRSScientificStatus = IIRSScientificStatus.ILLUSTRATIVE
    limitation_statement: str = _DEFAULT_LIMITATION_STATEMENT

    def __post_init__(self) -> None:
        if not isinstance(self.status, IIRSScientificStatus):
            raise TypeError(
                "status must be an IIRSScientificStatus enum member."
            )
        if not isinstance(self.limitation_statement, str) or not self.limitation_statement.strip():
            raise ValueError(
                "limitation_statement must be a non-empty string."
            )

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_scientifically_validated(self) -> bool:
        """Whether this output has been independently scientifically validated."""
        return self.status == IIRSScientificStatus.VALIDATED

    @property
    def is_publication_grade(self) -> bool:
        """Whether this output may be treated as publication-grade mineral identification."""
        return self.status == IIRSScientificStatus.VALIDATED

    # ------------------------------------------------------------------
    # Deterministic serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the guardrail metadata deterministically."""
        return {
            "status": self.status.value,
            "limitation_statement": self.limitation_statement,
            "is_scientifically_validated": self.is_scientifically_validated,
            "is_publication_grade": self.is_publication_grade,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "IIRSScientificGuardrail":
        """Reconstruct a guardrail from a serialized dictionary.

        Deserialization explicitly maps the status string back to the enum.
        It will NEVER silently upgrade an ILLUSTRATIVE status to VALIDATED.
        An unrecognised status string raises ``ValueError``.
        """
        if not isinstance(payload, dict):
            raise TypeError("IIRSScientificGuardrail payload must be a dictionary.")

        if "status" not in payload:
            raise ValueError("Payload is missing required field: status")

        raw_status = payload["status"]
        try:
            status = IIRSScientificStatus(raw_status)
        except ValueError:
            raise ValueError(
                f"Unrecognised scientific status: {raw_status!r}"
            )

        limitation = payload.get("limitation_statement", _DEFAULT_LIMITATION_STATEMENT)

        return cls(
            status=status,
            limitation_statement=limitation,
        )


def create_default_guardrail() -> IIRSScientificGuardrail:
    """Return the canonical ILLUSTRATIVE guardrail for current Phase 8 outputs.

    This is the only sanctioned factory for guardrail metadata in the
    current pipeline.  It guarantees the status is ``ILLUSTRATIVE`` and
    the limitation statement is the project-approved constant.
    """
    return IIRSScientificGuardrail()
