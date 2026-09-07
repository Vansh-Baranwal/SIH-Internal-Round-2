"""
Member 4 — Crater Landmark Network End-to-End Validation.

Validates the complete scientific flow from synthetic terrain DEM through crater detection,
geometry extraction, DEM profile generation, component quality scoring, quality classification,
CraterLandmark construction, CraterLandmarkNetwork storage, retrieval, and RegistrationAnchor selection.

This module acts strictly as a validation and verification harness. It reuses existing M4 scientific
algorithms without duplicating their calculations or storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lunar_hazard_mapper.m3_terrain.synthetic import create_synthetic_terrain

from .builder import CraterLandmarkBuilder
from .detector import CraterDetector
from .geometry import CraterGeometryExtractor
from .matching import RegistrationAnchor, RegistrationAnchorSelector
from .network import CraterLandmarkNetwork
from .profile import DEMProfileGenerator
from .quality import LandmarkQuality
from .retrieval import CraterLandmarkRetriever
from .scoring import (
    classify_quality,
    score_combined,
    score_detection,
    score_geometry,
    score_profile,
)
from .types import CraterLandmark, SensorAppearance


@dataclass(frozen=True)
class E2EPipelineResult:
    """
    Data record summarizing an end-to-end pipeline execution run.

    Parameters
    ----------
    is_valid : bool
        True if all end-to-end pipeline stages and preservation checks pass.
    detected_candidates_count : int
        Number of crater candidates detected.
    extracted_landmarks_count : int
        Number of crater landmarks constructed.
    network_landmarks_count : int
        Number of crater landmarks stored in network.
    retrieved_landmarks_count : int
        Number of landmarks retrieved by query.
    selected_anchors_count : int
        Number of registration anchors selected.
    landmark_ids : list of str
        List of landmark IDs processed.
    selected_anchor_ids : list of str
        List of selected anchor IDs.
    stage_passed : dict
        Boolean flags for individual pipeline stage executions.
    preservation_checks : dict
        Boolean flags for individual field preservation checks.
    errors : list of str
        Descriptive error messages if any validation fails.
    """

    is_valid: bool
    detected_candidates_count: int
    extracted_landmarks_count: int
    network_landmarks_count: int
    retrieved_landmarks_count: int
    selected_anchors_count: int
    landmark_ids: List[str]
    selected_anchor_ids: List[str]
    stage_passed: Dict[str, bool]
    preservation_checks: Dict[str, bool]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic dictionary serialization of E2E validation result.
        """
        return {
            "is_valid": self.is_valid,
            "detected_candidates_count": self.detected_candidates_count,
            "extracted_landmarks_count": self.extracted_landmarks_count,
            "network_landmarks_count": self.network_landmarks_count,
            "retrieved_landmarks_count": self.retrieved_landmarks_count,
            "selected_anchors_count": self.selected_anchors_count,
            "landmark_ids": list(self.landmark_ids),
            "selected_anchor_ids": list(self.selected_anchor_ids),
            "stage_passed": dict(self.stage_passed),
            "preservation_checks": dict(self.preservation_checks),
            "errors": list(self.errors),
        }


class LandmarkE2EValidator:
    """
    End-to-End validator for verifying full pipeline composition and data preservation.
    """

    @staticmethod
    def run_e2e_pipeline(
        crater_id: str = "E2E_CRATER_001",
        dem_size: int = 128,
        pixel_size_m: float = 1.0,
        radius_px: int = 20,
        depth_m: float = 8.0,
        latitude_deg: float = -85.0,
        longitude_deg: float = 15.0,
        min_quality_score: float = 0.80,
    ) -> Tuple[E2EPipelineResult, List[RegistrationAnchor]]:
        """
        Execute the full M4 crater landmark pipeline on synthetic terrain and validate end-to-end integrity.

        Stages executed & verified:
        1. Terrain generation (create_synthetic_terrain)
        2. Crater detection (CraterDetector)
        3. Geometry extraction (CraterGeometryExtractor)
        4. Radial DEM profile generation (DEMProfileGenerator)
        5. Quality scoring & classification (score_detection, score_geometry, score_profile, score_combined, classify_quality)
        6. Landmark construction (CraterLandmarkBuilder)
        7. Network registration (CraterLandmarkNetwork)
        8. Query & retrieval (CraterLandmarkRetriever)
        9. Registration anchor selection (RegistrationAnchorSelector)
        10. Scientific field preservation & determinism validation
        """
        errors: List[str] = []
        stages: Dict[str, bool] = {}
        preservation: Dict[str, bool] = {}

        # 1. Terrain generation
        dem = create_synthetic_terrain(
            kind="crater",
            size=dem_size,
            pixel_size_m=pixel_size_m,
            radius_px=radius_px,
            depth_m=depth_m,
        )
        stages["terrain_generation"] = (dem is not None and dem.shape == (dem_size, dem_size))

        # 2. Detection
        detector = CraterDetector()
        candidates = detector.detect(dem)
        stages["crater_detection"] = (len(candidates) > 0)
        if not stages["crater_detection"]:
            errors.append("No crater candidates detected in synthetic DEM.")
            return (
                E2EPipelineResult(
                    is_valid=False,
                    detected_candidates_count=0,
                    extracted_landmarks_count=0,
                    network_landmarks_count=0,
                    retrieved_landmarks_count=0,
                    selected_anchors_count=0,
                    landmark_ids=[],
                    selected_anchor_ids=[],
                    stage_passed=stages,
                    preservation_checks=preservation,
                    errors=errors,
                ),
                [],
            )

        candidate = candidates[0]

        # 3. Geometry extraction
        geometry_extractor = CraterGeometryExtractor()
        extracted_geo = geometry_extractor.extract(dem=dem, candidate=candidate)
        stages["geometry_extraction"] = (extracted_geo is not None)

        # 4. Profile generation
        profile_generator = DEMProfileGenerator()
        profile = profile_generator.generate(
            dem=dem,
            center_x_m=candidate.center_x_m,
            center_y_m=candidate.center_y_m,
        )
        stages["profile_generation"] = (len(profile.distances_m) >= 2)

        # 5. Quality scoring & classification
        det_score = score_detection(candidate)
        geo_score = score_geometry(candidate=candidate, geometry=extracted_geo.geometry, pixel_size_m=dem.pixel_size_m)
        prof_score = score_profile(profile)
        comb_score = score_combined(det_score, geo_score, prof_score)
        classification = classify_quality(comb_score)

        quality = LandmarkQuality(
            detection_score=det_score,
            geometry_score=geo_score,
            profile_score=prof_score,
            overall_score=comb_score,
            classification=classification,
        )
        stages["quality_scoring"] = (0.0 <= comb_score <= 1.0)

        # 6. Landmark construction
        landmark = CraterLandmarkBuilder.build(
            crater_id=crater_id,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            extracted_geometry=extracted_geo,
            dem_profile=profile,
            quality=quality,
            detection_method="synthetic_depression",
            sensor_appearances=[
                SensorAppearance(sensor_name="TMC", reference=f"tmc_{crater_id}.tif"),
                SensorAppearance(sensor_name="OHRC", reference=f"ohrc_{crater_id}.tif"),
                SensorAppearance(sensor_name="IIRS", reference=f"iirs_{crater_id}.tif"),
            ],
        )
        stages["landmark_construction"] = (landmark.crater_id == crater_id)

        # 7. Network storage
        network = CraterLandmarkNetwork()
        network.add_landmark(landmark)
        stages["network_storage"] = (network.count() == 1 and network.contains(crater_id))

        # 8. Retrieval
        retriever = CraterLandmarkRetriever(network)
        retrieved_lms = retriever.query(min_quality_score=min_quality_score)
        stages["landmark_retrieval"] = isinstance(retrieved_lms, list)

        # 9. Anchor selection
        anchors = RegistrationAnchorSelector.select_anchors(
            landmarks=retrieved_lms,
            min_quality_score=min_quality_score,
        )
        stages["anchor_selection"] = isinstance(anchors, list)

        # 10. Data preservation checks
        if len(anchors) > 0:
            anchor = anchors[0]
            preservation["crater_id_preserved"] = (anchor.crater_id == crater_id == landmark.crater_id)
            preservation["latitude_preserved"] = (anchor.landmark.latitude_deg == latitude_deg)
            preservation["longitude_preserved"] = (anchor.landmark.longitude_deg == longitude_deg)
            preservation["diameter_preserved"] = (anchor.landmark.diameter_m == extracted_geo.geometry.diameter_m)
            preservation["depth_preserved"] = (anchor.landmark.geometry.depth_m == extracted_geo.geometry.depth_m)
            preservation["dem_profile_preserved"] = (anchor.landmark.dem_profile is profile)
            preservation["detection_score_preserved"] = (anchor.landmark.quality.detection_score == det_score)
            preservation["geometry_score_preserved"] = (anchor.landmark.quality.geometry_score == geo_score)
            preservation["profile_score_preserved"] = (anchor.landmark.quality.profile_score == prof_score)
            preservation["combined_quality_preserved"] = (anchor.quality_score == comb_score)
            preservation["classification_preserved"] = (anchor.classification == classification)
            preservation["sensors_preserved"] = (len(anchor.landmark.sensor_appearances) == 3)

        is_valid = all(stages.values()) and (all(preservation.values()) if preservation else True) and (len(errors) == 0)

        res = E2EPipelineResult(
            is_valid=is_valid,
            detected_candidates_count=len(candidates),
            extracted_landmarks_count=1,
            network_landmarks_count=network.count(),
            retrieved_landmarks_count=len(retrieved_lms),
            selected_anchors_count=len(anchors),
            landmark_ids=[landmark.crater_id],
            selected_anchor_ids=[a.crater_id for a in anchors],
            stage_passed=stages,
            preservation_checks=preservation,
            errors=errors,
        )

        return res, anchors


def run_e2e_pipeline_validation(
    crater_id: str = "E2E_CRATER_001",
    dem_size: int = 128,
    pixel_size_m: float = 1.0,
    radius_px: int = 20,
    depth_m: float = 8.0,
    latitude_deg: float = -85.0,
    longitude_deg: float = 15.0,
    min_quality_score: float = 0.80,
) -> Tuple[E2EPipelineResult, List[RegistrationAnchor]]:
    """
    Convenience function for running the M4 end-to-end pipeline validation.
    """
    return LandmarkE2EValidator.run_e2e_pipeline(
        crater_id=crater_id,
        dem_size=dem_size,
        pixel_size_m=pixel_size_m,
        radius_px=radius_px,
        depth_m=depth_m,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        min_quality_score=min_quality_score,
    )
