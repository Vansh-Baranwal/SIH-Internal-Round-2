"""
Member 4 — Crater Landmark Database / Index.

Provides local persistent storage, indexing, JSON persistence, and reconstruction capability
for CraterLandmark records, building upon the in-memory CraterLandmarkNetwork.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .builder import CraterLandmarkBuilder
from .network import CraterLandmarkNetwork
from .quality import LandmarkQuality
from .types import (
    CraterCenter,
    CraterGeometry,
    CraterLandmark,
    DEMProfile,
    SensorAppearance,
)


class CraterLandmarkDatabase:
    """
    Local persistent database and index layer for CraterLandmark records.

    Integrates with CraterLandmarkNetwork while providing file/JSON persistence,
    crater_id indexing, spatial bounding-box indexing, deterministic serialization,
    and full scientific landmark reconstruction.
    """

    def __init__(
        self,
        network: Optional[CraterLandmarkNetwork] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self._network: CraterLandmarkNetwork = (
            network if network is not None else CraterLandmarkNetwork()
        )
        self._db_path: Optional[Path] = Path(db_path) if db_path is not None else None

        if self._db_path is not None and self._db_path.exists():
            self.load(self._db_path)

    @property
    def network(self) -> CraterLandmarkNetwork:
        """Return the underlying in-memory network."""
        return self._network

    @property
    def db_path(self) -> Optional[Path]:
        """Return the configured file path for database persistence."""
        return self._db_path

    def add(self, landmark: CraterLandmark) -> None:
        """
        Add a valid CraterLandmark to the database and index.

        Raises
        ------
        TypeError
            If landmark is not an instance of CraterLandmark.
        ValueError
            If a landmark with the same crater_id already exists.
        """
        if not isinstance(landmark, CraterLandmark):
            raise TypeError("landmark must be an instance of CraterLandmark.")
        self._network.add_landmark(landmark)

    def get(self, crater_id: str) -> Optional[CraterLandmark]:
        """
        Retrieve a landmark by crater_id. Returns None if not found.
        """
        if not isinstance(crater_id, str) or not crater_id.strip():
            return None
        return self._network.get_landmark(crater_id.strip())

    def contains(self, crater_id: str) -> bool:
        """
        Check if a landmark with crater_id exists in the database.
        """
        if not isinstance(crater_id, str) or not crater_id.strip():
            return False
        return self._network.contains(crater_id.strip())

    def remove(self, crater_id: str) -> Optional[CraterLandmark]:
        """
        Remove and return a landmark by crater_id. Returns None if not present.
        """
        if not isinstance(crater_id, str) or not crater_id.strip():
            return None
        return self._network.remove_landmark(crater_id.strip())

    def count(self) -> int:
        """
        Return the total number of stored landmarks.
        """
        return self._network.count()

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, crater_id: str) -> bool:
        return self.contains(crater_id)

    def clear(self) -> None:
        """
        Clear all landmarks from the database.
        """
        self._network.clear()

    def list(
        self,
        min_quality_score: Optional[float] = None,
        classification: Optional[str] = None,
    ) -> List[CraterLandmark]:
        """
        Return stored landmarks in deterministic alphabetical order by crater_id.
        """
        return self._network.landmarks(
            min_quality_score=min_quality_score,
            classification=classification,
        )

    def query(
        self,
        min_quality_score: Optional[float] = None,
        classification: Optional[str] = None,
        min_latitude_deg: Optional[float] = None,
        max_latitude_deg: Optional[float] = None,
        min_longitude_deg: Optional[float] = None,
        max_longitude_deg: Optional[float] = None,
        min_diameter_m: Optional[float] = None,
        max_diameter_m: Optional[float] = None,
    ) -> List[CraterLandmark]:
        """
        Query stored landmarks with quality and geographic filters while preserving
        deterministic alphabetical ordering by crater_id.
        """
        if min_quality_score is not None:
            if not isinstance(min_quality_score, (int, float)) or not (0.0 <= float(min_quality_score) <= 1.0):
                raise ValueError("min_quality_score must be between 0.0 and 1.0.")

        if classification is not None:
            allowed = {"HIGH", "MEDIUM", "LOW"}
            if not isinstance(classification, str) or classification.upper() not in allowed:
                raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")
            classification = classification.upper()

        if min_diameter_m is not None:
            if not isinstance(min_diameter_m, (int, float)) or float(min_diameter_m) <= 0:
                raise ValueError("min_diameter_m must be positive.")

        if max_diameter_m is not None:
            if not isinstance(max_diameter_m, (int, float)) or float(max_diameter_m) <= 0:
                raise ValueError("max_diameter_m must be positive.")

        if min_diameter_m is not None and max_diameter_m is not None and float(min_diameter_m) > float(max_diameter_m):
            raise ValueError("min_diameter_m cannot be greater than max_diameter_m.")

        if any(bound is not None for bound in (min_latitude_deg, max_latitude_deg, min_longitude_deg, max_longitude_deg)):
            if not all(bound is not None for bound in (min_latitude_deg, max_latitude_deg, min_longitude_deg, max_longitude_deg)):
                raise ValueError("Latitude and longitude bounds must be provided as complete pairs.")
            result = self.query_bounding_box(
                min_latitude_deg=float(min_latitude_deg),
                max_latitude_deg=float(max_latitude_deg),
                min_longitude_deg=float(min_longitude_deg),
                max_longitude_deg=float(max_longitude_deg),
            )
        else:
            result = self.list(
                min_quality_score=min_quality_score,
                classification=classification,
            )

        filtered: List[CraterLandmark] = []
        for lm in result:
            if min_quality_score is not None and (lm.quality_score is None or lm.quality_score < float(min_quality_score)):
                continue
            if classification is not None:
                lm_cls = lm.quality.classification if lm.quality is not None else None
                if lm_cls != classification:
                    continue
            if min_diameter_m is not None and lm.diameter_m < float(min_diameter_m):
                continue
            if max_diameter_m is not None and lm.diameter_m > float(max_diameter_m):
                continue
            filtered.append(lm)

        return filtered

    def query_bounding_box(
        self,
        min_latitude_deg: float,
        max_latitude_deg: float,
        min_longitude_deg: float,
        max_longitude_deg: float,
    ) -> List[CraterLandmark]:
        """
        Retrieve stored landmarks within a geographic bounding box [min_lat, max_lat] x [min_lon, max_lon].
        Returns landmarks sorted deterministically by crater_id.
        """
        if not (-90.0 <= min_latitude_deg <= 90.0) or not (-90.0 <= max_latitude_deg <= 90.0):
            raise ValueError("Latitude bounds must be between -90 and 90 degrees.")
        if min_latitude_deg > max_latitude_deg:
            raise ValueError("min_latitude_deg cannot be greater than max_latitude_deg.")

        if not (-180.0 <= min_longitude_deg <= 180.0) or not (-180.0 <= max_longitude_deg <= 180.0):
            raise ValueError("Longitude bounds must be between -180 and 180 degrees.")
        if min_longitude_deg > max_longitude_deg:
            raise ValueError("min_longitude_deg cannot be greater than max_longitude_deg.")

        result: List[CraterLandmark] = []
        for lm in self.list():
            if lm.latitude_deg is not None and lm.longitude_deg is not None:
                if (min_latitude_deg <= lm.latitude_deg <= max_latitude_deg) and (
                    min_longitude_deg <= lm.longitude_deg <= max_longitude_deg
                ):
                    result.append(lm)

        return result

    def to_dict(self) -> Dict[str, Any]:
        """
        Deterministic dictionary serialization of the database state.
        """
        return {
            "database_version": "1.0",
            "total_landmarks": self.count(),
            "landmarks": {
                lm.crater_id: lm.to_dict() for lm in self.list()
            },
        }

    def save(self, filepath: Optional[Union[str, Path]] = None) -> Path:
        """
        Persist the database to a JSON file.

        Parameters
        ----------
        filepath : str or Path, optional
            Destination file path. Uses self._db_path if not supplied.

        Returns
        -------
        Path
            Path to the saved JSON file.
        """
        target_path = Path(filepath) if filepath is not None else self._db_path
        if target_path is None:
            raise ValueError("No filepath specified for save operation.")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        self._db_path = target_path
        return target_path

    def load(self, filepath: Optional[Union[str, Path]] = None) -> None:
        """
        Load the database from a JSON file and reconstruct all CraterLandmark objects.

        Parameters
        ----------
        filepath : str or Path, optional
            Source file path. Uses self._db_path if not supplied.
        """
        source_path = Path(filepath) if filepath is not None else self._db_path
        if source_path is None:
            raise ValueError("No filepath specified for load operation.")

        if not source_path.exists():
            raise FileNotFoundError(f"Database file not found: {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "landmarks" not in data:
            raise ValueError("Invalid database format: missing 'landmarks' dictionary.")

        self.clear()
        landmarks_dict = data["landmarks"]

        # Sort crater_ids to ensure deterministic insertion order during load
        for cid in sorted(landmarks_dict.keys()):
            lm_data = landmarks_dict[cid]
            lm = self._reconstruct_landmark(lm_data)
            self._network.add_landmark(lm)

        self._db_path = source_path

    @staticmethod
    def _reconstruct_landmark(lm_data: Dict[str, Any]) -> CraterLandmark:
        """
        Reconstruct a valid CraterLandmark from a serialized dictionary representation.
        """
        crater_id = lm_data["crater_id"]
        lat = lm_data.get("latitude_deg")
        lon = lm_data.get("longitude_deg")
        diam = lm_data.get("diameter_m")

        # Center reconstruction
        center_dict = lm_data.get("center", {})
        center = CraterCenter(
            latitude_deg=center_dict.get("latitude_deg", lat),
            longitude_deg=center_dict.get("longitude_deg", lon),
            x_m=center_dict.get("x_m"),
            y_m=center_dict.get("y_m"),
        )

        # Geometry reconstruction
        geo_dict = lm_data.get("geometry", {})
        geometry = CraterGeometry(
            diameter_m=geo_dict.get("diameter_m", diam),
            depth_m=geo_dict.get("depth_m"),
            radius_m=geo_dict.get("radius_m"),
            circularity=geo_dict.get("circularity"),
            rim_height_m=geo_dict.get("rim_height_m"),
        )

        # DEM Profile reconstruction
        profile_dict = lm_data.get("dem_profile", {})
        dem_profile = DEMProfile(
            distances_m=profile_dict.get("distances_m", [0.0, 1.0]),
            elevations_m=profile_dict.get("elevations_m", [0.0, 0.0]),
            sampling_interval_m=profile_dict.get("sampling_interval_m"),
        )

        # Quality reconstruction
        quality_dict = lm_data.get("quality")
        quality = None
        if quality_dict is not None and isinstance(quality_dict, dict):
            quality = LandmarkQuality(
                detection_score=quality_dict.get("detection_score", 1.0),
                geometry_score=quality_dict.get("geometry_score", 1.0),
                profile_score=quality_dict.get("profile_score", 1.0),
                overall_score=quality_dict.get("overall_score", 1.0),
                classification=quality_dict.get("classification", "HIGH"),
            )

        quality_score = lm_data.get("quality_score")

        # Sensor appearances reconstruction
        sensor_apps_data = lm_data.get("sensor_appearances", [])
        sensor_appearances: List[SensorAppearance] = []
        for app in sensor_apps_data:
            if isinstance(app, dict):
                sensor_appearances.append(
                    SensorAppearance(
                        sensor_name=app.get("sensor_name", "TMC"),
                        reference=app.get("reference"),
                        crop_path=app.get("crop_path"),
                        metadata=app.get("metadata", {}),
                    )
                )

        return CraterLandmarkBuilder.build(
            crater_id=crater_id,
            latitude_deg=lat,
            longitude_deg=lon,
            diameter_m=diam,
            center=center,
            geometry=geometry,
            dem_profile=dem_profile,
            quality=quality,
            quality_score=quality_score,
            detection_method=lm_data.get("detection_method"),
            source_type=lm_data.get("source_type", "synthetic"),
            label=lm_data.get("label", "Simulated Data"),
            sensor_appearances=sensor_appearances,
            metadata=lm_data.get("metadata", {}),
        )

    def summary(self) -> Dict[str, Any]:
        """
        Return a deterministic summary of database contents.
        """
        return {
            "database_file": str(self._db_path) if self._db_path else None,
            "total_landmarks": self.count(),
            "network_summary": self._network.summary(),
        }

    def __repr__(self) -> str:
        path_str = f", path='{self._db_path}'" if self._db_path else ""
        return f"CraterLandmarkDatabase(count={self.count()}{path_str})"


class CraterLandmarkDatabaseRetriever:
    """
    Database-backed retrieval layer that wraps CraterLandmarkDatabase while preserving
    deterministic ordering and returning the original stored CraterLandmark objects.
    """

    def __init__(self, database: CraterLandmarkDatabase) -> None:
        if not isinstance(database, CraterLandmarkDatabase):
            raise TypeError("database must be an instance of CraterLandmarkDatabase.")
        self._database = database

    @property
    def database(self) -> CraterLandmarkDatabase:
        return self._database

    def get_by_id(self, crater_id: str) -> Optional[CraterLandmark]:
        return self._database.get(crater_id)

    def get_all(self) -> List[CraterLandmark]:
        return self._database.list()

    def get_by_classification(self, classification: str) -> List[CraterLandmark]:
        allowed = {"HIGH", "MEDIUM", "LOW"}
        if not isinstance(classification, str) or classification.upper() not in allowed:
            raise ValueError("classification must be one of 'HIGH', 'MEDIUM', or 'LOW'.")
        return self._database.list(classification=classification.upper())

    def get_by_min_quality(self, min_score: float) -> List[CraterLandmark]:
        if not isinstance(min_score, (int, float)) or not (0.0 <= float(min_score) <= 1.0):
            raise ValueError("min_score must be a float between 0.0 and 1.0.")
        return self._database.list(min_quality_score=float(min_score))

    def query(
        self,
        min_quality_score: Optional[float] = None,
        classification: Optional[str] = None,
        min_latitude_deg: Optional[float] = None,
        max_latitude_deg: Optional[float] = None,
        min_longitude_deg: Optional[float] = None,
        max_longitude_deg: Optional[float] = None,
        min_diameter_m: Optional[float] = None,
        max_diameter_m: Optional[float] = None,
    ) -> List[CraterLandmark]:
        return self._database.query(
            min_quality_score=min_quality_score,
            classification=classification,
            min_latitude_deg=min_latitude_deg,
            max_latitude_deg=max_latitude_deg,
            min_longitude_deg=min_longitude_deg,
            max_longitude_deg=max_longitude_deg,
            min_diameter_m=min_diameter_m,
            max_diameter_m=max_diameter_m,
        )

    def query_bounding_box(
        self,
        min_latitude_deg: float,
        max_latitude_deg: float,
        min_longitude_deg: float,
        max_longitude_deg: float,
    ) -> List[CraterLandmark]:
        return self._database.query_bounding_box(
            min_latitude_deg=min_latitude_deg,
            max_latitude_deg=max_latitude_deg,
            min_longitude_deg=min_longitude_deg,
            max_longitude_deg=max_longitude_deg,
        )
