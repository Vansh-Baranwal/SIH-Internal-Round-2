"""
Stage A.4: Viewpoint Handling.

Where a DEM is available (from your existing M3 module), apply orthorectification
to remove severe topographic distortion caused by different viewing angles —
e.g. a crater imaged off-nadir looks skewed compared to the same crater imaged
straight down. This is a HOOK, not a full standalone photogrammetry engine —
it's designed to accept your existing M3 DEM-handling code directly.

If no DEM is provided, this stage is skipped and the pipeline relies on the
feature matcher + RANSAC's projective/affine model to absorb moderate
viewpoint differences (Stage C handles this fallback case).
"""
from __future__ import annotations
import numpy as np


def orthorectify(image: np.ndarray, dem: np.ndarray | None,
                  camera_params: dict | None = None) -> np.ndarray:
    """
    Placeholder integration point for DEM-based orthorectification.

    Plug in your existing M3 module here — this function is intentionally a
    thin pass-through so it's a one-line swap once you have your M3 DEM
    object and camera geometry (position/pointing) available:

        from your_m3_module import orthorectify_with_dem
        return orthorectify_with_dem(image, dem, camera_params)

    Without a DEM or camera parameters, returns the image unchanged — Stage C's
    projective/affine RANSAC model will absorb moderate viewpoint distortion
    on its own, so this stage is a quality improvement, not a hard requirement.
    """
    if dem is None or camera_params is None:
        return image

    # TODO: call your existing M3 orthorectification routine here.
    # e.g.: return your_m3_module.orthorectify_with_dem(image, dem, camera_params)
    return image
