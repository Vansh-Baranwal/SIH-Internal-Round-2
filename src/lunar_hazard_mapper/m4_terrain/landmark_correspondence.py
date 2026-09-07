"""Phase 11.4 landmark correspondence for unknown lunar images.

This module intentionally implements the retrieval-to-correspondence boundary only.
It does not estimate geometry, select anchors, or localize the unknown image.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from lunar_hazard_mapper.m4_terrain import DataProvenance, UnknownImage
from lunar_hazard_mapper.m4_terrain.landmark_retrieval import LandmarkRetrievalResult


class CorrespondenceStatus(str, Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_FEATURES = "no_features"
    REFERENCE_FEATURES_UNAVAILABLE = "reference_features_unavailable"
    IMAGE_UNAVAILABLE = "image_unavailable"
    INVALID_INPUT = "invalid_input"
    INCOMPATIBLE_FEATURES = "incompatible_features"
    NO_CORRESPONDENCES = "no_correspondences"
    PARTIAL_CORRESPONDENCE = "partial_correspondence"
    CORRESPONDENCE_FAILED = "correspondence_failed"
    BLOCKED_BY_PROVENANCE = "blocked_by_provenance"


@dataclass(frozen=True)
class CorrespondenceFeatureSet:
    feature_type: str
    keypoints: Tuple[Tuple[float, float], ...]
    descriptors: Tuple[Tuple[float, ...], ...]
    descriptor_dim: int
    feature_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_type": self.feature_type,
            "keypoints": [[float(x), float(y)] for x, y in self.keypoints],
            "descriptors": [[float(v) for v in row] for row in self.descriptors],
            "descriptor_dim": self.descriptor_dim,
            "feature_count": self.feature_count,
        }


@dataclass(frozen=True)
class LandmarkCorrespondenceRecord:
    candidate_id: str
    status: CorrespondenceStatus
    reference_feature_count: int
    unknown_feature_count: int
    tentative_match_count: int
    surviving_match_count: int
    descriptor_distances: Tuple[float, ...] = ()
    similarity_scores: Tuple[float, ...] = ()
    matched_keypoints: Tuple[Tuple[Tuple[float, float], Tuple[float, float]], ...] = ()
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    method: str = "sift-ratio-test"
    geometric_verification_performed: bool = False
    source_provenance: Optional[DataProvenance] = None
    candidate_provenance: Optional[DataProvenance] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "reference_feature_count": self.reference_feature_count,
            "unknown_feature_count": self.unknown_feature_count,
            "tentative_match_count": self.tentative_match_count,
            "surviving_match_count": self.surviving_match_count,
            "descriptor_distances": list(self.descriptor_distances),
            "similarity_scores": list(self.similarity_scores),
            "matched_keypoints": [[list(p1), list(p2)] for p1, p2 in self.matched_keypoints],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "method": self.method,
            "geometric_verification_performed": self.geometric_verification_performed,
            "source_provenance": self.source_provenance.value if self.source_provenance is not None else None,
            "candidate_provenance": self.candidate_provenance.value if self.candidate_provenance is not None else None,
        }


@dataclass(frozen=True)
class LandmarkCorrespondenceRequest:
    image: UnknownImage
    retrieval_result: LandmarkRetrievalResult
    reference_features: Optional[Mapping[str, Any]] = None
    matcher: str = "sift"
    ratio_threshold: float = 0.75
    min_matches: int = 2
    allow_partial: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.image, UnknownImage):
            raise TypeError("image must be a valid UnknownImage instance.")
        if self.retrieval_result is None:
            raise TypeError("retrieval_result must not be None.")
        if not isinstance(self.matcher, str) or not self.matcher.strip():
            raise ValueError("matcher must be a non-empty string.")
        if not isinstance(self.ratio_threshold, (int, float)) or not (0.0 < float(self.ratio_threshold) <= 1.0):
            raise ValueError("ratio_threshold must be between 0 and 1.")
        if not isinstance(self.min_matches, int) or self.min_matches <= 0:
            raise ValueError("min_matches must be a positive integer.")


@dataclass(frozen=True)
class LandmarkCorrespondenceResult:
    status: CorrespondenceStatus
    unknown_image_id: str
    candidate_ids: Tuple[str, ...]
    records: Tuple[LandmarkCorrespondenceRecord, ...]
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    claims_localization: bool = False
    claims_geometric_verification: bool = False
    claims_correspondence: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "unknown_image_id": self.unknown_image_id,
            "candidate_ids": list(self.candidate_ids),
            "records": [record.to_dict() for record in self.records],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
            "claims_localization": self.claims_localization,
            "claims_geometric_verification": self.claims_geometric_verification,
            "claims_correspondence": self.claims_correspondence,
        }


def _normalize_feature_payload(feature_payload: Any, *, candidate_id: str) -> CorrespondenceFeatureSet:
    if feature_payload is None:
        raise ValueError(f"Reference feature data for {candidate_id} is missing.")
    if isinstance(feature_payload, CorrespondenceFeatureSet):
        return feature_payload
    if isinstance(feature_payload, Mapping):
        keypoints = feature_payload.get("keypoints")
        descriptors = feature_payload.get("descriptors")
        if keypoints is None or descriptors is None:
            raise ValueError(f"Reference feature data for {candidate_id} is incomplete.")
        if not isinstance(keypoints, Sequence) or len(keypoints) == 0:
            raise ValueError(f"Reference feature keypoints for {candidate_id} are empty.")
        descriptors_list = list(descriptors)
        if len(descriptors_list) == 0:
            raise ValueError(f"Reference feature descriptors for {candidate_id} are empty.")
        normalized_keypoints = []
        for item in keypoints:
            if not isinstance(item, Sequence) or len(item) != 2:
                raise ValueError(f"Feature keypoint for {candidate_id} must be a 2D point.")
            x, y = item
            if not np.isfinite(x) or not np.isfinite(y):
                raise ValueError(f"Feature keypoint for {candidate_id} contains NaN/Inf.")
            normalized_keypoints.append((float(x), float(y)))
        normalized_descriptors = []
        for row in descriptors_list:
            if not isinstance(row, Sequence) or len(row) == 0:
                raise ValueError(f"Descriptor row for {candidate_id} is malformed.")
            desc = tuple(float(v) for v in row)
            normalized_descriptors.append(desc)
        descriptor_dim = len(normalized_descriptors[0])
        if any(len(row) != descriptor_dim for row in normalized_descriptors):
            raise ValueError(f"Descriptor rows for {candidate_id} have inconsistent lengths.")
        return CorrespondenceFeatureSet(
            feature_type=str(feature_payload.get("feature_type", "sift")),
            keypoints=tuple(normalized_keypoints),
            descriptors=tuple(normalized_descriptors),
            descriptor_dim=descriptor_dim,
            feature_count=len(normalized_keypoints),
        )
    raise ValueError(f"Reference feature payload for {candidate_id} is not a recognized feature representation.")


def _read_unknown_features(image: UnknownImage) -> CorrespondenceFeatureSet:
    if image.image_reference_type in {
        image.image_reference_type.EXTERNAL_REFERENCE,
        image.image_reference_type.UNAVAILABLE,
        image.image_reference_type.UNKNOWN,
        image.image_reference_type.INVALID,
    }:
        raise ValueError("Image reference is not a local, readable source.")
    local_path = image.local_path or image.image_reference
    if not local_path:
        raise ValueError("No usable local path is available for feature extraction.")
    file_path = str(local_path)
    if not file_path or not os.path.exists(file_path):
        raise ValueError("Local image file does not exist or is unreadable.")
    image_arr = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if image_arr is None:
        raise ValueError("Local image file could not be read for feature extraction.")
    sift = cv2.SIFT_create()
    keypoints, descriptors = sift.detectAndCompute(image_arr, None)
    if keypoints is None or descriptors is None or len(keypoints) == 0 or descriptors.size == 0:
        raise ValueError("No usable features were extracted from the unknown image.")
    return CorrespondenceFeatureSet(
        feature_type="sift",
        keypoints=tuple((float(kp.pt[0]), float(kp.pt[1])) for kp in keypoints),
        descriptors=tuple(tuple(float(v) for v in row) for row in descriptors.tolist()),
        descriptor_dim=int(descriptors.shape[1]),
        feature_count=len(keypoints),
    )


def _match_descriptors(source_descriptors: np.ndarray, reference_descriptors: np.ndarray, *, ratio_threshold: float) -> List[Tuple[float, float, Tuple[float, float], Tuple[float, float]]]:
    if source_descriptors.size == 0 or reference_descriptors.size == 0:
        return []
    if source_descriptors.shape[1] != reference_descriptors.shape[1]:
        raise ValueError("Descriptor dimensionality mismatch")
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    if source_descriptors.dtype.kind in {"u", "i", "b"} or reference_descriptors.dtype.kind in {"u", "i", "b"}:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = matcher.knnMatch(source_descriptors.astype(np.float32), reference_descriptors.astype(np.float32), k=2)
    filtered: List[Tuple[float, float, Tuple[float, float], Tuple[float, float]]] = []
    for pair in matches:
        if len(pair) != 2:
            continue
        m, n = pair
        if m.distance < ratio_threshold * n.distance:
            filtered.append((float(m.distance), 1.0 / (1.0 + float(m.distance)), (float(m.queryIdx), float(m.trainIdx)), (0.0, 0.0)))
    return filtered


def _candidate_reference_feature(request: LandmarkCorrespondenceRequest, candidate_id: str) -> Optional[CorrespondenceFeatureSet]:
    if request.reference_features is None:
        return None
    ref = request.reference_features.get(candidate_id)
    if ref is None:
        return None
    try:
        return _normalize_feature_payload(ref, candidate_id=candidate_id)
    except ValueError:
        return None


def compute_landmark_correspondence(request: LandmarkCorrespondenceRequest) -> LandmarkCorrespondenceResult:
    if not isinstance(request, LandmarkCorrespondenceRequest):
        raise TypeError("request must be a LandmarkCorrespondenceRequest instance.")

    image = request.image
    retrieval_result = request.retrieval_result
    warnings: List[str] = []
    limitations: List[str] = []

    if image is None or not isinstance(image, UnknownImage):
        raise TypeError("request.image must be a valid UnknownImage instance.")

    if request.reference_features is None or len(request.reference_features) == 0:
        return LandmarkCorrespondenceResult(
            status=CorrespondenceStatus.REFERENCE_FEATURES_UNAVAILABLE,
            unknown_image_id=image.image_id,
            candidate_ids=tuple(candidate.landmark_id for candidate in retrieval_result.candidates),
            records=(),
            warnings=("reference_features_unavailable",),
            limitations=("No reference feature map was supplied for any landmark candidate.",),
            provenance={
                "unknown_image_provenance": image.provenance,
                "candidate_provenance": None,
                "matcher": request.matcher,
                "ratio_threshold": request.ratio_threshold,
                "min_matches": request.min_matches,
            },
            claims_localization=False,
            claims_geometric_verification=False,
            claims_correspondence=False,
        )

    if retrieval_result is None or not getattr(retrieval_result, "candidates", ()):
        return LandmarkCorrespondenceResult(
            status=CorrespondenceStatus.NO_CANDIDATES,
            unknown_image_id=image.image_id,
            candidate_ids=(),
            records=(),
            warnings=("no_retrieval_candidates",),
            limitations=("No retrieved landmark candidates were supplied for correspondence.",),
            provenance={
                "unknown_image_provenance": image.provenance,
                "candidate_provenance": None,
                "matcher": request.matcher,
                "ratio_threshold": request.ratio_threshold,
                "min_matches": request.min_matches,
            },
            claims_localization=False,
            claims_geometric_verification=False,
            claims_correspondence=False,
        )

    if image.image_reference_type in {
        image.image_reference_type.EXTERNAL_REFERENCE,
        image.image_reference_type.UNAVAILABLE,
        image.image_reference_type.UNKNOWN,
        image.image_reference_type.INVALID,
    }:
        return LandmarkCorrespondenceResult(
            status=CorrespondenceStatus.IMAGE_UNAVAILABLE,
            unknown_image_id=image.image_id,
            candidate_ids=tuple(candidate.landmark_id for candidate in retrieval_result.candidates),
            records=(),
            warnings=("image_reference_unavailable",),
            limitations=("No local image is available to extract unknown-image features.",),
            provenance={
                "unknown_image_provenance": image.provenance,
                "candidate_provenance": None,
                "matcher": request.matcher,
                "ratio_threshold": request.ratio_threshold,
                "min_matches": request.min_matches,
            },
            claims_localization=False,
            claims_geometric_verification=False,
            claims_correspondence=False,
        )

    try:
        unknown_features = _read_unknown_features(image)
    except ValueError as exc:
        return LandmarkCorrespondenceResult(
            status=CorrespondenceStatus.NO_FEATURES,
            unknown_image_id=image.image_id,
            candidate_ids=tuple(candidate.landmark_id for candidate in retrieval_result.candidates),
            records=(),
            warnings=("unknown_image_has_no_features",),
            limitations=(str(exc),),
            provenance={
                "unknown_image_provenance": image.provenance,
                "candidate_provenance": None,
                "matcher": request.matcher,
                "ratio_threshold": request.ratio_threshold,
                "min_matches": request.min_matches,
            },
            claims_localization=False,
            claims_geometric_verification=False,
            claims_correspondence=False,
        )

    records: List[LandmarkCorrespondenceRecord] = []
    for candidate in retrieval_result.candidates:
        candidate_id = candidate.landmark_id
        feature_map = request.reference_features or {}
        candidate_ref = feature_map.get(candidate_id)
        if candidate_ref is None:
            records.append(LandmarkCorrespondenceRecord(
                candidate_id=candidate_id,
                status=CorrespondenceStatus.REFERENCE_FEATURES_UNAVAILABLE,
                reference_feature_count=0,
                unknown_feature_count=unknown_features.feature_count,
                tentative_match_count=0,
                surviving_match_count=0,
                warnings=("reference_feature_missing",),
                limitations=(f"Reference features for candidate {candidate_id} are unavailable.",),
                source_provenance=image.provenance,
                candidate_provenance=candidate.provenance,
            ))
            continue

        try:
            ref_features = _normalize_feature_payload(candidate_ref, candidate_id=candidate_id)
        except ValueError as exc:
            records.append(LandmarkCorrespondenceRecord(
                candidate_id=candidate_id,
                status=CorrespondenceStatus.INVALID_INPUT,
                reference_feature_count=0,
                unknown_feature_count=unknown_features.feature_count,
                tentative_match_count=0,
                surviving_match_count=0,
                warnings=("malformed_reference_features",),
                limitations=(str(exc),),
                source_provenance=image.provenance,
                candidate_provenance=candidate.provenance,
            ))
            continue

        if ref_features.descriptor_dim != unknown_features.descriptor_dim:
            records.append(LandmarkCorrespondenceRecord(
                candidate_id=candidate_id,
                status=CorrespondenceStatus.INCOMPATIBLE_FEATURES,
                reference_feature_count=ref_features.feature_count,
                unknown_feature_count=unknown_features.feature_count,
                tentative_match_count=0,
                surviving_match_count=0,
                warnings=("descriptor_dim_mismatch",),
                limitations=(f"Descriptor dimensionality mismatch for {candidate_id}: {ref_features.descriptor_dim} vs {unknown_features.descriptor_dim}.",),
                source_provenance=image.provenance,
                candidate_provenance=candidate.provenance,
            ))
            continue

        try:
            src_arr = np.asarray([np.asarray(row, dtype=np.float32) for row in unknown_features.descriptors], dtype=np.float32)
            ref_arr = np.asarray([np.asarray(row, dtype=np.float32) for row in ref_features.descriptors], dtype=np.float32)
            matches = _match_descriptors(src_arr, ref_arr, ratio_threshold=request.ratio_threshold)
        except ValueError:
            records.append(LandmarkCorrespondenceRecord(
                candidate_id=candidate_id,
                status=CorrespondenceStatus.INCOMPATIBLE_FEATURES,
                reference_feature_count=ref_features.feature_count,
                unknown_feature_count=unknown_features.feature_count,
                tentative_match_count=0,
                surviving_match_count=0,
                warnings=("descriptor_incompatible",),
                limitations=("Feature descriptors are incompatible and cannot be matched.",),
                source_provenance=image.provenance,
                candidate_provenance=candidate.provenance,
            ))
            continue

        tentative_count = len(matches)
        surviving = tentative_count
        if tentative_count == 0:
            status = CorrespondenceStatus.NO_CORRESPONDENCES
            warnings.append("no_tentative_correspondences")
        elif tentative_count < request.min_matches:
            status = CorrespondenceStatus.PARTIAL_CORRESPONDENCE
            warnings.append("partial_correspondence")
        else:
            status = CorrespondenceStatus.SUCCESS

        if image.provenance is DataProvenance.REAL and candidate.provenance is DataProvenance.SYNTHETIC:
            warnings.append("provenance_mismatch_real_image_synthetic_candidate")
        if image.provenance is DataProvenance.SYNTHETIC and candidate.provenance is DataProvenance.UNAVAILABLE:
            warnings.append("synthetic_image_unknown_candidate_provenance")

        distances = tuple(item[0] for item in matches)
        similarities = tuple(item[1] for item in matches)
        matched_points = tuple(((float(item[2][0]), float(item[2][1])), (float(item[3][0]), float(item[3][1]))) for item in matches)

        records.append(
            LandmarkCorrespondenceRecord(
                candidate_id=candidate_id,
                status=status,
                reference_feature_count=ref_features.feature_count,
                unknown_feature_count=unknown_features.feature_count,
                tentative_match_count=tentative_count,
                surviving_match_count=surviving,
                descriptor_distances=distances,
                similarity_scores=similarities,
                matched_keypoints=matched_points,
                warnings=tuple(dict.fromkeys(warnings)),
                limitations=("Geometric verification is intentionally not performed in Phase 11.4.",),
                method=request.matcher,
                geometric_verification_performed=False,
                source_provenance=image.provenance,
                candidate_provenance=candidate.provenance,
            )
        )

    aggregate_status = CorrespondenceStatus.SUCCESS if any(r.status == CorrespondenceStatus.SUCCESS for r in records) else CorrespondenceStatus.NO_CORRESPONDENCES
    if not records:
        aggregate_status = CorrespondenceStatus.NO_CANDIDATES
    elif any(r.status == CorrespondenceStatus.PARTIAL_CORRESPONDENCE for r in records):
        aggregate_status = CorrespondenceStatus.PARTIAL_CORRESPONDENCE
    elif any(r.status == CorrespondenceStatus.INCOMPATIBLE_FEATURES for r in records):
        aggregate_status = CorrespondenceStatus.INCOMPATIBLE_FEATURES
    elif any(r.status == CorrespondenceStatus.REFERENCE_FEATURES_UNAVAILABLE for r in records):
        aggregate_status = CorrespondenceStatus.REFERENCE_FEATURES_UNAVAILABLE
    elif all(r.status in {CorrespondenceStatus.NO_CORRESPONDENCES, CorrespondenceStatus.INVALID_INPUT} for r in records):
        aggregate_status = CorrespondenceStatus.NO_CORRESPONDENCES

    candidate_provenance = {
        candidate.landmark_id: candidate.provenance for candidate in retrieval_result.candidates
    }
    if len(candidate_provenance) == 1:
        first_value = next(iter(candidate_provenance.values()))
        candidate_provenance = first_value

    result = LandmarkCorrespondenceResult(
        status=aggregate_status,
        unknown_image_id=image.image_id,
        candidate_ids=tuple(candidate.landmark_id for candidate in retrieval_result.candidates),
        records=tuple(records),
        warnings=tuple(dict.fromkeys(warnings)),
        limitations=tuple(dict.fromkeys(limitations + ["Geometric verification and localization are intentionally deferred to later phases."])),
        provenance={
            "unknown_image_provenance": image.provenance,
            "candidate_provenance": candidate_provenance,
            "matcher": request.matcher,
            "ratio_threshold": request.ratio_threshold,
            "min_matches": request.min_matches,
            "feature_extractor": "sift",
            "geometric_verification_performed": False,
        },
        claims_localization=False,
        claims_geometric_verification=False,
        claims_correspondence=aggregate_status is CorrespondenceStatus.SUCCESS,
    )
    return result


__all__ = [
    "CorrespondenceFeatureSet",
    "CorrespondenceStatus",
    "LandmarkCorrespondenceRecord",
    "LandmarkCorrespondenceRequest",
    "LandmarkCorrespondenceResult",
    "compute_landmark_correspondence",
]
