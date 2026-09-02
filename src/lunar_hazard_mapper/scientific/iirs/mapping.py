"""M4-08.8 Registration-to-Optical Mapping layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .result import IIRSSpectralResult
from lunar_hazard_mapper.scientific.common.types import RegistrationResult


@dataclass(frozen=True, eq=False)
class IIRSOpticalMappingResult:
    """Read-only contract mapping IIRS spectral results to an optical footprint.

    This explicitly consumes the established RegistrationResult (produced upstream)
    to mathematically map the IIRS spatial footprint onto an OHRC or TMC image space.
    Per M4-08.8 rules, this contract does NOT perform resampling or raster warping.
    It simply validates and preserves the mapping relationship.
    """

    spectral_result: IIRSSpectralResult
    registration: RegistrationResult

    def __post_init__(self) -> None:
        if not isinstance(self.spectral_result, IIRSSpectralResult):
            raise TypeError("spectral_result must be an IIRSSpectralResult instance.")
        if not isinstance(self.registration, RegistrationResult):
            raise TypeError("registration must be a RegistrationResult instance.")

        # Validate that the registration result contains required spatial mapping data
        if not self.registration.success:
            raise ValueError("Cannot map IIRS data using an unsuccessful registration result.")
            
        if self.registration.transform is None:
            raise ValueError("RegistrationResult must contain a valid transform.")
            
        if not self.registration.spatial_reference:
            raise ValueError("RegistrationResult must contain a target spatial_reference footprint.")

        # Ensure spatial_reference has minimal required footprint dimensions
        if "height" not in self.registration.spatial_reference or "width" not in self.registration.spatial_reference:
            raise ValueError("Target spatial_reference must define height and width.")

    @property
    def target_footprint(self) -> Dict[str, Any]:
        """Expose the expected optical footprint dimensions and metadata."""
        return dict(self.registration.spatial_reference)

    @property
    def valid_mask(self) -> None:
        """Explicit validity mask is deferred to the M4-08.9 overlay layer.
        
        Since resampling is forbidden in M4-08.8, invalid/unmapped regions 
        are inherently preserved by leaving the source spectral result un-warped.
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the mapping contract."""
        return {
            "spectral_result": self.spectral_result.to_dict(),
            # Note: RegistrationResult doesn't strictly define a to_dict in common.types,
            # so we serialize its basic fields here for completeness.
            "registration": {
                "registration_id": self.registration.registration_id,
                "source_sensor": self.registration.source_sensor,
                "reference_sensor": self.registration.reference_sensor,
                "success": self.registration.success,
                "spatial_reference": self.target_footprint,
            }
        }
