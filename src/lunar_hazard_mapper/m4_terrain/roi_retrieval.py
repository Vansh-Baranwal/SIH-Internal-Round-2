"""Phase 11.9 retrieval of an explicitly requested ROI from a reference raster."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.windows import Window, bounds as window_bounds, transform as window_transform

from .coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus, ReferenceImageGeoreferencing
from .localization_confidence import LocalizationConfidenceResult


class ROIStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    INVALID_INPUT = "invalid_input"
    REFERENCE_UNAVAILABLE = "reference_unavailable"
    OUT_OF_BOUNDS = "out_of_bounds"
    PARTIAL = "partial"
    FAILED = "failed"


class ReferenceProductSource(str, Enum):
    LOCAL_AVAILABLE = "local_available"
    EXTERNAL_REFERENCE = "external_reference"
    LOCAL_MISSING = "local_missing"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    INVALID = "invalid"


@dataclass(frozen=True)
class ROIWindow:
    """A native-pixel ROI request, or a coordinate-sized ROI in product units."""

    width: float
    height: float
    units: str
    allow_partial: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.width)) or not math.isfinite(float(self.height)):
            raise ValueError("ROI width and height must be finite.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI width and height must be positive.")
        if self.units not in {"pixels", "coordinate"}:
            raise ValueError("ROI units must be 'pixels' or 'coordinate'.")
        if self.units == "pixels" and (int(self.width) != self.width or int(self.height) != self.height):
            raise ValueError("Pixel ROI dimensions must be positive integers.")


@dataclass(frozen=True)
class ReferenceProduct:
    """Explicit metadata for one authoritative reference product."""

    product_id: str
    source_type: ReferenceProductSource
    georeferencing: ReferenceImageGeoreferencing
    path: Optional[Path] = None
    external_reference: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.product_id, str) or not self.product_id.strip():
            raise ValueError("product_id must be non-empty.")
        if not isinstance(self.source_type, ReferenceProductSource):
            raise ValueError("source_type must be a ReferenceProductSource.")
        if self.georeferencing.reference_image_id != self.product_id:
            raise ValueError("Product and georeferencing identifiers must match.")
        if self.provenance is None:
            raise ValueError("provenance is required.")
        if self.source_type is ReferenceProductSource.LOCAL_AVAILABLE and self.path is None:
            raise ValueError("A local available product requires a path.")
        if self.source_type is ReferenceProductSource.EXTERNAL_REFERENCE and not self.external_reference:
            raise ValueError("An external reference requires external_reference.")


@dataclass(frozen=True)
class ROIRetrievalRequest:
    coordinate_estimation: Optional[CoordinateEstimationResult]
    reference_product: ReferenceProduct
    roi: ROIWindow
    request_id: str
    localization_confidence: Optional[LocalizationConfidenceResult] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be non-empty.")
        if not isinstance(self.reference_product, ReferenceProduct):
            raise TypeError("reference_product must be a ReferenceProduct.")
        if not isinstance(self.roi, ROIWindow):
            raise TypeError("roi must be an ROIWindow.")


@dataclass(frozen=True)
class ROIRetrievalResult:
    request_id: str
    status: ROIStatus
    localization_result_id: Optional[str]
    reference_product_id: Optional[str]
    requested_center_coordinate: Optional[Tuple[float, float]]
    roi: Optional[ROIWindow]
    raster_window: Optional[Tuple[int, int, int, int]] = None
    roi_data: Optional[np.ndarray] = None
    roi_dimensions: Optional[Tuple[int, int]] = None
    parent_dimensions: Optional[Tuple[int, int]] = None
    roi_bounds: Optional[Tuple[float, float, float, float]] = None
    roi_transform: Optional[Tuple[float, ...]] = None
    coordinate_system: Optional[str] = None
    reference_frame: Optional[str] = None
    units: Optional[str] = None
    axis_order: Optional[Tuple[str, str]] = None
    source_type: Optional[ReferenceProductSource] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "localization_result_id": self.localization_result_id,
            "reference_product_id": self.reference_product_id,
            "requested_center_coordinate": list(self.requested_center_coordinate) if self.requested_center_coordinate else None,
            "roi": {"width": self.roi.width, "height": self.roi.height, "units": self.roi.units, "allow_partial": self.roi.allow_partial} if self.roi else None,
            "raster_window": list(self.raster_window) if self.raster_window else None,
            "roi_dimensions": list(self.roi_dimensions) if self.roi_dimensions else None,
            "parent_dimensions": list(self.parent_dimensions) if self.parent_dimensions else None,
            "roi_bounds": list(self.roi_bounds) if self.roi_bounds else None,
            "roi_transform": list(self.roi_transform) if self.roi_transform else None,
            "coordinate_system": self.coordinate_system,
            "reference_frame": self.reference_frame,
            "units": self.units,
            "axis_order": list(self.axis_order) if self.axis_order else None,
            "source_type": self.source_type.value if self.source_type else None,
            "provenance": dict(self.provenance),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "reason": self.reason,
            "pixels_retrieved": self.roi_data is not None,
        }


def _result(request: ROIRetrievalRequest, status: ROIStatus, reason: Optional[str], **kwargs: Any) -> ROIRetrievalResult:
    product = request.reference_product
    geo = product.georeferencing
    result_provenance = kwargs.pop("provenance", None)
    return ROIRetrievalResult(
        request_id=request.request_id,
        status=status,
        localization_result_id=getattr(request.coordinate_estimation, "unknown_image_id", None),
        reference_product_id=product.product_id,
        requested_center_coordinate=getattr(request.coordinate_estimation, "estimated_coordinate", None),
        roi=request.roi,
        coordinate_system=geo.coordinate_system,
        reference_frame=geo.reference_frame,
        units=geo.units,
        axis_order=geo.axis_order,
        source_type=product.source_type,
        provenance=result_provenance or {**dict(request.provenance), "reference_product": dict(product.metadata), "product_provenance": product.provenance, "pixels_retrieved": False},
        limitations=("Retrieval does not establish localization accuracy or agreement with metadata or ground truth.",),
        reason=reason,
        **kwargs,
    )


def retrieve_roi(request: ROIRetrievalRequest) -> ROIRetrievalResult:
    """Map a valid estimated coordinate into the selected local product and read its ROI."""
    if not isinstance(request, ROIRetrievalRequest):
        raise TypeError("request must be a ROIRetrievalRequest instance.")
    estimation = request.coordinate_estimation
    product = request.reference_product
    geo = product.georeferencing
    if estimation is None:
        return _result(request, ROIStatus.BLOCKED, "missing_coordinate_estimation")
    if not isinstance(estimation, CoordinateEstimationResult):
        return _result(request, ROIStatus.INVALID_INPUT, "invalid_coordinate_estimation")
    if estimation.status is not CoordinateEstimationStatus.SUCCESS:
        blocked_statuses = {CoordinateEstimationStatus.ESTIMATION_BLOCKED, CoordinateEstimationStatus.VERIFICATION_NOT_ACCEPTED, CoordinateEstimationStatus.MISSING_REFERENCE_GEOREFERENCING, CoordinateEstimationStatus.UNKNOWN_CRS, CoordinateEstimationStatus.UNSUPPORTED_COORDINATE_SYSTEM, CoordinateEstimationStatus.PROVENANCE_BLOCKED, CoordinateEstimationStatus.OUT_OF_REFERENCE_EXTENT}
        status = ROIStatus.BLOCKED if estimation.status in blocked_statuses else ROIStatus.INVALID_INPUT
        return _result(request, status, f"coordinate_estimation_{estimation.status.value}")
    if request.localization_confidence is not None:
        confidence = request.localization_confidence
        if not isinstance(confidence, LocalizationConfidenceResult) or confidence.unknown_image_id != estimation.unknown_image_id or confidence.reference_image_id != estimation.reference_image_id:
            return _result(request, ROIStatus.INVALID_INPUT, "localization_confidence_identity_mismatch")
    coordinate = estimation.estimated_coordinate
    semantics = (estimation.coordinate_system, estimation.reference_frame, estimation.units)
    if coordinate is None or len(coordinate) != 2 or not all(math.isfinite(float(value)) for value in coordinate):
        return _result(request, ROIStatus.INVALID_INPUT, "nonfinite_or_missing_coordinate")
    if any(value is None or not isinstance(value, str) or not value.strip() for value in semantics) or estimation.axis_order is None or len(estimation.axis_order) != 2 or any(not isinstance(axis, str) or not axis.strip() for axis in estimation.axis_order):
        return _result(request, ROIStatus.BLOCKED, "missing_coordinate_reference_semantics")
    if (estimation.reference_image_id != product.product_id or estimation.coordinate_system != geo.coordinate_system or estimation.reference_frame != geo.reference_frame or estimation.units != geo.units or estimation.axis_order != geo.axis_order):
        return _result(request, ROIStatus.INVALID_INPUT, "coordinate_reference_semantics_mismatch")
    if product.source_type is ReferenceProductSource.INVALID:
        return _result(request, ROIStatus.INVALID_INPUT, "invalid_reference_product")
    if product.source_type is not ReferenceProductSource.LOCAL_AVAILABLE:
        return _result(request, ROIStatus.REFERENCE_UNAVAILABLE, f"reference_product_{product.source_type.value}")
    path = Path(product.path) if product.path is not None else None
    if path is None or not path.is_file():
        return _result(request, ROIStatus.REFERENCE_UNAVAILABLE, "local_reference_product_missing")
    try:
        with rasterio.open(path) as dataset:
            if dataset.width != geo.width or dataset.height != geo.height or dataset.crs is None or tuple(dataset.transform)[:6] != tuple(geo.transform):
                return _result(request, ROIStatus.INVALID_INPUT, "raster_metadata_does_not_match_reference_contract")
            if dataset.crs != CRS.from_user_input(geo.crs):
                return _result(request, ROIStatus.INVALID_INPUT, "raster_crs_does_not_match_reference_contract")
            inverse = ~dataset.transform
            center_col, center_row = inverse @ (float(coordinate[0]), float(coordinate[1]))
            if request.roi.units == "pixels":
                width, height = int(request.roi.width), int(request.roi.height)
                col_start = math.floor(center_col - width / 2.0)
                row_start = math.floor(center_row - height / 2.0)
                col_end, row_end = col_start + width, row_start + height
            else:
                half_width, half_height = request.roi.width / 2.0, request.roi.height / 2.0
                corners = [inverse @ (coordinate[0] + dx, coordinate[1] + dy) for dx, dy in ((-half_width, -half_height), (-half_width, half_height), (half_width, -half_height), (half_width, half_height))]
                col_start, col_end = math.floor(min(item[0] for item in corners)), math.ceil(max(item[0] for item in corners))
                row_start, row_end = math.floor(min(item[1] for item in corners)), math.ceil(max(item[1] for item in corners))
            clipped = col_start < 0 or row_start < 0 or col_end > dataset.width or row_end > dataset.height
            if clipped and not request.roi.allow_partial:
                return _result(request, ROIStatus.OUT_OF_BOUNDS, "requested_roi_intersects_raster_boundary", parent_dimensions=(dataset.height, dataset.width))
            read_col_start, read_row_start = max(0, col_start), max(0, row_start)
            read_col_end, read_row_end = min(dataset.width, col_end), min(dataset.height, row_end)
            if read_col_start >= read_col_end or read_row_start >= read_row_end:
                return _result(request, ROIStatus.OUT_OF_BOUNDS, "requested_roi_is_outside_raster", parent_dimensions=(dataset.height, dataset.width))
            window = Window(read_col_start, read_row_start, read_col_end - read_col_start, read_row_end - read_row_start)
            data = dataset.read(window=window)
            transform = window_transform(window, dataset.transform)
            bounds = window_bounds(window, dataset.transform)
            status = ROIStatus.PARTIAL if clipped else ROIStatus.SUCCESS
            provenance = {"source_product": product.product_id, "source_type": product.source_type.value, "product_provenance": product.provenance, "pixels_retrieved": True, "synthetic": str(product.provenance).lower() == "synthetic", "confidence_recalculated": False}
            return _result(request, status, "partial_roi" if clipped else None, raster_window=(read_row_start, read_col_start, read_row_end - read_row_start, read_col_end - read_col_start), roi_data=data, roi_dimensions=(int(data.shape[-2]), int(data.shape[-1])), parent_dimensions=(dataset.height, dataset.width), roi_bounds=tuple(float(value) for value in bounds), roi_transform=tuple(float(value) for value in tuple(transform)[:6]), provenance={**dict(request.provenance), **provenance})
    except (rasterio.errors.RasterioIOError, ValueError, OSError) as exc:
        return _result(request, ROIStatus.FAILED, f"raster_extraction_failed:{type(exc).__name__}")


__all__ = ["ROIStatus", "ReferenceProductSource", "ROIWindow", "ReferenceProduct", "ROIRetrievalRequest", "ROIRetrievalResult", "retrieve_roi"]