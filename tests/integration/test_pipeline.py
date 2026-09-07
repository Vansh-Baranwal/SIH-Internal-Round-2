import pytest
import numpy as np
from pathlib import Path
import rasterio
import cv2

from lunar_hazard_mapper.api.alignment import (
    align_rasters,
    filter_uniform_grid,
    refine_point_subpixel,
    refine_points_subpixel,
    run_m3_subpixel_refinement,
    generate_synthetic_scene,
    generate_mock_correspondences,
    REFINEMENT_STATUS_REFINED,
    REFINEMENT_STATUS_FALLBACK_BOUNDARY,
    REFINEMENT_STATUS_FALLBACK_LOW_TEXTURE,
    REFINEMENT_STATUS_FALLBACK_NUMERICAL,
)
# NOTE: `from lunar_hazard_mapper.api.pipeline import run_dual_pipeline` used to be
# imported here at module level. It is now imported LAZILY, inside the two test
# functions below that actually call it, instead. Reason: api.pipeline imports
# m2_super_resolution.inference, which imports torch -- a module-level import here
# meant torch was required just to COLLECT this file, breaking the M3 tests below
# (which don't touch M2/pipeline at all) on any machine without torch installed.
# Both functions that need it are already @pytest.mark.skipif-gated on a real local
# dataset that usually isn't present; pytest evaluates skipif at collection time
# without running the function body, so when skipped, the lazy import below never
# executes and torch is never required. No behavioural change when the dataset (and
# torch) ARE present -- same import, just deferred from module load to test run.

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent / "Different Repo" / "SIH" / "CODE_SIH1519_ORION SPACE SYSTEM"

OPTICAL_PATH = REPO_DIR / "TMCORTHO5-1" / "TMCORTHO5-1" / "TMCORTHO5-1" / "TMCORTHOCH_01_01.tif"
DEM_PATH = REPO_DIR / "TMCDTM" / "TMCDTM" / "TMCDTM_01_01.tif"

@pytest.mark.skipif(not OPTICAL_PATH.exists() or not DEM_PATH.exists(), reason="Real dataset not found locally")
def test_tmc_ortho_tmcdtm_alignment():
    # Verify bounds are identical
    with rasterio.open(OPTICAL_PATH) as opt, rasterio.open(DEM_PATH) as dem:
        assert np.isclose(opt.bounds.left, dem.bounds.left)
        assert np.isclose(opt.bounds.bottom, dem.bounds.bottom)
        assert np.isclose(opt.bounds.right, dem.bounds.right)
        assert np.isclose(opt.bounds.top, dem.bounds.top)
        
        assert opt.crs == dem.crs

@pytest.mark.skipif(not OPTICAL_PATH.exists() or not DEM_PATH.exists(), reason="Real dataset not found locally")
def test_full_dual_path_pipeline_blocked_missing_state():
    # Lazy import: see NOTE near the top of this file -- deferred so collecting
    # this module doesn't require torch when this test is skipped (no local dataset).
    from lunar_hazard_mapper.api.pipeline import run_dual_pipeline
    # CASE A: No initial_state provided. Must block M6 legitimately.
    stats = run_dual_pipeline(scene_id="01_01", subset_window=((0, 100), (0, 100)))
    
    assert stats["m3"]["status"] == "success"
    assert stats["m5"]["status"] == "success"
    
    # If there are candidates, M6 must block due to missing initial state
    if stats["m5"]["candidates_found"] > 0:
        assert stats["m6"]["status"] == "blocked"
        assert "Missing initial mission state" in stats["m6"]["trajectory"]["reason"]

@pytest.mark.skipif(not OPTICAL_PATH.exists() or not DEM_PATH.exists(), reason="Real dataset not found locally")
def test_full_dual_path_pipeline_explicit_state():
    # Lazy import: see NOTE near the top of this file -- deferred so collecting
    # this module doesn't require torch when this test is skipped (no local dataset).
    from lunar_hazard_mapper.api.pipeline import run_dual_pipeline
    # CASE B: Explicit test initial_state provided. Must run real M6 physics.
    test_initial_state = [0.0, 0.0, 15000.0, 100.0, 0.0, -10.0]
    stats = run_dual_pipeline(scene_id="01_01", subset_window=((0, 100), (0, 100)), initial_state=test_initial_state)
    
    m6_status = stats["m6"]["status"]
    
    # Valid M6 statuses based on true trajectory integration
    valid_m6_statuses = ["success", "blocked", "ground_collision", "timeout", "invalid", "no_candidates"]
    assert m6_status in valid_m6_statuses
    
    trajectory_info = stats["m6"]["trajectory"]
    if m6_status != "no_candidates" and m6_status != "blocked" and m6_status != "invalid":
        assert trajectory_info["reachable"] is True
        assert "delta_v" in trajectory_info
        assert isinstance(trajectory_info["delta_v"], float)
        assert "points_count" in trajectory_info
        assert trajectory_info["points_count"] > 0


# ==========================================================================================
# M3 -- SUB-PIXEL REFINEMENT & UNIFORM SPATIAL DISTRIBUTION (tests)
# ==========================================================================================
# Appended here because this file already imports from lunar_hazard_mapper.api.alignment
# (see the updated import line at the top of this file) and is the existing integration
# test home for that module. Unlike the tests above (which are skipif-gated on a real local
# dataset that isn't present in CI/most dev machines), these run unconditionally: they use
# only synthetic, in-memory data via generate_mock_correspondences (see alignment.py's "M3"
# section for why -- M2, the real correspondence-matching engine, is not implemented yet
# anywhere in this repo).

import numpy as np


def test_m3_filter_uniform_grid_thins_clustered_points():
    points = [
        {"id": f"c{i}", "x_a": 10 + i * 0.1, "y_a": 10 + i * 0.1, "x_b": 0.0, "y_b": 0.0, "score": float(i)}
        for i in range(10)
    ]
    result = filter_uniform_grid(points, image_shape=(100, 100), grid_size=(4, 4), max_per_cell=1)
    assert len(result["kept"]) == 1
    assert len(result["dropped_clustered"]) == 9
    assert result["kept"][0]["id"] == "c9"  # highest score in the (shared) cell


def test_m3_filter_uniform_grid_keeps_spread_points():
    points = []
    for row in range(4):
        for col in range(4):
            points.append({"id": f"p{row}_{col}", "x_a": (col + 0.5) * 25, "y_a": (row + 0.5) * 25,
                            "x_b": 0.0, "y_b": 0.0, "score": 1.0})
    result = filter_uniform_grid(points, image_shape=(100, 100), grid_size=(4, 4), max_per_cell=1)
    assert len(result["kept"]) == 16
    assert result["spatial_coverage_fraction"] == 1.0


def test_m3_filter_uniform_grid_drops_out_of_bounds_and_nan():
    points = [
        {"id": "in", "x_a": 50, "y_a": 50, "x_b": 0, "y_b": 0},
        {"id": "neg", "x_a": -1, "y_a": 50, "x_b": 0, "y_b": 0},
        {"id": "nan", "x_a": float("nan"), "y_a": 50, "x_b": 0, "y_b": 0},
    ]
    result = filter_uniform_grid(points, image_shape=(100, 100), grid_size=(4, 4))
    assert len(result["kept"]) == 1
    assert result["kept"][0]["id"] == "in"
    assert len(result["dropped_invalid"]) == 2


def test_m3_refine_point_subpixel_recovers_known_subpixel_shift():
    """Core M3 accuracy claim, verified against a KNOWN synthetic shift (also
    verifies the cv2.phaseCorrelate sign convention documented in alignment.py's
    'M3' section didn't silently change in this OpenCV version)."""
    scene = generate_synthetic_scene(size=128, seed=1)
    true_dx, true_dy = 1.4, -0.6
    shift_matrix = np.array([[1, 0, true_dx], [0, 1, true_dy]], dtype=np.float32)
    shifted = cv2.warpAffine(scene, shift_matrix, (128, 128), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    xa, ya = 64.0, 64.0
    xb_guess, yb_guess = round(xa + true_dx), round(ya + true_dy)
    point = {"id": "p", "x_a": xa, "y_a": ya, "x_b": float(xb_guess), "y_b": float(yb_guess), "score": 0.9}

    result = refine_point_subpixel(scene, shifted, point)

    assert result["refinement_status"] == REFINEMENT_STATUS_REFINED
    true_xb, true_yb = xa + true_dx, ya + true_dy
    assert abs(result["x_b_refined"] - true_xb) < 0.25
    assert abs(result["y_b_refined"] - true_yb) < 0.25


def test_m3_refine_point_subpixel_boundary_falls_back_without_crash():
    scene = generate_synthetic_scene(size=128, seed=2)
    point = {"id": "edge", "x_a": 1.0, "y_a": 1.0, "x_b": 2.0, "y_b": 1.0, "score": 0.9}
    result = refine_point_subpixel(scene, scene, point)
    assert result["refinement_status"] == REFINEMENT_STATUS_FALLBACK_BOUNDARY
    assert result["x_b_refined"] == point["x_b"]
    assert result["displacement_px"] == 0.0


def test_m3_refine_point_subpixel_low_texture_falls_back():
    flat = np.full((128, 128), 0.5, dtype=np.float32)
    flat += np.random.default_rng(0).normal(0, 1e-4, flat.shape).astype(np.float32)
    point = {"id": "flat", "x_a": 64.0, "y_a": 64.0, "x_b": 64.0, "y_b": 64.0, "score": 0.9}
    result = refine_point_subpixel(flat, flat, point)
    assert result["refinement_status"] == REFINEMENT_STATUS_FALLBACK_LOW_TEXTURE


def test_m3_refine_point_subpixel_nan_input_does_not_crash():
    scene = generate_synthetic_scene(size=128, seed=3)
    point = {"id": "nan", "x_a": float("nan"), "y_a": 64.0, "x_b": 64.0, "y_b": 64.0, "score": 0.9}
    result = refine_point_subpixel(scene, scene, point)
    assert result["refinement_status"] == REFINEMENT_STATUS_FALLBACK_NUMERICAL


def test_m3_refine_point_subpixel_rejects_non_grayscale_images():
    bad_a = np.zeros((64, 64, 3), dtype=np.float32)
    bad_b = np.zeros((64, 64, 3), dtype=np.float32)
    point = {"id": "p", "x_a": 32.0, "y_a": 32.0, "x_b": 32.0, "y_b": 32.0, "score": 0.9}
    try:
        refine_point_subpixel(bad_a, bad_b, point)
        assert False, "expected ValueError for non-grayscale input"
    except ValueError:
        pass


def test_m3_refine_points_subpixel_one_bad_point_does_not_abort_batch():
    scene = generate_synthetic_scene(size=128, seed=4)
    points = [
        {"id": "good", "x_a": 64.0, "y_a": 64.0, "x_b": 64.0, "y_b": 64.0, "score": 0.9},
        {"id": "boundary", "x_a": 1.0, "y_a": 1.0, "x_b": 1.0, "y_b": 1.0, "score": 0.9},
        {"id": "nan", "x_a": float("nan"), "y_a": 1.0, "x_b": 1.0, "y_b": 1.0, "score": 0.9},
    ]
    results = refine_points_subpixel(scene, scene, points)
    assert len(results) == 3
    statuses = {r["id"]: r["refinement_status"] for r in results}
    assert statuses["boundary"] == REFINEMENT_STATUS_FALLBACK_BOUNDARY
    assert statuses["nan"] == REFINEMENT_STATUS_FALLBACK_NUMERICAL


def test_m3_run_m3_subpixel_refinement_end_to_end_on_mock_data():
    image_a, image_b, points, true_shift = generate_mock_correspondences(
        size=200, seed=10, n_points=30, true_shift=(1.1, -0.7),
    )
    result = run_m3_subpixel_refinement(image_a, image_b, points)

    dist = result["validation"]["distribution"]
    refine = result["validation"]["refinement"]
    assert dist["n_input"] == len(points)
    assert len(result["refined_points"]) == dist["n_kept"]
    assert refine["n_points"] == dist["n_kept"]
    # every mock point in this generator is marked "source": "mock" -- confirm
    # nothing downstream silently dropped that marker.
    assert all(p.get("source") == "mock" for p in result["refined_points"])


def test_m3_run_m3_subpixel_refinement_rmse_improves_on_clean_mock_data():
    image_a, image_b, points, _ = generate_mock_correspondences(
        size=200, seed=11, n_points=40, true_shift=(0.8, -0.3),
    )
    result = run_m3_subpixel_refinement(image_a, image_b, points)
    validation = result["validation"]
    assert validation["rmse_before_refinement"] is not None
    assert validation["rmse_after_refinement"] is not None
    assert validation["rmse_after_refinement"] <= validation["rmse_before_refinement"] + 1e-6


def test_m3_run_m3_subpixel_refinement_empty_input_does_not_crash():
    image_a, image_b, _, _ = generate_mock_correspondences(size=100, seed=12, n_points=1)
    result = run_m3_subpixel_refinement(image_a, image_b, [])
    assert result["refined_points"] == []
    assert result["validation"]["rmse_before_refinement"] is None


def test_m3_run_m3_subpixel_refinement_rejects_non_grayscale_images():
    bad_a = np.zeros((50, 50, 3), dtype=np.float32)
    bad_b = np.zeros((50, 50, 3), dtype=np.float32)
    try:
        run_m3_subpixel_refinement(bad_a, bad_b, [])
        assert False, "expected ValueError for non-grayscale input"
    except ValueError:
        pass
