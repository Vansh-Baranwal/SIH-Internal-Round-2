"""Minimal HTTP boundary for the frozen Phase 11 lunar-GPS contracts."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    LandmarkRetrievalRequest,
    UnknownImage,
    UnknownImageReferenceType,
    assess_metadata_quality,
    retrieve_landmarks,
)

router = APIRouter(prefix="/api/phase11", tags=["phase11-lunar-gps"])


class Phase11HttpError(str, Enum):
    INVALID_INPUT = "invalid_input"
    INTERNAL_ERROR = "internal_error"


class UnknownImageHttpRequest(BaseModel):
    """The supported JSON projection of the frozen UnknownImage contract."""

    model_config = ConfigDict(extra="forbid")

    image_id: StrictStr = Field(min_length=1)
    image_reference: StrictStr = Field(min_length=1)
    image_reference_type: UnknownImageReferenceType = UnknownImageReferenceType.UNKNOWN
    provenance: DataProvenance = DataProvenance.UNAVAILABLE
    provenance_source: StrictStr = Field(min_length=1)
    is_real_data: StrictBool = False
    validation_status: StrictStr = Field(default="unvalidated", min_length=1)
    source_id: Optional[StrictStr] = None
    product_id: Optional[StrictStr] = None
    local_path: Optional[StrictStr] = None
    external_reference: Optional[StrictStr] = None
    width: Optional[StrictInt] = Field(default=None, gt=0)
    height: Optional[StrictInt] = Field(default=None, gt=0)
    channels: Optional[StrictInt] = Field(default=None, gt=0)
    image_format: Optional[StrictStr] = None
    dtype: Optional[StrictStr] = None
    bit_depth: Optional[StrictInt] = Field(default=None, gt=0)
    gsd_m: Optional[StrictFloat | StrictInt] = Field(default=None, gt=0)
    crs: Optional[StrictStr] = None
    geospatial_reference: Optional[Dict[str, Any]] = None
    footprint: Optional[Dict[str, Any]] = None
    acquisition_timestamp: Optional[StrictStr] = None
    acquisition_date: Optional[StrictStr] = None
    sensor: Optional[StrictStr] = None
    source_name: Optional[StrictStr] = None
    illumination: Optional[Dict[str, Any]] = None
    view_geometry: Optional[Dict[str, Any]] = None
    metadata_coordinates: Optional[Dict[str, Any]] = None
    metadata_quality: Optional[StrictStr] = None
    warnings: List[StrictStr] = Field(default_factory=list)
    notes: Optional[StrictStr] = None

    @field_validator(
        "image_id",
        "image_reference",
        "provenance_source",
        "validation_status",
        "source_id",
        "product_id",
        "local_path",
        "external_reference",
        "image_format",
        "dtype",
        "crs",
        "acquisition_timestamp",
        "acquisition_date",
        "sensor",
        "source_name",
        "metadata_quality",
        "notes",
    )
    @classmethod
    def reject_blank_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("text values must not be blank")
        return value

    def to_unknown_image(self) -> UnknownImage:
        return UnknownImage(**self.model_dump())


class Phase11StageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StrictStr
    result: Dict[str, Any]


class Phase11ApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_request_id: StrictStr
    status: StrictStr
    source_image_id: StrictStr
    metadata_quality: Phase11StageResponse
    landmark_retrieval: Phase11StageResponse
    downstream_statuses: Dict[str, Optional[str]]
    match_points: Optional[Dict[str, Any]] = None
    registration_metrics: Optional[Dict[str, Any]] = None
    localization: Optional[Dict[str, Any]] = None
    final_validation: Optional[Dict[str, Any]] = None
    warnings: List[StrictStr] = Field(default_factory=list)
    limitations: List[StrictStr] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class Phase11Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_request_id: StrictStr = Field(min_length=1)
    image: UnknownImageHttpRequest

    @field_validator("validation_request_id")
    @classmethod
    def reject_blank_request_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("validation_request_id must not be blank")
        return value


@router.post("/lunar-gps", response_model=Phase11ApiResponse)
def run_phase11(request: Phase11Request) -> Phase11ApiResponse:
    """Run the real available Phase 11 prefix and report blocked prerequisites.

    The frozen chain requires a project landmark source, reference features,
    verified point pairs, georeferencing, and (for accuracy) explicit truth.
    None of those are safely representable from the current repository as a
    production HTTP input. The adapter therefore stops at the real retrieval
    boundary instead of manufacturing downstream evidence.
    """
    try:
        image = request.image.to_unknown_image()
        metadata = assess_metadata_quality(image)
        retrieval = retrieve_landmarks(
            LandmarkRetrievalRequest(image=image, metadata_quality=metadata)
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"status": Phase11HttpError.INVALID_INPUT.value, "reason": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"status": Phase11HttpError.INTERNAL_ERROR.value, "reason": "Phase 11 execution failed."},
        ) from exc

    metadata_payload = metadata.to_dict()
    retrieval_payload = retrieval.to_dict()
    limitations = list(retrieval.limitations)
    limitations.append(
        "Phase 11 execution is blocked because no serializable project landmark source is supplied by this API."
    )
    limitations.append(
        "Phases 11.4-11.12 are not executed without real upstream prerequisites; no downstream result is fabricated."
    )
    provenance = {
        "api_boundary": "phase11",
        "validation_request_id": request.validation_request_id,
        "image_provenance": image.provenance.value,
        "provenance_source": image.provenance_source,
        "synthetic": image.provenance is DataProvenance.SYNTHETIC,
        "downstream_execution": "blocked_at_11.3_prerequisite",
    }
    return Phase11ApiResponse(
        validation_request_id=request.validation_request_id,
        status="blocked",
        source_image_id=image.image_id,
        metadata_quality=Phase11StageResponse(
            status=metadata.assessment_status.value,
            result=metadata_payload,
        ),
        landmark_retrieval=Phase11StageResponse(
            status=retrieval.status.value,
            result=retrieval_payload,
        ),
        downstream_statuses={
            "11.4_landmark_correspondence": "not_executed",
            "11.5_anchor_selection": "not_executed",
            "11.6_geometric_verification": "not_executed",
            "11.7_coordinate_estimation": "not_executed",
            "11.8_localization_confidence": "not_executed",
            "11.9_roi_retrieval": "not_executed",
            "11.10_metadata_separation": "not_executed",
            "11.11_localization_accuracy": "not_executed",
            "11.12_final_validation": "not_executed",
        },
        match_points=None,
        registration_metrics=None,
        localization=None,
        warnings=list(metadata.warnings) + list(retrieval.warnings),
        limitations=limitations,
        provenance=provenance,
    )


__all__ = ["Phase11Request", "Phase11ApiResponse", "router", "run_phase11"]
