"""Focused Phase 12.13 checks for existing spatial contracts."""

from lunar_hazard_mapper.api.phase12_11_phase11_to_phase10 import adapt_phase11_to_phase10
from lunar_hazard_mapper.api.phase12_12_registered_output_handoff import (
    RegisteredOutputHandoffStatus,
    adapt_phase11_to_registered_output,
    downstream_invocation_allowed,
)
from lunar_hazard_mapper.m4_terrain.spatial_sync import (
    LOCAL_UNITS,
    TERRAIN_GRID_CONVENTION,
    VIEW_COORDINATE_CONVENTION,
    terrain_grid_to_viewer,
)


def test_existing_viewer_convention_and_units_remain_unchanged():
    assert VIEW_COORDINATE_CONVENTION == {
        "x": "local_east_meters",
        "y": "local_up_meters",
        "z": "local_north_meters",
    }
    assert TERRAIN_GRID_CONVENTION == {
        "x": "local_east_meters",
        "y": "local_north_meters",
        "z": "local_up_meters",
    }
    assert LOCAL_UNITS == "metres"


def test_only_existing_explicit_grid_to_viewer_reorder_is_applied():
    assert terrain_grid_to_viewer(10.0, 20.0, 30.0) == (10.0, 30.0, 20.0)


def test_phase11_to_phase10_unavailable_path_creates_no_spatial_observation():
    result = adapt_phase11_to_phase10(None)

    assert result.observation is None
    assert result.status.value == "unavailable"


def test_phase12_12_unavailable_handoff_has_no_spatial_values():
    handoff = adapt_phase11_to_registered_output(None)

    assert handoff.status is RegisteredOutputHandoffStatus.UNAVAILABLE
    assert handoff.registered_output_reference is None
    assert not downstream_invocation_allowed(handoff)
    assert not hasattr(handoff, "coordinates")
    assert not hasattr(handoff, "crs")
    assert not hasattr(handoff, "datum")
    assert not hasattr(handoff, "transform")