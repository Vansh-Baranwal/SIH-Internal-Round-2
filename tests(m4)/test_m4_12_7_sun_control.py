"""Focused M4-12.7 Sun Control tests.  No real ephemeris data is fabricated."""

import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    DEFAULT_AZIMUTH_DEG,
    DEFAULT_ELEVATION_DEG,
    DEFAULT_INTENSITY,
    SunConfigModel,
    SunDataStatus,
    default_synthetic_sun_config,
    sun_direction_from_angles,
)
from lunar_hazard_mapper.scientific.common.types import SunState


def test_default_synthetic_sun_is_explicitly_development_only():
    cfg = default_synthetic_sun_config()
    payload = cfg.payload()

    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT SUN CONFIGURATION"
    assert "not represent real" in payload["provenance"]["note"].lower() or \
           "does not represent real" in payload["provenance"]["note"]
    assert payload["azimuth_deg"] == DEFAULT_AZIMUTH_DEG
    assert payload["elevation_deg"] == DEFAULT_ELEVATION_DEG
    assert payload["intensity"] == DEFAULT_INTENSITY


def test_sun_direction_from_angles_zenith():
    """Elevation 90° should produce straight up (0, distance, 0)."""
    x, y, z = sun_direction_from_angles(0.0, 90.0, distance=1000.0)
    assert abs(x) < 1e-6
    assert abs(y - 1000.0) < 1e-6
    assert abs(z) < 1e-6


def test_sun_direction_from_angles_north_horizon():
    """Azimuth 0° (North), elevation 0° → position at (0, 0, distance)."""
    x, y, z = sun_direction_from_angles(0.0, 0.0, distance=1000.0)
    assert abs(x) < 1e-6
    assert abs(y) < 1e-6
    assert abs(z - 1000.0) < 1e-6


def test_sun_direction_from_angles_east_horizon():
    """Azimuth 90° (East), elevation 0° → position at (distance, 0, 0)."""
    x, y, z = sun_direction_from_angles(90.0, 0.0, distance=1000.0)
    assert abs(x - 1000.0) < 1e-6
    assert abs(y) < 1e-6
    assert abs(z) < 1e-6


def test_sun_direction_preserves_distance():
    """Resulting position should always be at the given distance from origin."""
    for az in [0, 45, 90, 135, 180, 270]:
        for el in [0, 15, 30, 45, 60, 90]:
            x, y, z = sun_direction_from_angles(float(az), float(el), distance=5000.0)
            dist = math.sqrt(x ** 2 + y ** 2 + z ** 2)
            assert abs(dist - 5000.0) < 0.01, f"az={az} el={el} → dist={dist}"


def test_sun_config_model_produces_canonical_sun_state():
    cfg = default_synthetic_sun_config()
    state = cfg.sun_state
    assert isinstance(state, SunState)
    assert state.azimuth_deg == DEFAULT_AZIMUTH_DEG
    assert state.elevation_deg == DEFAULT_ELEVATION_DEG


def test_sun_config_payload_coordinate_convention():
    payload = default_synthetic_sun_config().payload()
    conv = payload["coordinate_convention"]
    assert conv["x"] == "local_east_meters"
    assert conv["y"] == "local_up_meters"
    assert conv["z"] == "local_north_meters"
    assert "north" in conv["azimuth"].lower()
    assert "horizon" in conv["elevation"].lower()


def test_sun_config_direction_position_in_payload():
    cfg = default_synthetic_sun_config()
    payload = cfg.payload()
    dp = payload["direction_position"]
    expected = sun_direction_from_angles(cfg.azimuth_deg, cfg.elevation_deg)
    assert abs(dp["x"] - expected[0]) < 1e-6
    assert abs(dp["y"] - expected[1]) < 1e-6
    assert abs(dp["z"] - expected[2]) < 1e-6


def test_sun_control_frontend_does_not_hardcode_synthetic_values():
    src = (PROJECT_ROOT / "web" / "src" / "components" / "SunControl.tsx").read_text(encoding="utf-8")
    assert "SunLight" in src
    assert "SunControlPanel" in src
    assert "sunPosition" in src
    assert "sun-control-panel" in src
    assert "sun-directional-light" in src
    assert "sun-gizmo" in src
    # Must NOT hardcode synthetic scientific values
    assert "ephemeris" not in src.lower() or "REAL EPHEMERIS SUN" in src
