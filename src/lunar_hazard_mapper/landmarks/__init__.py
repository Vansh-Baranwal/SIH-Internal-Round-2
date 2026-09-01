"""Lunar Landmark Network: geo-database of stable crater geometries for coarse-to-fine localization."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import numpy as np


@dataclass
class Landmark:
    id: str
    name: str
    lat: float           # degrees
    lon: float           # degrees
    radius_km: float     # crater rim radius
    depth_m: float       # approximate depth
    confidence: float    # 0–1 quality score
    tags: List[str] = field(default_factory=list)


@dataclass
class GeolocationResult:
    landmark: Landmark
    distance_km: float
    bearing_deg: float
    confidence: float


_DEFAULT_LANDMARKS = [
    Landmark("LM001", "Tycho",       -43.31, -11.36, 42.7, 4700.0, 0.99, ["prominent", "raycrater"]),
    Landmark("LM002", "Copernicus",   9.62, -20.08, 46.8, 3800.0, 0.98, ["prominent", "raycrater"]),
    Landmark("LM003", "Aristarchus",  23.73, -47.40, 40.0, 3200.0, 0.96, ["prominent", "uvbright"]),
    Landmark("LM004", "Clavius",     -58.40, -14.10, 231.0, 4000.0, 0.95, ["large", "highland"]),
    Landmark("LM005", "Plato",        51.60, -9.30, 101.0, 2400.0, 0.94, ["flatfloor", "prominent"]),
    Landmark("LM006", "Shackleton",  -89.90, 0.00, 21.0, 4200.0, 0.93, ["southpole", "psr"]),
    Landmark("LM007", "Haworth",     -87.50, -5.00, 35.0, 3500.0, 0.88, ["southpole", "psr"]),
    Landmark("LM008", "Nobile",      -85.20, 53.50, 73.0, 4100.0, 0.87, ["southpole"]),
    Landmark("LM009", "De Gerlache", -88.50, -87.80, 32.0, 3900.0, 0.89, ["southpole", "psr"]),
    Landmark("LM010", "Cabeus",      -84.90, -35.50, 98.0, 4900.0, 0.92, ["southpole", "psr", "lcross"]),
]


class LandmarkDatabase:
    """In-memory landmark database with geo-search."""

    def __init__(self, landmarks: Optional[List[Landmark]] = None):
        self._landmarks: List[Landmark] = landmarks if landmarks is not None else list(_DEFAULT_LANDMARKS)
        self._index: Dict[str, Landmark] = {lm.id: lm for lm in self._landmarks}

    def add(self, landmark: Landmark) -> None:
        self._landmarks.append(landmark)
        self._index[landmark.id] = landmark

    def get(self, landmark_id: str) -> Optional[Landmark]:
        return self._index.get(landmark_id)

    def all(self) -> List[Landmark]:
        return list(self._landmarks)

    def search(
        self,
        lat: float,
        lon: float,
        radius_km: float = 500.0,
        tags: Optional[List[str]] = None,
    ) -> List[GeolocationResult]:
        """Find landmarks within radius_km of (lat, lon), optionally filtered by tags."""
        results = []
        for lm in self._landmarks:
            d = _haversine_km(lat, lon, lm.lat, lm.lon)
            if d > radius_km:
                continue
            if tags and not any(t in lm.tags for t in tags):
                continue
            bearing = _bearing(lat, lon, lm.lat, lm.lon)
            results.append(GeolocationResult(lm, d, bearing, lm.confidence))
        results.sort(key=lambda r: r.distance_km)
        return results

    def geolocate(
        self,
        lat: float,
        lon: float,
        radius_km: float = 1000.0,
        top_k: int = 5,
    ) -> List[GeolocationResult]:
        """Return top-k nearest landmarks for coarse-to-fine localization."""
        return self.search(lat, lon, radius_km=radius_km)[:top_k]

    def to_json(self) -> str:
        return json.dumps([asdict(lm) for lm in self._landmarks], indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "LandmarkDatabase":
        data = json.loads(json_str)
        landmarks = [Landmark(**d) for d in data]
        return cls(landmarks)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 1737.4  # Moon radius km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return math.degrees(math.atan2(y, x)) % 360.0
