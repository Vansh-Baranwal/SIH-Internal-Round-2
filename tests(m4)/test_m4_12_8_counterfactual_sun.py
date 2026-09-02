"""Focused M4-12.8 Counterfactual Sun UI tests.

Verifies baseline vs counterfactual separation, active Sun selection,
apply/reset behavior, and synthetic/what-if provenance.
No real ephemeris data is fabricated.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    DEFAULT_AZIMUTH_DEG,
    DEFAULT_ELEVATION_DEG,
    DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG,
    DEFAULT_COUNTERFACTUAL_ELEVATION_DEG,
    SunConfigModel,
    SunDataStatus,
    SunScenarioModel,
    default_synthetic_sun_config,
    default_counterfactual_sun_config,
    default_sun_scenario,
    sun_direction_from_angles,
)


def test_default_scenario_has_baseline_and_counterfactual_separated():
    scenario = default_sun_scenario()

    assert isinstance(scenario, SunScenarioModel)
    assert not scenario.counterfactual_enabled

    # Baseline and counterfactual must be distinct
    assert scenario.baseline.azimuth_deg == DEFAULT_AZIMUTH_DEG
    assert scenario.baseline.elevation_deg == DEFAULT_ELEVATION_DEG
    assert scenario.baseline.data_status == SunDataStatus.SYNTHETIC

    assert scenario.counterfactual.azimuth_deg == DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG
    assert scenario.counterfactual.elevation_deg == DEFAULT_COUNTERFACTUAL_ELEVATION_DEG
    assert scenario.counterfactual.data_status == SunDataStatus.COUNTERFACTUAL

    # When not enabled, active_sun must equal baseline
    assert scenario.active_sun == scenario.baseline
    assert scenario.active_sun.data_status == SunDataStatus.SYNTHETIC


def test_apply_counterfactual_switches_active_sun_without_mutating_baseline():
    scenario = default_sun_scenario()
    applied = scenario.apply_counterfactual()

    assert applied.counterfactual_enabled is True
    # Active sun must now match counterfactual
    assert applied.active_sun == applied.counterfactual
    assert applied.active_sun.data_status == SunDataStatus.COUNTERFACTUAL
    assert applied.active_sun.azimuth_deg == DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG

    # Baseline must be preserved unchanged
    assert applied.baseline.azimuth_deg == DEFAULT_AZIMUTH_DEG
    assert applied.baseline.elevation_deg == DEFAULT_ELEVATION_DEG


def test_reset_to_baseline_restores_active_sun_and_preserves_counterfactual():
    scenario = default_sun_scenario().apply_counterfactual()
    # Modify counterfactual parameters while active
    modified_scenario = scenario.with_counterfactual(azimuth_deg=300.0, elevation_deg=15.0, intensity=5.0)
    assert modified_scenario.counterfactual_enabled is True
    assert modified_scenario.active_sun.azimuth_deg == 300.0

    # Reset to baseline
    reverted = modified_scenario.reset_to_baseline()
    assert reverted.counterfactual_enabled is False
    assert reverted.active_sun == reverted.baseline
    assert reverted.active_sun.azimuth_deg == DEFAULT_AZIMUTH_DEG

    # Counterfactual parameters are preserved for subsequent use
    assert reverted.counterfactual.azimuth_deg == 300.0
    assert reverted.counterfactual.elevation_deg == 15.0
    assert reverted.counterfactual.intensity == 5.0


def test_with_counterfactual_updates_only_counterfactual():
    scenario = default_sun_scenario()
    updated = scenario.with_counterfactual(azimuth_deg=180.0, elevation_deg=60.0)

    # Counterfactual updated
    assert updated.counterfactual.azimuth_deg == 180.0
    assert updated.counterfactual.elevation_deg == 60.0
    assert updated.counterfactual.data_status == SunDataStatus.COUNTERFACTUAL

    # Baseline untouched
    assert updated.baseline.azimuth_deg == DEFAULT_AZIMUTH_DEG
    assert updated.baseline.elevation_deg == DEFAULT_ELEVATION_DEG


def test_with_baseline_updates_only_baseline():
    scenario = default_sun_scenario()
    updated = scenario.with_baseline(azimuth_deg=90.0, elevation_deg=70.0)

    # Baseline updated
    assert updated.baseline.azimuth_deg == 90.0
    assert updated.baseline.elevation_deg == 70.0

    # Counterfactual untouched
    assert updated.counterfactual.azimuth_deg == DEFAULT_COUNTERFACTUAL_AZIMUTH_DEG
    assert updated.counterfactual.elevation_deg == DEFAULT_COUNTERFACTUAL_ELEVATION_DEG


def test_scenario_payload_serialization_and_provenance():
    scenario = default_sun_scenario()
    payload = scenario.payload()

    assert payload["counterfactual_enabled"] is False
    assert payload["active_sun"]["data_status"] == "synthetic"
    assert payload["baseline_sun"]["data_status"] == "synthetic"
    assert payload["counterfactual_sun"]["data_status"] == "counterfactual"
    assert "separate objects" in payload["provenance"]["note"]

    # When counterfactual applied
    applied_payload = scenario.apply_counterfactual().payload()
    assert applied_payload["counterfactual_enabled"] is True
    assert applied_payload["active_sun"]["data_status"] == "counterfactual"
    assert "WHAT-IF ACTIVE" in applied_payload["display_label"]


def test_frontend_sun_control_scenario_integration():
    src = (PROJECT_ROOT / "web" / "src" / "components" / "SunControl.tsx").read_text(encoding="utf-8")
    assert "DEFAULT_SUN_SCENARIO" in src
    assert "DEFAULT_COUNTERFACTUAL_CONFIG" in src
    assert "getActiveSunConfig" in src
    assert "SunScenarioState" in src
    assert "counterfactual-btn-apply" in src
    assert "counterfactual-btn-reset" in src
    assert "tab-sun-counterfactual" in src
    assert "tab-sun-baseline" in src
    assert "WHAT-IF" in src
