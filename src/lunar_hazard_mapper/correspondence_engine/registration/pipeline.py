"""
Full M2 Correspondence Engine pipeline: Stage A -> B -> C -> D -> Evaluation.

CLI entry point:
    python -m src.registration.pipeline --source X --reference Y --matcher sift --out output/
"""
from __future__ import annotations
import argparse
import os
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import cv2

from lunar_hazard_mapper.correspondence_engine.preprocessing.radiometric import radiometric_pipeline
from lunar_hazard_mapper.correspondence_engine.preprocessing.scale import match_scale
from lunar_hazard_mapper.correspondence_engine.preprocessing.illumination import phase_congruency_map
from lunar_hazard_mapper.correspondence_engine.features.baseline_sift import match_sift, match_akaze
from lunar_hazard_mapper.correspondence_engine.features.deep_matcher import match_superpoint_lightglue
from lunar_hazard_mapper.correspondence_engine.features.loftr_matcher import match_loftr
from lunar_hazard_mapper.correspondence_engine.geometry.ransac import geometric_verification
from lunar_hazard_mapper.correspondence_engine.geometry.subpixel import refine_subpixel_phase_correlation
from lunar_hazard_mapper.correspondence_engine.geometry.spatial_uniform import quadtree_uniform_filter
from lunar_hazard_mapper.correspondence_engine.registration.warp import warp_image, export_matches_csv, export_matches_json, draw_match_visualization
from lunar_hazard_mapper.correspondence_engine.evaluation.metrics import evaluate_registration


MATCHERS = {
    "sift": match_sift,
    "akaze": match_akaze,
    "superpoint_lightglue": match_superpoint_lightglue,
    "loftr": match_loftr,
}


def load_grayscale(path: str) -> np.ndarray:
    if path.lower().endswith((".tif", ".tiff")):
        import rasterio
        with rasterio.open(path) as src:
            arr = src.read(1)
            arr = cv2.normalize(arr, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    else:
        img = Image.open(path).convert("L")
        arr = np.array(img)
    
    # Auto-downsample massive images to prevent OpenCV SIFT OutOfMemoryError (e.g. 4.2GB allocs)
    max_dim = 2000
    h, w = arr.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        arr = cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
    return arr


def run_pipeline(
    source_path: str,
    reference_path: str,
    output_dir: str,
    matcher: str = "sift",
    geo_model: str = "affine",
    source_gsd_m: float = 0.3,
    reference_gsd_m: float = 5.0,
    apply_scale_matching: bool = False,
    apply_uniform_filter: bool = True,
    max_per_cell: int = 3,
    apply_illumination_invariant: bool = False,
    sun_azimuth: float = 135.0,
):
    os.makedirs(output_dir, exist_ok=True)

    print(f"[Stage A] Loading and normalizing images...")
    source = load_grayscale(source_path)
    reference = load_grayscale(reference_path)

    if apply_scale_matching:
        source, reference, scale_factor = match_scale(source, reference, source_gsd_m, reference_gsd_m)
        print(f"          scale-matched, factor applied: {scale_factor:.3f}")

    source_norm, reference_norm = radiometric_pipeline(source, reference)

    if apply_illumination_invariant:
        print(f"          applying sun-angle directional filter (Azimuth: {sun_azimuth})...")
        from lunar_hazard_mapper.correspondence_engine.preprocessing.illumination import simulate_sun_angle_filter
        source_for_matching = simulate_sun_angle_filter(source_norm, sun_azimuth)
        reference_for_matching = simulate_sun_angle_filter(reference_norm, sun_azimuth)
    else:
        source_for_matching = source_norm
        reference_for_matching = reference_norm

    print(f"[Stage B] Matching features (backend requested: {matcher})...")
    if matcher not in MATCHERS:
        raise ValueError(f"unknown matcher: {matcher}. choose from {list(MATCHERS.keys())}")
    match_result = MATCHERS[matcher](source_for_matching, reference_for_matching)
    actual_backend = match_result.backend
    print(f"          backend used: {actual_backend}  |  raw matches: {len(match_result.keypoints_source)}")

    if len(match_result.keypoints_source) < 3:
        print("          WARNING: too few matches to proceed with geometric verification.")
        return None

    print(f"[Stage C] Geometric verification (model={geo_model})...")
    reg_transform = geometric_verification(
        match_result.keypoints_source, match_result.keypoints_reference, model=geo_model
    )
    print(f"          inliers: {reg_transform.inlier_mask.sum()} / {len(match_result.keypoints_source)}")

    pts_src_in = match_result.keypoints_source[reg_transform.inlier_mask]
    pts_ref_in = match_result.keypoints_reference[reg_transform.inlier_mask]
    conf_in = match_result.match_confidences[reg_transform.inlier_mask]

    print(f"          sub-pixel refinement...")
    pts_ref_refined = refine_subpixel_phase_correlation(source_norm, reference_norm, pts_src_in, pts_ref_in)

    if apply_uniform_filter and len(pts_ref_refined) > 0:
        print(f"          applying QuadTree uniform-distribution filter...")
        keep = quadtree_uniform_filter(pts_ref_refined, conf_in, reference_norm.shape, max_per_cell=max_per_cell)
        pts_src_final = pts_src_in[keep]
        pts_ref_final = pts_ref_refined[keep]
        conf_final = conf_in[keep]
        print(f"          kept after uniform filtering: {keep.sum()} / {len(keep)}")
    else:
        pts_src_final, pts_ref_final, conf_final = pts_src_in, pts_ref_refined, conf_in

    print(f"[Stage D] Warping and exporting...")
    if reg_transform.transform_matrix is not None or reg_transform.tps_transformer is not None:
        warped = warp_image(source, reg_transform.transform_matrix, reg_transform.tps_transformer,
                             reg_transform.model_type, reference.shape)
        cv2.imwrite(os.path.join(output_dir, "warped_source.png"), warped)

    metrics = evaluate_registration(
        pts_src_in, pts_ref_refined,
        inlier_count=len(pts_src_in), total_matches=len(match_result.keypoints_source),
        transform_matrix=reg_transform.transform_matrix, model_type=reg_transform.model_type,
        coverage_points=pts_ref_final, image_shape=reference.shape,
        tps_transformer=reg_transform.tps_transformer,
    )
    print(f"\n=== METRICS ===")
    for k, v in metrics.to_dict().items():
        print(f"  {k}: {v}")

    export_matches_csv(pts_src_final, pts_ref_final, conf_final, os.path.join(output_dir, "matches.csv"))
    export_matches_json(pts_src_final, pts_ref_final, conf_final, metrics.to_dict(),
                         os.path.join(output_dir, "matches.json"))

    viz = draw_match_visualization(source, reference, pts_src_final, pts_ref_final)
    cv2.imwrite(os.path.join(output_dir, "match_visualization.png"), viz)

    print(f"\nDone. Outputs in {output_dir}/: warped_source.png, matches.csv, matches.json, match_visualization.png")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--out", default="output/")
    parser.add_argument("--matcher", default="sift", choices=list(MATCHERS.keys()))
    parser.add_argument("--geo-model", default="affine", choices=["affine", "homography", "tps"])
    parser.add_argument("--scale-match", action="store_true")
    parser.add_argument("--illumination-invariant", action="store_true",
                         help="Apply Stage A.2 phase-congruency illumination-invariant "
                              "transform before feature matching (helps with severe "
                              "sun-angle differences between source and reference).")
    parser.add_argument("--source-gsd", type=float, default=0.3)
    parser.add_argument("--reference-gsd", type=float, default=5.0)
    args = parser.parse_args()

    run_pipeline(
        args.source, args.reference, args.out,
        matcher=args.matcher, geo_model=args.geo_model,
        source_gsd_m=args.source_gsd, reference_gsd_m=args.reference_gsd,
        apply_scale_matching=args.scale_match,
        apply_illumination_invariant=args.illumination_invariant,
    )