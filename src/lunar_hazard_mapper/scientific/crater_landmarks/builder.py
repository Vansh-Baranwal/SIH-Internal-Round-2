"""
Member 4 — Crater Landmark Builder.

Assembles validated CraterLandmark data contract records from pre-computed M4
scientific outputs (CraterCandidate, ExtractedCraterGeometry, DEMProfile,
LandmarkQuality, and SensorAppearance).

This builder acts strictly as an assembly and validation layer. It does NOT
perform detection, geometry extraction, profile generation, or quality scoring.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .detector import CraterCandidate
from .geometry import ExtractedCraterGeometry
from .quality import LandmarkQuality
from .types import (
    CraterCenter,
    CraterGeometry,
    CraterLandmark,
    DEMProfile,
    SensorAppearance,
)


class CraterLandmarkBuilder:
    """
    Deterministic assembly builder for constructing canonical CraterLandmark records.
    """

    @staticmethod
    def build(
        crater_id: str,
        dem_profile: Optional[DEMProfile] = None,
        center: Optional[CraterCenter] = None,
        geometry: Optional[CraterGeometry] = None,
        extracted_geometry: Optional[ExtractedCraterGeometry] = None,
        candidate: Optional[CraterCandidate] = None,
        latitude_deg: Optional[float] = None,
        longitude_deg: Optional[float] = None,
        diameter_m: Optional[float] = None,
        quality: Optional[LandmarkQuality] = None,
        quality_score: Optional[float] = None,
        sensor_appearances: Optional[
            Union[List[SensorAppearance], Dict[str, Any]]
        ] = None,
        detection_method: Optional[str] = None,
        source_type: str = "synthetic",
        label: str = "Simulated Data",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CraterLandmark:
        """
        Assemble a CraterLandmark record from provided scientific components.

        Parameters
        ----------
        crater_id : str
            Unique identifier for the landmark. Must be non-empty.
        dem_profile : DEMProfile, optional
            Extracted radial DEM profile. Can be inferred from `extracted_geometry`.
        center : CraterCenter, optional
            Crater centre coordinates object.
        geometry : CraterGeometry, optional
            Crater structural geometry object.
        extracted_geometry : ExtractedCraterGeometry, optional
            Pre-packaged center, geometry, and DEMProfile extracted from DEM.
        candidate : CraterCandidate, optional
            Detection candidate with local x/y, radius, depth, and confidence.
        latitude_deg : float, optional
            Geographic center latitude in degrees [-90, 90].
        longitude_deg : float, optional
            Geographic center longitude in degrees [-180, 180].
        diameter_m : float, optional
            Crater diameter in metres (> 0).
        quality : LandmarkQuality, optional
            Pre-computed landmark quality assessment object.
        quality_score : float, optional
            Combined quality score [0, 1].
        sensor_appearances : list or dict, optional
            TMC, OHRC, and/or IIRS SensorAppearance records.
        detection_method : str, optional
            Description of detection method used.
        source_type : str
            Provenance source category (default: 'synthetic').
        label : str
            Human-readable label (default: 'Simulated Data').
        metadata : dict, optional
            Arbitrary auxiliary metadata key-values.

        Returns
        -------
        CraterLandmark
            Validated canonical crater landmark record.
        """
        # Resolve inputs from ExtractedCraterGeometry if provided
        if extracted_geometry is not None:
            if not isinstance(extracted_geometry, ExtractedCraterGeometry):
                raise TypeError(
                    "extracted_geometry must be an instance of ExtractedCraterGeometry."
                )
            if center is None:
                center = extracted_geometry.center
            if geometry is None:
                geometry = extracted_geometry.geometry
            if dem_profile is None:
                dem_profile = extracted_geometry.dem_profile

        # Resolve inputs from CraterCandidate if provided
        if candidate is not None:
            if not isinstance(candidate, CraterCandidate):
                raise TypeError(
                    "candidate must be an instance of CraterCandidate."
                )
            if geometry is None and diameter_m is None:
                geometry = CraterGeometry(
                    diameter_m=candidate.diameter_m,
                    depth_m=candidate.depth_m,
                    radius_m=candidate.radius_m,
                )
            if center is None and latitude_deg is None and longitude_deg is None:
                center = CraterCenter(
                    x_m=candidate.center_x_m,
                    y_m=candidate.center_y_m,
                )

        # Validate that required DEMProfile is supplied (do not silently generate or invent)
        if dem_profile is None:
            raise ValueError(
                "Missing required DEMProfile for landmark construction."
            )

        # Construct and validate through CraterLandmark contract
        return CraterLandmark(
            crater_id=crater_id,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            diameter_m=diameter_m,
            center=center,
            geometry=geometry,
            dem_profile=dem_profile,
            quality=quality,
            quality_score=quality_score,
            detection_method=detection_method,
            source_type=source_type,
            label=label,
            sensor_appearances=sensor_appearances,
            metadata=metadata,
        )


def build_landmark(
    crater_id: str,
    dem_profile: Optional[DEMProfile] = None,
    center: Optional[CraterCenter] = None,
    geometry: Optional[CraterGeometry] = None,
    extracted_geometry: Optional[ExtractedCraterGeometry] = None,
    candidate: Optional[CraterCandidate] = None,
    latitude_deg: Optional[float] = None,
    longitude_deg: Optional[float] = None,
    diameter_m: Optional[float] = None,
    quality: Optional[LandmarkQuality] = None,
    quality_score: Optional[float] = None,
    sensor_appearances: Optional[
        Union[List[SensorAppearance], Dict[str, Any]]
    ] = None,
    detection_method: Optional[str] = None,
    source_type: str = "synthetic",
    label: str = "Simulated Data",
    metadata: Optional[Dict[str, Any]] = None,
) -> CraterLandmark:
    """
    Convenience function for building a CraterLandmark record via CraterLandmarkBuilder.
    """
    return CraterLandmarkBuilder.build(
        crater_id=crater_id,
        dem_profile=dem_profile,
        center=center,
        geometry=geometry,
        extracted_geometry=extracted_geometry,
        candidate=candidate,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        diameter_m=diameter_m,
        quality=quality,
        quality_score=quality_score,
        sensor_appearances=sensor_appearances,
        detection_method=detection_method,
        source_type=source_type,
        label=label,
        metadata=metadata,
    )
