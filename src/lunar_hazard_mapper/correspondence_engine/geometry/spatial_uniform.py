"""
Stage C.3: Uniform Match Distribution (QuadTree Grid Filtering).

Raw matching tends to cluster matches around highly-textured, easy features
(e.g. a single distinctive crater cluster) and leave large regions of the
image with zero matches. Your PS explicitly requires "uniform distribution
across the images" — this module enforces that by recursively subdividing
the image into a grid and capping how many matches survive per cell,
prioritizing highest-confidence matches within each cell.
"""
from __future__ import annotations
import numpy as np


def quadtree_uniform_filter(pts_ref: np.ndarray, confidences: np.ndarray,
                             image_shape: tuple[int, int],
                             max_per_cell: int = 3, min_cell_size: int = 64) -> np.ndarray:
    """
    Returns a boolean mask (same length as pts_ref) selecting which matches
    to KEEP, enforcing spatial uniformity.

    image_shape: (height, width) of the reference image.
    max_per_cell: cap on matches retained per grid cell.
    min_cell_size: recursion stops subdividing once a cell is smaller than this
                   (in pixels) — prevents over-fragmenting into tiny, near-empty cells.
    """
    h, w = image_shape[:2]
    keep_mask = np.zeros(len(pts_ref), dtype=bool)

    def process_cell(x0, y0, x1, y1):
        cell_w, cell_h = x1 - x0, y1 - y0
        in_cell = (
            (pts_ref[:, 0] >= x0) & (pts_ref[:, 0] < x1) &
            (pts_ref[:, 1] >= y0) & (pts_ref[:, 1] < y1)
        )
        indices = np.where(in_cell)[0]

        if len(indices) == 0:
            return

        if cell_w <= min_cell_size or cell_h <= min_cell_size or len(indices) <= max_per_cell:
            # base case: keep top-N highest-confidence matches in this cell
            if len(indices) > max_per_cell:
                top_indices = indices[np.argsort(-confidences[indices])[:max_per_cell]]
            else:
                top_indices = indices
            keep_mask[top_indices] = True
            return

        # recurse into 4 quadrants
        mid_x, mid_y = (x0 + x1) // 2, (y0 + y1) // 2
        process_cell(x0, y0, mid_x, mid_y)
        process_cell(mid_x, y0, x1, mid_y)
        process_cell(x0, mid_y, mid_x, y1)
        process_cell(mid_x, mid_y, x1, y1)

    process_cell(0, 0, w, h)
    return keep_mask


def compute_spatial_coverage(pts_ref: np.ndarray, image_shape: tuple[int, int],
                              grid_cells: int = 8) -> float:
    """
    Evaluation metric: fraction of an N x N grid over the image that contains
    at least one match. Directly required by your roadmap doc's "Spatial
    Coverage" metric.
    """
    h, w = image_shape[:2]
    cell_h, cell_w = h / grid_cells, w / grid_cells
    occupied = set()

    for x, y in pts_ref:
        cell_x = min(int(x // cell_w), grid_cells - 1)
        cell_y = min(int(y // cell_h), grid_cells - 1)
        occupied.add((cell_x, cell_y))

    return len(occupied) / (grid_cells * grid_cells)
