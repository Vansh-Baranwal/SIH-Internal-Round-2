"""
Data contracts for the Member 4 Crater Landmark Network.

These contracts are intentionally independent of the
implementations of Members 1, 2, 3 and 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class CraterCenter:
    """
    Geographic and local coordinates of a crater centre.

    Latitude/longitude are optional because synthetic or
    locally generated DEM scenes may not have geographic
    metadata yet.
    """

    latitude_deg: Optional[float] = None
    longitude_deg: Optional[float] = None

    x_m: Optional[float] = None
    y_m: Optional[float] = None

    def __post_init__(self) -> None:

        if self.latitude_deg is not None:
            if not -90.0 <= self.latitude_deg <= 90.0:
                raise ValueError(
                    "Latitude must be between -90 and 90 degrees."
                )

        if self.longitude_deg is not None:
            if not -180.0 <= self.longitude_deg <= 180.0:
                raise ValueError(
                    "Longitude must be between -180 and 180 degrees."
                )


@dataclass(frozen=True)
class CraterGeometry:
    """
    Structural geometry describing a crater.
    """

    diameter_m: float

    depth_m: Optional[float] = None

    radius_m: Optional[float] = None

    circularity: Optional[float] = None

    rim_height_m: Optional[float] = None

    def __post_init__(self) -> None:

        if self.diameter_m <= 0:
            raise ValueError(
                "Crater diameter must be positive."
            )

        if self.radius_m is not None:
            if self.radius_m <= 0:
                raise ValueError(
                    "Crater radius must be positive."
                )

        if self.depth_m is not None:
            if self.depth_m < 0:
                raise ValueError(
                    "Crater depth cannot be negative."
                )

        if self.circularity is not None:
            if not 0.0 <= self.circularity <= 1.0:
                raise ValueError(
                    "Circularity must be between 0 and 1."
                )


@dataclass(frozen=True)
class DEMProfile:
    """
    Radial elevation profile extracted from the DEM.

    distances_m[i] corresponds to elevations_m[i].
    """

    distances_m: List[float]

    elevations_m: List[float]

    sampling_interval_m: Optional[float] = None

    def __post_init__(self) -> None:

        if len(self.distances_m) != len(
            self.elevations_m
        ):
            raise ValueError(
                "DEM profile distances and elevations "
                "must have the same length."
            )

        if len(self.distances_m) < 2:
            raise ValueError(
                "DEM profile requires at least two samples."
            )

        if self.sampling_interval_m is not None:
            if self.sampling_interval_m <= 0:
                raise ValueError(
                    "Sampling interval must be positive."
                )


@dataclass
class SensorAppearance:
    """
    Sensor-specific representation of a crater.

    The actual TMC/OHRC/IIRS representations can be attached
    later during final integration without changing this contract.
    """

    sensor_name: str

    reference: Optional[str] = None

    crop_path: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:

        allowed_sensors = {
            "TMC",
            "OHRC",
            "IIRS",
        }

        if self.sensor_name not in allowed_sensors:
            raise ValueError(
                "sensor_name must be one of "
                "TMC, OHRC, or IIRS."
            )


from .quality import LandmarkQuality


class CraterLandmark:
    """
    Complete M4 crater landmark record.

    Represents a validated landmark in the Crater-Based Lunar Landmark Network.
    Serves as a stable registration anchor with validated geographic coordinates,
    geometry, radial DEM profile, multi-sensor appearance references, and optional
    scientific quality assessment.
    """

    def __init__(
        self,
        crater_id: str,
        latitude_deg: Optional[float] = None,
        longitude_deg: Optional[float] = None,
        diameter_m: Optional[float] = None,
        center: Optional[CraterCenter] = None,
        geometry: Optional[CraterGeometry] = None,
        dem_profile: Optional[DEMProfile] = None,
        quality: Optional[Union[LandmarkQuality, float]] = None,
        quality_score: Optional[float] = None,
        detection_method: Optional[str] = None,
        source_type: str = "synthetic",
        label: str = "Simulated Data",
        sensor_appearances: Optional[
            Union[List[SensorAppearance], Dict[str, Any]]
        ] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Validate and store crater_id
        if not isinstance(crater_id, str) or not crater_id.strip():
            raise ValueError("crater_id cannot be empty.")
        self.crater_id: str = crater_id.strip()

        # Coordinate resolution & validation
        resolved_lat = latitude_deg
        resolved_lon = longitude_deg

        if center is not None:
            if not isinstance(center, CraterCenter):
                raise TypeError("center must be an instance of CraterCenter.")
            if resolved_lat is not None and center.latitude_deg is not None:
                if resolved_lat != center.latitude_deg:
                    raise ValueError(
                        "Conflicting latitude_deg and center.latitude_deg provided."
                    )
            elif resolved_lat is None:
                resolved_lat = center.latitude_deg

            if resolved_lon is not None and center.longitude_deg is not None:
                if resolved_lon != center.longitude_deg:
                    raise ValueError(
                        "Conflicting longitude_deg and center.longitude_deg provided."
                    )
            elif resolved_lon is None:
                resolved_lon = center.longitude_deg

        if resolved_lat is not None:
            if not isinstance(resolved_lat, (int, float)) or not (-90.0 <= float(resolved_lat) <= 90.0):
                raise ValueError("Latitude must be between -90 and 90 degrees.")
            self.latitude_deg: Optional[float] = float(resolved_lat)
        else:
            self.latitude_deg = None

        if resolved_lon is not None:
            if not isinstance(resolved_lon, (int, float)) or not (-180.0 <= float(resolved_lon) <= 180.0):
                raise ValueError("Longitude must be between -180 and 180 degrees.")
            self.longitude_deg: Optional[float] = float(resolved_lon)
        else:
            self.longitude_deg = None

        if center is not None:
            self.center: CraterCenter = center
        else:
            self.center = CraterCenter(
                latitude_deg=self.latitude_deg,
                longitude_deg=self.longitude_deg,
            )

        # Geometry & diameter resolution & validation
        resolved_diam = diameter_m
        if geometry is not None:
            if not isinstance(geometry, CraterGeometry):
                raise TypeError("geometry must be an instance of CraterGeometry.")
            if resolved_diam is not None and resolved_diam != geometry.diameter_m:
                raise ValueError(
                    "Conflicting diameter_m and geometry.diameter_m provided."
                )
            if resolved_diam is None:
                resolved_diam = geometry.diameter_m

        if resolved_diam is None:
            raise ValueError("Crater diameter must be positive.")

        if not isinstance(resolved_diam, (int, float)) or float(resolved_diam) <= 0:
            raise ValueError("Crater diameter must be positive.")

        self.diameter_m: float = float(resolved_diam)

        if geometry is not None:
            self.geometry: CraterGeometry = geometry
        else:
            self.geometry = CraterGeometry(diameter_m=self.diameter_m)

        # DEM Profile validation
        if dem_profile is None:
            raise ValueError("dem_profile is required for CraterLandmark.")
        if not isinstance(dem_profile, DEMProfile):
            raise TypeError("dem_profile must be an instance of DEMProfile.")
        self.dem_profile: DEMProfile = dem_profile

        # Quality assessment resolution & validation
        self.quality: Optional[LandmarkQuality] = None
        self.quality_score: Optional[float] = None

        if quality is not None:
            if isinstance(quality, LandmarkQuality):
                self.quality = quality
                self.quality_score = quality.overall_score
            elif isinstance(quality, (int, float)):
                q_val = float(quality)
                if not (0.0 <= q_val <= 1.0):
                    raise ValueError("quality_score must be between 0 and 1.")
                self.quality_score = q_val
            else:
                raise TypeError(
                    "quality must be an instance of LandmarkQuality or a float score."
                )
        elif quality_score is not None:
            q_val = float(quality_score)
            if not (0.0 <= q_val <= 1.0):
                raise ValueError("quality_score must be between 0 and 1.")
            self.quality_score = q_val

        # Metadata & provenance
        self.detection_method: Optional[str] = detection_method
        self.source_type: str = source_type
        self.label: str = label
        self.metadata: Dict[str, Any] = dict(metadata) if metadata is not None else {}

        # Sensor appearances
        self.sensor_appearances: List[SensorAppearance] = []
        if sensor_appearances is not None:
            if isinstance(sensor_appearances, list):
                for app in sensor_appearances:
                    self.add_sensor_appearance(app)
            elif isinstance(sensor_appearances, dict):
                for sensor_key, app in sensor_appearances.items():
                    if isinstance(app, SensorAppearance):
                        self.add_sensor_appearance(app)
                    elif isinstance(app, str):
                        self.add_sensor_appearance(
                            SensorAppearance(sensor_name=sensor_key, reference=app)
                        )
                    elif isinstance(app, dict):
                        self.add_sensor_appearance(
                            SensorAppearance(sensor_name=sensor_key, **app)
                        )
                    else:
                        raise TypeError(
                            f"Unsupported sensor appearance value for sensor '{sensor_key}'."
                        )
            else:
                raise TypeError(
                    "sensor_appearances must be a list of SensorAppearance or dict."
                )

    def add_sensor_appearance(
        self,
        appearance: SensorAppearance,
    ) -> None:
        """
        Attach a TMC/OHRC/IIRS representation.
        """
        if not isinstance(appearance, SensorAppearance):
            raise TypeError(
                "appearance must be an instance of SensorAppearance."
            )
        self.sensor_appearances.append(appearance)

    def get_sensor_appearance(
        self,
        sensor_name: str,
    ) -> Optional[SensorAppearance]:
        """
        Retrieve a sensor appearance reference by sensor name.
        """
        for app in self.sensor_appearances:
            if app.sensor_name == sensor_name:
                return app
        return None

    def summary(self) -> Dict[str, Any]:
        """
        Return a JSON-friendly summary.
        """
        return {
            "crater_id": self.crater_id,
            "center": {
                "latitude_deg": self.center.latitude_deg,
                "longitude_deg": self.center.longitude_deg,
                "x_m": self.center.x_m,
                "y_m": self.center.y_m,
            },
            "geometry": {
                "diameter_m": self.geometry.diameter_m,
                "depth_m": self.geometry.depth_m,
                "radius_m": self.geometry.radius_m,
                "circularity": self.geometry.circularity,
                "rim_height_m": self.geometry.rim_height_m,
            },
            "dem_profile_samples": len(self.dem_profile.distances_m),
            "quality_score": self.quality_score,
            "detection_method": self.detection_method,
            "source_type": self.source_type,
            "label": self.label,
            "sensor_appearances": [
                appearance.sensor_name
                for appearance in self.sensor_appearances
            ],
            "metadata": self.metadata,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic serialization of the CraterLandmark record.
        """
        return {
            "crater_id": self.crater_id,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "diameter_m": self.diameter_m,
            "center": {
                "latitude_deg": self.center.latitude_deg,
                "longitude_deg": self.center.longitude_deg,
                "x_m": self.center.x_m,
                "y_m": self.center.y_m,
            },
            "geometry": {
                "diameter_m": self.geometry.diameter_m,
                "depth_m": self.geometry.depth_m,
                "radius_m": self.geometry.radius_m,
                "circularity": self.geometry.circularity,
                "rim_height_m": self.geometry.rim_height_m,
            },
            "dem_profile": {
                "distances_m": list(self.dem_profile.distances_m),
                "elevations_m": list(self.dem_profile.elevations_m),
                "sampling_interval_m": self.dem_profile.sampling_interval_m,
            },
            "quality": {
                "detection_score": self.quality.detection_score,
                "geometry_score": self.quality.geometry_score,
                "profile_score": self.quality.profile_score,
                "overall_score": self.quality.overall_score,
                "classification": self.quality.classification,
            }
            if self.quality is not None
            else None,
            "quality_score": self.quality_score,
            "detection_method": self.detection_method,
            "source_type": self.source_type,
            "label": self.label,
            "sensor_appearances": [
                {
                    "sensor_name": app.sensor_name,
                    "reference": app.reference,
                    "crop_path": app.crop_path,
                    "metadata": app.metadata,
                }
                for app in self.sensor_appearances
            ],
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"CraterLandmark("
            f"crater_id='{self.crater_id}', "
            f"lat={self.latitude_deg}, "
            f"lon={self.longitude_deg}, "
            f"diameter_m={self.diameter_m})"
        )