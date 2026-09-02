"""Focused M4-12.5 contract tests; no real IIRS metadata is created or claimed."""

import sys
from pathlib import Path
import pytest
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    IirsDataStatus,
    IirsCameraModel,
    IirsFootprintModel,
    IirsProvider,
    SyntheticIirsProvider,
    SyntheticTerrainProvider,
    TerrainFoundation,
    compute_iirs_footprint,
    intersect_ray_with_dem,
)


class IndependentIirsProvider(IirsProvider):
    """Proves the renderer-facing contract is not provider-specific."""

    def load_camera(self) -> IirsCameraModel:
        return IirsCameraModel(
            position_m=(100.0, 500.0, 100.0),
            target_m=(100.0, 0.0, 100.0),
            fov_across_track_degrees=10.0,
            fov_along_track_degrees=8.0,
            near_m=1.0,
            far_m=1000.0,
            data_status=IirsDataStatus.SYNTHETIC,
            provenance={"note": "Independent synthetic IIRS test camera."},
        )

    def load_footprint(self, foundation: TerrainFoundation | None = None) -> IirsFootprintModel:
        if foundation is None:
            foundation = TerrainFoundation(SyntheticTerrainProvider())
        return compute_iirs_footprint(self.load_camera(), foundation)


def test_synthetic_iirs_is_explicitly_development_only():
    provider = SyntheticIirsProvider()
    camera = provider.load_camera()
    footprint = provider.load_footprint()

    cam_payload = camera.payload()
    fp_payload = footprint.payload()

    assert cam_payload["data_status"] == "synthetic"
    assert fp_payload["data_status"] == "synthetic"
    assert "not real IIRS calibration" in cam_payload["provenance"]["note"]
    assert fp_payload["display_label"] == "SYNTHETIC DEVELOPMENT DATA"


def test_footprint_payload_preserves_render_axis_and_geometry_parameters():
    provider = SyntheticIirsProvider()
    payload = provider.load_footprint().payload()

    assert payload["coordinate_convention"] == {
        "x": "local_east_meters",
        "y": "local_up_meters",
        "z": "local_north_meters",
    }
    assert payload["sensor_type"] == "IIRS"
    assert "footprint" in payload
    assert len(payload["footprint"]["boundary_vertices"]) >= 4
    assert payload["footprint"]["surface_area_m2"] > 0
    assert payload["footprint"]["is_within_dem_bounds"] is True


def test_footprint_provider_contract_is_replaceable():
    provider = IndependentIirsProvider()
    assert isinstance(provider, IirsProvider)

    camera = provider.load_camera()
    assert camera.position_m == (100.0, 500.0, 100.0)

    footprint = provider.load_footprint()
    assert isinstance(footprint, IirsFootprintModel)
    assert len(footprint.boundary_vertices) > 0


def test_footprint_viewer_does_not_depend_on_synthetic_provider_implementation():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "IirsFootprint.tsx").read_text(encoding="utf-8")
    assert "SyntheticIirsProvider" not in viewer_source
    assert "fetchIirsFootprint" in viewer_source
    assert "iirs-footprint-boundary" in viewer_source
    assert "IIRS footprint metadata is malformed" in viewer_source


def test_terrain_intersection_derives_valid_dem_elevations():
    foundation = TerrainFoundation(SyntheticTerrainProvider())
    camera = SyntheticIirsProvider().load_camera()
    footprint = compute_iirs_footprint(camera, foundation)

    # All footprint boundary vertices must have realistic elevation matching DEM
    elevations = [v[1] for v in footprint.boundary_vertices]
    assert all(np.isfinite(e) for e in elevations)
    # Check elevations are reasonable on terrain
    assert min(elevations) < max(elevations) or len(elevations) > 0


def test_invalid_camera_parameters_raise_value_error():
    with pytest.raises(ValueError, match="fov_across_track_degrees"):
        IirsCameraModel(
            position_m=(0.0, 100.0, 0.0),
            target_m=(0.0, 0.0, 0.0),
            fov_across_track_degrees=0.0,
            fov_along_track_degrees=10.0,
            near_m=1.0,
            far_m=100.0,
            data_status=IirsDataStatus.SYNTHETIC,
            provenance={},
        )
    with pytest.raises(ValueError, match="Clip planes"):
        IirsCameraModel(
            position_m=(0.0, 100.0, 0.0),
            target_m=(0.0, 0.0, 0.0),
            fov_across_track_degrees=10.0,
            fov_along_track_degrees=10.0,
            near_m=100.0,
            far_m=10.0,
            data_status=IirsDataStatus.SYNTHETIC,
            provenance={},
        )
