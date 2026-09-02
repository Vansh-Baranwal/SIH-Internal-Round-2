"""M4-09.4 Spatial Normalization of Water-Ice Evidence Layers.

Provides generic spatial normalization of existing WaterIceEvidenceLayers
onto explicitly supplied target spatial grids.
"""

from typing import Optional, Tuple

import numpy as np
from affine import Affine
from rasterio.warp import Resampling, reproject

from lunar_hazard_mapper.scientific.common.types import RegistrationResult
from lunar_hazard_mapper.scientific.water_ice.types import WaterIceEvidenceLayer


def normalize_evidence_layer(
    source_layer: WaterIceEvidenceLayer,
    target_transform: Affine,
    target_shape: Tuple[int, int],
    target_crs: Optional[str],
    target_pixel_size_m: float,
    resampling_method: Resampling = Resampling.nearest,
) -> WaterIceEvidenceLayer:
    """Resamples a WaterIceEvidenceLayer onto a target spatial grid.

    This performs generic spatial normalization. It does NOT calculate
    scientific confidence, hydration, or hotspots. The `resampling_method`
    must be explicitly supplied and is NOT a scientifically validated
    interpolation rule.

    The valid_mask is propagated conservatively using nearest-neighbor
    resampling to avoid interpolating boolean validity.
    """
    if not isinstance(source_layer, WaterIceEvidenceLayer):
        raise TypeError("source_layer must be a WaterIceEvidenceLayer.")
    if not isinstance(target_transform, Affine):
        raise TypeError("target_transform must be an Affine instance.")
    
    try:
        height, width = target_shape
    except (TypeError, ValueError):
        raise ValueError("target_shape must be a tuple of (height, width).")
        
    if not isinstance(height, int) or not isinstance(width, int) or height <= 0 or width <= 0:
        raise ValueError("target_shape must be positive integers.")
        
    if target_crs is not None and not isinstance(target_crs, str):
        raise TypeError("target_crs must be a string or None.")
    if not isinstance(resampling_method, Resampling):
        raise TypeError("resampling_method must be a rasterio.warp.Resampling enum.")

    src_values = source_layer.values.astype(np.float64)
    src_mask = source_layer.valid_mask.astype(np.uint8)

    # Prepare output arrays
    dst_values = np.full(
        (height, width),
        source_layer.nodata if source_layer.nodata is not None else np.nan,
        dtype=np.float64
    )
    dst_mask = np.zeros((height, width), dtype=np.uint8)

    # Warp numeric values using explicit resampling policy
    reproject(
        source=src_values,
        destination=dst_values,
        src_transform=source_layer.transform,
        src_crs=source_layer.crs,
        src_nodata=source_layer.nodata,
        dst_transform=target_transform,
        dst_crs=target_crs,
        dst_nodata=source_layer.nodata if source_layer.nodata is not None else np.nan,
        resampling=resampling_method,
    )

    # Warp boolean mask conservatively (nearest-neighbor only)
    reproject(
        source=src_mask,
        destination=dst_mask,
        src_transform=source_layer.transform,
        src_crs=source_layer.crs,
        src_nodata=0,  # 0 is invalid
        dst_transform=target_transform,
        dst_crs=target_crs,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )

    out_mask = dst_mask > 0

    # Ensure output strictly adheres to nodata semantics
    if source_layer.nodata is not None:
        if np.isnan(source_layer.nodata):
            dst_values[~out_mask] = np.nan
        else:
            dst_values[~out_mask] = source_layer.nodata

    return WaterIceEvidenceLayer(
        source=source_layer.source,
        values=dst_values,
        valid_mask=out_mask,
        pixel_size_m=target_pixel_size_m,
        transform=target_transform,
        crs=target_crs,
        nodata=source_layer.nodata,
        dataset_name=f"{source_layer.dataset_name}_normalized",
        sensor=source_layer.sensor,
        observation_date=source_layer.observation_date,
        orbit_id=source_layer.orbit_id,
        notes=f"{source_layer.notes} | Normalized".strip(),
        extra=dict(source_layer.extra),
    )


def normalize_with_registration(
    source_layer: WaterIceEvidenceLayer,
    registration: RegistrationResult,
    target_pixel_size_m: float,
    resampling_method: Resampling = Resampling.nearest,
) -> WaterIceEvidenceLayer:
    """Normalizes an evidence layer using an existing RegistrationResult."""
    if not isinstance(registration, RegistrationResult):
        raise TypeError("registration must be a RegistrationResult.")
    if not registration.success:
        raise ValueError("Cannot normalize using an unsuccessful RegistrationResult.")
    
    tgt_transform = registration.transform
    if not isinstance(tgt_transform, Affine):
        raise TypeError("RegistrationResult.transform must be an explicitly validated Affine instance.")

    spatial_ref = registration.spatial_reference
    if not isinstance(spatial_ref, dict):
        raise TypeError("RegistrationResult.spatial_reference must be a dict.")

    try:
        tgt_height = int(spatial_ref["height"])
        tgt_width = int(spatial_ref["width"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("spatial_reference must define positive integer 'height' and 'width'.") from exc

    tgt_crs = spatial_ref.get("crs")
    if tgt_crs is not None and not isinstance(tgt_crs, str):
        raise TypeError("spatial_reference 'crs' must be a string or None.")

    return normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=tgt_transform,
        target_shape=(tgt_height, tgt_width),
        target_crs=tgt_crs,
        target_pixel_size_m=target_pixel_size_m,
        resampling_method=resampling_method,
    )
