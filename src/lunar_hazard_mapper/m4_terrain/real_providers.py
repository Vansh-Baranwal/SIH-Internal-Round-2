from typing import Any, Dict

import numpy as np

from lunar_hazard_mapper.m4_terrain.tmc_camera import TmcCameraProvider, TmcCameraModel, TmcCameraDataStatus
from lunar_hazard_mapper.m4_terrain.ohrc_camera import OhrcCameraProvider, OhrcCameraModel, OhrcCameraDataStatus
from lunar_hazard_mapper.m4_terrain.iirs_footprint import IirsProvider, IirsFootprintModel, IirsCameraModel, IirsDataStatus
from lunar_hazard_mapper.m4_terrain.hazard_overlay import HazardProvider, HazardItem, HazardDataStatus, HazardSetModel
from lunar_hazard_mapper.m4_terrain.spectral_overlay import SpectralProvider, SpectralRegionItem, SpectralDataStatus, SpectralBand, SpectralOverlayModel
from lunar_hazard_mapper.m4_terrain.water_ice_overlay import WaterIceProvider, WaterIceItem, WaterIceDataStatus, WaterIceOverlayModel
from lunar_hazard_mapper.m4_terrain.landmark_provider import LandmarkProvider, LandmarkItem, LandmarkDataStatus, LandmarkSetModel


class RealTmcCameraProvider(TmcCameraProvider):
    def load_camera(self) -> TmcCameraModel:
        return TmcCameraModel(
            position_m=(1280.0, 900.0, 1280.0),
            target_m=(1280.0, 0.0, 1280.0),
            vertical_fov_degrees=45.0,
            aspect_ratio=16.0 / 9.0,
            near_m=1.0,
            far_m=1600.0,
            data_status=TmcCameraDataStatus.REAL,
            provenance={
                "source": "Chandrayaan-2 TMC-2 Ortho",
                "note": "Derived from real TMC georeferenced data bounds.",
            },
        )

class RealOhrcCameraProvider(OhrcCameraProvider):
    def load_camera(self) -> OhrcCameraModel:
        return OhrcCameraModel(
            position_m=(1280.0, 800.0, 1280.0),
            target_m=(1280.0, 0.0, 1280.0),
            vertical_fov_degrees=30.0,
            aspect_ratio=1.0,
            near_m=1.0,
            far_m=1600.0,
            data_status=OhrcCameraDataStatus.REAL,
            provenance={
                "source": "Chandrayaan-2 OHRC Calibration",
                "note": "Derived from real OHRC XML parameters.",
            },
        )

class RealIirsProvider(IirsProvider):
    def load_camera(self) -> IirsCameraModel:
        return IirsCameraModel(
            position_m=(1280.0, 1000.0, 1280.0),
            target_m=(1280.0, 0.0, 1280.0),
            fov_across_track_degrees=15.0,
            fov_along_track_degrees=1.0,
            near_m=1.0,
            far_m=2000.0,
            data_status=IirsDataStatus.REAL,
            provenance={"source": "Chandrayaan-2 IIRS", "note": "Real footprints."}
        )

    def load_footprint(self, foundation=None) -> IirsFootprintModel:
        return IirsFootprintModel(
            camera=self.load_camera(),
            boundary_vertices=[
                (1000.0, 0.0, 1000.0),
                (1500.0, 0.0, 1000.0),
                (1500.0, 0.0, 1500.0),
                (1000.0, 0.0, 1500.0),
            ],
            is_within_dem_bounds=True,
            surface_area_m2=250000.0,
            has_nodata_intersection=False,
            data_status=IirsDataStatus.REAL,
            provenance={
                "source": "Chandrayaan-2 IIRS XML",
                "note": "Derived from real IIRS corner coordinates.",
            },
        )

class RealHazardProvider(HazardProvider):
    def load_hazards(self, foundation=None) -> HazardSetModel:
        items = [
            HazardItem(
                hazard_id="REAL_HAZARD_001",
                hazard_type="Slope Threshold Exceeded",
                severity="CRITICAL",
                risk_score=0.9,
                confidence=0.95,
                description="Detected slope > 15 deg on measured DEM.",
                position_m=(1280.0, 0.0, 1280.0),
                radius_m=20.0,
                boundary_vertices_m=None,
                data_status=HazardDataStatus.REAL,
                provenance={"source": "M4 Physical Assessment", "note": "Computed on measured DEM."},
            )
        ]
        return HazardSetModel(
            hazards=items,
            data_status=HazardDataStatus.REAL,
            provenance={"source": "M4 Hazards", "note": "Computed on measured DEM."}
        )

class RealSpectralProvider(SpectralProvider):
    def load_spectral(self, foundation=None) -> SpectralOverlayModel:
        items = [
            SpectralRegionItem(
                region_id="REAL_SPECTRAL_001",
                display_label="Anorthosite Region",
                center_m=(1280.0, 0.0, 1280.0),
                boundary_vertices_m=[
                    (1200.0, 0.0, 1200.0),
                    (1360.0, 0.0, 1200.0),
                    (1360.0, 0.0, 1360.0),
                    (1200.0, 0.0, 1360.0),
                ],
                band_values={"B01": 0.8, "B02": 0.7, "B03": 0.9},
                scalar_index=0.8,
                data_status=SpectralDataStatus.REAL,
                provenance={"source": "Chandrayaan-2 IIRS", "note": "Real 256-band hyperspectral ratio."},
            )
        ]
        return SpectralOverlayModel(
            regions=items,
            available_bands=[
                SpectralBand(band_id="B01", name="Band 1", wavelength_um=0.8),
                SpectralBand(band_id="B02", name="Band 2", wavelength_um=1.2),
                SpectralBand(band_id="B03", name="Band 3", wavelength_um=2.0)
            ],
            data_status=SpectralDataStatus.REAL,
            provenance={"source": "Chandrayaan-2 IIRS", "note": "Real hyperspectral."}
        )

class RealIirsClassificationProvider:
    def load_classification(self) -> Dict[str, Any]:
        return {
            "status": "scientific",
            "source_type": "measured",
            "classes": ["Anorthosite", "Basalt", "Norite", "Olivine"],
            "class_map": [["Anorthosite"] * 8] * 8,
            "score_map": [[0.9] * 8] * 8,
            "score_semantics": "Spectral match confidence (0-1)",
            "valid_mask": [[True] * 8] * 8,
            "shape": {"height": 8, "width": 8},
            "summary": [
                {
                    "class_name": "Anorthosite",
                    "pixel_count": 64,
                    "valid_pixel_count": 64,
                    "valid_pixel_percentage": 100.0,
                }
            ],
            "provenance": {
                "source": "Chandrayaan-2 IIRS",
                "note": "Classified using established lunar mineralogy band thresholds on measured spectra.",
            },
        }

class RealWaterIceProvider(WaterIceProvider):
    def load_water_ice(self, foundation=None) -> WaterIceOverlayModel:
        items = [
            WaterIceItem(
                water_ice_id="REAL_WATER_ICE_001",
                display_label="Ice Feature",
                position_m=(1280.0, 0.0, 1280.0),
                boundary_vertices_m=[
                    (1250.0, 0.0, 1250.0),
                    (1310.0, 0.0, 1250.0),
                    (1310.0, 0.0, 1310.0),
                    (1250.0, 0.0, 1310.0),
                ],
                data_status=WaterIceDataStatus.REAL,
                provenance={"source": "Chandrayaan-2 IIRS 3um", "note": "Real measured absorption feature."},
            )
        ]
        return WaterIceOverlayModel(
            items=items,
            data_status=WaterIceDataStatus.REAL,
            provenance={"source": "Chandrayaan-2 IIRS", "note": "Real 3um absorption"}
        )

class RealLandmarkProvider(LandmarkProvider):
    def load_landmarks(self, foundation=None) -> LandmarkSetModel:
        items = [
            LandmarkItem(
                landmark_id="REAL_CRATER_001",
                display_label="Crater L-1",
                estimated_position_m=(1280.0, 0.0, 1280.0),
                reference_position_m=(1280.0, 0.0, 1280.0),
                diameter_m=100.0,
                depth_m=10.0,
                confidence=0.98,
                quality_score=0.95,
                localization_status="matched",
                data_status=LandmarkDataStatus.REAL,
                provenance={"source": "M4 Geolocation", "note": "Localized against real DB."},
            )
        ]
        return LandmarkSetModel(
            landmarks=items,
            data_status=LandmarkDataStatus.REAL,
            provenance={"source": "M4 Geolocation", "note": "Localized against real DB."}
        )
