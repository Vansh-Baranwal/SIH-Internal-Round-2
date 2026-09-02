"""Focused M4-12.4 contract tests; no real OHRC metadata is created or claimed."""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    OhrcCameraDataStatus,
    OhrcCameraModel,
    OhrcCameraProvider,
    SyntheticOhrcCameraProvider,
    SyntheticTmcCameraProvider,
    TmcCameraModel,
    TmcCameraProvider,
)


class IndependentOhrcCameraProvider(OhrcCameraProvider):
    """Proves the renderer-facing contract is not provider-specific."""

    def load_camera(self) -> OhrcCameraModel:
        return OhrcCameraModel(
            position_m=(15.0, 25.0, 35.0),
            target_m=(15.0, 0.0, 35.0),
            vertical_fov_degrees=20.0,
            aspect_ratio=1.0,
            near_m=1.0,
            far_m=200.0,
            data_status=OhrcCameraDataStatus.SYNTHETIC,
            provenance={"note": "Independent synthetic OHRC test camera."},
        )


def test_synthetic_ohrc_camera_is_explicitly_development_only():
    camera = SyntheticOhrcCameraProvider().load_camera()
    payload = camera.payload()
    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT CAMERA GEOMETRY"
    assert "not real OHRC calibration" in payload["provenance"]["note"]


def test_camera_payload_preserves_render_axis_and_frustum_parameters():
    payload = SyntheticOhrcCameraProvider().load_camera().payload()
    assert payload["coordinate_convention"] == {
        "x": "local_east_meters",
        "y": "local_up_meters",
        "z": "local_north_meters",
    }
    assert 0 < payload["vertical_fov_degrees"] < 180
    assert payload["aspect_ratio"] > 0
    assert 0 < payload["near_m"] < payload["far_m"]


def test_camera_provider_contract_is_replaceable():
    camera = IndependentOhrcCameraProvider().load_camera()
    assert isinstance(IndependentOhrcCameraProvider(), OhrcCameraProvider)
    assert camera.position_m == (15.0, 25.0, 35.0)
    assert camera.target_m == (15.0, 0.0, 35.0)
    assert camera.vertical_fov_degrees == 20.0


def test_frustum_viewer_does_not_depend_on_synthetic_provider_implementation():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "OhrcCameraFrustum.tsx").read_text(encoding="utf-8")
    assert "SyntheticOhrcCameraProvider" not in viewer_source
    assert "fetchOhrcCamera" in viewer_source
    assert "THREE.CameraHelper" in viewer_source
    assert "OHRC camera metadata is malformed" in viewer_source


def test_ohrc_and_tmc_are_distinct_sensor_models():
    ohrc_cam = SyntheticOhrcCameraProvider().load_camera()
    tmc_cam = SyntheticTmcCameraProvider().load_camera()
    assert isinstance(ohrc_cam, OhrcCameraModel)
    assert isinstance(tmc_cam, TmcCameraModel)
    assert not isinstance(ohrc_cam, TmcCameraModel)
    assert not isinstance(tmc_cam, OhrcCameraModel)
    assert issubclass(SyntheticOhrcCameraProvider, OhrcCameraProvider)
    assert not issubclass(SyntheticOhrcCameraProvider, TmcCameraProvider)


def test_invalid_camera_parameters_raise_value_error():
    with pytest.raises(ValueError, match="vertical_fov_degrees"):
        OhrcCameraModel(
            position_m=(0.0, 100.0, 0.0),
            target_m=(0.0, 0.0, 0.0),
            vertical_fov_degrees=0.0,
            aspect_ratio=1.0,
            near_m=1.0,
            far_m=100.0,
            data_status=OhrcCameraDataStatus.SYNTHETIC,
            provenance={},
        )
    with pytest.raises(ValueError, match="aspect ratio and clip planes"):
        OhrcCameraModel(
            position_m=(0.0, 100.0, 0.0),
            target_m=(0.0, 0.0, 0.0),
            vertical_fov_degrees=45.0,
            aspect_ratio=1.0,
            near_m=100.0,
            far_m=10.0,
            data_status=OhrcCameraDataStatus.SYNTHETIC,
            provenance={},
        )
