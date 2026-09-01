"""
Unit tests for the correspondence detection and registration module.
Tests coverage for metrics computation, geometric estimation (RANSAC/MAGSAC),
QuadTree spatial filtering, sub-pixel LK refinement, image preprocessing, and matchers.
All image inputs are synthetic numpy arrays generated in-memory.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_hazard_mapper.correspondence.exporter import MatchExporter
from lunar_hazard_mapper.correspondence.geometry import (
    GeometryResult,
    QuadTreeFilter,
    RobustGeometry,
    subpixel_refine,
)
from lunar_hazard_mapper.correspondence.matcher import CorrespondenceEngine
from lunar_hazard_mapper.correspondence.matchers import (
    AKAZEMatcher,
    MatchResult,
    ORBMatcher,
    SIFTMatcher,
    match_images,
)
from lunar_hazard_mapper.correspondence.metrics import (
    RegistrationMetrics,
    _project_points,
    _spatial_coverage,
    compute_metrics,
)
from lunar_hazard_mapper.correspondence.preprocessing import (
    build_scale_pyramid,
    illumination_invariant_filter,
    normalize_radiometric,
)


# ---------------------------------------------------------------------------
# Helpers to generate synthetic image patterns
# ---------------------------------------------------------------------------
def _generate_textured_patch(size: int = 256, num_craters: int = 15, seed: int = 42) -> np.ndarray:
    """Generate a reproducible synthetic lunar texture patch with crater circles and noise."""
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 128, dtype=np.float32)
    # Add random crater-like structures
    for _ in range(num_craters):
        cx = rng.integers(30, size - 30)
        cy = rng.integers(30, size - 30)
        radius = rng.integers(8, 25)
        y_grid, x_grid = np.ogrid[:size, :size]
        dist_sq = (x_grid - cx) ** 2 + (y_grid - cy) ** 2
        # Crater floor (dark) and rim (bright)
        floor_mask = dist_sq <= (radius * 0.8) ** 2
        rim_mask = (dist_sq > (radius * 0.8) ** 2) & (dist_sq <= (radius * 1.2) ** 2)
        img[floor_mask] -= 50
        img[rim_mask] += 40

    # Add Gaussian noise
    noise = rng.normal(0, 10, (size, size))
    img = np.clip(img + noise, 0, 255).astype(np.uint8)
    return img


# ---------------------------------------------------------------------------
# Section 1: compute_metrics() & RMSE calculations
# ---------------------------------------------------------------------------
def test_compute_metrics_empty_correspondences_returns_inf_rmse():
    """Empty correspondence set yields infinite RMSE and zero inliers."""
    empty_mask = np.zeros(0, dtype=bool)
    geo = GeometryResult(H=None, inlier_mask=empty_mask, inlier_src=np.zeros((0, 2)), inlier_dst=np.zeros((0, 2)))
    metrics = compute_metrics(geo, image_shape=(256, 256), raw_match_count=0, method="SIFT")

    assert metrics.rmse_px == float("inf")
    assert metrics.inlier_count == 0
    assert metrics.inlier_ratio == 0.0
    assert metrics.spatial_coverage == 0.0
    assert metrics.meets_target is False


def test_compute_metrics_perfect_correspondences_returns_zero_rmse():
    """Identity homography on identical points yields 0.0 RMSE and meets_target=True."""
    pts = np.array([[10.0, 10.0], [200.0, 10.0], [200.0, 200.0], [10.0, 200.0]], dtype=np.float32)
    H = np.eye(3, dtype=np.float32)
    mask = np.ones(len(pts), dtype=bool)
    geo = GeometryResult(H=H, inlier_mask=mask, inlier_src=pts, inlier_dst=pts, method="SIFT")

    metrics = compute_metrics(geo, image_shape=(256, 256), raw_match_count=4, method="SIFT")

    assert metrics.rmse_px == pytest.approx(0.0, abs=1e-6)
    assert metrics.inlier_count == 4
    assert metrics.inlier_ratio == 1.0
    assert metrics.meets_target is True


@pytest.mark.parametrize("dx,dy,expected_rmse", [
    (0.3, 0.4, 0.5),           # sqrt(0.3^2 + 0.4^2) = 0.5
    (0.6, 0.8, 1.0),           # sqrt(0.6^2 + 0.8^2) = 1.0 -> meets_target is False
    (0.0, 0.5, 0.5),           # 0.5 px
])
def test_compute_metrics_known_offset_pairs_matches_analytical_rmse(dx: float, dy: float, expected_rmse: float):
    """Known uniform displacement offset yields exactly hand-calculated RMSE within 1e-6."""
    src_pts = np.array([[20.0, 20.0], [180.0, 20.0], [180.0, 180.0], [20.0, 180.0]], dtype=np.float32)
    # Target points are offset by (dx, dy)
    dst_pts = src_pts + np.array([dx, dy], dtype=np.float32)

    # When H is Identity, projected points equal src_pts, so error to dst_pts is sqrt(dx^2 + dy^2)
    H = np.eye(3, dtype=np.float32)
    mask = np.ones(len(src_pts), dtype=bool)
    geo = GeometryResult(H=H, inlier_mask=mask, inlier_src=src_pts, inlier_dst=dst_pts, method="TEST")

    metrics = compute_metrics(geo, image_shape=(256, 256), raw_match_count=4, method="TEST")

    assert metrics.rmse_px == pytest.approx(expected_rmse, rel=1e-5)
    assert metrics.meets_target == (expected_rmse < 1.0)


def test_compute_metrics_fewer_than_four_points_returns_inf_rmse():
    """Less than 4 points cannot reliably evaluate a 3x3 homography and falls back to inf."""
    src_pts = np.array([[10.0, 10.0], [50.0, 50.0], [90.0, 90.0]], dtype=np.float32)
    dst_pts = np.array([[10.0, 10.0], [50.0, 50.0], [90.0, 90.0]], dtype=np.float32)
    H = np.eye(3, dtype=np.float32)
    mask = np.ones(len(src_pts), dtype=bool)
    geo = GeometryResult(H=H, inlier_mask=mask, inlier_src=src_pts, inlier_dst=dst_pts)

    metrics = compute_metrics(geo, image_shape=(256, 256), raw_match_count=3)
    assert metrics.rmse_px == float("inf")
    assert metrics.meets_target is False


# ---------------------------------------------------------------------------
# Section 2: Inlier filtering, QuadTree, and Sub-pixel LK Refinement
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["RANSAC", "MAGSAC"])
def test_filter_inliers_perfect_points_all_inliers(method: str):
    """Synthetic points with pure translation homography have 100% inlier ratio."""
    src_pts = np.array([
        [20.0, 20.0], [100.0, 20.0], [180.0, 20.0],
        [20.0, 100.0], [100.0, 100.0], [180.0, 100.0],
        [20.0, 180.0], [100.0, 180.0], [180.0, 180.0],
    ], dtype=np.float32)
    shift = np.array([5.0, 3.0], dtype=np.float32)
    dst_pts = src_pts + shift
    scores = np.ones(len(src_pts), dtype=np.float32)

    match = MatchResult(src_pts=src_pts, dst_pts=dst_pts, scores=scores, method=method)
    robust_geo = RobustGeometry(method=method, reproj_thresh=3.0)
    geo_res = robust_geo.estimate_homography(match)

    assert geo_res.H is not None
    assert geo_res.inlier_mask.all()
    assert len(geo_res.inlier_src) == len(src_pts)


def test_filter_inliers_with_outliers_identifies_inlier_subset():
    """Corrupted outlier points are rejected by robust homography estimation."""
    src_pts = np.array([
        [20.0, 20.0], [100.0, 20.0], [180.0, 20.0],
        [20.0, 100.0], [100.0, 100.0], [180.0, 100.0],
        [20.0, 180.0], [100.0, 180.0], [180.0, 180.0],
        [50.0, 50.0], [150.0, 150.0],  # Outliers
    ], dtype=np.float32)
    dst_pts = src_pts.copy()
    # Corrupt the 2 outliers heavily
    dst_pts[-2] += np.array([200.0, -150.0], dtype=np.float32)
    dst_pts[-1] += np.array([-180.0, 220.0], dtype=np.float32)

    match = MatchResult(src_pts=src_pts, dst_pts=dst_pts, scores=np.ones(len(src_pts)), method="RANSAC")
    geo_res = RobustGeometry(method="RANSAC", reproj_thresh=2.0).estimate_homography(match)

    assert geo_res.H is not None
    assert geo_res.inlier_mask.sum() == 9
    assert geo_res.inlier_mask[-2:].sum() == 0  # Outliers excluded


def test_quadtree_spatial_filter_distributes_grid_points():
    """QuadTree retains at most one point per grid cell, prioritizing higher scores."""
    # 4 points located in the exact same top-left grid cell (0, 0)
    src_pts = np.array([[2.0, 2.0], [5.0, 5.0], [8.0, 8.0], [10.0, 10.0]], dtype=np.float32)
    dst_pts = src_pts.copy()
    scores = np.array([0.2, 0.9, 0.4, 0.1], dtype=np.float32)  # Index 1 has highest score

    qtree = QuadTreeFilter(grid_size=4)
    filtered_src, filtered_dst = qtree.filter(src_pts, dst_pts, image_shape=(100, 100), scores=scores)

    assert len(filtered_src) == 1
    assert np.allclose(filtered_src[0], [5.0, 5.0])


def test_quadtree_spatial_filter_empty_input_returns_empty():
    """QuadTree filter on empty points returns empty arrays safely."""
    qtree = QuadTreeFilter(grid_size=8)
    f_src, f_dst = qtree.filter(np.zeros((0, 2)), np.zeros((0, 2)), image_shape=(200, 200))
    assert len(f_src) == 0
    assert len(f_dst) == 0


def test_subpixel_refine_with_high_contrast_patches():
    """Lucas-Kanade subpixel optical flow refines coordinates on high-contrast synthetic patches."""
    patch_src = _generate_textured_patch(size=128, seed=1)
    # Small subpixel translation using cv2.warpAffine
    M = np.float32([[1, 0, 0.5], [0, 1, 0.5]])
    patch_dst = cv2.warpAffine(patch_src, M, (128, 128))

    pts_src = np.array([[50.0, 50.0], [70.0, 70.0], [90.0, 60.0]], dtype=np.float32)
    pts_dst = pts_src.copy()

    ref_src, ref_dst = subpixel_refine(patch_src, patch_dst, pts_src, pts_dst, win_size=15)

    assert len(ref_src) > 0
    assert ref_dst.shape == ref_src.shape


def test_subpixel_refine_empty_input_returns_empty():
    """subpixel_refine handles zero matches without error."""
    src = np.zeros((64, 64), dtype=np.uint8)
    dst = np.zeros((64, 64), dtype=np.uint8)
    r_src, r_dst = subpixel_refine(src, dst, np.zeros((0, 2)), np.zeros((0, 2)))
    assert len(r_src) == 0
    assert len(r_dst) == 0


# ---------------------------------------------------------------------------
# Section 3: Matchers & Preprocessing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("algo", ["sift", "orb", "akaze"])
@pytest.mark.skipif(not hasattr(cv2, "AKAZE_create"), reason="OpenCV build does not provide AKAZE")
def test_match_images_identical_patches_finds_matches(algo: str):
    """Matching an image against itself yields strong feature correspondences."""
    img = _generate_textured_patch(size=256, num_craters=25, seed=10)
    result = match_images(img, img, algorithm=algo)

    assert isinstance(result, MatchResult)
    assert len(result.src_pts) > 5
    assert len(result.dst_pts) == len(result.src_pts)
    assert result.method.lower() == algo.lower()


def test_match_images_blank_zeros_returns_graceful_empty():
    """Feature match on blank zero-filled images returns zero matches gracefully without exception."""
    blank = np.zeros((200, 200), dtype=np.uint8)
    result = match_images(blank, blank, algorithm="sift")

    assert len(result.src_pts) == 0
    assert len(result.dst_pts) == 0
    assert result.raw_match_count == 0


def test_match_images_unknown_algorithm_raises_value_error():
    """Passing an unrecognised algorithm name raises ValueError."""
    img = np.zeros((100, 100), dtype=np.uint8)
    with pytest.raises(ValueError, match="Unknown algorithm"):
        match_images(img, img, algorithm="unsupported_quantum_matcher")


def test_normalize_radiometric_clips_and_scales_to_uint8():
    """Percentile normalization maps float/integer images to a uint8 display range."""
    raw = np.linspace(0, 1000, 10000, dtype=np.float32).reshape(100, 100)
    norm = normalize_radiometric(raw)

    assert norm.dtype == np.uint8
    assert norm.shape == (100, 100)
    # CLAHE may lift the clipped minimum slightly while preserving the display range.
    assert 0 <= norm.min() <= 10
    assert norm.max() == 255


def test_illumination_invariant_filter_suppresses_low_frequencies():
    """Illumination high-pass filter suppresses smooth illumination gradients."""
    # Create smooth lighting gradient + high-frequency edges
    gradient = np.linspace(0, 200, 100, dtype=np.float32)[:, None] * np.ones((1, 100), dtype=np.float32)
    filtered = illumination_invariant_filter(gradient.astype(np.uint8), sigma=5.0)

    assert filtered.shape == (100, 100)
    assert filtered.dtype == np.uint8
    # Uniform gradient should become roughly flat/neutral after high-pass filtering
    assert filtered.std() < gradient.std()


def test_build_scale_pyramid_creates_gaussian_levels():
    """Scale pyramid generates monotonically downsampled image levels."""
    img = _generate_textured_patch(size=256)
    levels, scale = build_scale_pyramid(img, target_gsd_m=1.0, source_gsd_m=0.25, max_levels=3)

    assert levels.shape == (64, 64)
    assert scale == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Section 4: MatchExporter serialization
# ---------------------------------------------------------------------------
def test_match_exporter_to_dict_and_csv_consistency():
    """MatchExporter formats matches, metrics, and CSV representations consistently."""
    src = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)
    dst = np.array([[12.0, 22.0], [32.0, 42.0]], dtype=np.float32)
    metrics = RegistrationMetrics(rmse_px=0.45, inlier_count=2, inlier_ratio=1.0, spatial_coverage=0.3, method="SIFT", meets_target=True)

    d = MatchExporter.to_dict(src, dst, metrics)
    assert d["method"] == "SIFT"
    assert d["metrics"]["rmse_px"] == 0.45
    assert len(d["matches"]) == 2
    assert d["matches"][0]["src"] == [10.0, 20.0]

    csv_str = MatchExporter.to_csv_str(src, dst)
    lines = csv_str.strip().splitlines()
    assert lines[0].rstrip("\\r") == "src_x,src_y,dst_x,dst_y"
    assert len(lines) == 3
