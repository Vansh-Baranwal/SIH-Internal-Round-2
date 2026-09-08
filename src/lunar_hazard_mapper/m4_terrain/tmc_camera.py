"""M4-12.3 replaceable TMC camera/frustum data contract.

No authoritative TMC camera pose or calibration is available in this repository.
The default provider therefore exposes only an explicitly labelled synthetic
development visualization.  A future provider with real metadata can implement
the same ``TmcCameraProvider`` contract; the 3D viewer remains unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Tuple


class TmcCameraDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    REAL = "real"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TmcCameraModel:
    """Camera parameters expressed in the established Three.js render axes.

    ``position_m`` and ``target_m`` use X=local East, Y=local Up,
    Z=local North, all in metres.  They are visualization pose fields, not an
    assertion of a lunar CRS, spacecraft pose, observation time, or coverage.
    """

    position_m: Tuple[float, float, float]
    target_m: Tuple[float, float, float]
    vertical_fov_degrees: float
    aspect_ratio: float
    near_m: float
    far_m: float
    data_status: TmcCameraDataStatus
    provenance: Dict[str, Any]

    def __post_init__(self) -> None:
        if not 0 < self.vertical_fov_degrees < 180:
            raise ValueError("vertical_fov_degrees must be in (0, 180).")
        if self.aspect_ratio <= 0 or self.near_m <= 0 or self.far_m <= self.near_m:
            raise ValueError("Camera aspect ratio and clip planes are invalid.")
        if len(self.position_m) != 3 or len(self.target_m) != 3:
            raise ValueError("Camera position and target must have three coordinates.")

    @property
    def display_label(self) -> str:
        if self.data_status is TmcCameraDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT CAMERA GEOMETRY"
        if self.data_status is TmcCameraDataStatus.REAL:
            return "TMC-2 Sensor Telemetry"
        return "TMC CAMERA METADATA UNAVAILABLE"

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "position_m": {"x": self.position_m[0], "y": self.position_m[1], "z": self.position_m[2]},
            "target_m": {"x": self.target_m[0], "y": self.target_m[1], "z": self.target_m[2]},
            "vertical_fov_degrees": self.vertical_fov_degrees,
            "aspect_ratio": self.aspect_ratio,
            "near_m": self.near_m,
            "far_m": self.far_m,
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
            },
            "provenance": dict(self.provenance),
        }


class TmcCameraProvider(ABC):
    """Provider boundary between TMC metadata and the frustum renderer."""

    @abstractmethod
    def load_camera(self) -> TmcCameraModel:
        raise NotImplementedError


class SyntheticTmcCameraProvider(TmcCameraProvider):
    """Isolated, non-scientific development configuration for the 3D viewer."""

    def load_camera(self) -> TmcCameraModel:
        return TmcCameraModel(
            position_m=(1280.0, 900.0, 1280.0),
            target_m=(1280.0, 0.0, 1280.0),
            vertical_fov_degrees=45.0,
            aspect_ratio=16.0 / 9.0,
            near_m=1.0,
            far_m=1600.0,
            data_status=TmcCameraDataStatus.SYNTHETIC,
            provenance={
                "source": "m4_12_3_synthetic_development_configuration",
                "note": (
                    "Synthetic development visualization only. Values are not real "
                    "TMC calibration, spacecraft pose, observation metadata, or "
                    "proof of observation coverage."
                ),
            },
        )
