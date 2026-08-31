"""
Stage D: Registration & Output Generation.

Applies the final verified transformation to warp the source image into
alignment with the reference, using high-quality Lanczos interpolation (per
your doc's explicit requirement), and exports the validated match points in
standard formats for downstream analysis/scoring.
"""
from __future__ import annotations
import numpy as np
import cv2
import json
import csv


def warp_image(source: np.ndarray, transform_matrix: np.ndarray | None,
                tps_transformer: object | None, model_type: str,
                output_shape: tuple[int, int]) -> np.ndarray:
    """
    output_shape: (height, width) of the reference image, which is the target
    frame the source gets warped into.
    """
    h, w = output_shape[:2]

    if model_type == "affine":
        return cv2.warpAffine(source, transform_matrix, (w, h), flags=cv2.INTER_LANCZOS4)
    elif model_type == "homography":
        return cv2.warpPerspective(source, transform_matrix, (w, h), flags=cv2.INTER_LANCZOS4)
    elif model_type == "tps":
        if tps_transformer is None:
            raise ValueError("TPS transformer is None — check that estimate_thin_plate_spline succeeded.")
        warped = tps_transformer.warpImage(source)
        return warped
    else:
        raise ValueError(f"unknown model_type: {model_type}")


def export_matches_csv(pts_src: np.ndarray, pts_ref: np.ndarray,
                        confidences: np.ndarray, out_path: str):
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["src_x", "src_y", "ref_x", "ref_y", "confidence"])
        for (sx, sy), (rx, ry), conf in zip(pts_src, pts_ref, confidences):
            writer.writerow([sx, sy, rx, ry, conf])


def export_matches_json(pts_src: np.ndarray, pts_ref: np.ndarray,
                         confidences: np.ndarray, metrics: dict, out_path: str):
    data = {
        "metrics": metrics,
        "matches": [
            {"src": [float(sx), float(sy)], "ref": [float(rx), float(ry)], "confidence": float(conf)}
            for (sx, sy), (rx, ry), conf in zip(pts_src, pts_ref, confidences)
        ],
    }
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)


def draw_match_visualization(source: np.ndarray, reference: np.ndarray,
                              pts_src: np.ndarray, pts_ref: np.ndarray,
                              max_lines: int = 200) -> np.ndarray:
    """
    Side-by-side visualization with lines connecting matched points — useful
    for the frontend's Registration Cockpit view described in your UX plan.
    """
    kp1 = [cv2.KeyPoint(float(x), float(y), 5) for x, y in pts_src]
    kp2 = [cv2.KeyPoint(float(x), float(y), 5) for x, y in pts_ref]
    matches = [cv2.DMatch(i, i, 0) for i in range(min(len(pts_src), max_lines))]

    src_color = cv2.cvtColor(source, cv2.COLOR_GRAY2BGR) if source.ndim == 2 else source
    ref_color = cv2.cvtColor(reference, cv2.COLOR_GRAY2BGR) if reference.ndim == 2 else reference

    return cv2.drawMatches(src_color, kp1, ref_color, kp2, matches, None,
                            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
