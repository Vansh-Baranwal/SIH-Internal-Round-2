"""Focused M4-12.3 contract tests; no real TMC metadata is created or claimed."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    SyntheticTmcCameraProvider,
    TmcCameraDataStatus,
    TmcCameraModel,
    TmcCameraProvider,
)


class IndependentCameraProvider(TmcCameraProvider):
    """Proves the renderer-facing contract is not provider-specific."""

    def load_camera(self) -> TmcCameraModel:
        return TmcCameraModel(
            position_m=(10.0, 20.0, 30.0),
            target_m=(10.0, 0.0, 30.0),
            vertical_fov_degrees=30.0,
            aspect_ratio=1.0,
            near_m=1.0,
            far_m=100.0,
            data_status=TmcCameraDataStatus.SYNTHETIC,
            provenance={"note": "Independent synthetic test camera."},
        )


def test_synthetic_tmc_camera_is_explicitly_development_only():
    camera = SyntheticTmcCameraProvider().load_camera()
    payload = camera.payload()
    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT CAMERA GEOMETRY"
    assert "not real TMC calibration" in payload["provenance"]["note"]


def test_camera_payload_preserves_render_axis_and_frustum_parameters():
    payload = SyntheticTmcCameraProvider().load_camera().payload()
    assert payload["coordinate_convention"] == {
        "x": "local_east_meters",
        "y": "local_up_meters",
        "z": "local_north_meters",
    }
    assert 0 < payload["vertical_fov_degrees"] < 180
    assert payload["aspect_ratio"] > 0
    assert 0 < payload["near_m"] < payload["far_m"]


def test_camera_provider_contract_is_replaceable():
    camera = IndependentCameraProvider().load_camera()
    assert isinstance(IndependentCameraProvider(), TmcCameraProvider)
    assert camera.position_m == (10.0, 20.0, 30.0)
    assert camera.target_m == (10.0, 0.0, 30.0)


def test_frustum_viewer_does_not_depend_on_synthetic_provider_implementation():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "TmcCameraFrustum.tsx").read_text(encoding="utf-8")
    assert "SyntheticTmcCameraProvider" not in viewer_source
    assert "fetchTmcCamera" in viewer_source
    assert "THREE.CameraHelper" in viewer_source
    assert "camera metadata is malformed" in viewer_source
