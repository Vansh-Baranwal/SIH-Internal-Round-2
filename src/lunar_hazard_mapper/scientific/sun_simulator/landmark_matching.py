"""
M4-07.7 — Landmark Matching Across Sun Conditions.

Establishes that the same physical crater landmark can be associated across
observations generated under different Sun conditions, using the existing
CraterLandmark representation and the generic landmark matcher in
``crater_landmarks.matching``.

The experiment:
  1. builds one CounterfactualObservation per Sun condition (M4-07.5),
  2. runs the existing detection / geometry / quality / builder pipeline on
     each observation's DEM to produce CraterLandmark records,
  3. matches baseline landmarks against counterfactual landmarks using the
     existing geometric landmark matcher,
  4. evaluates correctness against retained ground truth (evaluation only).

Ground truth is never consumed by the matcher; it is used only after the match
decision to score whether the correspondence was correct.

This module does NOT implement registration, pose estimation, coordinate
transform, or any later 7.8+ functionality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from lunar_hazard_mapper.scientific.common.types import SunState
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterDetector,
    CraterGeometryExtractor,
    CraterLandmark,
    CraterLandmarkBuilder,
    DEMProfileGenerator,
    LandmarkQuality,
    SyntheticCraterScene,
    classify_quality,
    score_combined,
    score_detection,
    score_geometry,
    score_profile,
)
from lunar_hazard_mapper.scientific.crater_landmarks.matching import (
    DEFAULT_MATCH_THRESHOLD,
    LandmarkMatch,
    match_landmarks,
)

from .counterfactual import generate_counterfactual_sun_states
from .observation import CounterfactualObservation, generate_counterfactual_observation


@dataclass(frozen=True)
class LandmarkMatchRecord:
    """
    One baseline landmark matched against one counterfactual condition.

    ``query_gt_id`` / ``candidate_gt_id`` are EVALUATION-ONLY metadata (assigned
    from retained ground truth AFTER matching). They are never consumed by the
    matcher. ``correct`` is True only when a match occurred AND the matched
    candidate corresponds to the same physical crater as the query.
    """

    query_index: int
    query_id: str
    query_gt_id: str  # EVALUATION ONLY
    candidate_index: int  # -1 if no match
    candidate_id: Optional[str]
    candidate_gt_id: Optional[str]  # EVALUATION ONLY
    similarity: float
    matched: bool  # matcher decision
    correct: bool  # EVALUATION ONLY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_index": self.query_index,
            "query_id": self.query_id,
            "query_gt_id": self.query_gt_id,
            "candidate_index": self.candidate_index,
            "candidate_id": self.candidate_id,
            "candidate_gt_id": self.candidate_gt_id,
            "similarity": float(self.similarity),
            "matched": bool(self.matched),
            "correct": bool(self.correct),
        }


@dataclass(frozen=True)
class SunConditionMatchingResult:
    """
    All baseline-landmark matches against one counterfactual condition.
    """

    condition_index: int
    sun: SunState
    matches: Tuple[LandmarkMatchRecord, ...]

    @property
    def num_attempts(self) -> int:
        return len(self.matches)

    @property
    def num_correct(self) -> int:
        return sum(1 for m in self.matches if m.correct)

    @property
    def num_incorrect(self) -> int:
        return sum(1 for m in self.matches if m.matched and not m.correct)

    @property
    def num_unmatched(self) -> int:
        return sum(1 for m in self.matches if not m.matched)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_index": self.condition_index,
            "sun": self.sun.to_dict(),
            "num_attempts": self.num_attempts,
            "num_correct": self.num_correct,
            "num_incorrect": self.num_incorrect,
            "num_unmatched": self.num_unmatched,
            "matches": [m.to_dict() for m in self.matches],
        }


@dataclass(frozen=True)
class SunLandmarkMatchingResult:
    """
    Aggregate result of the M4-07.7 landmark-matching experiment.

    The contract contains no registration, pose, transform, geographic, or
    coordinate-alignment information—only matching decisions and metrics.
    """

    baseline: SunState
    conditions: Tuple[SunState, ...]
    baseline_landmark_count: int
    condition_landmark_counts: Tuple[int, ...]
    condition_results: Tuple[SunConditionMatchingResult, ...]
    match_threshold: float
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "conditions": [s.to_dict() for s in self.conditions],
            "baseline_landmark_count": self.baseline_landmark_count,
            "condition_landmark_counts": list(self.condition_landmark_counts),
            "condition_results": [cr.to_dict() for cr in self.condition_results],
            "match_threshold": float(self.match_threshold),
            "metrics": dict(self.metrics),
        }

    def summary(self) -> str:
        return (
            f"SunLandmarkMatching(baseline={self.baseline.as_tuple()}, "
            f"conditions={len(self.conditions)}, "
            f"baseline_landmarks={self.baseline_landmark_count}, "
            f"metrics={self.metrics})"
        )


def _build_conditions(
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]],
    elevation_offsets: Optional[Sequence[float]],
    sun_states: Optional[Sequence[SunState]],
) -> List[SunState]:
    """Baseline first, then counterfactual conditions (de-duplicated)."""
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
        if bool(azimuth_offsets) or bool(elevation_offsets):
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


def _build_landmarks(
    dem,
    detector: CraterDetector,
    extractor: CraterGeometryExtractor,
    profile_generator: DEMProfileGenerator,
    id_prefix: str,
) -> List[CraterLandmark]:
    """Run the existing M4 landmark pipeline on a DEM to produce landmarks."""
    landmarks: List[CraterLandmark] = []
    pixel_size_m = float(dem.pixel_size_m)

    for index, candidate in enumerate(detector.detect(dem)):
        extracted_geo = extractor.extract(dem, candidate)
        profile = profile_generator.generate(
            dem,
            candidate.center_x_m,
            candidate.center_y_m,
        )

        detection_score = score_detection(candidate)
        geometry_score = score_geometry(
            candidate,
            extracted_geo.geometry,
            pixel_size_m,
        )
        profile_score = score_profile(profile)
        combined_score = score_combined(
            detection_score, geometry_score, profile_score
        )
        quality = LandmarkQuality(
            detection_score=detection_score,
            geometry_score=geometry_score,
            profile_score=profile_score,
            overall_score=combined_score,
            classification=classify_quality(combined_score),
        )

        landmark = CraterLandmarkBuilder.build(
            crater_id=f"{id_prefix}_{index}",
            extracted_geometry=extracted_geo,
            dem_profile=profile,
            quality=quality,
            detection_method="synthetic_depression",
            source_type="synthetic",
            metadata={"condition_prefix": id_prefix, "pipeline_index": index},
        )
        landmarks.append(landmark)

    return landmarks


def _nearest_ground_truth_id(
    scene: SyntheticCraterScene,
    x_m: float,
    y_m: float,
) -> str:
    """Map a landmark centre to the nearest retained ground-truth crater id."""
    best_id: Optional[str] = None
    best_distance = float("inf")
    for ground_truth in scene.ground_truth:
        distance = hypot(
            x_m - ground_truth.center_xy_m[0],
            y_m - ground_truth.center_xy_m[1],
        )
        if distance < best_distance:
            best_distance = distance
            best_id = ground_truth.crater_id
    if best_id is None:  # pragma: no cover - validated non-empty ground truth
        raise ValueError("scene has no ground truth.")
    return best_id


def match_landmarks_across_sun_conditions(
    scene: SyntheticCraterScene,
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]] = None,
    elevation_offsets: Optional[Sequence[float]] = None,
    sun_states: Optional[Sequence[SunState]] = None,
    match_threshold: Optional[float] = None,
    detector: Optional[CraterDetector] = None,
    geometry_extractor: Optional[CraterGeometryExtractor] = None,
    profile_generator: Optional[DEMProfileGenerator] = None,
) -> SunLandmarkMatchingResult:
    """
    Build landmarks and match the same physical craters across Sun conditions.

    One CounterfactualObservation is generated per Sun condition; the existing
    detection / geometry / quality / landmark-builder pipeline runs on each
    observation's DEM. Baseline landmarks are then matched against each
    counterfactual condition's landmarks using the existing geometric matcher.
    Correctness is evaluated against retained ground truth after matching only.

    Args:
        scene: SyntheticCraterScene (retains ground truth separately).
        baseline: Baseline SunState (always the first evaluated condition).
        azimuth_offsets / elevation_offsets: counterfactual Sun offsets (M4-07.3).
        sun_states: Optional explicit sequence of SunStates (overrides offsets).
        match_threshold: Minimum similarity to count as a match (default 0.85).
        detector / geometry_extractor / profile_generator: optional injected
            pipeline components (defaults reuse the existing implementations).

    Returns:
        SunLandmarkMatchingResult.

    Raises:
        TypeError: if ``scene`` or ``baseline`` are not the expected types.
        ValueError: if the configuration is invalid, no counterfactual
                    condition exists, or no baseline landmark is produced.
    """
    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if not isinstance(scene, SyntheticCraterScene):
        raise TypeError("scene must be a SyntheticCraterScene instance.")
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")
    if not scene.ground_truth:
        raise ValueError("scene must contain at least one crater ground truth.")

    threshold = (
        DEFAULT_MATCH_THRESHOLD if match_threshold is None else float(match_threshold)
    )
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("match_threshold must be between 0.0 and 1.0.")

    # ------------------------------------------------------------------
    # Conditions (baseline + counterfactuals)
    # ------------------------------------------------------------------
    conditions = _build_conditions(
        baseline, azimuth_offsets, elevation_offsets, sun_states
    )
    if len(conditions) < 2:
        raise ValueError(
            "Experiment requires at least one counterfactual Sun condition in "
            "addition to the baseline."
        )

    detector = detector if detector is not None else CraterDetector()
    geometry_extractor = (
        geometry_extractor if geometry_extractor is not None else CraterGeometryExtractor()
    )
    profile_generator = (
        profile_generator
        if profile_generator is not None
        else DEMProfileGenerator()
    )

    # ------------------------------------------------------------------
    # One observation per condition, then the existing landmark pipeline
    # ------------------------------------------------------------------
    condition_landmarks: List[List[CraterLandmark]] = []
    for index, sun in enumerate(conditions):
        observation = generate_counterfactual_observation(scene.dem, sun)
        landmarks = _build_landmarks(
            observation.dem,
            detector,
            geometry_extractor,
            profile_generator,
            f"OBS{index}",
        )
        condition_landmarks.append(landmarks)

    baseline_landmarks = condition_landmarks[0]
    if not baseline_landmarks:
        raise ValueError("No crater landmarks were produced from the baseline observation.")

    # ------------------------------------------------------------------
    # Match baseline landmarks against each counterfactual condition
    # ------------------------------------------------------------------
    condition_results: List[SunConditionMatchingResult] = []
    total_attempts = 0
    total_correct = 0
    total_incorrect = 0
    total_unmatched = 0

    for condition_index in range(1, len(conditions)):
        condition_sun = conditions[condition_index]
        candidate_landmarks = condition_landmarks[condition_index]
        candidate_id_to_index = {
            landmark.crater_id: idx for idx, landmark in enumerate(candidate_landmarks)
        }

        records: List[LandmarkMatchRecord] = []
        for query_index, query_landmark in enumerate(baseline_landmarks):
            query_gt_id = _nearest_ground_truth_id(
                scene, query_landmark.center.x_m, query_landmark.center.y_m
            )

            match = match_landmarks(query_landmark, candidate_landmarks, threshold)

            matched = match.matched
            candidate_index = -1
            candidate_gt_id: Optional[str] = None
            correct = False
            if matched and match.candidate_id is not None:
                candidate_index = candidate_id_to_index.get(match.candidate_id, -1)
                if candidate_index >= 0:
                    candidate_landmark = candidate_landmarks[candidate_index]
                    candidate_gt_id = _nearest_ground_truth_id(
                        scene, candidate_landmark.center.x_m, candidate_landmark.center.y_m
                    )
                    correct = candidate_gt_id == query_gt_id

            record = LandmarkMatchRecord(
                query_index=query_index,
                query_id=query_landmark.crater_id,
                query_gt_id=query_gt_id,
                candidate_index=candidate_index,
                candidate_id=match.candidate_id,
                candidate_gt_id=candidate_gt_id,
                similarity=match.similarity,
                matched=matched,
                correct=correct,
            )
            records.append(record)

            total_attempts += 1
            if correct:
                total_correct += 1
            elif matched and not correct:
                total_incorrect += 1
            else:
                total_unmatched += 1

        condition_results.append(
            SunConditionMatchingResult(
                condition_index=condition_index,
                sun=condition_sun,
                matches=tuple(records),
            )
        )

    match_rate = total_correct / total_attempts if total_attempts > 0 else 0.0

    return SunLandmarkMatchingResult(
        baseline=baseline,
        conditions=tuple(conditions),
        baseline_landmark_count=len(baseline_landmarks),
        condition_landmark_counts=tuple(len(lms) for lms in condition_landmarks),
        condition_results=tuple(condition_results),
        match_threshold=threshold,
        metrics={
            "total_attempts": total_attempts,
            "correct_matches": total_correct,
            "incorrect_matches": total_incorrect,
            "unmatched": total_unmatched,
            "match_rate": float(match_rate),
        },
    )


