"""Minimal HTTP transport for the existing Phase 10.3 pair selection."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator

from lunar_hazard_mapper.m4_terrain import DataProvenance, LunarObservation, evaluate_pair


router = APIRouter(prefix="/api/phase10", tags=["phase10-temporal-change"])


class Phase10HttpError(str, Enum):
    INVALID_INPUT = "invalid_input"
    PROCESSING_ERROR = "processing_error"
    INTERNAL_ERROR = "internal_error"


class Phase10ObservationRequest(BaseModel):
    """HTTP-safe projection of the existing ``LunarObservation`` contract."""

    model_config = ConfigDict(extra="forbid")

    observation_id: StrictStr = Field(min_length=1)
    source: StrictStr = Field(min_length=1)
    image_reference: StrictStr = Field(min_length=1)
    acquisition_timestamp: Optional[StrictStr] = None
    product_id: Optional[StrictStr] = None
    crs: Optional[StrictStr] = None
    geospatial_reference: Optional[Dict[str, Any]] = None
    dimensions: Optional[tuple[StrictInt, StrictInt]] = None
    gsd_m: Optional[StrictFloat | StrictInt] = Field(default=None, gt=0)
    footprint: Optional[Dict[str, Any]] = None
    view_geometry: Optional[Dict[str, Any]] = None
    sun_azimuth_deg: Optional[StrictFloat | StrictInt] = Field(default=None, ge=0, lt=360)
    sun_elevation_deg: Optional[StrictFloat | StrictInt] = Field(default=None, ge=0, le=90)
    phase_angle_deg: Optional[StrictFloat | StrictInt] = Field(default=None, ge=0, le=180)
    incidence_angle_deg: Optional[StrictFloat | StrictInt] = Field(default=None, ge=0, le=180)
    emission_angle_deg: Optional[StrictFloat | StrictInt] = Field(default=None, ge=0, le=180)
    metadata_quality: Optional[StrictStr] = None
    provenance_source: StrictStr = Field(min_length=1)
    provenance: DataProvenance = DataProvenance.UNAVAILABLE
    is_real_data: StrictBool = False
    validation_status: StrictStr = Field(default="unvalidated", min_length=1)
    notes: Optional[StrictStr] = None

    @field_validator(
        "observation_id", "source", "image_reference", "acquisition_timestamp",
        "product_id", "crs", "metadata_quality", "provenance_source",
        "validation_status", "notes",
    )
    @classmethod
    def reject_blank_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("text values must not be blank")
        return value

    @field_validator("image_reference")
    @classmethod
    def reject_server_path_reference(cls, value: str) -> str:
        if value.startswith(("/", "\\")) or (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
            raise ValueError("absolute filesystem image references are not accepted by the HTTP boundary")
        if value.lower().startswith("file:"):
            raise ValueError("file URI image references are not accepted by the HTTP boundary")
        parsed = urlparse(value)
        if not parsed.scheme and ("/" in value or "\\" in value):
            raise ValueError("path-like image references are not accepted by the HTTP boundary")
        return value

    def to_observation(self) -> LunarObservation:
        return LunarObservation(**self.model_dump())


class Phase10PairSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_a: Phase10ObservationRequest
    observation_b: Phase10ObservationRequest


class Phase10PairSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_a_id: Optional[StrictStr]
    observation_b_id: Optional[StrictStr]
    eligibility: StrictStr
    hard_rejection_reasons: List[StrictStr]
    warnings: List[StrictStr]
    candidate_selection_score: Optional[StrictFloat]
    temporal_metadata: Optional[Dict[str, Any]]
    crs_compatibility: StrictStr
    footprint_compatibility: StrictStr
    sensor_compatibility: StrictStr
    image_reference_a: StrictStr
    image_reference_b: StrictStr
    metadata_completeness: StrictFloat
    provenance_status: StrictStr


class Phase10ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: Dict[str, StrictStr]


@router.post(
    "/pair-selection",
    response_model=Phase10PairSelectionResponse,
    responses={
        422: {"description": "Invalid request or observation metadata."},
        500: {"model": Phase10ErrorResponse, "description": "Phase 10 adapter failure."},
    },
)
def select_phase10_pair(request: Phase10PairSelectionRequest) -> Phase10PairSelectionResponse:
    """Evaluate one client-ordered pair using the frozen Phase 10.3 callable."""
    try:
        result = evaluate_pair(
            request.observation_a.to_observation(),
            request.observation_b.to_observation(),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"status": Phase10HttpError.INVALID_INPUT.value, "reason": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"status": Phase10HttpError.INTERNAL_ERROR.value, "reason": "Phase 10 pair selection failed."},
        ) from exc

    try:
        return Phase10PairSelectionResponse.model_validate(result.to_dict())
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"status": Phase10HttpError.PROCESSING_ERROR.value, "reason": "Phase 10 returned an invalid pair-selection result."},
        ) from exc


__all__ = [
    "Phase10ObservationRequest",
    "Phase10PairSelectionRequest",
    "Phase10PairSelectionResponse",
    "Phase10ErrorResponse",
    "router",
    "select_phase10_pair",
]