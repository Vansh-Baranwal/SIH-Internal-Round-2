"""Focused M4-12.13 interaction/performance source-contract tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_planner_raycast_is_limited_to_dem_and_animation_callbacks_are_stable():
    source = (ROOT / "web" / "src" / "pages" / "Simulation.tsx").read_text(encoding="utf-8")
    assert 'scene.getObjectByName(\'dem-terrain\')' in source
    assert 'raycaster.intersectObject(terrain, false)' in source
    assert 'useCallback' in source


def test_water_ice_resources_are_memoized_and_layer_controls_exist():
    overlay = (ROOT / "web" / "src" / "components" / "WaterIceOverlay.tsx").read_text(encoding="utf-8")
    simulation = (ROOT / "web" / "src" / "pages" / "Simulation.tsx").read_text(encoding="utf-8")
    assert 'memo(function WaterIceOverlay' in overlay
    assert 'useMemo(() => boundary ? new THREE.Line' in overlay
    assert 'layerVisibility' in simulation
    assert 'WATER-ICE' in simulation


def test_spatial_contract_and_api_fetch_remain_unchanged():
    utility = (ROOT / "web" / "src" / "spatial" / "coordinates.ts").read_text(encoding="utf-8")
    client = (ROOT / "web" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    assert "East, Up, North" in utility
    assert 'fetchWaterIceOverlay' in client
    assert 'water-ice' in client

