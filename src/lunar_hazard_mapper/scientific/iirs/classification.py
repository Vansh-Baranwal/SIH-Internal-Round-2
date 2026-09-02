"""Deterministic mineral/material classification from M4-08.5 spectral features.

This module implements an illustrative, lightweight classifier that assigns pixels
to discrete material classes based on spectral feature values. It explicitly uses
illustrative rules rather than published scientific thresholds.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Tuple

import numpy as np

from .features import IIRSSpectralFeatureSet


class MaterialClass(enum.Enum):
    """Supported mineral/material classification categories.

    These represent the deterministic output classes of the M4-08.6 phase.
    """

    ILLMENITE = "ILLMENITE"
    PYROXENE = "PYROXENE"
    OLIVINE = "OLIVINE"
    PLAGIOCLASE_FELDSPAR = "PLAGIOCLASE_FELDSPAR"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, eq=False)
class IIRSMaterialClassificationResult:
    """Deterministic spatial output of the material classification phase.

    This preserves the spatial layout of the input feature set.
    """

    class_map: np.ndarray
    score_map: np.ndarray
    valid_mask: np.ndarray

    def __post_init__(self) -> None:
        class_map = np.asarray(self.class_map)
        score_map = np.asarray(self.score_map)
        valid_mask = np.asarray(self.valid_mask)

        if class_map.ndim != 2 or any(size <= 0 for size in class_map.shape):
            raise ValueError("class_map must be a non-empty 2D array.")
        if score_map.shape != class_map.shape:
            raise ValueError("score_map shape must match class_map.")
        if valid_mask.shape != class_map.shape:
            raise ValueError("valid_mask shape must match class_map.")

        if class_map.dtype != object:
            raise TypeError("class_map must contain MaterialClass enum instances.")
        if not np.issubdtype(score_map.dtype, np.number):
            raise TypeError("score_map must contain numeric values.")
        if valid_mask.dtype != bool:
            raise TypeError("valid_mask must be a boolean array.")

        # Ensure valid mask logic is maintained
        if not np.isfinite(score_map[valid_mask]).all():
            raise ValueError("valid scores must be finite.")
        if not np.isnan(score_map[~valid_mask]).all():
            raise ValueError("invalid scores must be NaN.")
        
        # Verify enum contents
        unique_classes = set(class_map.ravel())
        for cls in unique_classes:
            if not isinstance(cls, MaterialClass):
                raise TypeError("class_map must contain only MaterialClass instances.")
        
        # Ensure invalid pixels are UNCLASSIFIED
        invalid_classes = class_map[~valid_mask]
        if invalid_classes.size > 0 and not all(c == MaterialClass.UNCLASSIFIED for c in invalid_classes):
            raise ValueError("invalid pixels must be UNCLASSIFIED.")

        object.__setattr__(self, "class_map", class_map)
        object.__setattr__(self, "score_map", score_map)
        object.__setattr__(self, "valid_mask", valid_mask)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the classification result deterministically."""
        # Convert enums to their string names for serialization
        class_names = np.vectorize(lambda x: x.name, otypes=[str])(self.class_map)
        return {
            "class_map": class_names.tolist(),
            "score_map": self.score_map.tolist(),
            "valid_mask": self.valid_mask.tolist(),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IIRSMaterialClassificationResult):
            return NotImplemented
        return (
            np.array_equal(self.class_map, other.class_map)
            and np.array_equal(self.score_map, other.score_map, equal_nan=True)
            and np.array_equal(self.valid_mask, other.valid_mask)
        )


@dataclass(frozen=True)
class IllustrativeClassificationRule:
    """An explicit, deterministic mapping from a feature to a material class.
    
    This is strictly an engineering/illustrative configuration, NOT a
    scientifically validated USGS threshold.
    """
    feature_name: str
    target_class: MaterialClass
    min_threshold: float


def classify_materials(
    features: IIRSSpectralFeatureSet,
    rules: Sequence[IllustrativeClassificationRule],
) -> IIRSMaterialClassificationResult:
    """Classify spectral features into material classes using explicit rules.

    The classification process evaluates all provided rules against the 
    corresponding features. For each pixel:
    - If multiple rules exceed their threshold, the one with the highest feature value wins.
    - If there is a tie for the highest value, the pixel is marked UNCLASSIFIED.
    - If no rule exceeds its threshold, or if data is invalid/missing, 
      the pixel is marked UNCLASSIFIED.
    
    The score returned is the feature value that triggered the classification,
    which has explicit semantics as the feature magnitude (NOT a probability).
    """
    if not isinstance(features, IIRSSpectralFeatureSet):
        raise TypeError("features must be an IIRSSpectralFeatureSet instance.")
    
    # Extract shape
    height, width, num_features = features.feature_maps.shape
    
    # Initialize outputs
    class_map = np.full((height, width), MaterialClass.UNCLASSIFIED, dtype=object)
    score_map = np.full((height, width), np.nan, dtype=np.float64)
    # The valid mask for classification requires that the input pixel was valid.
    # We use a 2D valid mask (all(axis=2) since features.valid_mask is 3D).
    base_valid_mask = np.all(features.valid_mask, axis=2)
    valid_mask = np.copy(base_valid_mask)
    
    if not rules:
        # If no rules are provided, everything remains unclassified
        valid_mask[:] = False
        return IIRSMaterialClassificationResult(
            class_map=class_map,
            score_map=score_map,
            valid_mask=valid_mask,
        )
    
    # For tracking the best rule
    best_scores = np.full((height, width), -np.inf, dtype=np.float64)
    
    # Map feature names to indices
    feature_index_map = {name: i for i, name in enumerate(features.feature_names)}
    
    for rule in rules:
        if rule.feature_name not in feature_index_map:
            continue
        
        idx = feature_index_map[rule.feature_name]
        feat_map = features.feature_maps[:, :, idx]
        feat_valid = features.valid_mask[:, :, idx]
        
        # We only consider pixels where this feature is valid
        # and where the base_valid_mask is valid.
        rule_valid = feat_valid & base_valid_mask
        
        # Where does this rule exceed its threshold?
        passes_threshold = feat_map >= rule.min_threshold
        active_mask = rule_valid & passes_threshold
        
        # Check against best score
        is_better = active_mask & (feat_map > best_scores)
        is_tie = active_mask & (feat_map == best_scores)
        
        # Update where better
        class_map[is_better] = rule.target_class
        best_scores[is_better] = feat_map[is_better]
        
        # Where tied (and classes differ), ambiguity -> UNCLASSIFIED
        # We check if the classes differ
        classes_differ = class_map[is_tie] != rule.target_class
        # Create a full 2D mask of the differing ties
        diff_tie_mask = np.zeros_like(is_tie)
        diff_tie_mask[is_tie] = classes_differ
        class_map[diff_tie_mask] = MaterialClass.UNCLASSIFIED

    # Finalize the output
    # Any pixel that was UNCLASSIFIED at the end should have no score and be invalid in the output mask
    is_unclassified = (class_map == MaterialClass.UNCLASSIFIED)
    valid_mask[is_unclassified] = False
    
    score_map[valid_mask] = best_scores[valid_mask]
    
    return IIRSMaterialClassificationResult(
        class_map=class_map,
        score_map=score_map,
        valid_mask=valid_mask,
    )
