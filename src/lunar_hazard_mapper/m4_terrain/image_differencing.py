"""M4 Phase 10.5 pixel differencing for a registered observation pair."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, UnidentifiedImageError

from .multi_date_registration import RegistrationStatus, TemporalRegistrationResult


class DifferenceStatus(str, Enum):
    SUCCESS = "success"
    NO_VALID_COMPARISON = "no_valid_comparison"
    INVALID_REGISTRATION_INPUT = "invalid_registration_input"
    MISSING_REGISTERED_IMAGE = "missing_registered_image"
    INVALID_IMAGE = "invalid_image"
    SHAPE_MISMATCH = "shape_mismatch"
    CHANNEL_MISMATCH = "channel_mismatch"
    INVALID_PIXEL_DATA = "invalid_pixel_data"
    DIFFERENCING_FAILED = "differencing_failed"


@dataclass(frozen=True)
class DifferenceConfig:
    """Explicit Phase 10.5 output and optional intensity normalization policy."""

    output_dir: Path
    normalization: str = "none"

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.normalization not in ("none", "minmax", "standardized"):
            raise ValueError("normalization must be one of: none, minmax, standardized")


@dataclass(frozen=True)
class ImageDifferencingRequest:
    """Input boundary referencing a successful Phase 10.4 result."""

    registration_result: TemporalRegistrationResult
    config: DifferenceConfig


@dataclass(frozen=True)
class ImageDifferenceResult:
    """Numerical difference products and metadata for Phase 10.6 consumption."""

    observation_a_id: Optional[str]
    observation_b_id: Optional[str]
    registration_status: Optional[str]
    status: DifferenceStatus
    method: str
    image_shape: Optional[tuple[int, ...]]
    channel_count: Optional[int]
    valid_pixel_count: int
    invalid_pixel_count: int
    valid_fraction: float
    signed_difference_reference: Optional[str]
    absolute_difference_reference: Optional[str]
    valid_mask_reference: Optional[str]
    summary_statistics: dict[str, Optional[float]]
    normalization_method: str
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id,
            "registration_status": self.registration_status,
            "status": self.status.value,
            "method": self.method,
            "image_shape": list(self.image_shape) if self.image_shape else None,
            "channel_count": self.channel_count,
            "valid_pixel_count": self.valid_pixel_count,
            "invalid_pixel_count": self.invalid_pixel_count,
            "valid_fraction": self.valid_fraction,
            "signed_difference_reference": self.signed_difference_reference,
            "absolute_difference_reference": self.absolute_difference_reference,
            "valid_mask_reference": self.valid_mask_reference,
            "summary_statistics": self.summary_statistics,
            "normalization_method": self.normalization_method,
            "warnings": list(self.warnings),
            "failure_reasons": list(self.failure_reasons),
            "provenance": self.provenance,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImageDifferenceResult":
        if not isinstance(payload, dict):
            raise ValueError("ImageDifferenceResult payload must be a dictionary")
        required = ("status", "method", "valid_pixel_count", "invalid_pixel_count", "valid_fraction")
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"ImageDifferenceResult payload missing fields: {missing}")
        try:
            return cls(
                observation_a_id=payload.get("observation_a_id"),
                observation_b_id=payload.get("observation_b_id"),
                registration_status=payload.get("registration_status"),
                status=DifferenceStatus(payload["status"]),
                method=payload["method"],
                image_shape=tuple(payload["image_shape"]) if payload.get("image_shape") else None,
                channel_count=payload.get("channel_count"),
                valid_pixel_count=int(payload["valid_pixel_count"]),
                invalid_pixel_count=int(payload["invalid_pixel_count"]),
                valid_fraction=float(payload["valid_fraction"]),
                signed_difference_reference=payload.get("signed_difference_reference"),
                absolute_difference_reference=payload.get("absolute_difference_reference"),
                valid_mask_reference=payload.get("valid_mask_reference"),
                summary_statistics=dict(payload.get("summary_statistics", {})),
                normalization_method=payload.get("normalization_method", "none"),
                warnings=tuple(payload.get("warnings", ())),
                failure_reasons=tuple(payload.get("failure_reasons", ())),
                provenance=dict(payload.get("provenance", {})),
                message=payload.get("message", ""),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Malformed ImageDifferenceResult payload: {exc}") from exc


def _failure(
    registration: Optional[TemporalRegistrationResult],
    config: DifferenceConfig,
    status: DifferenceStatus,
    reason: str,
    message: str,
) -> ImageDifferenceResult:
    return ImageDifferenceResult(
        getattr(registration, "observation_a_id", None),
        getattr(registration, "observation_b_id", None),
        getattr(getattr(registration, "status", None), "value", None),
        status,
        "registered_a_minus_reference_b",
        None,
        None,
        0,
        0,
        0.0,
        None,
        None,
        None,
        {},
        config.normalization,
        (),
        (reason,),
        {"phase": "m4_10.5", "registration_result": "unavailable"},
        message,
    )


def _load_image(path: str) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(path) as image:
        array = np.asarray(image).copy()
    if array.ndim not in (2, 3):
        raise ValueError("image must be grayscale or have explicit channels")
    if array.ndim == 3 and array.shape[2] == 4:
        alpha = array[:, :, 3]
        data = array[:, :, :3]
        valid = alpha > 0
    elif array.ndim == 3 and array.shape[2] in (1, 3):
        data = array[:, :, 0] if array.shape[2] == 1 else array
        valid = np.ones(data.shape[:2], dtype=bool)
    elif array.ndim == 2:
        data = array
        valid = np.ones(data.shape, dtype=bool)
    else:
        raise ValueError("unsupported channel count")
    if np.issubdtype(data.dtype, np.floating):
        valid &= np.all(np.isfinite(data), axis=2) if data.ndim == 3 else np.isfinite(data)
    return data, valid


def _normalize(data: np.ndarray, valid: np.ndarray, method: str) -> np.ndarray:
    result = data.astype(np.float64, copy=True)
    if method == "none":
        return result
    values = result[valid] if result.ndim == 2 else result[valid, :]
    if values.size == 0:
        return result
    if method == "minmax":
        low, high = float(np.min(values)), float(np.max(values))
        if high != low:
            result = (result - low) / (high - low)
    elif method == "standardized":
        mean, std = float(np.mean(values)), float(np.std(values))
        if std == 0:
            result = result - mean
        else:
            result = (result - mean) / std
    return result


def _statistics(values: np.ndarray) -> dict[str, Optional[float]]:
    if values.size == 0:
        return {
            "signed_min": None, "signed_max": None, "signed_mean": None,
            "signed_median": None, "signed_std": None, "absolute_min": None,
            "absolute_max": None, "absolute_mean": None, "absolute_median": None,
            "absolute_std": None,
        }
    absolute = np.abs(values)
    return {
        "signed_min": float(np.min(values)),
        "signed_max": float(np.max(values)),
        "signed_mean": float(np.mean(values)),
        "signed_median": float(np.median(values)),
        "signed_std": float(np.std(values)),
        "absolute_min": float(np.min(absolute)),
        "absolute_max": float(np.max(absolute)),
        "absolute_mean": float(np.mean(absolute)),
        "absolute_median": float(np.median(absolute)),
        "absolute_std": float(np.std(absolute)),
    }


def difference_registered_pair(request: ImageDifferencingRequest) -> ImageDifferenceResult:
    """Compute signed and absolute differences from the registered frame."""
    registration = request.registration_result
    config = request.config
    if not isinstance(registration, TemporalRegistrationResult) or registration.status is not RegistrationStatus.SUCCESS:
        return _failure(registration, config, DifferenceStatus.INVALID_REGISTRATION_INPUT, "invalid_registration_input", "A successful Phase 10.4 registration result is required.")
    if not registration.registered_output_reference or not registration.reference_image_reference:
        return _failure(registration, config, DifferenceStatus.MISSING_REGISTERED_IMAGE, "missing_registered_image", "Both registered A and reference-frame B image references are required.")
    try:
        first, valid_first = _load_image(registration.registered_output_reference)
        second, valid_second = _load_image(registration.reference_image_reference)
    except (FileNotFoundError, OSError):
        return _failure(registration, config, DifferenceStatus.MISSING_REGISTERED_IMAGE, "missing_registered_image", "A registered image artifact is unavailable.")
    except (UnidentifiedImageError, ValueError, TypeError):
        return _failure(registration, config, DifferenceStatus.INVALID_IMAGE, "invalid_image", "A registered image artifact could not be decoded safely.")
    if first.shape[:2] != second.shape[:2]:
        return _failure(registration, config, DifferenceStatus.SHAPE_MISMATCH, "shape_mismatch", "Registered images do not have matching height and width.")
    first_channels = first.shape[2] if first.ndim == 3 else 1
    second_channels = second.shape[2] if second.ndim == 3 else 1
    if first_channels != second_channels:
        return _failure(registration, config, DifferenceStatus.CHANNEL_MISMATCH, "channel_mismatch", "Registered images have different channel counts.")
    valid = valid_first & valid_second
    first = _normalize(first, valid_first, config.normalization)
    second = _normalize(second, valid_second, config.normalization)
    signed = first - second
    absolute = np.abs(signed)
    signed[~valid] = np.nan
    absolute[~valid] = np.nan
    values = signed[valid] if signed.ndim == 2 else signed[valid, :].reshape(-1)
    if values.size and not np.all(np.isfinite(values)):
        return _failure(registration, config, DifferenceStatus.INVALID_PIXEL_DATA, "invalid_pixel_data", "Valid comparison pixels produced non-finite differences.")
    pixel_count = int(valid.size)
    valid_count = int(np.count_nonzero(valid))
    invalid_count = pixel_count - valid_count
    if valid_count == 0:
        return ImageDifferenceResult(
            registration.observation_a_id, registration.observation_b_id, registration.status.value,
            DifferenceStatus.NO_VALID_COMPARISON, "registered_a_minus_reference_b", tuple(signed.shape),
            first_channels, 0, invalid_count, 0.0, None, None, None, _statistics(values),
            config.normalization, ("no_valid_comparison_pixels",), (),
            {"phase": "m4_10.5", "registration_result": "success", "valid_pixel_policy": "finite_and_alpha"},
            "No valid comparison pixels were available; no difference artifacts were written.",
        )
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    signed_path = output_dir / "signed_difference.npy"
    absolute_path = output_dir / "absolute_difference.npy"
    mask_path = output_dir / "valid_comparison_mask.npy"
    summary_path = output_dir / "difference_summary.json"
    np.save(signed_path, signed)
    np.save(absolute_path, absolute)
    np.save(mask_path, valid)
    result = ImageDifferenceResult(
        registration.observation_a_id, registration.observation_b_id, registration.status.value,
        DifferenceStatus.SUCCESS, "registered_a_minus_reference_b", tuple(signed.shape), first_channels,
        valid_count, invalid_count, valid_count / pixel_count, str(signed_path), str(absolute_path),
        str(mask_path), _statistics(values), config.normalization,
        ("normalization_enabled" if config.normalization != "none" else "raw_differencing",), (),
        {"phase": "m4_10.5", "registration_result": "success", "valid_pixel_policy": "finite_and_alpha", "difference_orientation": "registered_A_minus_reference_B"},
        "Pixel-level difference only; no physical lunar change determination was performed.",
    )
    summary_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return result