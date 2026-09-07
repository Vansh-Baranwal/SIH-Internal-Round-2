"""Final consolidated spectral analysis result contract (M4-08.7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Tuple

import numpy as np

from .types import IIRSCube
from .validation import IIRSInputValidationResult
from .preprocessing import IIRSSpectralPreprocessingResult
from .band_ratio import IIRSBandRatioResult
from .features import IIRSSpectralFeatureSet
from .classification import IIRSMaterialClassificationResult, MaterialClass


@dataclass(frozen=True, eq=False)
class IIRSSpectralResult:
    """A stable, read-only scientific contract consolidating IIRS spectral analysis.

    This preserves the original data and all subsequent derivations from M4-08.3
    to M4-08.6 without mutating or recalculating them. It explicitly validates
    spatial shape compatibility across the analytical stack.
    """

    source_cube: IIRSCube
    preprocessing_result: IIRSSpectralPreprocessingResult
    band_ratio_results: Tuple[IIRSBandRatioResult, ...]
    feature_set: IIRSSpectralFeatureSet
    classification_result: IIRSMaterialClassificationResult

    def __post_init__(self) -> None:
        if not isinstance(self.source_cube, IIRSCube):
            raise TypeError("source_cube must be an IIRSCube instance.")
        if not isinstance(self.preprocessing_result, IIRSSpectralPreprocessingResult):
            raise TypeError("preprocessing_result must be an IIRSSpectralPreprocessingResult instance.")
        if not isinstance(self.band_ratio_results, Sequence) or isinstance(self.band_ratio_results, (str, bytes)):
            raise TypeError("band_ratio_results must be a sequence of IIRSBandRatioResult instances.")
        for br in self.band_ratio_results:
            if not isinstance(br, IIRSBandRatioResult):
                raise TypeError("band_ratio_results must contain only IIRSBandRatioResult instances.")
        if not isinstance(self.feature_set, IIRSSpectralFeatureSet):
            raise TypeError("feature_set must be an IIRSSpectralFeatureSet instance.")
        if not isinstance(self.classification_result, IIRSMaterialClassificationResult):
            raise TypeError("classification_result must be an IIRSMaterialClassificationResult instance.")

        # Structural validation: spatial shapes must match exactly
        spatial_shape = self.source_cube.data.shape[:2]

        if np.asarray(self.preprocessing_result.normalized_data).shape[:2] != spatial_shape:
            raise ValueError("preprocessing_result spatial shape differs from source_cube.")

        for br in self.band_ratio_results:
            if br.ratio_map.shape != spatial_shape:
                raise ValueError("band_ratio_results spatial shape differs from source_cube.")
            if br.valid_mask.shape != spatial_shape:
                raise ValueError("band_ratio_results valid_mask shape differs from source_cube.")

        if self.feature_set.feature_maps.shape[:2] != spatial_shape:
            raise ValueError("feature_set spatial shape differs from source_cube.")
        if self.feature_set.valid_mask.shape[:2] != spatial_shape:
            raise ValueError("feature_set valid_mask shape differs from source_cube.")

        if self.classification_result.class_map.shape != spatial_shape:
            raise ValueError("classification_result spatial shape differs from source_cube.")
        if self.classification_result.score_map.shape != spatial_shape:
            raise ValueError("classification_result score_map shape differs from source_cube.")
        if self.classification_result.valid_mask.shape != spatial_shape:
            raise ValueError("classification_result valid_mask shape differs from source_cube.")

        object.__setattr__(self, "band_ratio_results", tuple(self.band_ratio_results))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the consolidated result deterministically."""
        return {
            "source_cube": self.source_cube.to_dict(),
            "preprocessing_result": self.preprocessing_result.to_dict(),
            "band_ratio_results": [br.to_dict() for br in self.band_ratio_results],
            "feature_set": self.feature_set.to_dict(),
            "classification_result": self.classification_result.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "IIRSSpectralResult":
        """Reconstruct the spectral result contract from a serialized payload.
        
        This explicitly rehydrates all dependent contracts following their internal
        numpy conventions.
        """
        if not isinstance(payload, dict):
            raise TypeError("IIRSSpectralResult payload must be a dict.")

        for key in (
            "source_cube",
            "preprocessing_result",
            "band_ratio_results",
            "feature_set",
            "classification_result",
        ):
            if key not in payload:
                raise ValueError(f"Payload is missing required field: {key}")

        source_cube = IIRSCube.from_dict(payload["source_cube"])

        # Rehydrate preprocessing
        pre_payload = payload["preprocessing_result"]
        val_payload = pre_payload["input_validation"]
        validation = IIRSInputValidationResult(
            is_valid=val_payload["is_valid"],
            errors=tuple(val_payload["errors"]),
            warnings=tuple(val_payload["warnings"]),
            checks=dict(val_payload["checks"]),
        )
        preprocessing_result = IIRSSpectralPreprocessingResult(
            normalized_data=np.asarray(pre_payload["normalized_data"]),
            valid_mask=np.asarray(pre_payload["valid_mask"], dtype=bool),
            normalization_min=pre_payload.get("normalization_min"),
            normalization_max=pre_payload.get("normalization_max"),
            input_validation=validation,
            normalization_method=pre_payload.get("normalization_method", "global_minmax"),
        )

        # Rehydrate band ratios
        br_results = []
        for br_payload in payload["band_ratio_results"]:
            br = IIRSBandRatioResult(
                ratio_map=np.asarray(br_payload["ratio_map"]),
                valid_mask=np.asarray(br_payload["valid_mask"], dtype=bool),
                numerator_band=br_payload["numerator_band"],
                denominator_band=br_payload["denominator_band"],
                numerator_wavelength_um=br_payload["numerator_wavelength_um"],
                denominator_wavelength_um=br_payload["denominator_wavelength_um"],
                normalization_method=br_payload["normalization_method"],
            )
            br_results.append(br)

        # Rehydrate feature set
        fs_payload = payload["feature_set"]
        feature_set = IIRSSpectralFeatureSet(
            feature_maps=np.asarray(fs_payload["feature_maps"]),
            valid_mask=np.asarray(fs_payload["valid_mask"], dtype=bool),
            feature_names=tuple(fs_payload["feature_names"]),
            ratio_bands=tuple(tuple(x) for x in fs_payload["ratio_bands"]),
            ratio_wavelengths_um=tuple(tuple(x) for x in fs_payload["ratio_wavelengths_um"]),
            normalization_methods=tuple(fs_payload["normalization_methods"]),
        )

        # Rehydrate classification result
        cls_payload = payload["classification_result"]
        class_map_raw = np.asarray(cls_payload["class_map"])
        class_map = np.empty(class_map_raw.shape, dtype=object)
        
        # Manually map strings back to enum
        for enum_val in MaterialClass:
            class_map[class_map_raw == enum_val.name] = enum_val
            
        classification_result = IIRSMaterialClassificationResult(
            class_map=class_map,
            score_map=np.asarray(cls_payload["score_map"]),
            valid_mask=np.asarray(cls_payload["valid_mask"], dtype=bool),
        )

        return cls(
            source_cube=source_cube,
            preprocessing_result=preprocessing_result,
            band_ratio_results=tuple(br_results),
            feature_set=feature_set,
            classification_result=classification_result,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSSpectralResult):
            return NotImplemented
        return (
            self.source_cube == other.source_cube
            and self.preprocessing_result == other.preprocessing_result
            and self.band_ratio_results == other.band_ratio_results
            and self.feature_set == other.feature_set
            and self.classification_result == other.classification_result
        )
