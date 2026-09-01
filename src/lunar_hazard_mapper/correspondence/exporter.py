"""Export match points to JSON / GeoJSON / CSV and save warped registered images."""

from __future__ import annotations

import json
import csv
import io
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List

import numpy as np
import cv2

from .geometry import GeometryResult
from .metrics import RegistrationMetrics


class MatchExporter:
    """Serialise correspondences and warped imagery to various output formats."""

    @staticmethod
    def to_dict(
        src_pts: np.ndarray,
        dst_pts: np.ndarray,
        metrics: RegistrationMetrics,
        warped_png_b64: Optional[str] = None,
    ) -> Dict[str, Any]:
        matches_list = [
            {"src": [float(x), float(y)], "dst": [float(u), float(v)]}
            for (x, y), (u, v) in zip(src_pts.tolist(), dst_pts.tolist())
        ]
        result: Dict[str, Any] = {
            "method": metrics.method,
            "metrics": {
                "rmse_px": metrics.rmse_px,
                "inlier_count": metrics.inlier_count,
                "inlier_ratio": metrics.inlier_ratio,
                "spatial_coverage": metrics.spatial_coverage,
                "meets_target": metrics.meets_target,
            },
            "matches": matches_list,
        }
        if warped_png_b64 is not None:
            result["warped_image_b64"] = warped_png_b64
        return result

    @staticmethod
    def to_geojson(
        src_pts: np.ndarray,
        dst_pts: np.ndarray,
        src_transform=None,  # optional affine transform for georeferencing
    ) -> Dict[str, Any]:
        features = []
        for i, ((sx, sy), (dx, dy)) in enumerate(zip(src_pts.tolist(), dst_pts.tolist())):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [sx, sy]},
                "properties": {"match_id": i, "dst_x": dx, "dst_y": dy},
            })
        return {"type": "FeatureCollection", "features": features}

    @staticmethod
    def to_csv_str(src_pts: np.ndarray, dst_pts: np.ndarray) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["src_x", "src_y", "dst_x", "dst_y"])
        for (sx, sy), (dx, dy) in zip(src_pts.tolist(), dst_pts.tolist()):
            writer.writerow([sx, sy, dx, dy])
        return buf.getvalue()

    @staticmethod
    def warp_to_b64(src_img: np.ndarray, H: np.ndarray, dst_shape: tuple) -> str:
        """Warp src_img and return as base64-encoded PNG string."""
        h, w = dst_shape[:2]
        warped = cv2.warpPerspective(src_img, H, (w, h), flags=cv2.INTER_LINEAR)
        _, buf = cv2.imencode(".png", warped)
        return base64.b64encode(buf.tobytes()).decode()

    @staticmethod
    def draw_matches_b64(
        src_img: np.ndarray,
        dst_img: np.ndarray,
        src_pts: np.ndarray,
        dst_pts: np.ndarray,
        max_lines: int = 200,
    ) -> str:
        """Draw match lines and return as base64-encoded PNG."""
        h1, w1 = src_img.shape[:2]
        h2, w2 = dst_img.shape[:2]
        canvas = np.zeros((max(h1, h2), w1 + w2, 3), dtype=np.uint8)

        s = cv2.cvtColor(src_img, cv2.COLOR_GRAY2BGR) if src_img.ndim == 2 else src_img
        d = cv2.cvtColor(dst_img, cv2.COLOR_GRAY2BGR) if dst_img.ndim == 2 else dst_img
        canvas[:h1, :w1] = s
        canvas[:h2, w1:w1 + w2] = d

        step = max(1, len(src_pts) // max_lines)
        for i in range(0, len(src_pts), step):
            p1 = (int(src_pts[i, 0]), int(src_pts[i, 1]))
            p2 = (int(dst_pts[i, 0]) + w1, int(dst_pts[i, 1]))
            color = (0, 255, 0)
            cv2.line(canvas, p1, p2, color, 1, cv2.LINE_AA)
            cv2.circle(canvas, p1, 3, (0, 165, 255), -1)
            cv2.circle(canvas, p2, 3, (0, 165, 255), -1)

        _, buf = cv2.imencode(".png", canvas)
        return base64.b64encode(buf.tobytes()).decode()
