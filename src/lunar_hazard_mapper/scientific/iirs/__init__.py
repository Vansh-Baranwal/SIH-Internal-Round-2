"""Data contracts for Chandrayaan-2 IIRS hyperspectral products."""

from .types import IIRSCube
from .validation import IIRSInputValidationResult, validate_iirs_cube
from .preprocessing import IIRSSpectralPreprocessingResult, preprocess_iirs_cube
from .band_ratio import IIRSBandRatioResult, compute_iirs_band_ratio
from .features import IIRSSpectralFeatureSet, extract_iirs_spectral_features
from .classification import (
    MaterialClass,
    IIRSMaterialClassificationResult,
    IllustrativeClassificationRule,
    classify_materials,
)
from .result import IIRSSpectralResult
from .mapping import IIRSOpticalMappingResult
from .overlay import SpectralOverlayResult, generate_spectral_overlay
from .guardrail import (
    IIRSScientificStatus,
    IIRSScientificGuardrail,
    create_default_guardrail,
)

__all__ = [
    "IIRSCube",
    "IIRSInputValidationResult",
    "validate_iirs_cube",
    "IIRSSpectralPreprocessingResult",
    "preprocess_iirs_cube",
    "IIRSBandRatioResult",
    "compute_iirs_band_ratio",
    "IIRSSpectralFeatureSet",
    "extract_iirs_spectral_features",
    "MaterialClass",
    "IIRSMaterialClassificationResult",
    "IllustrativeClassificationRule",
    "classify_materials",
    "IIRSSpectralResult",
    "IIRSOpticalMappingResult",
    "SpectralOverlayResult",
    "generate_spectral_overlay",
    "IIRSScientificStatus",
    "IIRSScientificGuardrail",
    "create_default_guardrail",
]

