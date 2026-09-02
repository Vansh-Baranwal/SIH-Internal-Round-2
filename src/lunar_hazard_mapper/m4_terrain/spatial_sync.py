"""M4-12.12 shared local scene spatial convention.

This is a local rendering-frame contract, not global lunar georeferencing.
"""

from __future__ import annotations

from typing import Mapping, Tuple

VIEW_COORDINATE_CONVENTION = {
    "x": "local_east_meters",
    "y": "local_up_meters",
    "z": "local_north_meters",
}
TERRAIN_GRID_CONVENTION = {
    "x": "local_east_meters",
    "y": "local_north_meters",
    "z": "local_up_meters",
}
LOCAL_UNITS = "metres"


def terrain_grid_to_viewer(east_m: float, north_m: float, up_m: float) -> Tuple[float, float, float]:
    """Convert the foundation ENU grid ordering to viewer (East, Up, North)."""
    return (float(east_m), float(up_m), float(north_m))


def viewer_position(position: Mapping[str, float]) -> Tuple[float, float, float]:
    """Validate and normalize an existing viewer-frame position."""
    try:
        result = (float(position["x"]), float(position["y"]), float(position["z"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("viewer position requires finite x, y, and z coordinates") from exc
    if not all(__import__("math").isfinite(value) for value in result):
        raise ValueError("viewer position requires finite x, y, and z coordinates")
    return result

