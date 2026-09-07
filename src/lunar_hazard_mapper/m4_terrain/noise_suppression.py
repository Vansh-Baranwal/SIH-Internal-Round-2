"""M4 Phase 10.7 mask-aware noise suppression for Phase 10.6 differences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.ndimage import generic_filter

from .illumination_filtering import IlluminationFilterResult, IlluminationFilterStatus


class NoiseSuppressionStatus(str, Enum):
    SUCCESS = "success"
    NO_VALID_DATA = "no_valid_data"
    INVALID_ILLUMINATION_INPUT = "invalid_illumination_input"
    MISSING_FILTERED_ARTIFACT = "missing_filtered_artifact"
    INVALID_FILTERED_ARTIFACT = "invalid_filtered_artifact"
    SHAPE_MISMATCH = "shape_mismatch"
    MASK_MISMATCH = "mask_mismatch"
    INVALID_PIXEL_DATA = "invalid_pixel_data"
    UNSUPPORTED_METHOD = "unsupported_method"
    SUPPRESSION_FAILED = "suppression_failed"


@dataclass(frozen=True)
class NoiseSuppressionConfig:
    """Explicit, conservative filtering parameters."""

    output_dir: Path
    method: str = "masked_median"
    kernel_size: int = 3
    minimum_valid_neighbors: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.method not in ("none", "masked_median"):
            raise ValueError(f"unsupported noise suppression method: {self.method}")
        if self.kernel_size < 1 or self.kernel_size % 2 == 0:
            raise ValueError("kernel_size must be a positive odd integer")
        if self.minimum_valid_neighbors < 1 or self.minimum_valid_neighbors > self.kernel_size ** 2:
            raise ValueError("minimum_valid_neighbors must fit inside the kernel")


@dataclass(frozen=True)
class NoiseSuppressionRequest:
    """Input boundary referencing a successful Phase 10.6 result."""

    illumination_result: IlluminationFilterResult
    config: NoiseSuppressionConfig


@dataclass(frozen=True)
class NoiseSuppressionResult:
    """Noise-suppressed representation, never a physical-change conclusion."""

    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    illumination_status: Optional[str]
    status: NoiseSuppressionStatus
    method: str
    kernel_size: int
    minimum_valid_neighbors: int
    image_shape: Optional[tuple[int, ...]]
    channel_count: Optional[int]
    valid_pixel_count: int
    invalid_pixel_count: int
    signed_difference_input_reference: Optional[str]
    absolute_difference_input_reference: Optional[str]
    valid_mask_input_reference: Optional[str]
    suppressed_signed_difference_reference: Optional[str]
    suppressed_absolute_difference_reference: Optional[str]
    propagated_valid_mask_reference: Optional[str]
    before_statistics: dict[str, Optional[float]]
    after_statistics: dict[str, Optional[float]]
    high_frequency_residual_std: Optional[float]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "illumination_status": self.illumination_status,
            "status": self.status.value,
            "method": self.method,
            "kernel_size": self.kernel_size,
            "minimum_valid_neighbors": self.minimum_valid_neighbors,
            "image_shape": list(self.image_shape) if self.image_shape else None,
            "channel_count": self.channel_count,
            "valid_pixel_count": self.valid_pixel_count,
            "invalid_pixel_count": self.invalid_pixel_count,
            "signed_difference_input_reference": self.signed_difference_input_reference,
            "absolute_difference_input_reference": self.absolute_difference_input_reference,
            "valid_mask_input_reference": self.valid_mask_input_reference,
            "suppressed_signed_difference_reference": self.suppressed_signed_difference_reference,
            "suppressed_absolute_difference_reference": self.suppressed_absolute_difference_reference,
            "propagated_valid_mask_reference": self.propagated_valid_mask_reference,
            "before_statistics": self.before_statistics,
            "after_statistics": self.after_statistics,
            "high_frequency_residual_std": self.high_frequency_residual_std,
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }


def _stats(signed: np.ndarray, absolute: np.ndarray, valid: np.ndarray) -> dict[str, Optional[float]]:
    signed_values = signed[valid] if signed.ndim == 2 else signed[valid, :].reshape(-1)
    absolute_values = absolute[valid] if absolute.ndim == 2 else absolute[valid, :].reshape(-1)
    signed_values = signed_values[np.isfinite(signed_values)]
    absolute_values = absolute_values[np.isfinite(absolute_values)]
    if signed_values.size == 0 or absolute_values.size == 0:
        return {"valid_count": 0, "finite_signed_count": 0, "finite_absolute_count": 0, "signed_mean": None, "absolute_mean": None, "absolute_median": None, "absolute_std": None}
    return {
        "valid_count": int(np.count_nonzero(valid)),
        "finite_signed_count": int(signed_values.size),
        "finite_absolute_count": int(absolute_values.size),
        "signed_mean": float(np.mean(signed_values)),
        "absolute_mean": float(np.mean(absolute_values)),
        "absolute_median": float(np.median(absolute_values)),
        "absolute_std": float(np.std(absolute_values)),
    }


def _masked_median(data: np.ndarray, valid: np.ndarray, config: NoiseSuppressionConfig) -> np.ndarray:
    def median_or_center(values: np.ndarray) -> float:
        finite = values[np.isfinite(values)]
        center = values[len(values) // 2]
        if finite.size < config.minimum_valid_neighbors:
            return center
        return float(np.median(finite))

    if data.ndim == 2:
        masked = np.where(valid, data, np.nan)
        return generic_filter(masked, median_or_center, size=config.kernel_size, mode="nearest")
    channels = []
    for channel in range(data.shape[2]):
        masked = np.where(valid, data[:, :, channel], np.nan)
        channels.append(generic_filter(masked, median_or_center, size=config.kernel_size, mode="nearest"))
    return np.stack(channels, axis=2)


def _failure(request: NoiseSuppressionRequest, status: NoiseSuppressionStatus, reason: str, message: str) -> NoiseSuppressionResult:
    upstream = request.illumination_result
    return NoiseSuppressionResult(
        upstream.observation_a_id, upstream.observation_b_id,
        getattr(upstream.status, "value", None), status, request.config.method,
        request.config.kernel_size, request.config.minimum_valid_neighbors,
        None, None, 0, 0,
        upstream.filtered_signed_difference_reference,
        upstream.filtered_absolute_difference_reference,
        upstream.illumination_mask_reference,
        None, None, None, {}, {}, None, (), (reason,),
        {"phase": "m4_10.7", "upstream_phase": "m4_10.6", "raw_difference_preserved": True}, message,
    )


def suppress_noise(request: NoiseSuppressionRequest) -> NoiseSuppressionResult:
    """Apply a mask-aware median filter to Phase 10.6 filtered differences."""
    upstream = request.illumination_result
    config = request.config
    if not isinstance(upstream, IlluminationFilterResult) or upstream.status is not IlluminationFilterStatus.SUCCESS:
        return _failure(request, NoiseSuppressionStatus.INVALID_ILLUMINATION_INPUT, "invalid_illumination_input", "A successful Phase 10.6 result with filtered artifacts is required.")
    references = (upstream.filtered_signed_difference_reference, upstream.filtered_absolute_difference_reference, upstream.illumination_mask_reference)
    if any(not reference for reference in references):
        return _failure(request, NoiseSuppressionStatus.MISSING_FILTERED_ARTIFACT, "missing_filtered_artifact", "Phase 10.6 filtered artifacts are required; raw differences are not fallback inputs.")
    try:
        signed = np.load(upstream.filtered_signed_difference_reference, allow_pickle=False)
        absolute = np.load(upstream.filtered_absolute_difference_reference, allow_pickle=False)
        valid = np.load(upstream.illumination_mask_reference, allow_pickle=False)
    except (OSError, ValueError, TypeError):
        return _failure(request, NoiseSuppressionStatus.INVALID_FILTERED_ARTIFACT, "invalid_filtered_artifact", "Phase 10.6 artifacts could not be loaded.")
    if signed.ndim not in (2, 3) or signed.shape != absolute.shape:
        return _failure(request, NoiseSuppressionStatus.SHAPE_MISMATCH, "shape_mismatch", "Filtered signed and absolute differences have incompatible shapes.")
    if valid.dtype != np.bool_ or valid.shape != signed.shape[:2]:
        return _failure(request, NoiseSuppressionStatus.MASK_MISMATCH, "mask_mismatch", "The Phase 10.6 illumination mask does not match the filtered difference shape.")
    if signed.ndim == 2:
        finite_valid = np.isfinite(signed[valid]) & np.isfinite(absolute[valid])
    else:
        finite_valid = np.isfinite(signed[valid, :]).all(axis=1) & np.isfinite(absolute[valid, :]).all(axis=1)
    if not np.all(finite_valid):
        return _failure(request, NoiseSuppressionStatus.INVALID_PIXEL_DATA, "invalid_pixel_data", "Valid Phase 10.6 pixels contain non-finite values.")
    if np.any(absolute[valid] < 0):
        return _failure(request, NoiseSuppressionStatus.INVALID_PIXEL_DATA, "invalid_absolute_difference", "Absolute difference contains negative valid values.")
    before = _stats(signed, absolute, valid)
    if before["valid_count"] == 0:
        return NoiseSuppressionResult(
            upstream.observation_a_id, upstream.observation_b_id, upstream.status.value,
            NoiseSuppressionStatus.NO_VALID_DATA, config.method, config.kernel_size,
            config.minimum_valid_neighbors, tuple(signed.shape), 1 if signed.ndim == 2 else signed.shape[2],
            0, int(valid.size), upstream.filtered_signed_difference_reference,
            upstream.filtered_absolute_difference_reference, upstream.illumination_mask_reference,
            None, None, None, before, {}, None, ("no_valid_input_pixels",), (),
            {"phase": "m4_10.7", "upstream_phase": "m4_10.6", "raw_difference_preserved": True},
            "No valid illumination-compatible pixels were available; no outputs were written.",
        )
    try:
        suppressed_signed = signed.astype(np.float64, copy=True) if config.method == "none" else _masked_median(signed.astype(np.float64), valid, config)
        suppressed_absolute = absolute.astype(np.float64, copy=True) if config.method == "none" else _masked_median(absolute.astype(np.float64), valid, config)
        suppressed_signed[~valid] = np.nan
        suppressed_absolute[~valid] = np.nan
    except (RuntimeError, ValueError, TypeError) as exc:
        return _failure(request, NoiseSuppressionStatus.SUPPRESSION_FAILED, "suppression_failed", str(exc))
    output_valid = valid.copy()
    output_values = suppressed_signed[output_valid] if suppressed_signed.ndim == 2 else suppressed_signed[output_valid, :].reshape(-1)
    output_absolute = suppressed_absolute[output_valid] if suppressed_absolute.ndim == 2 else suppressed_absolute[output_valid, :].reshape(-1)
    if not np.all(np.isfinite(output_values)) or not np.all(np.isfinite(output_absolute)) or np.any(output_absolute < 0):
        return _failure(request, NoiseSuppressionStatus.INVALID_PIXEL_DATA, "invalid_pixel_data", "Noise suppression produced invalid valid-pixel output.")
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    signed_path = output_dir / "noise_suppressed_signed_difference.npy"
    absolute_path = output_dir / "noise_suppressed_absolute_difference.npy"
    mask_path = output_dir / "propagated_valid_mask.npy"
    np.save(signed_path, suppressed_signed)
    np.save(absolute_path, suppressed_absolute)
    np.save(mask_path, output_valid)
    residual = signed - suppressed_signed
    residual_values = residual[valid] if residual.ndim == 2 else residual[valid, :].reshape(-1)
    residual_values = residual_values[np.isfinite(residual_values)]
    result = NoiseSuppressionResult(
        upstream.observation_a_id, upstream.observation_b_id, upstream.status.value,
        NoiseSuppressionStatus.SUCCESS, config.method, config.kernel_size,
        config.minimum_valid_neighbors, tuple(suppressed_signed.shape),
        1 if suppressed_signed.ndim == 2 else suppressed_signed.shape[2],
        int(np.count_nonzero(output_valid)), int(output_valid.size - np.count_nonzero(output_valid)),
        upstream.filtered_signed_difference_reference, upstream.filtered_absolute_difference_reference,
        upstream.illumination_mask_reference, str(signed_path), str(absolute_path), str(mask_path),
        before, _stats(suppressed_signed, suppressed_absolute, output_valid),
        float(np.std(residual_values)) if residual_values.size else None,
        ("masked_median_applied" if config.method == "masked_median" else "no_suppression_applied",), (),
        {"phase": "m4_10.7", "upstream_phase": "m4_10.6", "raw_difference_preserved": True, "valid_pixel_policy": "upstream_illumination_mask_and_finite_values", "scientific_interpretation": "noise-suppressed representation only"},
        "Noise suppression only; no physical lunar change determination was performed.",
    )
    (output_dir / "noise_suppression_summary.json").write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result