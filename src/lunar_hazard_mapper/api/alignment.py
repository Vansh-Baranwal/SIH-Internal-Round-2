import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np

def align_rasters(source_path, reference_path, output_path, is_dem=False):
    """
    Reproject and resample the source raster to exactly match the 
    geospatial footprint, CRS, and resolution of the reference raster.
    """
    with rasterio.open(reference_path) as ref:
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_width = ref.width
        ref_height = ref.height
        
    with rasterio.open(source_path) as src:
        source_array = src.read(1)
        source_crs = src.crs
        source_transform = src.transform
        source_nodata = src.nodata
        
        # Output array
        aligned_array = np.zeros((ref_height, ref_width), dtype=src.dtypes[0])
        
        # Reproject
        reproject(
            source=source_array,
            destination=aligned_array,
            src_transform=source_transform,
            src_crs=source_crs,
            src_nodata=source_nodata,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            dst_nodata=source_nodata,
            resampling=Resampling.bilinear if is_dem else Resampling.nearest
        )
        
        # Save aligned raster
        profile = src.profile.copy()
        profile.update({
            'crs': ref_crs,
            'transform': ref_transform,
            'width': ref_width,
            'height': ref_height
        })
        
        if output_path:
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(aligned_array, 1)
            
    return aligned_array, ref_transform, ref_crs


# ==========================================================================================
# M3 -- SUB-PIXEL REFINEMENT & UNIFORM SPATIAL DISTRIBUTION
# ==========================================================================================
# Everything below this banner is the NEW SIH26166 M3 module (sub-pixel refinement of
# point correspondences + uniform spatial distribution filtering), appended to this file
# because it is the only existing module in this repository concerned with image
# alignment/registration. `align_rasters` above is untouched and unrelated: it does coarse
# CRS-level raster reprojection, while everything below operates on individual point
# correspondences at the pixel level.
#
# NOT to be confused with `m3_terrain` (a different, pre-existing "M3" under this project's
# earlier numbering -- DEM/elevation, see 01_EXISTING_PROJECT_AND_TARGET_ARCHITECTURE.md
# sec 2) or with `m6_planner/mocks/m3_mock.py` (a mock DEM provider for that same earlier
# "M3"). This section is the SIH26166 correspondence-pipeline M3 stage described in
# 02_MULTIMODAL_CORRESPONDENCE_AND_REGISTRATION.md sec 3C:
#
#     M2 (matching + RANSAC, NOT YET IMPLEMENTED anywhere in this repo)
#             |
#             v  list of correspondence dicts (see docstring of filter_uniform_grid)
#             |
#     filter_uniform_grid(...)    -- uniform spatial distribution
#             |
#             v
#     refine_points_subpixel(...) -- sub-pixel phase-correlation refinement
#             |
#             v
#     validate_m3_refinement(...) -- honest, only-what-was-measured metrics
#
# `run_m3_subpixel_refinement(...)` runs the three in order and returns everything.
#
# CORRESPONDENCE POINT FORMAT (the M2 -> M3 contract):
#   a plain dict: {"id": str, "x_a": float, "y_a": float, "x_b": float, "y_b": float,
#                  "score": float (default 1.0), "inlier": bool (default True)}
#   x = column (horizontal), y = row (vertical) -- OpenCV convention, matching what
#   cv2.getRectSubPix / cv2.phaseCorrelate expect directly.
#   Plain dicts (not a new class) are used here to match this file's and the rest of the
#   codebase's existing style (see e.g. m1_data/pairs.py) and to avoid introducing a new
#   dependency (Pydantic) or a new type definition file.
#
# M2 IS NOT IMPLEMENTED YET: `generate_mock_correspondences(...)` stands in for it, so this
# M3 code is independently testable today. It ALWAYS returns points with a
# "source": "mock" marker in the returned dict -- never present numbers computed from this
# as real-world lunar registration accuracy. Once M2 exists, replace the call to
# `generate_mock_correspondences(...)` with M2's real output (same dict-list shape); nothing
# in filter_uniform_grid / refine_points_subpixel / validate_m3_refinement needs to change.
# ==========================================================================================

import math


# ---- 1. Uniform spatial distribution --------------------------------------------------
#
# WHY A FIXED GRID, NOT A QUADTREE: 02_MULTIMODAL_CORRESPONDENCE_AND_REGISTRATION.md lists
# grid-based filtering and QuadTree as alternative approaches to the same goal (stop
# correspondences from clustering in a few high-texture regions). A fixed-resolution grid
# is used here because it is a single O(n) pass with no tree-balancing edge cases, and a
# QuadTree's main advantage (finer cells where points are dense) isn't needed for "at most K
# matches per region of one static image pair" -- only a per-cell cap is needed here.

def _point_is_finite(point):
    """Cheap sanity check: reject a correspondence with NaN/inf coordinates or a
    negative score before trusting it at all. Does not check image bounds (that
    needs image_shape, done in _grid_cell_index below)."""
    for key in ("x_a", "y_a", "x_b", "y_b", "score"):
        value = point.get(key, 0.0 if key != "score" else 1.0)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
    return point.get("score", 1.0) >= 0.0


def _grid_cell_index(x, y, image_shape, grid_size):
    """Map an (x, y) pixel coordinate (reference image A frame) to a (row, col) grid
    cell index. Returns None if the point is outside the image bounds or non-finite
    (NaN comparisons are always False in Python, so NaN falls through to "outside
    bounds" here with no special-casing needed)."""
    height, width = image_shape
    n_rows, n_cols = grid_size
    if not (0.0 <= x < width) or not (0.0 <= y < height):
        return None
    cell_col = min(int(x / width * n_cols), n_cols - 1)
    cell_row = min(int(y / height * n_rows), n_rows - 1)
    return cell_row, cell_col


def filter_uniform_grid(points, image_shape, grid_size=(8, 8), max_per_cell=1):
    """Keep at most `max_per_cell` correspondences per grid cell, preferring the
    highest-`score` point(s) within each cell, so matches end up spread across the
    whole overlap rather than concentrated in a few textured regions.

    Cell assignment uses REFERENCE image (A) coordinates, since A is the common
    frame every correspondence shares even when B is a different sensor/resolution
    (see 02_MULTIMODAL_CORRESPONDENCE_AND_REGISTRATION.md sec 2, TMC<->OHRC scale
    differences).

    Args:
        points: list of correspondence dicts (see module banner above for the shape).
        image_shape: (height, width) of reference image A, in pixels.
        grid_size: (n_rows, n_cols) cells to divide image A into.
        max_per_cell: maximum points kept per cell.

    Returns:
        dict with keys:
            "kept": list of dicts kept (spatially spread, highest score per cell)
            "dropped_clustered": list of dicts dropped only for uniformity
            "dropped_invalid": list of dicts dropped for being out of bounds / non-finite
            "grid_size": (n_rows, n_cols)
            "occupied_cells": number of cells containing at least one kept point
            "total_cells": n_rows * n_cols
            "spatial_coverage_fraction": occupied_cells / total_cells
    """
    if max_per_cell < 1:
        raise ValueError("max_per_cell must be >= 1")
    n_rows, n_cols = grid_size
    if n_rows < 1 or n_cols < 1:
        raise ValueError("grid_size dimensions must be >= 1")
    if image_shape[0] <= 0 or image_shape[1] <= 0:
        raise ValueError("image_shape must have positive height and width")

    buckets = {}
    dropped_invalid = []

    for point in points:
        if not _point_is_finite(point):
            dropped_invalid.append(point)
            continue
        cell = _grid_cell_index(point["x_a"], point["y_a"], image_shape, grid_size)
        if cell is None:
            dropped_invalid.append(point)
            continue
        buckets.setdefault(cell, []).append(point)

    kept = []
    dropped_clustered = []
    for cell_points in buckets.values():
        cell_points_sorted = sorted(cell_points, key=lambda p: p.get("score", 1.0), reverse=True)
        kept.extend(cell_points_sorted[:max_per_cell])
        dropped_clustered.extend(cell_points_sorted[max_per_cell:])

    total_cells = n_rows * n_cols
    occupied_cells = len(buckets)

    return {
        "kept": kept,
        "dropped_clustered": dropped_clustered,
        "dropped_invalid": dropped_invalid,
        "grid_size": (n_rows, n_cols),
        "occupied_cells": occupied_cells,
        "total_cells": total_cells,
        "spatial_coverage_fraction": (occupied_cells / total_cells) if total_cells else 0.0,
    }


# ---- 2. Sub-pixel refinement ------------------------------------------------------------
#
# METHOD: localized phase correlation (cv2.phaseCorrelate) on a small patch centred on each
# correspondence, rather than Lucas-Kanade optical flow. Both are listed as candidates in
# 02_MULTIMODAL_CORRESPONDENCE_AND_REGISTRATION.md. Phase correlation was chosen because it
# directly estimates one translational sub-pixel shift in a single shot (well suited to "we
# already have an approximate integer match, refine it", with no iteration/convergence
# behaviour to tune), and its response value doubles directly as a usable confidence signal.
# Lucas-Kanade would be worth revisiting if patches show significant local rotation/scale
# (which phase correlation does not model), but only one refinement path is implemented here.
#
# SIGN CONVENTION (verified empirically before relying on it, not assumed from memory of the
# OpenCV docs): for patch_a centred on (x_a, y_a) and patch_b centred on the current
# (possibly-wrong-by-a-few-pixels) guess (x_b, y_b),
#     (shift_x, shift_y), response = cv2.phaseCorrelate(patch_a, patch_b)
# gives the residual correction such that the true corresponding location in image B is
# (x_b + shift_x, y_b + shift_y). Confirmed with a synthetic image pair with a known,
# deliberately-introduced integer rounding error while building this module; the same check
# is codified in tests/integration/test_pipeline.py so a future OpenCV version silently
# changing this convention would fail loudly rather than silently refining backwards.
#
# FALLBACK BEHAVIOUR (required by the M3 spec): refinement never discards a point. If it
# cannot be trusted for a given point, this falls back to the ORIGINAL (unrefined) M2
# coordinate and records *why* refinement was skipped, so the point stays usable downstream
# and the reason is auditable.

REFINEMENT_STATUS_REFINED = "refined"
REFINEMENT_STATUS_FALLBACK_LOW_CONFIDENCE = "fallback_low_confidence"
REFINEMENT_STATUS_FALLBACK_BOUNDARY = "fallback_boundary"
REFINEMENT_STATUS_FALLBACK_LOW_TEXTURE = "fallback_low_texture"
REFINEMENT_STATUS_FALLBACK_NUMERICAL = "fallback_numerical"


def _refinement_patch_in_bounds(cx, cy, image_shape, half):
    height, width = image_shape
    return (half <= cx <= width - half) and (half <= cy <= height - half)


def _extract_refinement_patch(image, cx, cy, half):
    import cv2
    size = (2 * half, 2 * half)
    return cv2.getRectSubPix(image.astype("float32"), size, (float(cx), float(cy)))


def _normalize01(patch):
    import numpy as np
    patch = patch.astype("float32")
    lo, hi = float(patch.min()), float(patch.max())
    if hi - lo < 1e-8:
        return np.zeros_like(patch)
    return (patch - lo) / (hi - lo)


def refine_point_subpixel(image_a, image_b, point, patch_half_size=16,
                           min_texture_std=0.01, min_response=0.5, max_displacement_px=8.0):
    """Refine a single correspondence dict to sub-pixel accuracy.

    Always returns a new dict (the input `point` merged with refinement outcome
    fields) -- never raises for a "bad" individual point (invalid values, out of
    bounds, low texture, low confidence, numerical failure). On any of those, the
    point falls back to its original (x_b, y_b) with displacement_px=0.0 and a
    "refinement_status" explaining why, so one bad correspondence never aborts a
    batch. A genuine input error (wrong image ndim) still raises ValueError --
    only the failure modes explicitly listed in the M3 spec (invalid points,
    boundary problems, low-texture areas, failed refinement, numerical
    instability) are treated as expected-and-handled.

    IMPORTANT (min_texture_std units): this is compared against the RAW,
    non-normalized patch standard deviation, so it assumes input images already
    live on a consistent, roughly-unit-scale numeric range -- exactly what M1's
    existing preprocessing already guarantees (configs/preprocessing.yaml:
    radiometric.normalize + percentile clipping, output float32). Min-max
    normalizing a patch BEFORE this check would be wrong: it stretches a flat
    patch's tiny noise to fill [0, 1] and would silently defeat this exact guard
    (confirmed empirically while building this module -- a flat patch's raw std of
    ~5e-5 measured ~0.16 after per-patch min-max normalization). Normalization
    below is therefore applied only AFTER this check passes, purely to condition
    the confirmed-textured patch for phaseCorrelate.
    """
    import cv2
    import numpy as np

    if image_a.ndim != 2 or image_b.ndim != 2:
        raise ValueError("refine_point_subpixel expects single-channel (grayscale) images")

    def _fallback(status, confidence):
        result = dict(point)
        result["x_b_refined"] = point["x_b"]
        result["y_b_refined"] = point["y_b"]
        result["displacement_px"] = 0.0
        result["refinement_status"] = status
        result["refinement_confidence"] = confidence
        return result

    if not _point_is_finite(point):
        return _fallback(REFINEMENT_STATUS_FALLBACK_NUMERICAL, None)

    half = patch_half_size

    if not _refinement_patch_in_bounds(point["x_a"], point["y_a"], image_a.shape[:2], half):
        return _fallback(REFINEMENT_STATUS_FALLBACK_BOUNDARY, None)
    if not _refinement_patch_in_bounds(point["x_b"], point["y_b"], image_b.shape[:2], half):
        return _fallback(REFINEMENT_STATUS_FALLBACK_BOUNDARY, None)

    try:
        patch_a = _extract_refinement_patch(image_a, point["x_a"], point["y_a"], half)
        patch_b = _extract_refinement_patch(image_b, point["x_b"], point["y_b"], half)
    except cv2.error:
        return _fallback(REFINEMENT_STATUS_FALLBACK_NUMERICAL, None)

    if patch_a.shape != patch_b.shape or patch_a.size == 0:
        return _fallback(REFINEMENT_STATUS_FALLBACK_NUMERICAL, None)

    # Guard: texture check on RAW patches, BEFORE normalization -- see docstring above.
    if float(patch_a.std()) < min_texture_std or float(patch_b.std()) < min_texture_std:
        return _fallback(REFINEMENT_STATUS_FALLBACK_LOW_TEXTURE, None)

    patch_a = _normalize01(patch_a)
    patch_b = _normalize01(patch_b)

    window = cv2.createHanningWindow((2 * half, 2 * half), cv2.CV_32F)
    try:
        (shift_x, shift_y), response = cv2.phaseCorrelate(patch_a * window, patch_b * window)
    except cv2.error:
        return _fallback(REFINEMENT_STATUS_FALLBACK_NUMERICAL, None)

    if not (math.isfinite(shift_x) and math.isfinite(shift_y) and math.isfinite(response)):
        return _fallback(REFINEMENT_STATUS_FALLBACK_NUMERICAL, None)

    response_clamped = float(np.clip(response, 0.0, 1.0))
    displacement = math.hypot(shift_x, shift_y)

    if response_clamped < min_response or displacement > max_displacement_px:
        return _fallback(REFINEMENT_STATUS_FALLBACK_LOW_CONFIDENCE, response_clamped)

    result = dict(point)
    result["x_b_refined"] = point["x_b"] + shift_x
    result["y_b_refined"] = point["y_b"] + shift_y
    result["displacement_px"] = displacement
    result["refinement_status"] = REFINEMENT_STATUS_REFINED
    result["refinement_confidence"] = response_clamped
    return result


def refine_points_subpixel(image_a, image_b, points, **kwargs):
    """Refine a batch of correspondence dicts. One bad point never aborts the batch
    (see refine_point_subpixel docstring)."""
    return [refine_point_subpixel(image_a, image_b, p, **kwargs) for p in points]


# ---- 3. Validation ------------------------------------------------------------------
#
# Only reports numbers this module can actually compute from the data it was given -- if a
# metric needs more data than is available (e.g. RMSE needs >= 4 points to fit a homography),
# the result says so explicitly instead of silently returning a misleading number.

_MIN_POINTS_FOR_HOMOGRAPHY = 4


def summarize_distribution(filter_result):
    """Human/machine-readable summary of a filter_uniform_grid(...) result."""
    n_input = (len(filter_result["kept"]) + len(filter_result["dropped_clustered"])
               + len(filter_result["dropped_invalid"]))
    return {
        "n_input": n_input,
        "n_kept": len(filter_result["kept"]),
        "n_dropped_clustered": len(filter_result["dropped_clustered"]),
        "n_dropped_invalid": len(filter_result["dropped_invalid"]),
        "grid_size": filter_result["grid_size"],
        "occupied_cells": filter_result["occupied_cells"],
        "total_cells": filter_result["total_cells"],
        "spatial_coverage_fraction": filter_result["spatial_coverage_fraction"],
    }


def summarize_refinement(refined_points):
    """Summarize refinement outcomes honestly: only points that actually reached
    'refined' status contribute to the displacement/confidence statistics --
    fallback points have displacement_px=0.0 by construction (they weren't moved),
    so including those zeros in a 'mean displacement' would understate how much
    refinement changed things when it succeeded."""
    import numpy as np

    n_points = len(refined_points)
    status_counts = {}
    for p in refined_points:
        status = p["refinement_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    refined = [p for p in refined_points if p["refinement_status"] == REFINEMENT_STATUS_REFINED]
    n_refined = len(refined)

    if refined:
        displacements = np.array([p["displacement_px"] for p in refined], dtype="float64")
        confidences = np.array(
            [p["refinement_confidence"] for p in refined if p["refinement_confidence"] is not None],
            dtype="float64",
        )
        disp_mean = float(displacements.mean())
        disp_median = float(np.median(displacements))
        disp_max = float(displacements.max())
        conf_mean = float(confidences.mean()) if confidences.size else None
    else:
        disp_mean = disp_median = disp_max = conf_mean = None

    return {
        "n_points": n_points,
        "status_counts": status_counts,
        "n_refined": n_refined,
        "refined_fraction": (n_refined / n_points) if n_points else 0.0,
        "displacement_px_mean": disp_mean,
        "displacement_px_median": disp_median,
        "displacement_px_max": disp_max,
        "mean_refinement_confidence": conf_mean,
    }


def summarize_inliers(points):
    """Inlier/outlier breakdown of the points M3 received from M2 (M3 does not
    re-run RANSAC -- this simply reports what M2 flagged)."""
    n = len(points)
    n_inlier = sum(1 for p in points if p.get("inlier", True))
    return {
        "n_points": n,
        "n_inlier": n_inlier,
        "n_outlier": n - n_inlier,
        "inlier_fraction": (n_inlier / n) if n else 0.0,
    }


def compute_homography_rmse(points, x_b_key="x_b", y_b_key="y_b", ransac_reproj_threshold=3.0):
    """OPTIONAL, informational-only check: fit a homography from (x_a, y_a) ->
    (x_b_key, y_b_key) with RANSAC, and report the RMSE of the inlier set. Useful
    for comparing "before refinement" (x_b_key="x_b") vs "after refinement"
    (x_b_key="x_b_refined") RMSE on the SAME correspondence set.

    This does not replace M2's own registration-quality metrics
    (02_MULTIMODAL_CORRESPONDENCE_AND_REGISTRATION.md sec 5) -- it's a lightweight
    sanity check M3 can run on its own output without depending on M2 existing.

    Returns {"label": "insufficient_points", "rmse_px": None, ...} rather than
    raising or fabricating a number when fewer than 4 valid points are available
    (a homography needs at least 4 point pairs to be fit at all).
    """
    import cv2
    import numpy as np

    valid = [p for p in points if _point_is_finite(p) and x_b_key in p and y_b_key in p]
    if len(valid) < _MIN_POINTS_FOR_HOMOGRAPHY:
        return {"label": "insufficient_points", "rmse_px": None,
                "n_points_used": len(valid), "n_inliers": 0}

    src = np.array([[p["x_a"], p["y_a"]] for p in valid], dtype="float64")
    dst = np.array([[p[x_b_key], p[y_b_key]] for p in valid], dtype="float64")

    H, inlier_mask = cv2.findHomography(src, dst, cv2.RANSAC, ransac_reproj_threshold)
    if H is None or inlier_mask is None:
        return {"label": "degenerate", "rmse_px": None,
                "n_points_used": len(valid), "n_inliers": 0}

    inlier_mask = inlier_mask.ravel().astype(bool)
    n_inliers = int(inlier_mask.sum())
    if n_inliers < _MIN_POINTS_FOR_HOMOGRAPHY:
        return {"label": "degenerate", "rmse_px": None,
                "n_points_used": len(valid), "n_inliers": n_inliers}

    src_h = cv2.perspectiveTransform(src[inlier_mask].reshape(-1, 1, 2), H).reshape(-1, 2)
    residuals = src_h - dst[inlier_mask]
    rmse = float(np.sqrt(np.mean(np.sum(residuals ** 2, axis=1))))

    return {"label": "computed", "rmse_px": rmse, "n_points_used": len(valid), "n_inliers": n_inliers}


def validate_m3_refinement(filter_result, refined_points, compute_rmse=True):
    """Combine all M3 validation reports into one dict -- the single call site
    the orchestrator (`run_m3_subpixel_refinement`) and callers should use."""
    report = {
        "distribution": summarize_distribution(filter_result),
        "refinement": summarize_refinement(refined_points),
        "inliers": summarize_inliers(filter_result["kept"]),
        "rmse_before_refinement": None,
        "rmse_after_refinement": None,
    }
    if compute_rmse:
        report["rmse_before_refinement"] = compute_homography_rmse(refined_points, "x_b", "y_b")["rmse_px"]
        report["rmse_after_refinement"] = compute_homography_rmse(
            refined_points, "x_b_refined", "y_b_refined")["rmse_px"]
    return report


# ---- 4. Orchestration ------------------------------------------------------------------

def run_m3_subpixel_refinement(image_a, image_b, correspondence_points,
                                grid_size=(8, 8), max_per_cell=1,
                                refinement_kwargs=None, compute_rmse=True):
    """Run the full M3 stage: uniform distribution filtering (cheap), then
    sub-pixel refinement (more expensive -- patch extraction + phase correlation),
    then validation reporting.

    Distribution runs BEFORE refinement deliberately: filtering down to a
    spatially-uniform subset first avoids spending refinement's per-point cost
    on points that would be discarded for clustering anyway.

    Args:
        image_a: reference image, single-channel (grayscale), any numeric dtype.
        image_b: source image to refine against, single-channel.
        correspondence_points: list of correspondence dicts (M2's output, or
            generate_mock_correspondences(...) for independent testing -- see
            module banner for the exact dict shape and the M2 integration note).
        grid_size, max_per_cell: passed to filter_uniform_grid.
        refinement_kwargs: dict of extra kwargs passed to refine_point_subpixel
            (patch_half_size, min_texture_std, min_response, max_displacement_px).
        compute_rmse: whether to run the optional homography-RMSE sanity check.

    Returns:
        dict with keys "refined_points" (list of dicts) and "validation" (the
        dict from validate_m3_refinement).
    """
    if image_a.ndim != 2 or image_b.ndim != 2:
        raise ValueError("run_m3_subpixel_refinement expects single-channel (grayscale) images")

    filter_result = filter_uniform_grid(
        correspondence_points, image_shape=image_a.shape[:2],
        grid_size=grid_size, max_per_cell=max_per_cell,
    )

    refined_points = refine_points_subpixel(
        image_a, image_b, filter_result["kept"], **(refinement_kwargs or {})
    )

    validation = validate_m3_refinement(filter_result, refined_points, compute_rmse=compute_rmse)

    return {"refined_points": refined_points, "validation": validation}


# ---- 5. Mock M2 input (TEMPORARY -- M2 is not implemented yet) --------------------------
#
# Stands in for M2's real output so M3 is independently developable/testable today.
# ALWAYS returns "source": "mock" -- never present numbers computed from this as
# real-world lunar registration accuracy. See module banner above for the
# real-M2-integration note (same dict-list shape, so nothing downstream needs to change).

def generate_synthetic_scene(size=256, seed=0):
    """A reproducible, texture-rich synthetic 'lunar-like' grayscale scene: blurred
    noise plus a handful of crater-like radial dips (for real texture) and two
    deliberately flat corners (so refinement's low-texture fallback path is
    actually exercised, not just the happy path). Returned as float32 in [0, 1].
    NOT lunar imagery -- purely a synthetic stand-in for testing M3 without
    depending on M2 or real data."""
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    scene = rng.uniform(0, 1, (size, size)).astype("float32")
    scene = cv2.GaussianBlur(scene, (5, 5), 1.2)

    yy, xx = np.mgrid[0:size, 0:size].astype("float32")
    for _ in range(6):
        cx, cy = rng.uniform(0.15, 0.85, 2) * size
        radius = rng.uniform(0.03, 0.08) * size
        depth = rng.uniform(0.15, 0.35)
        dist2 = (xx - cx) ** 2 + (yy - cy) ** 2
        scene -= depth * np.exp(-dist2 / (2 * radius ** 2)).astype("float32")

    scene = np.clip(scene, 0.0, 1.0)

    flat_size = size // 8
    scene[0:flat_size, 0:flat_size] = 0.5
    scene[-flat_size:, -flat_size:] = 0.5

    return scene


def generate_mock_correspondences(size=256, seed=0, true_shift=(1.3, -0.8),
                                   n_points=40, cluster_fraction=0.4, margin=24):
    """Build a synthetic image pair (image_a, image_b) where image_b is image_a's
    scene content shifted by a known sub-pixel (true_shift_x, true_shift_y), plus
    a mock list of candidate correspondence dicts between them.

    Candidates deliberately mimic realistic matcher output: placed at INTEGER
    pixel coordinates only (a real matcher would not hand M3 an already-perfect
    sub-pixel answer -- that's exactly what M3 exists to add), with a fraction
    (`cluster_fraction`) intentionally clustered into one region (simulating a
    texture-rich crater cluster dominating the raw match set, so
    filter_uniform_grid has something real to do) and the rest spread
    pseudo-uniformly.

    Returns:
        (image_a, image_b, correspondence_points, true_shift) -- true_shift is
        returned separately (not embedded in the correspondence dicts) because a
        real M2 would not know it either; it exists only so tests/demos can check
        how close refinement gets to it.
    """
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    scene = generate_synthetic_scene(size=size, seed=seed)
    image_a = scene

    shift_x, shift_y = true_shift
    M = np.array([[1, 0, shift_x], [0, 1, shift_y]], dtype="float32")
    image_b = cv2.warpAffine(scene, M, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # margin/jitter are clamped relative to `size` so this never produces an
    # inverted/empty [low, high] range on small images (e.g. small test fixtures).
    margin = min(margin, max(1, size // 4 - 1))
    low, high = margin, size - margin
    if high <= low:
        raise ValueError(f"generate_mock_correspondences: size={size} too small for any margin")
    span = high - low
    cluster_jitter = min(20.0, span * 0.25)
    cluster_radius = min(15.0, span * 0.2)

    n_clustered = int(n_points * cluster_fraction)
    n_spread = n_points - n_clustered
    points = []

    cluster_cx = float(rng.uniform(low + cluster_jitter, high - cluster_jitter))
    cluster_cy = float(rng.uniform(low + cluster_jitter, high - cluster_jitter))
    for i in range(n_clustered):
        xa = float(np.clip(cluster_cx + rng.uniform(-cluster_radius, cluster_radius), low, high))
        ya = float(np.clip(cluster_cy + rng.uniform(-cluster_radius, cluster_radius), low, high))
        points.append(_make_mock_point(f"cluster_{i}", xa, ya, shift_x, shift_y, rng))

    grid_n = max(1, int(math.ceil(math.sqrt(n_spread))))
    idx = 0
    for gy in range(grid_n):
        for gx in range(grid_n):
            if idx >= n_spread:
                break
            xa = low + (high - low) * (gx + 0.5) / grid_n + rng.uniform(-3, 3)
            ya = low + (high - low) * (gy + 0.5) / grid_n + rng.uniform(-3, 3)
            xa, ya = float(np.clip(xa, low, high)), float(np.clip(ya, low, high))
            points.append(_make_mock_point(f"spread_{idx}", xa, ya, shift_x, shift_y, rng))
            idx += 1

    return image_a, image_b, points, true_shift


def _make_mock_point(point_id, xa, ya, shift_x, shift_y, rng):
    """Round the true corresponding B location to the nearest integer pixel,
    simulating a real matcher's inherent quantization -- exactly what
    refine_point_subpixel's phase correlation is meant to recover."""
    xb = round(xa + shift_x)
    yb = round(ya + shift_y)
    score = float(min(max(rng.uniform(0.6, 0.99), 0.0), 1.0))
    return {"id": point_id, "x_a": xa, "y_a": ya, "x_b": float(xb), "y_b": float(yb),
            "score": score, "inlier": True, "source": "mock"}


if __name__ == "__main__":
    # Runnable demo / sanity check using SYNTHETIC mock data (M2 is not implemented
    # yet -- see module banner). Run with:
    #     PYTHONPATH=src python -m lunar_hazard_mapper.api.alignment
    print("M3 (Sub-Pixel Refinement & Uniform Distribution) demo")
    print("*** ALL DATA BELOW IS SYNTHETIC / MOCK -- M2 is not implemented yet. ***\n")

    image_a, image_b, points, true_shift = generate_mock_correspondences(
        size=256, seed=0, true_shift=(1.3, -0.8), n_points=40, cluster_fraction=0.4,
    )
    print(f"Generated {len(points)} mock correspondences. True synthetic shift: {true_shift}\n")

    result = run_m3_subpixel_refinement(image_a, image_b, points)
    dist = result["validation"]["distribution"]
    refine = result["validation"]["refinement"]

    print("Uniform spatial distribution filtering:")
    print(f"  input={dist['n_input']}  kept={dist['n_kept']}  "
          f"dropped_clustered={dist['n_dropped_clustered']}  "
          f"dropped_invalid={dist['n_dropped_invalid']}")
    print(f"  grid={dist['grid_size']}  coverage={dist['spatial_coverage_fraction']:.1%}\n")

    print("Sub-pixel refinement:")
    for status, count in sorted(refine["status_counts"].items()):
        print(f"  {status:<28} {count}")
    if refine["n_refined"]:
        print(f"  mean correction: {refine['displacement_px_mean']:.3f} px")
        print(f"  mean confidence: {refine['mean_refinement_confidence']:.3f}")
    print(f"\n  RMSE before refinement: {result['validation']['rmse_before_refinement']}")
    print(f"  RMSE after refinement:  {result['validation']['rmse_after_refinement']}")
