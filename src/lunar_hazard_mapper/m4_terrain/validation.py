"""
M4-12.1 terrain foundation validation and scientific-quality/safety checks.

Any validation report here is only as trustworthy as the underlying DEM. If the
DEM is synthetic, the report reflects internal consistency of the provider ->
foundation -> viewer data path, NOT real-world lunar accuracy. No real-lunar
accuracy is measured or claimed anywhere in this module.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from lunar_hazard_mapper.m4_terrain.status import (
    SOURCE_SYNTHETIC,
    TerrainDataStatus,
)


def validate_foundation(foundation) -> Dict[str, Any]:
    """
    Run focused quality/safety checks on a ``TerrainFoundation``.

    Returns a dict mapping check name -> bool, plus ``all_passed``. The checks
    cover the provider contract, DEM metadata preservation, nodata/valid-mask
    behavior, coordinate semantics, provenance visibility, and the safety rule
    that synthetic data must never be presented as real scientific observation.
    """
    from lunar_hazard_mapper.m4_terrain.foundation import TerrainFoundation

    checks: Dict[str, bool] = {}

    # --- provider contract --------------------------------------------- #
    # The foundation may only be constructed against the provider contract.
    checks["is_foundation"] = isinstance(foundation, TerrainFoundation)
    provider = getattr(foundation, "provider", None)
    checks["provider_contract_satisfied"] = provider is not None and hasattr(
        provider, "load_dem"
    )
    dem = foundation.dem
    metadata = foundation.metadata()

    # --- DEM metadata preservation ------------------------------------- #
    checks["dimensions_valid"] = foundation.width > 0 and foundation.height > 0
    elev = np.asarray(dem.elevation, dtype=np.float64)
    checks["elevation_2d"] = elev.ndim == 2
    checks["pixel_size_positive"] = foundation.pixel_size_m > 0
    checks["transform_present"] = dem.transform is not None
    checks["vertical_units_set"] = bool(foundation.vertical_units)
    checks["nodata_defined"] = foundation.nodata is not None
    checks["source_type_valid"] = metadata["source_type"] in (
        "synthetic",
        "sr_estimated",
        "measured",
    )
    checks["crs_consistent_with_georef"] = (
        metadata["is_georeferenced"] == (metadata["crs"] is not None)
    )

    # --- nodata / valid-mask behavior ---------------------------------- #
    vmask = foundation.valid_mask()
    checks["valid_mask_shape"] = vmask.shape == elev.shape
    checks["valid_mask_matches_nodata"] = bool(
        np.all(vmask == ((elev != foundation.nodata) & np.isfinite(elev)))
    )
    # If any cell equals nodata it must be excluded from valid.
    has_nodata = bool((elev == foundation.nodata).any())
    if has_nodata:
        checks["nodata_excluded_from_valid"] = bool(
            np.all(np.logical_not(vmask[elev == foundation.nodata]))
        )
    else:
        checks["nodata_excluded_from_valid"] = True
    # All valid cells must be finite.
    checks["valid_cells_finite"] = bool(
        np.all(np.isfinite(elev[vmask])) if vmask.any() else True
    )

    # --- coordinate semantics ------------------------------------------ #
    cc = metadata["coordinate_convention"]
    checks["coordinate_convention_preserved"] = cc == {
        "x": "local_east_meters",
        "y": "local_north_meters",
        "z": "local_up_meters",
    }
    grid = foundation.grid()
    checks["grid_has_x_y_z"] = set(("x", "y", "z")).issubset(grid.keys())
    bounds = foundation.bounds
    checks["bounds_finite"] = all(
        np.isfinite(bounds[k]) for k in ("min_x", "max_x", "min_y", "max_y")
    )
    checks["bounds_positive_extent"] = bounds["width_m"] > 0 and bounds["height_m"] > 0

    # --- provenance / source type -------------------------------------- #
    prov = metadata["provenance"]
    checks["provenance_explicit"] = bool(prov.get("data_status"))
    checks["provenance_has_label"] = bool(prov.get("display_label"))
    checks["status_matches_source_type"] = (
        _status_matches(metadata["source_type"], metadata["data_status"])
    )

    # --- safety: synthetic never presented as real --------------------- #
    is_synthetic = metadata["source_type"] == SOURCE_SYNTHETIC
    checks["synthetic_not_presented_as_real"] = (
        metadata["data_status"] != TerrainDataStatus.REAL.value
        or not is_synthetic
    )
    if is_synthetic:
        checks["synthetic_label_explicit"] = (
            metadata["data_status"] == TerrainDataStatus.SYNTHETIC.value
            and "SYNTHETIC" in metadata["display_label"].upper()
        )
        checks["synthetic_provenance_disclaims_real"] = (
            "NOT real lunar" in (prov.get("note", "") + metadata["notes"]) or
            "synthetic" in (prov.get("note", "") + metadata["notes"]).lower()
        )
    else:
        checks["synthetic_label_explicit"] = True
        checks["synthetic_provenance_disclaims_real"] = True

    checks["all_passed"] = all(checks.values())
    return checks


def _status_matches(source_type: str, data_status: str) -> bool:
    """Ensure the declared data-status is consistent with the DEM source_type."""
    if source_type == "synthetic":
        return data_status == TerrainDataStatus.SYNTHETIC.value
    if source_type == "measured":
        return data_status == TerrainDataStatus.REAL.value
    return data_status == TerrainDataStatus.UNKNOWN.value
