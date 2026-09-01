"""High-level CorrespondenceEngine that chains preprocessing → matching → geometry → metrics."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

from .preprocessing import normalize_radiometric, illumination_invariant_filter
from .matchers import match_images, MatchResult
from .geometry import RobustGeometry, QuadTreeFilter, subpixel_refine
from .metrics import compute_metrics, RegistrationMetrics
from .exporter import MatchExporter


@dataclass
class CorrespondenceResult:
    metrics: RegistrationMetrics
    inlier_src: np.ndarray
    inlier_dst: np.ndarray
    homography: Optional[np.ndarray]
    match_dict: Dict[str, Any] = field(default_factory=dict)
    warped_b64: Optional[str] = None
    match_vis_b64: Optional[str] = None


class CorrespondenceEngine:
    """End-to-end multi-modal image registration pipeline."""

    def __init__(
        self,
        algorithm: str = "sift",
        geo_method: str = "RANSAC",
        reproj_thresh: float = 4.0,
        grid_size: int = 8,
        refine: bool = True,
        illumination_invariant: bool = True,
    ):
        self.algorithm = algorithm
        self.geo = RobustGeometry(method=geo_method, reproj_thresh=reproj_thresh)
        self.qtree = QuadTreeFilter(grid_size=grid_size)
        self.refine = refine
        self.illumination_invariant = illumination_invariant

    def run(
        self,
        src_img: np.ndarray,
        dst_img: np.ndarray,
        src_gsd_m: float = 1.0,
        dst_gsd_m: float = 1.0,
        include_warped: bool = False,
        include_vis: bool = False,
    ) -> CorrespondenceResult:
        """Register src_img to dst_img. Returns metrics + inlier correspondences."""
        # Preprocessing
        src_proc = normalize_radiometric(src_img)
        dst_proc = normalize_radiometric(dst_img)

        if self.illumination_invariant:
            src_proc = illumination_invariant_filter(src_proc)
            dst_proc = illumination_invariant_filter(dst_proc)

        # Feature matching
        raw_match: MatchResult = match_images(src_proc, dst_proc, algorithm=self.algorithm)

        # QuadTree spatial filtering
        if len(raw_match.src_pts) > 0:
            filtered_src, filtered_dst = self.qtree.filter(
                raw_match.src_pts,
                raw_match.dst_pts,
                dst_img.shape[:2],
                scores=raw_match.scores,
            )
        else:
            filtered_src, filtered_dst = raw_match.src_pts, raw_match.dst_pts

        # Geometric verification
        filtered_match = MatchResult(
            filtered_src, filtered_dst,
            np.ones(len(filtered_src), np.float32),
            method=raw_match.method,
            raw_match_count=raw_match.raw_match_count,
        )
        geo_result = self.geo.estimate_homography(filtered_match)

        # Sub-pixel refinement
        if self.refine and len(geo_result.inlier_src) > 0:
            ref_src, ref_dst = subpixel_refine(
                src_img, dst_img, geo_result.inlier_src, geo_result.inlier_dst
            )
        else:
            ref_src, ref_dst = geo_result.inlier_src, geo_result.inlier_dst

        # Metrics
        metrics = compute_metrics(
            geo_result,
            dst_img.shape,
            raw_match_count=raw_match.raw_match_count,
            method=raw_match.method,
        )

        # Warped output (optional)
        warped_b64 = None
        if include_warped and geo_result.H is not None:
            warped_b64 = MatchExporter.warp_to_b64(src_img, geo_result.H, dst_img.shape)

        # Match visualisation (optional)
        vis_b64 = None
        if include_vis and len(ref_src) > 0:
            vis_b64 = MatchExporter.draw_matches_b64(src_proc, dst_proc, ref_src, ref_dst)

        match_dict = MatchExporter.to_dict(ref_src, ref_dst, metrics, warped_png_b64=warped_b64)

        return CorrespondenceResult(
            metrics=metrics,
            inlier_src=ref_src,
            inlier_dst=ref_dst,
            homography=geo_result.H,
            match_dict=match_dict,
            warped_b64=warped_b64,
            match_vis_b64=vis_b64,
        )

    def benchmark(
        self,
        src_img: np.ndarray,
        dst_img: np.ndarray,
    ) -> Dict[str, CorrespondenceResult]:
        """Run all algorithms and return comparative results."""
        algorithms = ["sift", "orb", "akaze"]
        results = {}
        for algo in algorithms:
            engine = CorrespondenceEngine(
                algorithm=algo,
                geo_method=self.geo.method_name,
                refine=self.refine,
                illumination_invariant=self.illumination_invariant,
            )
            try:
                results[algo] = engine.run(src_img, dst_img)
            except Exception as e:
                # Return a failed result
                from .metrics import RegistrationMetrics
                results[algo] = CorrespondenceResult(
                    metrics=RegistrationMetrics(
                        rmse_px=float("inf"), inlier_count=0, inlier_ratio=0.0,
                        spatial_coverage=0.0, method=algo, meets_target=False,
                    ),
                    inlier_src=np.zeros((0, 2)),
                    inlier_dst=np.zeros((0, 2)),
                    homography=None,
                )
        return results
