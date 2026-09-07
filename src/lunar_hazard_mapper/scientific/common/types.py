"""
Shared data types for Member 4 scientific modules.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SunState:
    """Immutable solar illumination state used by the Sun Simulator."""

    azimuth_deg: float
    elevation_deg: float

    def __post_init__(self) -> None:
        azimuth = float(self.azimuth_deg)
        elevation = float(self.elevation_deg)

        if not isinstance(self.azimuth_deg, (int, float)) or isinstance(self.azimuth_deg, bool):
            raise TypeError("Sun azimuth must be a numeric value in degrees.")

        if not isinstance(self.elevation_deg, (int, float)) or isinstance(self.elevation_deg, bool):
            raise TypeError("Sun elevation must be a numeric value in degrees.")

        if not 0.0 <= azimuth < 360.0:
            raise ValueError(
                "Sun azimuth must be in [0, 360) degrees."
            )

        if not 0.0 <= elevation <= 90.0:
            raise ValueError(
                "Sun elevation must be in [0, 90] degrees."
            )

        object.__setattr__(self, "azimuth_deg", azimuth)
        object.__setattr__(self, "elevation_deg", elevation)

    def to_dict(self) -> Dict[str, float]:
        """Deterministic dictionary serialization for the Sun state."""
        return {
            "azimuth_deg": float(self.azimuth_deg),
            "elevation_deg": float(self.elevation_deg),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SunState":
        """Reconstruct a SunState from a deterministic serialized dictionary."""
        if not isinstance(payload, dict):
            raise TypeError("SunState payload must be a dictionary.")

        if "azimuth_deg" not in payload or "elevation_deg" not in payload:
            raise ValueError("SunState payload must include azimuth_deg and elevation_deg.")

        return cls(
            azimuth_deg=payload["azimuth_deg"],
            elevation_deg=payload["elevation_deg"],
        )

    def as_tuple(self) -> tuple[float, float]:
        """Stable tuple representation matching the deterministic contract."""
        return (float(self.azimuth_deg), float(self.elevation_deg))


@dataclass
class RegistrationMetrics:
    """Metrics produced by image registration."""

    rmse_px: Optional[float] = None
    inlier_count: Optional[int] = None
    inlier_ratio: Optional[float] = None

    def __post_init__(self) -> None:

        if self.rmse_px is not None and self.rmse_px < 0:
            raise ValueError(
                "RMSE cannot be negative."
            )

        if self.inlier_count is not None and self.inlier_count < 0:
            raise ValueError(
                "Inlier count cannot be negative."
            )

        if self.inlier_ratio is not None:
            if not 0.0 <= self.inlier_ratio <= 1.0:
                raise ValueError(
                    "Inlier ratio must be between 0 and 1."
                )


@dataclass
class RegistrationResult:
    """
    Generic result returned by a future correspondence/
    registration engine.

    Member 4 will consume this interface later.
    """

    registration_id: str

    source_sensor: str

    reference_sensor: str

    metrics: RegistrationMetrics = field(
        default_factory=RegistrationMetrics
    )

    transform: Optional[Any] = None

    match_points: Optional[Any] = None

    registered_output: Optional[str] = None

    spatial_reference: Dict[str, Any] = field(
        default_factory=dict
    )

    success: bool = False

    message: str = ""


@dataclass
class ScientificResult:
    """Generic result returned by a Member 4 scientific module."""

    feature: str

    success: bool

    output_path: Optional[str] = None

    source_type: str = "unknown"

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    warnings: List[str] = field(
        default_factory=list
    )

    errors: List[str] = field(
        default_factory=list
    )

    def add_warning(
        self,
        message: str,
    ) -> None:
        self.warnings.append(message)

    def add_error(
        self,
        message: str,
    ) -> None:
        self.errors.append(message)


@dataclass
class ValidationResult:
    """Standard validation result for Member 4."""

    feature: str

    passed: bool

    metrics: Dict[str, float] = field(
        default_factory=dict
    )

    checks: Dict[str, bool] = field(
        default_factory=dict
    )

    message: str = ""

    def add_check(
        self,
        name: str,
        passed: bool,
    ) -> None:

        self.checks[name] = passed

        if not passed:
            self.passed = False