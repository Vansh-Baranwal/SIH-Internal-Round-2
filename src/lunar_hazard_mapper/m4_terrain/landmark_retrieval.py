"""Phase 11.3 landmark retrieval for unknown lunar images.

This module implements retrieval-only behavior for the Phase 11 Lunar Image GPS
pipeline. It consumes the frozen `UnknownImage` contract and, when available,
uses an existing project landmark source to assemble candidate landmark records.

A retrieved landmark is explicitly a candidate reference; it is not a confirmed
landmark correspondence and it does not establish that the landmark appears in
the unknown image.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from lunar_hazard_mapper.m4_terrain import DataProvenance, MetadataQualityResult, UnknownImage
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterLandmark,
    CraterLandmarkDatabase,
    CraterLandmarkNetwork,
)


class RetrievalStatus(str, Enum):
    SUCCESS = "success"
    EMPTY_RESULT = "empty_result"
    NO_RETRIEVAL_CONTEXT = "no_retrieval_context"
    LANDMARK_SOURCE_UNAVAILABLE = "landmark_source_unavailable"
    INVALID_INPUT = "invalid_input"
    INVALID_LANDMARK_SOURCE = "invalid_landmark_source"
    RETRIEVAL_FAILED = "retrieval_failed"


@dataclass(frozen=True)
class LandmarkQuery:
    image_id: str
    image_reference: str
    sensor: Optional[str]
    gsd_m: Optional[float]
    crs: Optional[str]
    metadata_coordinates: Optional[Dict[str, Any]]
    image_reference_type: Optional[str]
    provenance: DataProvenance
    metadata_quality_status: Optional[str]
    requires_context: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "image_reference": self.image_reference,
            "sensor": self.sensor,
            "gsd_m": self.gsd_m,
            "crs": self.crs,
            "metadata_coordinates": self.metadata_coordinates,
            "image_reference_type": self.image_reference_type,
            "provenance": self.provenance.value,
            "metadata_quality_status": self.metadata_quality_status,
            "requires_context": self.requires_context,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LandmarkQuery":
        if not isinstance(payload, dict):
            raise ValueError("LandmarkQuery payload must be a dictionary.")
        return cls(
            image_id=str(payload["image_id"]),
            image_reference=str(payload["image_reference"]),
            sensor=payload.get("sensor"),
            gsd_m=payload.get("gsd_m"),
            crs=payload.get("crs"),
            metadata_coordinates=payload.get("metadata_coordinates"),
            image_reference_type=payload.get("image_reference_type"),
            provenance=DataProvenance(payload["provenance"]),
            metadata_quality_status=payload.get("metadata_quality_status"),
            requires_context=bool(payload.get("requires_context", False)),
        )


@dataclass(frozen=True)
class LandmarkCandidate:
    landmark_id: str
    source_id: Optional[str]
    source_database: str
    reference_image_id: Optional[str]
    reference_image_reference: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    crs: Optional[str]
    sensor: Optional[str]
    gsd_m: Optional[float]
    landmark_type: Optional[str]
    provenance: DataProvenance
    retrieval_reason: str
    retrieval_rank: int
    score: Optional[float] = None
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    is_synthetic: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "landmark_id": self.landmark_id,
            "source_id": self.source_id,
            "source_database": self.source_database,
            "reference_image_id": self.reference_image_id,
            "reference_image_reference": self.reference_image_reference,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "crs": self.crs,
            "sensor": self.sensor,
            "gsd_m": self.gsd_m,
            "landmark_type": self.landmark_type,
            "provenance": self.provenance.value,
            "retrieval_reason": self.retrieval_reason,
            "retrieval_rank": self.retrieval_rank,
            "score": self.score,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "is_synthetic": self.is_synthetic,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LandmarkCandidate":
        if not isinstance(payload, dict):
            raise ValueError("LandmarkCandidate payload must be a dictionary.")
        return cls(
            landmark_id=str(payload["landmark_id"]),
            source_id=payload.get("source_id"),
            source_database=str(payload.get("source_database", "unknown")),
            reference_image_id=payload.get("reference_image_id"),
            reference_image_reference=payload.get("reference_image_reference"),
            latitude_deg=payload.get("latitude_deg"),
            longitude_deg=payload.get("longitude_deg"),
            crs=payload.get("crs"),
            sensor=payload.get("sensor"),
            gsd_m=payload.get("gsd_m"),
            landmark_type=payload.get("landmark_type"),
            provenance=DataProvenance(payload["provenance"]),
            retrieval_reason=str(payload.get("retrieval_reason", "retrieved_from_source")),
            retrieval_rank=int(payload.get("retrieval_rank", 0)),
            score=payload.get("score"),
            warnings=tuple(payload.get("warnings", ())),
            limitations=tuple(payload.get("limitations", ())),
            is_synthetic=bool(payload.get("is_synthetic", False)),
        )


@dataclass(frozen=True)
class LandmarkRetrievalRequest:
    image: UnknownImage
    landmark_source: Optional[Union[CraterLandmarkDatabase, CraterLandmarkNetwork, Sequence[CraterLandmark], object]] = None
    metadata_quality: Optional[MetadataQualityResult] = None
    query_context: Optional[Dict[str, Any]] = None
    min_quality_score: Optional[float] = None
    max_candidates: Optional[int] = None
    require_context: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.image, UnknownImage):
            raise TypeError("image must be an UnknownImage instance.")

    def normalized_source(self) -> Optional[Union[CraterLandmarkDatabase, CraterLandmarkNetwork]]:
        if self.landmark_source is None:
            return None
        if isinstance(self.landmark_source, (CraterLandmarkDatabase, CraterLandmarkNetwork)):
            return self.landmark_source
        if isinstance(self.landmark_source, Sequence) and not isinstance(self.landmark_source, (str, bytes, bytearray)):
            network = CraterLandmarkNetwork()
            for item in self.landmark_source:
                if not isinstance(item, CraterLandmark):
                    raise TypeError("landmark_source sequence must contain CraterLandmark instances.")
                network.add_landmark(item)
            return network
        return None


@dataclass(frozen=True)
class LandmarkRetrievalResult:
    status: RetrievalStatus
    request: LandmarkRetrievalRequest
    query: LandmarkQuery
    candidates: Tuple[LandmarkCandidate, ...] = ()
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    is_synthetic: bool = False
    claims_correspondence: bool = False
    claims_localization: bool = False

    @property
    def total_candidates(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "query": self.query.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "is_synthetic": self.is_synthetic,
            "claims_correspondence": self.claims_correspondence,
            "claims_localization": self.claims_localization,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LandmarkRetrievalResult":
        if not isinstance(payload, dict):
            raise ValueError("LandmarkRetrievalResult payload must be a dictionary.")
        query_payload = payload.get("query")
        if not isinstance(query_payload, dict):
            raise ValueError("query payload must be a dictionary.")
        request = LandmarkRetrievalRequest(
            image=UnknownImage.from_dict({
                "image_id": query_payload["image_id"],
                "image_reference": query_payload["image_reference"],
                "image_reference_type": query_payload.get("image_reference_type", "unknown"),
                "provenance": query_payload.get("provenance", DataProvenance.UNAVAILABLE.value),
                "provenance_source": "serialized_query",
                "is_real_data": False,
                "validation_status": "unvalidated",
            }),
            landmark_source=None,
            metadata_quality=None,
            query_context=None,
        )
        return cls(
            status=RetrievalStatus(payload["status"]),
            request=request,
            query=LandmarkQuery.from_dict(query_payload),
            candidates=tuple(LandmarkCandidate.from_dict(item) for item in payload.get("candidates", ())),
            warnings=tuple(payload.get("warnings", ())),
            limitations=tuple(payload.get("limitations", ())),
            is_synthetic=bool(payload.get("is_synthetic", False)),
            claims_correspondence=bool(payload.get("claims_correspondence", False)),
            claims_localization=bool(payload.get("claims_localization", False)),
        )


def _build_query(image: UnknownImage, metadata_quality: Optional[MetadataQualityResult] = None, query_context: Optional[Dict[str, Any]] = None, *, require_context: bool = False) -> LandmarkQuery:
    metadata_status = None
    if metadata_quality is not None:
        metadata_status = metadata_quality.assessment_status.value

    return LandmarkQuery(
        image_id=image.image_id,
        image_reference=image.image_reference,
        sensor=image.sensor,
        gsd_m=image.gsd_m,
        crs=image.crs,
        metadata_coordinates=image.metadata_coordinates,
        image_reference_type=image.image_reference_type.value if hasattr(image.image_reference_type, "value") else str(image.image_reference_type),
        provenance=image.provenance,
        metadata_quality_status=metadata_status,
        requires_context=require_context,
    )


def _candidate_from_landmark(landmark: CraterLandmark, *, rank: int, source_name: str) -> LandmarkCandidate:
    if not isinstance(landmark, CraterLandmark):
        raise TypeError("landmark candidate must be a CraterLandmark instance.")
    provenance = DataProvenance.SYNTHETIC if getattr(landmark, "source_type", "").lower() == "synthetic" else DataProvenance.UNAVAILABLE
    is_synthetic = provenance is DataProvenance.SYNTHETIC
    metadata = getattr(landmark, "metadata", {}) or {}
    return LandmarkCandidate(
        landmark_id=landmark.crater_id,
        source_id=metadata.get("source_id"),
        source_database=source_name,
        reference_image_id=metadata.get("reference_image_id"),
        reference_image_reference=metadata.get("reference_image_reference"),
        latitude_deg=landmark.latitude_deg,
        longitude_deg=landmark.longitude_deg,
        crs=metadata.get("crs"),
        sensor=metadata.get("sensor"),
        gsd_m=metadata.get("gsd_m"),
        landmark_type=metadata.get("landmark_type"),
        provenance=provenance,
        retrieval_reason="retrieved_from_source_by_standardized_query",
        retrieval_rank=rank,
        score=getattr(landmark, "quality_score", None),
        is_synthetic=is_synthetic,
        warnings=tuple(metadata.get("warnings", ())),
        limitations=tuple(metadata.get("limitations", ())),
    )


def _determine_landmark_source_name(landmark_source: Any) -> str:
    if isinstance(landmark_source, CraterLandmarkDatabase):
        return "CraterLandmarkDatabase"
    if isinstance(landmark_source, CraterLandmarkNetwork):
        return "CraterLandmarkNetwork"
    return "unknown_landmark_source"


def retrieve_landmarks(request: LandmarkRetrievalRequest) -> LandmarkRetrievalResult:
    """Retrieve landmark candidate records from the authoritative source.

    Phase 11.3 does not perform land-mark correspondence; it only fetches and
    filters candidate records from the existing landmark source.
    """
    if not isinstance(request, LandmarkRetrievalRequest):
        raise TypeError("request must be a LandmarkRetrievalRequest instance.")

    image = request.image
    if not isinstance(image, UnknownImage):
        return LandmarkRetrievalResult(
            status=RetrievalStatus.INVALID_INPUT,
            request=request,
            query=_build_query(image, request.metadata_quality, request.query_context, require_context=request.require_context),
            warnings=("invalid_unknown_image",),
            limitations=("No valid UnknownImage was supplied for retrieval.",),
        )

    query = _build_query(image, request.metadata_quality, request.query_context, require_context=request.require_context)
    warnings: List[str] = []
    limitations: List[str] = []

    if image.metadata_coordinates is not None:
        warnings.append("metadata_coordinates_present_not_estimated")
        limitations.append("Metadata coordinates are preserved as metadata-only and are not treated as estimated localization.")

    if image.gsd_m is None:
        warnings.append("unknown_gsd")
        limitations.append("GSD is unavailable, so retrieval specificity is reduced.")

    if image.sensor is None:
        warnings.append("unknown_sensor")
        limitations.append("Sensor metadata is unavailable, so cross-source compatibility filtering is limited.")

    if image.crs is None:
        warnings.append("unknown_crs")
        limitations.append("CRS metadata is unavailable, so retrieval remains conservative and metadata-only.")

    if request.landmark_source is None:
        return LandmarkRetrievalResult(
            status=RetrievalStatus.LANDMARK_SOURCE_UNAVAILABLE,
            request=request,
            query=query,
            candidates=[],
            warnings=tuple(dict.fromkeys(warnings + ["landmark_source_unavailable"])),
            limitations=tuple(dict.fromkeys(limitations + ["No authoritative landmark source is available for Phase 11.3 retrieval."])),
        )

    if request.landmark_source is not None and request.normalized_source() is None:
        return LandmarkRetrievalResult(
            status=RetrievalStatus.INVALID_LANDMARK_SOURCE,
            request=request,
            query=query,
            candidates=[],
            warnings=("invalid_landmark_source",),
            limitations=("The landmark source is not a recognized project source type.",),
        )

    landmark_source = request.normalized_source()

    if request.require_context and image.sensor is None and image.gsd_m is None and image.crs is None:
        return LandmarkRetrievalResult(
            status=RetrievalStatus.NO_RETRIEVAL_CONTEXT,
            request=request,
            query=query,
            candidates=[],
            warnings=("no_retrieval_context",),
            limitations=("Insufficient legitimate information exists to construct a meaningful Phase 11.3 retrieval query.",),
        )

    source_name = _determine_landmark_source_name(landmark_source)
    records: List[CraterLandmark] = []
    try:
        if isinstance(landmark_source, CraterLandmarkDatabase):
            records = landmark_source.list(min_quality_score=request.min_quality_score)
        elif isinstance(landmark_source, CraterLandmarkNetwork):
            records = landmark_source.landmarks(min_quality_score=request.min_quality_score)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return LandmarkRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_FAILED,
            request=request,
            query=query,
            warnings=("retrieval_failed",),
            limitations=(f"Retrieval failed: {exc}",),
        )

    if records is None:
        records = []

    candidates: List[LandmarkCandidate] = []
    for rank, landmark in enumerate(sorted(records, key=lambda item: item.crater_id), start=1):
        if request.max_candidates is not None and rank > request.max_candidates:
            break
        candidate = _candidate_from_landmark(landmark, rank=rank, source_name=source_name)
        if request.min_quality_score is not None and (candidate.score is None or candidate.score < request.min_quality_score):
            continue
        candidates.append(candidate)

    if not candidates:
        return LandmarkRetrievalResult(
            status=RetrievalStatus.EMPTY_RESULT,
            request=request,
            query=query,
            candidates=[],
            warnings=tuple(dict.fromkeys(warnings + ["empty_result"])),
            limitations=tuple(dict.fromkeys(limitations + ["The query executed successfully but no candidate landmark records were available."])),
            is_synthetic=image.provenance is DataProvenance.SYNTHETIC,
            claims_correspondence=False,
            claims_localization=False,
        )

    # Preserve synthetic-vs-real provenance mismatches as retrieval warnings without
    # claiming a landmark match or localization.
    for candidate in candidates:
        if image.provenance is DataProvenance.REAL and candidate.provenance is DataProvenance.SYNTHETIC:
            warnings.append("provenance_mismatch_real_unknown_image_synthetic_landmark")
            limitations.append("An image with real-data provenance was queried against synthetic landmark records.")
        elif image.provenance is DataProvenance.SYNTHETIC and candidate.provenance is DataProvenance.UNAVAILABLE:
            warnings.append("synthetic_image_with_unknown_landmark_provenance")

    result = LandmarkRetrievalResult(
        status=RetrievalStatus.SUCCESS,
        request=request,
        query=query,
        candidates=tuple(candidates),
        warnings=tuple(dict.fromkeys(warnings)),
        limitations=tuple(dict.fromkeys(limitations)),
        is_synthetic=image.provenance is DataProvenance.SYNTHETIC,
        claims_correspondence=False,
        claims_localization=False,
    )
    return result


__all__ = [
    "LandmarkCandidate",
    "LandmarkQuery",
    "LandmarkRetrievalRequest",
    "LandmarkRetrievalResult",
    "RetrievalStatus",
    "retrieve_landmarks",
]
