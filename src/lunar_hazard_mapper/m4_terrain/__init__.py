"""
M4-12.1 3D Terrain Foundation public interface.

Re-usable, replaceable terrain data provider abstraction plus the
``TerrainFoundation`` that bridges any provider to the 3D viewer. Downstream
members should import from here rather than reaching into individual files, so
the contract can evolve without breaking callers.
"""

# Import order matters: status -> provider -> foundation -> validation, so each
# submodule's absolute imports resolve against an already-initialized package.
from .status import (
    DATA_STATUS_LABELS,
    SOURCE_SYNTHETIC,
    TerrainDataStatus,
    display_label_for_status,
    status_from_dem,
    status_from_source_type,
)
from .provider import TerrainDataProvider, SyntheticTerrainProvider, DemDataProvider
from .foundation import TerrainFoundation
from .tmc_camera import (
    SyntheticTmcCameraProvider,
    TmcCameraDataStatus,
    TmcCameraModel,
    TmcCameraProvider,
)
from .ohrc_camera import (
    OhrcCameraDataStatus,
    OHRCCameraDataStatus,
    OhrcCameraModel,
    OHRCCameraModel,
    OhrcCameraProvider,
    OHRCCameraProvider,
    SyntheticOhrcCameraProvider,
    SyntheticOHRCameraProvider,
    SyntheticOHRCCameraProvider,
)
from .iirs_footprint import (
    IirsDataStatus,
    IirsCameraDataStatus,
    IIRSCameraDataStatus,
    IirsCameraModel,
    IIRSCameraModel,
    IirsFootprintModel,
    IIRSFootprintModel,
    IirsProvider,
    IIRSProvider,
    SyntheticIirsProvider,
    SyntheticIIRSProvider,
    compute_iirs_footprint,
    intersect_ray_with_dem,
)
from .landmark_provider import (
    LandmarkDataStatus,
    LandmarkItem,
    LandmarkModel,
    LandmarkSetModel,
    LandmarkProvider,
    SyntheticLandmarkProvider,
)
from .sun_control import (
    SunDataStatus,
    SunConfigModel,
    SunScenarioModel,
    sun_direction_from_angles,
    default_synthetic_sun_config,
    default_counterfactual_sun_config,
    default_sun_scenario,
    DEFAULT_AZIMUTH_DEG,
    DEFAULT_ELEVATION_DEG,
    DEFAULT_INTENSITY,
    DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG,
    DEFAULT_COUNTERFACTUAL_ELEVATION_DEG,
    DEFAULT_COUNTERFACTUAL_INTENSITY,
)
from .hazard_overlay import (
    HazardDataStatus,
    HazardSeverity,
    HazardType,
    HazardItem,
    HazardModel,
    HazardSetModel,
    HazardProvider,
    SyntheticHazardProvider,
)
from .spectral_overlay import (
    SpectralDataStatus,
    SpectralBand,
    SpectralRegionItem,
    SpectralModel,
    SpectralOverlayModel,
    SpectralProvider,
    SyntheticSpectralProvider,
)
from .iirs_runtime import SyntheticIirsClassificationProvider
from .water_ice_overlay import (
    WaterIceDataStatus, WaterIceItem, WaterIceRegionItem, WaterIceModel, WaterIceOverlayModel,
    WaterIceProvider, SyntheticWaterIceProvider,
)
from .spatial_sync import (
    LOCAL_UNITS, TERRAIN_GRID_CONVENTION, VIEW_COORDINATE_CONVENTION,
    terrain_grid_to_viewer, viewer_position,
)
from .validation import validate_foundation
from .provenance import (
    DataProvenance,
    ProvenanceMetadata,
    M4DataProvenanceRegistry,
    get_provenance_registry,
)

__all__ = [
    # status / provenance
    "TerrainDataStatus",
    "DATA_STATUS_LABELS",
    "SOURCE_SYNTHETIC",
    "status_from_dem",
    "status_from_source_type",
    "display_label_for_status",
    # centralized provenance registry (Phase 15.10)
    "DataProvenance",
    "ProvenanceMetadata",
    "M4DataProvenanceRegistry",
    "get_provenance_registry",
    # providers
    "TerrainDataProvider",
    "SyntheticTerrainProvider",
    "DemDataProvider",
    # foundation
    "TerrainFoundation",
    "TmcCameraDataStatus",
    "TmcCameraModel",
    "TmcCameraProvider",
    "SyntheticTmcCameraProvider",
    # ohrc camera
    "OhrcCameraDataStatus",
    "OHRCCameraDataStatus",
    "OhrcCameraModel",
    "OHRCCameraModel",
    "OhrcCameraProvider",
    "OHRCCameraProvider",
    "SyntheticOhrcCameraProvider",
    "SyntheticOHRCameraProvider",
    "SyntheticOHRCCameraProvider",
    # iirs footprint
    "IirsDataStatus",
    "IirsCameraDataStatus",
    "IIRSCameraDataStatus",
    "IirsCameraModel",
    "IIRSCameraModel",
    "IirsFootprintModel",
    "IIRSFootprintModel",
    "IirsProvider",
    "IIRSProvider",
    "SyntheticIirsProvider",
    "SyntheticIIRSProvider",
    "compute_iirs_footprint",
    "intersect_ray_with_dem",
    # landmark visualization
    "LandmarkDataStatus",
    "LandmarkItem",
    "LandmarkModel",
    "LandmarkSetModel",
    "LandmarkProvider",
    "SyntheticLandmarkProvider",
    # sun control
    "SunDataStatus",
    "SunConfigModel",
    "SunScenarioModel",
    "sun_direction_from_angles",
    "default_synthetic_sun_config",
    "default_counterfactual_sun_config",
    "default_sun_scenario",
    "DEFAULT_AZIMUTH_DEG",
    "DEFAULT_ELEVATION_DEG",
    "DEFAULT_INTENSITY",
    "DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG",
    "DEFAULT_COUNTERFACTUAL_ELEVATION_DEG",
    "DEFAULT_COUNTERFACTUAL_INTENSITY",
    # hazard overlay
    "HazardDataStatus",
    "HazardSeverity",
    "HazardType",
    "HazardItem",
    "HazardModel",
    "HazardSetModel",
    "HazardProvider",
    "SyntheticHazardProvider",
    # spectral overlay
    "SpectralDataStatus",
    "SpectralBand",
    "SpectralRegionItem",
    "SpectralModel",
    "SpectralOverlayModel",
    "SpectralProvider",
    "SyntheticSpectralProvider",
    "SyntheticIirsClassificationProvider",
    "WaterIceDataStatus",
    "WaterIceItem",
    "WaterIceRegionItem",
    "WaterIceModel",
    "WaterIceOverlayModel",
    "WaterIceProvider",
    "SyntheticWaterIceProvider",
    "LOCAL_UNITS",
    "TERRAIN_GRID_CONVENTION",
    "VIEW_COORDINATE_CONVENTION",
    "terrain_grid_to_viewer",
    "viewer_position",
    # validation
    "validate_foundation",
]
