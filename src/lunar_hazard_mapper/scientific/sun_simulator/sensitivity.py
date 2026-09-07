"""
M4-07.9 — Sun-Position Sensitivity Experiment.

Measures how the existing observation / landmark / matching / registration-anchor
behaviour responds to controlled changes in Sun position, using the SAME fixed
terrain/crater scene.

This is strictly a validation layer: it REUSES the existing M4 stages rather than
re-implementing them:

  - M4-07.6  run_sun_invariance_experiment  -> observation/invariance sensitivity
  - M4-07.7  match_landmarks_across_sun_conditions -> landmark matching sensitivity
  - M4-07.8  select_registration_anchors    -> registration-anchor stability

It does NOT implement map/image registration, warping, transform estimation, or
any later 7.10 functionality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    DEMProfileGenerator,
    SyntheticCraterScene,
    select_registration_anchors,
)

from .invariance import run_sun_invariance_experiment
from .landmark_matching import _build_landmarks, match_landmarks_across_sun_conditions


@dataclass(frozen=True)
class SunSensitivityCondition:
    """Per-condition record for one Sun position in the sensitivity experiment."""

    condition_index: int
    sun: SunState
    is_baseline: bool
    # Observation-level sensitivity (from the existing rendering pipeline)
    image_mean: float
    shadow_fraction: float
    image_diff_from_baseline: float
    shadow_diff_from_baseline: float
    # Detection/geometry invariance (terrain-based, illumination independent)
    detected: bool
    center_error_m: Optional[float]
    diameter_relative_error: Optional[float]
    # Landmark matching result
    matched: bool
    correct: bool  # EVALUATION ONLY (retained ground truth, after matching)
    # Registration-anchor availability
    anchor_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_index": self.condition_index,
            "sun": self.sun.to_dict(),
            "is_baseline": self.is_baseline,
            "image_mean": self.image_mean,
            "shadow_fraction": self.shadow_fraction,
            "image_diff_from_baseline": self.image_diff_from_baseline,
            "shadow_diff_from_baseline": self.shadow_diff_from_baseline,
            "detected": self.detected,
            "center_error_m": self.center_error_m,
            "diameter_relative_error": self.diameter_relative_error,
            "matched": self.matched,
            "correct": self.correct,
            "anchor_count": self.anchor_count,
        }


@dataclass(frozen=True)
class SunSensitivityResult:
    """Aggregate result of the M4-07.9 Sun-position sensitivity experiment."""

    baseline: SunState
    conditions: Tuple[SunSensitivityCondition, ...]
    metrics: Dict[str, Any]
    dem_unchanged: bool
    ground_truth_unchanged: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "num_conditions": len(self.conditions),
            "conditions": [c.to_dict() for c in self.conditions],
            "metrics": dict(self.metrics),
            "dem_unchanged": self.dem_unchanged,
            "ground_truth_unchanged": self.ground_truth_unchanged,
        }

    def summary(self) -> str:
        return (
            f"SunSensitivity(base={self.baseline.as_tuple()}, "
            f"conditions={len(self.conditions)}, metrics={self.metrics})"
        )


def run_sun_position_sensitivity_experiment(
    scene: SyntheticCraterScene,
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]] = None,
    elevation_offsets: Optional[Sequence[float]] = None,
    sun_states: Optional[Sequence[SunState]] = None,
    center_tolerance_m: Optional[float] = None,
    geometry_tolerance_frac: Optional[float] = None,
    match_threshold: Optional[float] = None,
    min_anchor_quality: float = 0.80,
    detector: Optional[CraterDetector] = None,
    geometry_extractor: Optional[CraterGeometryExtractor] = None,
    profile_generator: Optional[DEMProfileGenerator] = None,
) -> SunSensitivityResult:
    """
    Run the Sun-position sensitivity experiment on a fixed crater scene.

    The same terrain/crater scene is used for every Sun position; only
    illumination (SunState) changes. Reuses M4-07.6 (observation/invariance),
    M4-07.7 (landmark matching) and M4-07.8 (registration anchors).
    """
    if not isinstance(scene, SyntheticCraterScene):
        raise TypeError("scene must be a SyntheticCraterScene instance.")
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")
    if not scene.ground_truth:
        raise ValueError("scene must contain at least one crater ground truth.")

    if (sun_states is not None) and (
        azimuth_offsets is not None or elevation_offsets is not None
    ):
        raise ValueError(
            "Provide either sun_states OR azimuth/elevation offsets, not both."
        )

    detector = detector if detector is not None else CraterDetector()
    geometry_extractor = (
        geometry_extractor if geometry_extractor is not None else CraterGeometryExtractor()
    )
    profile_generator = (
        profile_generator if profile_generator is not None else DEMProfileGenerator()
    )

    # Reuse M4-07.6 (observation/invariance) and M4-07.7 (landmark matching).
    invariance = run_sun_invariance_experiment(
        scene,
        baseline,
        azimuth_offsets=azimuth_offsets,
        elevation_offsets=elevation_offsets,
        sun_states=sun_states,
        center_tolerance_m=center_tolerance_m,
        geometry_tolerance_frac=geometry_tolerance_frac,
    )
    matching = match_landmarks_across_sun_conditions(
        scene,
        baseline,
        azimuth_offsets=azimuth_offsets,
        elevation_offsets=elevation_offsets,
        sun_states=sun_states,
        match_threshold=match_threshold,
    )

    # Capture fixed inputs for integrity checks.
    dem_before = np.array(scene.dem.elevation, copy=True)
    ground_truth_before = list(scene.ground_truth)

    # Reuse M4-07.8 (registration anchors). Crater geometry is DEM-derived, so
    # landmark construction and thus anchor selection are identical across Sun
    # positions; anchors are therefore Sun-invariant.
    baseline_landmarks = _build_landmarks(
        scene.dem, detector, geometry_extractor, profile_generator, "BASE"
    )
    anchors = select_registration_anchors(
        baseline_landmarks,
        min_quality_score=min_anchor_quality,
    )
    anchor_ids = [anchor.crater_id for anchor in anchors]

    invariance_conditions = invariance.conditions
    matching_conditions = matching.condition_results

    conditions: List[SunSensitivityCondition] = []
    for index, invariance_condition in enumerate(invariance_conditions):
        is_baseline = index == 0
        matched = True
        correct = True
        if not is_baseline:
            condition_matching = matching_conditions[index - 1]
            if condition_matching.matches:
                first = condition_matching.matches[0]
                matched = first.matched
                correct = first.correct
            else:  # pragma: no cover - guarded by presence of baseline landmarks
                matched = False
                correct = False

        conditions.append(
            SunSensitivityCondition(
                condition_index=index,
                sun=invariance_condition.sun,
                is_baseline=is_baseline,
                image_mean=invariance_condition.image_mean,
                shadow_fraction=invariance_condition.shadow_fraction,
                image_diff_from_baseline=invariance_condition.image_diff_to_baseline,
                shadow_diff_from_baseline=abs(
                    invariance_condition.shadow_fraction
                    - invariance_conditions[0].shadow_fraction
                ),
                detected=invariance_condition.detected,
                center_error_m=invariance_condition.center_error_m,
                diameter_relative_error=invariance_condition.diameter_relative_error,
                matched=matched,
                correct=correct,
                anchor_count=len(anchors),
            )
        )

    # ------------------------------------------------------------------
    # Quantitative sensitivity metrics (derived from actual pipeline outputs)
    # ------------------------------------------------------------------
    variant_conditions = [c for c in conditions if not c.is_baseline]
    image_diffs = [c.image_diff_from_baseline for c in variant_conditions]
    shadow_diffs = [c.shadow_diff_from_baseline for c in variant_conditions]

    max_observation_difference = float(max(image_diffs)) if image_diffs else 0.0
    mean_observation_difference = (
        float(np.mean(image_diffs)) if image_diffs else 0.0
    )
    max_shadow_difference = float(max(shadow_diffs)) if shadow_diffs else 0.0

    observation_is_sensitive = max_observation_difference > 1e-6
    elevation_sensitive = any(
        c.sun.elevation_deg != baseline.elevation_deg
        and c.image_diff_from_baseline > 1e-6
        for c in variant_conditions
    )
    azimuth_sensitive = any(
        c.sun.azimuth_deg != baseline.azimuth_deg
        and c.image_diff_from_baseline > 1e-6
        for c in variant_conditions
    )

    detection_consistency = sum(1 for c in conditions if c.detected) / len(conditions)
    max_center_error = max(
        (c.center_error_m for c in conditions if c.center_error_m is not None),
        default=None,
    )
    max_diameter_relative_error = max(
        (
            c.diameter_relative_error
            for c in conditions
            if c.diameter_relative_error is not None
        ),
        default=None,
    )

    metrics: Dict[str, Any] = {
        "num_conditions": len(conditions),
        "num_variants": len(variant_conditions),
        "max_observation_difference": max_observation_difference,
        "mean_observation_difference": mean_observation_difference,
        "max_shadow_difference": max_shadow_difference,
        "observation_is_sensitive": observation_is_sensitive,
        "elevation_sensitive": elevation_sensitive,
        "azimuth_sensitive": azimuth_sensitive,
        "detection_consistency": float(detection_consistency),
        "max_center_error_m": max_center_error,
        "max_diameter_relative_error": max_diameter_relative_error,
        "match_rate": float(matching.metrics.get("match_rate", 0.0)),
        "anchor_count": len(anchors),
        "anchor_ids": anchor_ids,
    }

    dem_unchanged = bool(np.array_equal(scene.dem.elevation, dem_before))
    ground_truth_unchanged = scene.ground_truth == ground_truth_before

    return SunSensitivityResult(
        baseline=baseline,
        conditions=tuple(conditions),
        metrics=metrics,
        dem_unchanged=dem_unchanged,
        ground_truth_unchanged=ground_truth_unchanged,
    )

