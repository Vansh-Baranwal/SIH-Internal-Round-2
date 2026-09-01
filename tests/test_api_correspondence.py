"""
Integration tests for correspondence, landmark, simulation, temporal, and spectral API endpoints.
Tests the FastAPI backend against expected response contracts and error conditions.

=============================================================================
API RESPONSE SCHEMA CONTRACT DOCUMENTATION (Frontend Phase 4 Dependency)
=============================================================================

1. POST /api/correspondence/match
   Response JSON shape:
   {
       "algorithm": str,
       "rmse_px": float,
       "inlier_count": int,
       "inlier_ratio": float,
       "spatial_coverage": float,
       "meets_target": bool,
       "match_points": list[{"src": [float, float], "dst": [float, float]}],
       "warped_b64": str | None,
       "match_vis_b64": str | None
   }

2. POST /api/correspondence/benchmark
   Response JSON shape:
   {
       "sift": {"rmse_px": float | None, "inlier_count": int, "inlier_ratio": float, "spatial_coverage": float, "meets_target": bool},
       "orb":  {"rmse_px": float | None, "inlier_count": int, "inlier_ratio": float, "spatial_coverage": float, "meets_target": bool},
       "akaze":{"rmse_px": float | None, "inlier_count": int, "inlier_ratio": float, "spatial_coverage": float, "meets_target": bool}
   }

3. POST /api/landmarks/geolocate
   Response JSON shape:
   {
       "query": {"lat": float, "lon": float},
       "results": list[{
           "id": str, "name": str, "lat": float, "lon": float,
           "radius_km": float, "depth_m": float, "distance_km": float,
           "bearing_deg": float, "confidence": float, "tags": list[str]
       }]
   }

4. GET /api/landmarks/list
   Response JSON shape:
   {
       "landmarks": list[{
           "id": str, "name": str, "lat": float, "lon": float,
           "radius_km": float, "depth_m": float, "confidence": float, "tags": list[str]
       }]
   }

5. POST /api/simulation/sun-invariance
   Response JSON shape:
   {
       "sun_azimuth_deg": float,
       "sun_elevation_deg": float,
       "shadow_fraction": float,
       "baseline": dict,
       "counterfactual": dict
   }

6. POST /api/temporal/change-detection
   Response JSON shape:
   {
       "change_fraction": float,
       "mean_diff": float,
       "max_diff": float,
       "heatmap_b64": str | None
   }

7. POST /api/spectral/overlay
   Response JSON shape:
   {
       "registered_band_b64": str,
       "iirs_gsd_m": float,
       "optical_gsd_m": float,
       "output_shape": list[int]
   }
=============================================================================
"""

from __future__ import annotations

import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from lunar_hazard_mapper.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _make_b64_image(size: int = 128, pattern: str = "textured") -> str:
    """Helper to generate in-memory base64 encoded PNG images."""
    if pattern == "textured":
        rng = np.random.default_rng(42)
        arr = rng.integers(50, 200, (size, size), dtype=np.uint8)
        cv2.circle(arr, (size // 2, size // 2), size // 4, 250, 3)
        cv2.circle(arr, (size // 4, size // 4), size // 6, 20, -1)
    elif pattern == "blank":
        arr = np.zeros((size, size), dtype=np.uint8)
    else:
        arr = np.ones((size, size), dtype=np.uint8) * 128

    _, buf = cv2.imencode(".png", arr)
    return base64.b64encode(buf.tobytes()).decode()


# ===========================================================================
# 1. /api/correspondence/match & /api/correspondence/benchmark
# ===========================================================================

def test_api_correspondence_match_happy_path(client: TestClient):
    """POST /api/correspondence/match returns complete schema and valid metrics."""
    img_b64 = _make_b64_image(size=200, pattern="textured")
    payload = {
        "src_image_b64": img_b64,
        "dst_image_b64": img_b64,
        "algorithm": "sift",
        "geo_method": "RANSAC",
        "include_warped": True,
        "include_vis": True,
    }

    response = client.post("/api/correspondence/match", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Schema contract checks
    assert isinstance(data["algorithm"], str)
    assert isinstance(data["rmse_px"], (float, int))
    assert isinstance(data["inlier_count"], int)
    assert isinstance(data["inlier_ratio"], (float, int))
    assert isinstance(data["spatial_coverage"], (float, int))
    assert isinstance(data["meets_target"], bool)
    assert isinstance(data["match_points"], list)

    # When matching identical images, RMSE should be 0.0 px and meet target
    assert data["rmse_px"] == 0.0
    assert data["meets_target"] is True
    assert data["warped_b64"] is not None
    assert data["match_vis_b64"] is not None


def test_api_correspondence_match_bad_image_data_returns_400(client: TestClient):
    """POST /api/correspondence/match with non-image string returns HTTP 400."""
    payload = {
        "src_image_b64": "not_a_valid_base64_image_content",
        "dst_image_b64": "invalid",
        "algorithm": "sift",
    }
    response = client.post("/api/correspondence/match", json=payload)
    assert response.status_code == 400
    assert "Image decode failed" in response.json()["detail"]


def test_api_correspondence_match_missing_fields_returns_422(client: TestClient):
    """POST /api/correspondence/match with missing required fields returns HTTP 422 validation error."""
    response = client.post("/api/correspondence/match", json={"algorithm": "sift"})
    assert response.status_code == 422


def test_api_correspondence_benchmark_happy_path(client: TestClient):
    """POST /api/correspondence/benchmark returns comparative results for SIFT, ORB, and AKAZE."""
    img_b64 = _make_b64_image(size=128, pattern="textured")
    payload = {
        "src_image_b64": img_b64,
        "dst_image_b64": img_b64,
    }

    response = client.post("/api/correspondence/benchmark", json=payload)
    assert response.status_code == 200
    data = response.json()

    for algo in ["sift", "orb", "akaze"]:
        assert algo in data
        item = data[algo]
        assert "inlier_count" in item
        assert "inlier_ratio" in item
        assert "spatial_coverage" in item
        assert "meets_target" in item


# ===========================================================================
# 2. /api/landmarks/geolocate & /api/landmarks/list
# ===========================================================================

def test_api_landmarks_list_returns_catalog(client: TestClient):
    """GET /api/landmarks/list returns full catalog list with all attributes."""
    response = client.get("/api/landmarks/list")
    assert response.status_code == 200
    data = response.json()

    assert "landmarks" in data
    assert len(data["landmarks"]) >= 10
    first = data["landmarks"][0]
    for key in ["id", "name", "lat", "lon", "radius_km", "depth_m", "confidence", "tags"]:
        assert key in first


def test_api_landmarks_geolocate_query(client: TestClient):
    """POST /api/landmarks/geolocate returns ranked landmarks around coordinates."""
    payload = {
        "lat": -89.9,
        "lon": 0.0,
        "radius_km": 1000.0,
        "top_k": 3,
    }
    response = client.post("/api/landmarks/geolocate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "results" in data
    assert len(data["results"]) <= 3
    if data["results"]:
        top = data["results"][0]
        assert top["name"] == "Shackleton"
        assert "distance_km" in top
        assert "bearing_deg" in top


# ===========================================================================
# 3. /api/simulation/sun-invariance
# ===========================================================================

def test_api_simulation_sun_invariance(client: TestClient):
    """POST /api/simulation/sun-invariance runs baseline vs counterfactual comparison."""
    img_b64 = _make_b64_image(size=128, pattern="textured")
    payload = {
        "src_image_b64": img_b64,
        "dst_image_b64": img_b64,
        "sun_azimuth_deg": 90.0,
        "sun_elevation_deg": 25.0,
        "algorithm": "sift",
    }
    response = client.post("/api/simulation/sun-invariance", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["sun_azimuth_deg"] == 90.0
    assert data["sun_elevation_deg"] == 25.0
    assert "shadow_fraction" in data
    assert "baseline" in data
    assert "counterfactual" in data


# ===========================================================================
# 4. /api/temporal/change-detection & /api/spectral/overlay
# ===========================================================================

def test_api_temporal_change_detection(client: TestClient):
    """POST /api/temporal/change-detection evaluates difference between image pairs."""
    img_b64_a = _make_b64_image(size=100, pattern="textured")
    img_b64_b = _make_b64_image(size=100, pattern="blank")

    payload = {
        "before_image_b64": img_b64_a,
        "after_image_b64": img_b64_b,
        "threshold": 10.0,
    }
    response = client.post("/api/temporal/change-detection", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "change_fraction" in data
    assert "mean_diff" in data
    assert "max_diff" in data
    assert data["change_fraction"] > 0.0


def test_api_spectral_overlay(client: TestClient):
    """POST /api/spectral/overlay registers IIRS band to optical base image."""
    iirs_b64 = _make_b64_image(size=64, pattern="textured")
    optical_b64 = _make_b64_image(size=128, pattern="textured")

    payload = {
        "iirs_band_b64": iirs_b64,
        "optical_image_b64": optical_b64,
        "iirs_gsd_m": 80.0,
        "optical_gsd_m": 5.0,
    }
    response = client.post("/api/spectral/overlay", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "registered_band_b64" in data
    assert data["iirs_gsd_m"] == 80.0
    assert data["optical_gsd_m"] == 5.0
    assert data["output_shape"] == [128, 128]
