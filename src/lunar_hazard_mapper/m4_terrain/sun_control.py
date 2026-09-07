"""M4-12.7 Sun Control — backend data model and conversion utilities.

Reuses the existing ``SunState`` from ``lunar_hazard_mapper.scientific.common.types``
and adds the Three.js direction vector conversion needed by the 3D Digital Twin.

No real ephemeris data is fabricated.  Default values are labelled as
SYNTHETIC DEVELOPMENT SUN CONFIGURATION.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from lunar_hazard_mapper.scientific.common.types import SunState


class SunDataStatus(str, Enum):
    SYNTHETIC = "synthetic"
    COUNTERFACTUAL = "counterfactual"
    REAL = "real"
    UNKNOWN = "unknown"


# ── Default synthetic development configuration ──────────────────────
DEFAULT_AZIMUTH_DEG: float = 135.0   # SE (scene convention: 0°=North, CW)
DEFAULT_ELEVATION_DEG: float = 45.0  # 45° above horizon
DEFAULT_INTENSITY: float = 3.0

# ── Default counterfactual development configuration ────────────────
DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG: float = 225.0   # SW alternative
DEFAULT_COUNTERFACTUAL_ELEVATION_DEG: float = 25.0  # 25° lower angle
DEFAULT_COUNTERFACTUAL_INTENSITY: float = 4.0


def sun_direction_from_angles(
    azimuth_deg: float,
    elevation_deg: float,
    distance: float = 5000.0,
) -> Tuple[float, float, float]:
    """Convert azimuth/elevation to a Three.js directional-light position.

    Convention
    ----------
    * Scene axes: X = local East, Y = local Up, Z = local North.
    * Azimuth 0° = North (+Z), measured clockwise when viewed from above.
    * Elevation 0° = horizon, 90° = zenith (+Y).

    Returns (x, y, z) position for a Three.js ``DirectionalLight``.
    The light shines *toward the origin* from this position.
    """
    az_rad = math.radians(azimuth_deg)
    el_rad = math.radians(elevation_deg)

    # Horizontal projection of direction FROM observer TOWARD the Sun
    horiz = distance * math.cos(el_rad)

    x = horiz * math.sin(az_rad)   # East component
    y = distance * math.sin(el_rad) # Up component
    z = horiz * math.cos(az_rad)   # North component

    return (x, y, z)


@dataclass(frozen=True)
class SunConfigModel:
    """Viewer-facing Sun configuration for the 3D Digital Twin."""

    azimuth_deg: float
    elevation_deg: float
    intensity: float
    data_status: SunDataStatus
    provenance: Dict[str, Any]

    @property
    def sun_state(self) -> SunState:
        """Return the canonical ``SunState`` for downstream scientific modules."""
        return SunState(azimuth_deg=self.azimuth_deg, elevation_deg=self.elevation_deg)

    @property
    def direction_position(self) -> Tuple[float, float, float]:
        """Three.js directional light position (x_east, y_up, z_north)."""
        return sun_direction_from_angles(self.azimuth_deg, self.elevation_deg)

    @property
    def display_label(self) -> str:
        if self.data_status is SunDataStatus.SYNTHETIC:
            return "SYNTHETIC DEVELOPMENT SUN CONFIGURATION"
        if self.data_status is SunDataStatus.COUNTERFACTUAL:
            return "COUNTERFACTUAL / WHAT-IF SUN CONFIGURATION"
        if self.data_status is SunDataStatus.REAL:
            return "REAL EPHEMERIS SUN CONFIGURATION"
        return "SUN CONFIGURATION"

    def payload(self) -> Dict[str, Any]:
        pos = self.direction_position
        return {
            "display_label": self.display_label,
            "data_status": self.data_status.value,
            "azimuth_deg": float(self.azimuth_deg),
            "elevation_deg": float(self.elevation_deg),
            "intensity": float(self.intensity),
            "direction_position": {"x": pos[0], "y": pos[1], "z": pos[2]},
            "coordinate_convention": {
                "x": "local_east_meters",
                "y": "local_up_meters",
                "z": "local_north_meters",
                "azimuth": "0_north_clockwise_degrees",
                "elevation": "0_horizon_90_zenith_degrees",
            },
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class SunScenarioModel:
    """M4-12.8 Scenario model maintaining baseline and counterfactual states separately."""

    baseline: SunConfigModel
    counterfactual: SunConfigModel
    counterfactual_enabled: bool = False

    @property
    def active_sun(self) -> SunConfigModel:
        """Active illumination configuration driving the 3D scene."""
        return self.counterfactual if self.counterfactual_enabled else self.baseline

    @property
    def display_label(self) -> str:
        if self.counterfactual_enabled:
            return "COUNTERFACTUAL SUN SCENARIO (WHAT-IF ACTIVE)"
        return "BASELINE SUN SCENARIO (REFERENCE ACTIVE)"

    def apply_counterfactual(self) -> "SunScenarioModel":
        """Apply counterfactual configuration to active illumination."""
        return SunScenarioModel(
            baseline=self.baseline,
            counterfactual=self.counterfactual,
            counterfactual_enabled=True,
        )

    def reset_to_baseline(self) -> "SunScenarioModel":
        """Revert active illumination to baseline while preserving counterfactual values."""
        return SunScenarioModel(
            baseline=self.baseline,
            counterfactual=self.counterfactual,
            counterfactual_enabled=False,
        )

    def with_counterfactual(
        self,
        azimuth_deg: float,
        elevation_deg: float,
        intensity: Optional[float] = None,
    ) -> "SunScenarioModel":
        """Update counterfactual parameters without mutating the baseline."""
        new_cf = SunConfigModel(
            azimuth_deg=float(azimuth_deg),
            elevation_deg=float(elevation_deg),
            intensity=float(intensity if intensity is not None else self.counterfactual.intensity),
            data_status=SunDataStatus.COUNTERFACTUAL,
            provenance={
                "source": "m4_12_8_counterfactual_sun_config",
                "note": "Counterfactual what-if scenario parameterization. Does not represent real ephemeris.",
            },
        )
        return SunScenarioModel(
            baseline=self.baseline,
            counterfactual=new_cf,
            counterfactual_enabled=self.counterfactual_enabled,
        )

    def with_baseline(
        self,
        azimuth_deg: float,
        elevation_deg: float,
        intensity: Optional[float] = None,
    ) -> "SunScenarioModel":
        """Update baseline parameters without mutating the counterfactual."""
        new_base = SunConfigModel(
            azimuth_deg=float(azimuth_deg),
            elevation_deg=float(elevation_deg),
            intensity=float(intensity if intensity is not None else self.baseline.intensity),
            data_status=self.baseline.data_status,
            provenance=self.baseline.provenance,
        )
        return SunScenarioModel(
            baseline=new_base,
            counterfactual=self.counterfactual,
            counterfactual_enabled=self.counterfactual_enabled,
        )

    def payload(self) -> Dict[str, Any]:
        return {
            "display_label": self.display_label,
            "counterfactual_enabled": self.counterfactual_enabled,
            "active_sun": self.active_sun.payload(),
            "baseline_sun": self.baseline.payload(),
            "counterfactual_sun": self.counterfactual.payload(),
            "provenance": {
                "source": "m4_12_8_sun_scenario_model",
                "note": (
                    "Baseline and counterfactual Sun states are preserved as separate objects. "
                    "Values represent synthetic development / what-if scenarios, not real historical ephemeris."
                ),
            },
        }


def default_synthetic_sun_config() -> SunConfigModel:
    """Return the default synthetic development Sun configuration."""
    return SunConfigModel(
        azimuth_deg=DEFAULT_AZIMUTH_DEG,
        elevation_deg=DEFAULT_ELEVATION_DEG,
        intensity=DEFAULT_INTENSITY,
        data_status=SunDataStatus.SYNTHETIC,
        provenance={
            "source": "m4_12_7_synthetic_sun_config",
            "note": (
                "Synthetic development Sun direction. Does not represent real "
                "lunar ephemeris, historical illumination, or spacecraft-observed "
                "Sun geometry."
            ),
        },
    )


def default_counterfactual_sun_config() -> SunConfigModel:
    """Return the default counterfactual what-if Sun configuration."""
    return SunConfigModel(
        azimuth_deg=DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG,
        elevation_deg=DEFAULT_COUNTERFACTUAL_ELEVATION_DEG,
        intensity=DEFAULT_COUNTERFACTUAL_INTENSITY,
        data_status=SunDataStatus.COUNTERFACTUAL,
        provenance={
            "source": "m4_12_8_counterfactual_sun_config",
            "note": (
                "Counterfactual what-if Sun scenario. Does not represent real "
                "historical illumination or ephemeris."
            ),
        },
    )


def default_sun_scenario() -> SunScenarioModel:
    """Return the default Sun scenario combining baseline and counterfactual configurations."""
    return SunScenarioModel(
        baseline=default_synthetic_sun_config(),
        counterfactual=default_counterfactual_sun_config(),
        counterfactual_enabled=False,
    )
