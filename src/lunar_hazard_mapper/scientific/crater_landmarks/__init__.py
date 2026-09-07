"""
Member 4 — Crater Landmark Network.

Stable crater geometry and retrieval infrastructure.
"""

from .types import (
    CraterCenter,
    CraterGeometry,
    DEMProfile,
    SensorAppearance,
    CraterLandmark,
)

from .detector import (
    CraterCandidate,
    CraterDetector,
)

from .geometry import (
    CraterGeometryExtractor,
    ExtractedCraterGeometry,
)

from .profile import (
    DEMProfileGenerator,
)

from .quality import (
    LandmarkQuality,
)

from .scoring import (
    score_detection,
    score_geometry,
    score_profile,
    score_combined,
    classify_quality,
)

from .builder import (
    CraterLandmarkBuilder,
    build_landmark,
)

from .network import (
    CraterLandmarkNetwork,
)

from .retrieval import (
    CraterLandmarkRetriever,
    retrieve_landmark_by_id,
    retrieve_landmarks,
)

from .matching import (
    DEFAULT_MATCH_THRESHOLD,
    LandmarkMatch,
    RegistrationAnchor,
    RegistrationAnchorSelector,
    landmark_signature,
    landmark_similarity,
    match_landmarks,
    select_registration_anchors,
)

from .validation import (
    PipelineValidationResult,
    LandmarkNetworkValidator,
    validate_network_pipeline,
)

from .e2e_validation import (
    E2EPipelineResult,
    LandmarkE2EValidator,
    run_e2e_pipeline_validation,
)

from .database import (
    CraterLandmarkDatabase,
    CraterLandmarkDatabaseRetriever,
)

from .synthetic import (
    LocalizationAccuracyResult,
    SyntheticCraterGroundTruth,
    SyntheticCraterScene,
    generate_synthetic_crater_scene,
    generate_synthetic_scene,
    strip_location_metadata,
)

__all__ = [
    "CraterCenter",
    "CraterGeometry",
    "DEMProfile",
    "SensorAppearance",
    "CraterLandmark",
    "CraterCandidate",
    "CraterDetector",
    "CraterGeometryExtractor",
    "ExtractedCraterGeometry",
    "DEMProfileGenerator",
    "LandmarkQuality",
    "score_detection",
    "score_geometry",
    "score_profile",
    "score_combined",
    "classify_quality",
    "CraterLandmarkBuilder",
    "build_landmark",
    "CraterLandmarkNetwork",
    "CraterLandmarkRetriever",
    "retrieve_landmark_by_id",
    "retrieve_landmarks",
    "RegistrationAnchor",
    "RegistrationAnchorSelector",
    "select_registration_anchors",
    "DEFAULT_MATCH_THRESHOLD",
    "LandmarkMatch",
    "landmark_signature",
    "landmark_similarity",
    "match_landmarks",
    "PipelineValidationResult",
    "LandmarkNetworkValidator",
    "validate_network_pipeline",
    "E2EPipelineResult",
    "LandmarkE2EValidator",
    "run_e2e_pipeline_validation",
    "CraterLandmarkDatabase",
    "CraterLandmarkDatabaseRetriever",
    "LocalizationAccuracyResult",
    "SyntheticCraterGroundTruth",
    "SyntheticCraterScene",
    "generate_synthetic_crater_scene",
    "generate_synthetic_scene",
    "strip_location_metadata",
]