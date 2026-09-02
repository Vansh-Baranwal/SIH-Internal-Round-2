"""M4-08.9 Spectral overlay generation on OHRC/TMC optical footprint.

This module produces a spatially-aligned overlay/heatmap raster of
already-computed IIRS spectral results on the target optical footprint
established by the M4-08.8 registration mapping.

It does NOT recalculate band ratios, spectral features, or classification.
It does NOT estimate or modify registration transforms.
It consumes existing upstream results exactly as they are.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
from affine import Affine

from .classification import MaterialClass
from .mapping import IIRSOpticalMappingResult


@dataclass(frozen=True, eq=False)
class SpectralOverlayResult:
    """Target-footprint raster overlay of IIRS spectral/classification data.

    All arrays share the target footprint shape ``(target_height, target_width)``.

    ``score_overlay`` contains the classification score for every mapped pixel
    and ``NaN`` for every unmapped or invalid pixel.

    ``class_overlay`` contains the ``MaterialClass`` enum for every mapped pixel
    and ``MaterialClass.UNCLASSIFIED`` for unmapped/invalid pixels.

    ``valid_mask`` is ``True`` only where the overlay contains a scientifically
    valid, source-backed value.  Unmapped target pixels, pixels whose source
    was invalid, or pixels that map outside the source grid are always ``False``.

    ``target_transform`` and ``target_crs`` record the spatial reference of the
    target footprint for downstream consumers.
    """

    score_overlay: np.ndarray
    class_overlay: np.ndarray
    valid_mask: np.ndarray
    target_transform: Affine
    target_crs: Optional[str]
    source_sensor: str
    reference_sensor: str
    registration_id: str

    def __post_init__(self) -> None:
        score = np.asarray(self.score_overlay)
        class_map = np.asarray(self.class_overlay)
        mask = np.asarray(self.valid_mask)

        if score.ndim != 2 or any(s <= 0 for s in score.shape):
            raise ValueError("score_overlay must be a non-empty 2D array.")
        if class_map.shape != score.shape:
            raise ValueError("class_overlay shape must match score_overlay.")
        if mask.shape != score.shape:
            raise ValueError("valid_mask shape must match score_overlay.")
        if mask.dtype != bool:
            raise TypeError("valid_mask must be boolean.")
        if not np.issubdtype(score.dtype, np.floating):
            raise TypeError("score_overlay must be a floating-point array.")

        # NaN/validity consistency
        if mask.any() and not np.isfinite(score[mask]).all():
            raise ValueError("Valid overlay scores must be finite.")
        if (~mask).any() and not np.isnan(score[~mask]).all():
            raise ValueError("Invalid overlay scores must be NaN.")

        if not isinstance(self.target_transform, Affine):
            raise TypeError("target_transform must be an Affine instance.")
        if not isinstance(self.registration_id, str) or not self.registration_id.strip():
            raise ValueError("registration_id must be a non-empty string.")

        object.__setattr__(self, "score_overlay", score)
        object.__setattr__(self, "class_overlay", class_map)
        object.__setattr__(self, "valid_mask", mask)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the overlay result deterministically."""
        class_names = np.vectorize(lambda x: x.name, otypes=[str])(self.class_overlay)
        return {
            "score_overlay": self.score_overlay.tolist(),
            "class_overlay": class_names.tolist(),
            "valid_mask": self.valid_mask.tolist(),
            "target_transform": list(tuple(self.target_transform)),
            "target_crs": self.target_crs,
            "source_sensor": self.source_sensor,
            "reference_sensor": self.reference_sensor,
            "registration_id": self.registration_id,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpectralOverlayResult):
            return NotImplemented
        return (
            np.array_equal(self.score_overlay, other.score_overlay, equal_nan=True)
            and np.array_equal(self.class_overlay, other.class_overlay)
            and np.array_equal(self.valid_mask, other.valid_mask)
            and tuple(self.target_transform) == tuple(other.target_transform)
            and self.target_crs == other.target_crs
            and self.source_sensor == other.source_sensor
            and self.reference_sensor == other.reference_sensor
            and self.registration_id == other.registration_id
        )


def generate_spectral_overlay(
    mapping: IIRSOpticalMappingResult,
) -> SpectralOverlayResult:
    """Generate a target-footprint overlay from the existing mapping contract.

    The function uses the registration transform to map each target-footprint
    pixel back into IIRS source space via nearest-neighbour lookup (the
    project's established convention for categorical/score data).  Only pixels
    that land within the valid source grid AND have a valid upstream
    classification are marked valid in the output.

    This function:
    - does NOT recalculate classification, features, or band ratios;
    - does NOT modify any upstream result;
    - does NOT estimate or refine the registration transform;
    - does NOT extrapolate into unmapped regions.
    """
    if not isinstance(mapping, IIRSOpticalMappingResult):
        raise TypeError("mapping must be an IIRSOpticalMappingResult instance.")

    # ---- Extract upstream references (read-only) ----
    spectral = mapping.spectral_result
    registration = mapping.registration
    footprint = mapping.target_footprint

    target_height = int(footprint["height"])
    target_width = int(footprint["width"])
    target_crs = footprint.get("crs")

    # Source classification arrays from M4-08.6 (via M4-08.7)
    src_class_map = spectral.classification_result.class_map
    src_score_map = spectral.classification_result.score_map
    src_valid_mask = spectral.classification_result.valid_mask
    src_height, src_width = src_class_map.shape

    # Transforms
    src_transform = spectral.source_cube.transform  # IIRS pixel→geo
    tgt_transform = registration.transform           # target pixel→geo

    # ---- Build target pixel grid ----
    # For each target pixel (row, col), find the geo coordinate at pixel centre,
    # then invert through the source transform to find the source pixel.
    tgt_cols, tgt_rows = np.meshgrid(
        np.arange(target_width, dtype=np.float64),
        np.arange(target_height, dtype=np.float64),
    )
    # Pixel centres: add 0.5 to index for centre-of-pixel convention
    tgt_x = tgt_transform.c + (tgt_cols + 0.5) * tgt_transform.a + (tgt_rows + 0.5) * tgt_transform.b
    tgt_y = tgt_transform.f + (tgt_cols + 0.5) * tgt_transform.d + (tgt_rows + 0.5) * tgt_transform.e

    # Invert source transform to get source pixel coordinates
    inv_src = ~src_transform
    src_col_f = inv_src.a * tgt_x + inv_src.b * tgt_y + inv_src.c
    src_row_f = inv_src.d * tgt_x + inv_src.e * tgt_y + inv_src.f

    # Nearest-neighbour: round to integer pixel indices
    src_col = np.round(src_col_f - 0.5).astype(np.int64)
    src_row = np.round(src_row_f - 0.5).astype(np.int64)

    # ---- Validity: only pixels that land inside the source grid ----
    in_bounds = (
        (src_row >= 0) & (src_row < src_height)
        & (src_col >= 0) & (src_col < src_width)
    )

    # ---- Sample source into target ----
    score_overlay = np.full((target_height, target_width), np.nan, dtype=np.float64)
    class_overlay = np.full((target_height, target_width), MaterialClass.UNCLASSIFIED, dtype=object)
    valid_mask = np.zeros((target_height, target_width), dtype=bool)

    if in_bounds.any():
        # Flatten for advanced indexing
        tgt_rows_valid = tgt_rows[in_bounds].astype(np.int64)
        tgt_cols_valid = tgt_cols[in_bounds].astype(np.int64)
        src_rows_valid = src_row[in_bounds]
        src_cols_valid = src_col[in_bounds]

        # Read source values (no mutation — just read)
        sampled_scores = src_score_map[src_rows_valid, src_cols_valid]
        sampled_classes = src_class_map[src_rows_valid, src_cols_valid]
        sampled_valid = src_valid_mask[src_rows_valid, src_cols_valid]

        # Only mark valid where upstream classification was also valid
        score_overlay[tgt_rows_valid[sampled_valid], tgt_cols_valid[sampled_valid]] = (
            sampled_scores[sampled_valid]
        )
        class_overlay[tgt_rows_valid[sampled_valid], tgt_cols_valid[sampled_valid]] = (
            sampled_classes[sampled_valid]
        )
        valid_mask[tgt_rows_valid[sampled_valid], tgt_cols_valid[sampled_valid]] = True

    return SpectralOverlayResult(
        score_overlay=score_overlay,
        class_overlay=class_overlay,
        valid_mask=valid_mask,
        target_transform=tgt_transform,
        target_crs=target_crs,
        source_sensor=registration.source_sensor,
        reference_sensor=registration.reference_sensor,
        registration_id=registration.registration_id,
    )
