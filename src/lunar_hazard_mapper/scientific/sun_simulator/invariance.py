"""
M4-07.6 — Sun-Angle Invariance Experiment.

Establishes a controlled experiment that evaluates whether the same synthetic
crater remains consistently detectable/observable when the illumination
SunState changes.

The evaluated input is a CounterfactualObservation produced from the SAME fixed
terrain, so the underlying crater/DEM never changes — only illumination.
Ground truth is retained by the experiment harness and is NOT exposed to the
detector or geometry pipeline.

This module reuses existing M4 components:

  - M4-07.3  generate_counterfactual_sun_states  (counterfactual sun generation)
  - M4-07.5  generate_counterfactual_observation  (observation generation)
  - M4       CraterDetector                       (detection)
  - M4       CraterGeometryExtractor              (geometry extraction)
  - M4       scoring module                       (geometry/landmark quality)

It deliberately does NOT implement landmark matching (7.7), registration (7.8),
sensitivity analysis (7.9), or later validation (7.10).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    SyntheticCraterGroundTruth,
    SyntheticCraterScene,
)
from lunar_hazard_mapper.scientific.crater_landmarks.scoring import (
    classify_quality,
    score_combined,
    score_detection,
    score_geometry,
    score_profile,
)

from .counterfactual import generate_counterfactual_sun_states
from .observation import CounterfactualObservation, generate_counterfactual_observation

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INVALID = "INVALID"

# Established localization tolerance reused from M4-06.10
# (LocalizationAccuracyResult default max_error_m).
DEFAULT_CENTER_TOLERANCE_M = 1.5

# Geometry tolerance: maximum relative difference between the pipeline-estimated
# and retained ground-truth crater diameter. For a radius-18m/depth-10m
# synthetic crater the extractor estimates ~34m against a 36m ground truth
# (relative error ~0.06). 0.25 is a meaningful gate: it tolerates the
# pipeline's inherent estimation bias while still rejecting a geometry that is
# materially wrong (e.g. >25% off).
DEFAULT_GEOMETRY_TOLERANCE_FRAC = 0.25


@dataclass(frozen=True)
class SunInvarianceConditionResult:
    """
    Per-condition result of evaluating one counterfactual Sun state.

    A condition is PASS only when the crater is detected, the estimated centre
    is within ``center_tolerance_m`` of the retained ground truth, and the
    estimated geometry (diameter) is within ``geometry_tolerance_frac``.
    """

    condition_index: int
    sun: SunState
    status: str  # PASS / FAIL / INVALID
    detected: bool
    message: str = ""

    # Detector estimate
    center_x_m: Optional[float] = None
    center_y_m: Optional[float] = None
    estimated_radius_m: Optional[float] = None
    estimated_diameter_m: Optional[float] = None
    estimated_depth_m: Optional[float] = None
    circularity: Optional[float] = None
    confidence: Optional[float] = None

    # Geometry quality (reuses existing M4 scoring)
    geometry_score: Optional[float] = None
    quality_class: Optional[str] = None

    # Deviations from retained ground truth
    center_error_m: Optional[float] = None
    center_error_px: Optional[float] = None
    diameter_relative_error: Optional[float] = None

    # Observation/shadow metrics (illumination behaviour)
    image_mean: float = 0.0
    shadow_fraction: float = 0.0
    image_diff_to_baseline: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic JSON-friendly serialization."""
        return {
            "condition_index": self.condition_index,
            "sun": self.sun.to_dict(),
            "status": self.status,
            "detected": self.detected,
            "message": self.message,
            "center_x_m": self.center_x_m,
            "center_y_m": self.center_y_m,
            "estimated_radius_m": self.estimated_radius_m,
            "estimated_diameter_m": self.estimated_diameter_m,
            "estimated_depth_m": self.estimated_depth_m,
            "circularity": self.circularity,
            "confidence": self.confidence,
            "geometry_score": self.geometry_score,
            "quality_class": self.quality_class,
            "center_error_m": self.center_error_m,
            "center_error_px": self.center_error_px,
            "diameter_relative_error": self.diameter_relative_error,
            "image_mean": self.image_mean,
            "shadow_fraction": self.shadow_fraction,
            "image_diff_to_baseline": self.image_diff_to_baseline,
        }


@dataclass(frozen=True)
class SunInvarianceExperimentResult:
    """
    Overall result of the Sun-angle invariance experiment.

    ``status`` is PASS when every evaluated condition is PASS, FAIL when at
    least one condition failed, and INVALID when at least one condition could
    not be evaluated (e.g. a detector/geometry error).
    """

    baseline: SunState
    conditions: Tuple[SunInvarianceConditionResult, ...]
    evaluated_crater_id: str

    # Consistency aggregates
    detection_consistency: float  # fraction of conditions with a detection
    all_detected: bool
    max_center_error_m: Optional[float]
    max_diameter_relative_error: Optional[float]
    center_estimate_spread_m: float

    status: str  # PASS / FAIL / INVALID
    message: str

    # Tolerances used (documented, not arbitrary)
    center_tolerance_m: float
    geometry_tolerance_frac: float

    # Integrity of fixed inputs
    dem_unchanged: bool
    ground_truth_unchanged: bool

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic JSON-friendly serialization of the whole experiment."""
        return {
            "baseline": self.baseline.to_dict(),
            "evaluated_crater_id": self.evaluated_crater_id,
            "num_conditions": len(self.conditions),
            "conditions": [c.to_dict() for c in self.conditions],
            "detection_consistency": self.detection_consistency,
            "all_detected": self.all_detected,
            "max_center_error_m": self.max_center_error_m,
            "max_diameter_relative_error": self.max_diameter_relative_error,
            "center_estimate_spread_m": self.center_estimate_spread_m,
            "status": self.status,
            "message": self.message,
            "center_tolerance_m": self.center_tolerance_m,
            "geometry_tolerance_frac": self.geometry_tolerance_frac,
            "dem_unchanged": self.dem_unchanged,
            "ground_truth_unchanged": self.ground_truth_unchanged,
        }

    def summary(self) -> str:
        """Concise human-readable summary (also used as a test hook)."""
        return (
            f"SunInvariance({self.evaluated_crater_id}): status={self.status}, "
            f"conditions={len(self.conditions)}, detected={self.all_detected}, "
            f"consistency={self.detection_consistency:.3f}, "
            f"max_center_error_m={self.max_center_error_m}, "
            f"max_diameter_rel_error={self.max_diameter_relative_error}, "
            f"spread_m={self.center_estimate_spread_m:.3f}"
        )


def _max_center_spread(
    centers: Sequence[Tuple[float, float]],
) -> float:
    """Largest pairwise distance (m) among estimated crater centres."""
    if len(centers) < 2:
        return 0.0
    max_dist = 0.0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            dist = hypot(
                centers[i][0] - centers[j][0],
                centers[i][1] - centers[j][1],
            )
            max_dist = max(max_dist, dist)
    return float(max_dist)


def _build_conditions(
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]],
    elevation_offsets: Optional[Sequence[float]],
    sun_states: Optional[Sequence[SunState]],
) -> List[SunState]:
    """
    Build the ordered, de-duplicated list of evaluated conditions.

    The baseline is always the first condition, followed by either the explicit
    ``sun_states`` or the counterfactual states generated via M4-07.3.
    """
    conditions: List[SunState] = [baseline]
    seen = {baseline.as_tuple()}

    if sun_states is not None:
        for state in list(sun_states):
            if not isinstance(state, SunState):
                raise TypeError("sun_states entries must be SunState instances.")
            if state.as_tuple() not in seen:
                conditions.append(state)
                seen.add(state.as_tuple())
    else:
        has_azimuth = bool(azimuth_offsets)
        has_elevation = bool(elevation_offsets)
        if has_azimuth or has_elevation:
            states = generate_counterfactual_sun_states(
                baseline,
                azimuth_offsets=azimuth_offsets,
                elevation_offsets=elevation_offsets,
            )
            for state in states:
                if state.as_tuple() not in seen:
                    conditions.append(state)
                    seen.add(state.as_tuple())

    return conditions


def _evaluate_condition(
    index: int,
    sun: SunState,
    obs: CounterfactualObservation,
    ground_truth: SyntheticCraterGroundTruth,
    pixel_size_m: float,
    baseline_image: np.ndarray,
    center_tolerance_m: float,
    geometry_tolerance_frac: float,
    min_confidence: float,
    detector: CraterDetector,
    extractor: CraterGeometryExtractor,
) -> SunInvarianceConditionResult:
    """Run the detector/geometry pipeline on one observation and score it."""

    image_mean = float(np.mean(obs.image))
    shadow_fraction = float(np.mean(obs.shadow_mask))
    image_diff = (
        float(np.mean(np.abs(obs.image - baseline_image)))
        if index > 0
        else 0.0
    )

    try:
        candidates = detector.detect(obs.dem)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        return SunInvarianceConditionResult(
            condition_index=index,
            sun=sun,
            status=STATUS_INVALID,
            detected=False,
            message=f"detection error: {exc}",
            image_mean=image_mean,
            shadow_fraction=shadow_fraction,
            image_diff_to_baseline=image_diff,
        )

    if not candidates:
        return SunInvarianceConditionResult(
            condition_index=index,
            sun=sun,
            status=STATUS_FAIL,
            detected=False,
            message="crater not detected",
            image_mean=image_mean,
            shadow_fraction=shadow_fraction,
            image_diff_to_baseline=image_diff,
        )

    candidate = candidates[0]

    if candidate.confidence < min_confidence:
        return SunInvarianceConditionResult(
            condition_index=index,
            sun=sun,
            status=STATUS_FAIL,
            detected=False,
            message=(
                f"detection below confidence threshold "
                f"({candidate.confidence:.3f} < {min_confidence:.3f})"
            ),
            center_x_m=candidate.center_x_m,
            center_y_m=candidate.center_y_m,
            estimated_radius_m=candidate.radius_m,
            estimated_diameter_m=candidate.diameter_m,
            estimated_depth_m=candidate.depth_m,
            confidence=candidate.confidence,
            image_mean=image_mean,
            shadow_fraction=shadow_fraction,
            image_diff_to_baseline=image_diff,
        )

    try:
        extracted = extractor.extract(obs.dem, candidate)
        geometry = extracted.geometry
        profile = extracted.dem_profile
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        return SunInvarianceConditionResult(
            condition_index=index,
            sun=sun,
            status=STATUS_INVALID,
            detected=True,
            message=f"geometry extraction error: {exc}",
            center_x_m=candidate.center_x_m,
            center_y_m=candidate.center_y_m,
            estimated_radius_m=candidate.radius_m,
            estimated_diameter_m=candidate.diameter_m,
            estimated_depth_m=candidate.depth_m,
            confidence=candidate.confidence,
            image_mean=image_mean,
            shadow_fraction=shadow_fraction,
            image_diff_to_baseline=image_diff,
        )

    center_error_m = float(
        hypot(
            candidate.center_x_m - ground_truth.center_xy_m[0],
            candidate.center_y_m - ground_truth.center_xy_m[1],
        )
    )
    center_error_px = (
        center_error_m / pixel_size_m if pixel_size_m > 0 else center_error_m
    )

    if ground_truth.diameter_m > 0:
        diameter_relative_error = abs(
            geometry.diameter_m - ground_truth.diameter_m
        ) / ground_truth.diameter_m
    else:  # pragma: no cover - validated GT is always positive
        diameter_relative_error = None

    # Reuse the existing M4 quality-scoring components.
    detection_score = score_detection(candidate)
    geometry_score = float(
        score_geometry(candidate, geometry, pixel_size_m)
    )
    profile_score = score_profile(profile)
    combined_score = score_combined(
        detection_score, geometry_score, profile_score
    )
    quality_class = classify_quality(combined_score)

    if center_error_m > center_tolerance_m:
        status = STATUS_FAIL
        message = (
            f"center error {center_error_m:.3f}m exceeds tolerance "
            f"{center_tolerance_m:.3f}m"
        )
    elif (
        diameter_relative_error is not None
        and diameter_relative_error > geometry_tolerance_frac
    ):
        status = STATUS_FAIL
        message = (
            f"diameter relative error {diameter_relative_error:.3f} exceeds "
            f"tolerance {geometry_tolerance_frac:.3f}"
        )
    else:
        status = STATUS_PASS
        message = "crater detected within center/geometry tolerance"

    return SunInvarianceConditionResult(
        condition_index=index,
        sun=sun,
        status=status,
        detected=True,
        message=message,
        center_x_m=candidate.center_x_m,
        center_y_m=candidate.center_y_m,
        estimated_radius_m=geometry.radius_m,
        estimated_diameter_m=geometry.diameter_m,
        estimated_depth_m=geometry.depth_m,
        circularity=geometry.circularity,
        confidence=candidate.confidence,
        geometry_score=combined_score,
        quality_class=quality_class,
        center_error_m=center_error_m,
        center_error_px=center_error_px,
        diameter_relative_error=diameter_relative_error,
        image_mean=image_mean,
        shadow_fraction=shadow_fraction,
        image_diff_to_baseline=image_diff,
    )


def run_sun_invariance_experiment(
    scene: SyntheticCraterScene,
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]] = None,
    elevation_offsets: Optional[Sequence[float]] = None,
    sun_states: Optional[Sequence[SunState]] = None,
    crater_id: Optional[str] = None,
    center_tolerance_m: Optional[float] = None,
    geometry_tolerance_frac: Optional[float] = None,
    min_confidence: float = 0.0,
    ambient: float = 0.15,
    diffuse: float = 0.85,
    shadow_floor: float = 0.08,
    detector: Optional[CraterDetector] = None,
    geometry_extractor: Optional[CraterGeometryExtractor] = None,
) -> SunInvarianceExperimentResult:
    """
    Run the Sun-angle invariance experiment over a fixed synthetic crater scene.

    The same terrain produces one CounterfactualObservation per Sun condition;
    each observation is run through the existing detector/geometry pipeline and
    compared against independently retained ground truth. The underlying DEM
    and ground truth are never mutated.

    Args:
        scene: SyntheticCraterScene (retains ground truth separately).
        baseline: Baseline SunState (always the first evaluated condition).
        azimuth_offsets: Azimuth offsets for counterfactual states (M4-07.3).
        elevation_offsets: Elevation offsets for counterfactual states (M4-07.3).
        sun_states: Optional explicit sequence of SunStates. Overrides offsets.
        crater_id: Ground-truth crater to evaluate. Defaults to the first.
        center_tolerance_m: Localization tolerance (m). Default 1.5.
        geometry_tolerance_frac: Max relative diameter deviation. Default 0.25.
        min_confidence: Minimum detector confidence for an accepted detection.
        ambient/diffuse/shadow_floor: Observation rendering parameters.
        detector/geometry_extractor: Optional injected pipeline components.

    Returns:
        SunInvarianceExperimentResult.

    Raises:
        TypeError: if ``scene`` or ``baseline`` are not the expected types.
        ValueError: if the configuration is invalid or no counterfactual
                    condition could be established.
    """
    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    if not isinstance(scene, SyntheticCraterScene):
        raise TypeError("scene must be a SyntheticCraterScene instance.")
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")
    if not scene.ground_truth:
        raise ValueError("scene must contain at least one crater ground truth.")

    if crater_id is not None:
        ground_truth = scene.get_ground_truth_by_id(crater_id)
        if ground_truth is None:
            raise ValueError(f"Unknown crater_id: {crater_id!r}.")
    else:
        ground_truth = scene.ground_truth[0]

    if center_tolerance_m is None:
        center_tolerance_m = DEFAULT_CENTER_TOLERANCE_M
    if geometry_tolerance_frac is None:
        geometry_tolerance_frac = DEFAULT_GEOMETRY_TOLERANCE_FRAC
    if center_tolerance_m <= 0:
        raise ValueError("center_tolerance_m must be positive.")
    if not 0.0 < geometry_tolerance_frac <= 1.0:
        raise ValueError("geometry_tolerance_frac must be in (0, 1].")

    # ------------------------------------------------------------------
    # Establish evaluated conditions (baseline + counterfactuals)
    # ------------------------------------------------------------------
    conditions = _build_conditions(
        baseline,
        azimuth_offsets,
        elevation_offsets,
        sun_states,
    )
    if len(conditions) < 2:
        raise ValueError(
            "Experiment requires at least one counterfactual Sun condition in "
            "addition to the baseline."
        )

    detector = detector if detector is not None else CraterDetector()
    extractor = (
        geometry_extractor
        if geometry_extractor is not None
        else CraterGeometryExtractor()
    )
    pixel_size_m = float(scene.dem.pixel_size_m)

    # ------------------------------------------------------------------
    # Capture fixed inputs for integrity checks
    # ------------------------------------------------------------------
    dem_before = np.array(scene.dem.elevation, copy=True)
    ground_truth_before = list(scene.ground_truth)

    # ------------------------------------------------------------------
    # Generate one observation per condition from the SAME terrain
    # ------------------------------------------------------------------
    observations: List[CounterfactualObservation] = []
    for sun in conditions:
        observations.append(
            generate_counterfactual_observation(
                scene.dem,
                sun,
                ambient=ambient,
                diffuse=diffuse,
                shadow_floor=shadow_floor,
            )
        )

    baseline_image = observations[0].image

    # ------------------------------------------------------------------
    # Evaluate each condition
    # ------------------------------------------------------------------
    condition_results = [
        _evaluate_condition(
            index,
            sun,
            obs,
            ground_truth,
            pixel_size_m,
            baseline_image,
            float(center_tolerance_m),
            float(geometry_tolerance_frac),
            float(min_confidence),
            detector,
            extractor,
        )
        for index, (sun, obs) in enumerate(zip(conditions, observations))
    ]

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    num_conditions = len(condition_results)
    detected_count = sum(1 for c in condition_results if c.detected)
    detection_consistency = detected_count / num_conditions
    all_detected = detected_count == num_conditions

    max_center_error = max(
        (c.center_error_m for c in condition_results if c.center_error_m is not None),
        default=None,
    )
    max_diameter_relative_error = max(
        (
            c.diameter_relative_error
            for c in condition_results
            if c.diameter_relative_error is not None
        ),
        default=None,
    )

    detected_centers = [
        (c.center_x_m, c.center_y_m)
        for c in condition_results
        if c.detected and c.center_x_m is not None and c.center_y_m is not None
    ]
    center_spread = _max_center_spread(detected_centers)

    if all(c.status == STATUS_PASS for c in condition_results):
        status = STATUS_PASS
        message = "crater invariance held across all evaluated conditions"
    elif any(c.status == STATUS_INVALID for c in condition_results):
        status = STATUS_INVALID
        message = "one or more conditions could not be evaluated"
    else:
        status = STATUS_FAIL
        message = "crater invariance did not hold across all evaluated conditions"

    # Fixed inputs must be untouched.
    dem_unchanged = bool(np.array_equal(scene.dem.elevation, dem_before))
    ground_truth_unchanged = scene.ground_truth == ground_truth_before

    return SunInvarianceExperimentResult(
        baseline=baseline,
        conditions=tuple(condition_results),
        evaluated_crater_id=ground_truth.crater_id,
        detection_consistency=detection_consistency,
        all_detected=all_detected,
        max_center_error_m=max_center_error,
        max_diameter_relative_error=max_diameter_relative_error,
        center_estimate_spread_m=center_spread,
        status=status,
        message=message,
        center_tolerance_m=float(center_tolerance_m),
        geometry_tolerance_frac=float(geometry_tolerance_frac),
        dem_unchanged=dem_unchanged,
        ground_truth_unchanged=ground_truth_unchanged,
    )
