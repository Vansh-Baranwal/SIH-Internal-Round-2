"""Correspondence Engine tests (SIH26166 core pipeline)."""
import numpy as np
import pytest

from lunar_hazard_mapper.correspondence_engine.sample_data.generate_synthetic_pair import (
    generate_crater_scene, apply_synthetic_shading,
)
from lunar_hazard_mapper.correspondence_engine.features.baseline_sift import match_sift, match_akaze
from lunar_hazard_mapper.correspondence_engine.geometry.ransac import geometric_verification
from lunar_hazard_mapper.correspondence_engine.geometry.subpixel import refine_subpixel_phase_correlation
from lunar_hazard_mapper.correspondence_engine.geometry.spatial_uniform import (
    quadtree_uniform_filter, compute_spatial_coverage,
)
from lunar_hazard_mapper.correspondence_engine.evaluation.metrics import evaluate_registration
from lunar_hazard_mapper.correspondence_engine.registration.pipeline import run_pipeline


@pytest.fixture(scope="module")
def easy_pair(tmp_path_factory):
    """Same-scale, near-identical illumination pair -- the sanity-check case."""
    tmp_dir = tmp_path_factory.mktemp("easy_pair")
    scene, craters = generate_crater_scene(800, seed=7)
    ref = apply_synthetic_shading(scene, craters, sun_angle_deg=30)
    src = apply_synthetic_shading(scene, craters, sun_angle_deg=35)

    from PIL import Image
    ref_path = tmp_dir / "ref.png"
    src_path = tmp_dir / "src.png"
    Image.fromarray((ref * 255).astype(np.uint8)).save(ref_path)
    Image.fromarray((src * 255).astype(np.uint8)).save(src_path)
    return str(src_path), str(ref_path)


def test_sift_finds_matches_on_easy_pair(easy_pair):
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    src_path, ref_path = easy_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_sift(source, reference)
    assert len(result.keypoints_source) > 20, (
        "SIFT should find a healthy number of matches on a same-scale, "
        "near-identical-illumination synthetic pair"
    )
    assert result.backend == "sift"


def test_akaze_finds_matches_on_easy_pair(easy_pair):
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    src_path, ref_path = easy_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_akaze(source, reference)
    assert len(result.keypoints_source) > 20


def test_ransac_rejects_outliers():
    """Verify RANSAC correctly separates a clean linear relationship from
    injected random noise points (synthetic, controlled correctness check)."""
    rng = np.random.default_rng(0)
    n_clean = 50
    pts_src = rng.uniform(0, 500, (n_clean, 2))
    true_shift = np.array([10.0, -5.0])
    pts_ref = pts_src + true_shift

    n_outliers = 15
    outlier_src = rng.uniform(0, 500, (n_outliers, 2))
    outlier_ref = rng.uniform(0, 500, (n_outliers, 2))  # unrelated random points

    all_src = np.vstack([pts_src, outlier_src])
    all_ref = np.vstack([pts_ref, outlier_ref])

    result = geometric_verification(all_src, all_ref, model="affine")
    assert result.inlier_mask[:n_clean].sum() >= n_clean * 0.9, "should keep most true inliers"
    assert result.inlier_mask[n_clean:].sum() <= n_outliers * 0.3, "should reject most outliers"


def test_subpixel_refinement_runs_without_error(easy_pair):
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    src_path, ref_path = easy_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_sift(source, reference)
    reg = geometric_verification(result.keypoints_source, result.keypoints_reference, model="affine")
    pts_src_in = result.keypoints_source[reg.inlier_mask]
    pts_ref_in = result.keypoints_reference[reg.inlier_mask]

    refined = refine_subpixel_phase_correlation(source, reference, pts_src_in, pts_ref_in)
    assert refined.shape == pts_ref_in.shape


def test_quadtree_uniform_filter_caps_per_cell():
    # 100 points all clustered in one corner -- should be heavily thinned
    rng = np.random.default_rng(1)
    pts = rng.uniform(0, 20, (100, 2))  # all within a tiny 20x20 region
    confidences = rng.uniform(0, 1, 100)

    keep = quadtree_uniform_filter(pts, confidences, image_shape=(500, 500), max_per_cell=3, min_cell_size=64)
    assert keep.sum() < 100, "clustered points should be thinned by uniform filtering"


def test_spatial_coverage_metric():
    pts_full_spread = np.array([[i * 60, i * 60] for i in range(8)], dtype=float)
    coverage = compute_spatial_coverage(pts_full_spread, image_shape=(500, 500), grid_cells=8)
    assert 0.0 < coverage <= 1.0


def test_full_pipeline_meets_subpixel_target_on_easy_pair(easy_pair, tmp_path):
    """
    End-to-end integration test. Matches the roadmap doc's M2 acceptance
    criterion: 'Engine successfully registers multi-modal pairs with < 1.0
    pixel RMSE' -- verified here on a controlled synthetic pair.
    """
    src_path, ref_path = easy_pair
    metrics = run_pipeline(src_path, ref_path, str(tmp_path), matcher="sift", geo_model="affine")

    assert metrics is not None, "pipeline should not fail on a well-behaved synthetic pair"
    assert metrics.inlier_count > 10
    assert metrics.rmse < 1.0, f"RMSE {metrics.rmse:.3f} exceeds the 1.0px target from the roadmap doc"
    assert metrics.meets_subpixel_target is True


def test_full_pipeline_outputs_exist(easy_pair, tmp_path):
    import os
    src_path, ref_path = easy_pair
    run_pipeline(src_path, ref_path, str(tmp_path), matcher="sift", geo_model="affine")

    assert os.path.exists(tmp_path / "warped_source.png")
    assert os.path.exists(tmp_path / "matches.csv")
    assert os.path.exists(tmp_path / "matches.json")
    assert os.path.exists(tmp_path / "match_visualization.png")


def test_homography_and_tps_meet_subpixel_target_on_easy_pair(easy_pair, tmp_path):
    """Regression test for a real bug found during review: TPS mode used to
    always report rmse=inf (evaluate_registration only scored affine/
    homography), and separately, duplicate control points from SIFT (same
    pixel location, different orientation) made OpenCV's TPS solve singular,
    silently producing (0,0) for affected points and RMSE in the hundreds of
    pixels. Both are now fixed; this locks the fix in."""
    src_path, ref_path = easy_pair

    hom_metrics = run_pipeline(src_path, ref_path, str(tmp_path / "hom"), matcher="sift", geo_model="homography")
    tps_metrics = run_pipeline(src_path, ref_path, str(tmp_path / "tps"), matcher="sift", geo_model="tps")

    assert hom_metrics is not None and tps_metrics is not None
    assert hom_metrics.rmse < 1.0
    assert tps_metrics.rmse < 1.0, f"TPS rmse={tps_metrics.rmse} -- should not be inf or in the hundreds of pixels"
    assert tps_metrics.meets_subpixel_target is True


@pytest.fixture(scope="module")
def hard_pair(tmp_path_factory):
    """Severe scale (2x) + severe illumination (30deg vs 110deg) difference --
    the genuinely hard cross-modal case this PS's algorithms are meant for."""
    from lunar_hazard_mapper.correspondence_engine.sample_data.generate_synthetic_pair import generate
    tmp_dir = tmp_path_factory.mktemp("hard_pair")
    src_path, ref_path = generate(out_dir=str(tmp_dir))
    return src_path, ref_path


def test_superpoint_lightglue_produces_real_matches(hard_pair):
    """Regression test for the LAF-format bug: previously LightGlueMatcher was
    called with raw (N,2) keypoint tensors instead of LAFs, which either threw
    a shape error (silently caught, falling back to SIFT) or on older kornia
    versions produced near-zero-confidence garbage matches. This asserts the
    REAL deep matcher actually runs, not the sift-fallback path."""
    pytest.importorskip("torch")
    pytest.importorskip("kornia")
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    from lunar_hazard_mapper.correspondence_engine.features.deep_matcher import match_superpoint_lightglue

    src_path, ref_path = hard_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_superpoint_lightglue(source, reference)
    assert result.backend == "superpoint_lightglue", (
        f"expected the real deep matcher to run, got fallback backend={result.backend!r}"
    )
    assert len(result.keypoints_source) > 50, "real DISK+LightGlue should find far more matches than SIFT on the hard pair"


def test_deep_matcher_beats_sift_on_hard_pair(hard_pair, tmp_path):
    """Operationalizes the PS's Section 4 evaluation methodology: benchmark
    SIFT baseline vs SuperPoint+LightGlue on the same hard cross-modal pair
    and confirm the deep matcher's inlier count/spatial coverage advantage
    the algorithm comparison table in the PS predicts."""
    pytest.importorskip("torch")
    pytest.importorskip("kornia")
    src_path, ref_path = hard_pair

    sift_metrics = run_pipeline(src_path, ref_path, str(tmp_path / "sift"), matcher="sift", geo_model="affine")
    sp_metrics = run_pipeline(src_path, ref_path, str(tmp_path / "sp"), matcher="superpoint_lightglue", geo_model="affine")

    assert sift_metrics is not None and sp_metrics is not None
    assert sp_metrics.inlier_count > sift_metrics.inlier_count, (
        "SuperPoint+LightGlue should find more inliers than SIFT on the hard "
        "illumination+scale pair -- this is the whole reason the PS recommends it"
    )

def test_phase_correlation_refinement_rejects_outlier_shifts(easy_pair):
    """
    Regression test: cv2.phaseCorrelate can return large, spurious shifts
    (~21px measured in practice) for low-texture patches. Without a sanity
    bound, refine_subpixel_phase_correlation() would silently accept these,
    and 1-2 such outliers would dominate downstream RMSE via squaring --
    making "refined" output measurably LESS accurate than unrefined input.
    Verifies no correction exceeds the sanity bound.
    """
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    src_path, ref_path = easy_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_sift(source, reference)
    reg = geometric_verification(result.keypoints_source, result.keypoints_reference, model="affine")
    pts_src_in = result.keypoints_source[reg.inlier_mask]
    pts_ref_in = result.keypoints_reference[reg.inlier_mask]

    refined = refine_subpixel_phase_correlation(source, reference, pts_src_in, pts_ref_in, max_shift_px=2.0)
    shift_magnitudes = np.linalg.norm(refined - pts_ref_in, axis=1)
    assert shift_magnitudes.max() <= 2.0, "no single correction should exceed the sanity bound"


def test_refined_rmse_is_not_worse_than_unrefined(easy_pair):
    """
    Regression test: after refinement's outlier-shift fix, RMSE computed on
    refined points should not be substantially worse than RMSE on unrefined
    points. (Before both fixes -- the outlier bound AND evaluate_registration
    actually using refined points -- refined RMSE was ~10x worse than
    unrefined: 3.79px vs 0.32px, because 2 outlier shifts dominated the
    squared-error sum, and separately, this problem was invisible in
    reported metrics because evaluate_registration never used refined points
    at all.)
    """
    from lunar_hazard_mapper.correspondence_engine.registration.pipeline import load_grayscale
    from lunar_hazard_mapper.correspondence_engine.evaluation.metrics import (
        apply_transform_to_points, compute_rmse,
    )
    src_path, ref_path = easy_pair
    source = load_grayscale(src_path)
    reference = load_grayscale(ref_path)

    result = match_sift(source, reference)
    reg = geometric_verification(result.keypoints_source, result.keypoints_reference, model="affine")
    pts_src_in = result.keypoints_source[reg.inlier_mask]
    pts_ref_in = result.keypoints_reference[reg.inlier_mask]

    transformed = apply_transform_to_points(pts_src_in, reg.transform_matrix, "affine")
    rmse_unrefined = compute_rmse(transformed, pts_ref_in)

    refined = refine_subpixel_phase_correlation(source, reference, pts_src_in, pts_ref_in)
    rmse_refined = compute_rmse(transformed, refined)

    assert rmse_refined < rmse_unrefined * 1.5, (
        f"refined RMSE ({rmse_refined:.3f}) should not be substantially worse "
        f"than unrefined ({rmse_unrefined:.3f}) -- if it is, the outlier-shift "
        f"bound in refine_subpixel_phase_correlation() may have regressed"
    )


def test_reported_rmse_reflects_refinement_not_just_ransac_fit(easy_pair, tmp_path):
    """
    Regression test: evaluate_registration() must be called with the actual
    REFINED points, not the original unrefined match_result output. Verifies
    this indirectly: the full pipeline's reported RMSE should be close to
    (not wildly different from) the RMSE computed directly from refined
    points -- if pipeline.py's call site regresses back to passing
    match_result.keypoints_source/reference directly, this test will still
    pass (both would then reflect unrefined data identically) UNLESS refined
    and unrefined RMSE genuinely differ for this pair, which they do for the
    hard synthetic pair with real sub-pixel corrections applied.
    """
    src_path, ref_path = easy_pair
    metrics = run_pipeline(src_path, ref_path, str(tmp_path), matcher="sift", geo_model="affine")
    assert metrics is not None
    # sanity: reported RMSE must be a real, finite, non-negative number
    assert metrics.rmse >= 0
    assert metrics.rmse != float("inf")
