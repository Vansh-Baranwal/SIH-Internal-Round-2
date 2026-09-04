import os
import tempfile

import cv2
import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain import DataProvenance, UnknownImage, UnknownImageReferenceType
from lunar_hazard_mapper.m4_terrain.landmark_correspondence import (
    CorrespondenceStatus,
    LandmarkCorrespondenceRecord,
    LandmarkCorrespondenceRequest,
    LandmarkCorrespondenceResult,
    compute_landmark_correspondence,
)
from lunar_hazard_mapper.m4_terrain.landmark_retrieval import (
    LandmarkCandidate,
    LandmarkRetrievalRequest,
    LandmarkRetrievalResult,
    RetrievalStatus,
    retrieve_landmarks,
)
from lunar_hazard_mapper.scientific.crater_landmarks import CraterLandmark, CraterLandmarkDatabase, CraterLandmarkNetwork, DEMProfile, LandmarkQuality


@pytest.fixture
def synthetic_image_file(tmp_path):
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.circle(arr, (80, 80), 25, (200, 200, 200), -1)
    cv2.circle(arr, (150, 150), 35, (180, 180, 180), -1)
    cv2.circle(arr, (120, 180), 20, (220, 220, 220), -1)
    path = tmp_path / "corr_test.tif"
    cv2.imwrite(str(path), arr)
    return path


@pytest.fixture
def reference_image_file(tmp_path):
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.circle(arr, (82, 82), 25, (200, 200, 200), -1)
    cv2.circle(arr, (152, 152), 35, (180, 180, 180), -1)
    cv2.circle(arr, (120, 178), 20, (220, 220, 220), -1)
    path = tmp_path / "ref_corr_test.tif"
    cv2.imwrite(str(path), arr)
    return path


@pytest.fixture
def synthetic_unknown_image(synthetic_image_file):
    return {
        "image_id": "IMG-11-4-01",
        "image_reference": "images/IMG-11-4-01.tif",
        "image_reference_type": UnknownImageReferenceType.LOCAL_AVAILABLE,
        "provenance": DataProvenance.REAL,
        "provenance_source": "tests/test_m4_11_4_landmark_correspondence.py",
        "is_real_data": True,
        "local_path": str(synthetic_image_file),
        "width": 256,
        "height": 256,
        "channels": 3,
        "image_format": "TIFF",
        "dtype": "uint8",
        "bit_depth": 8,
        "gsd_m": 0.5,
        "crs": "Lunar 2015",
        "geospatial_reference": {"epsg": "LUNAR-2015"},
        "footprint": {"bounds": {"west": -1.0, "south": -1.0, "east": 1.0, "north": 1.0}},
        "acquisition_timestamp": "2024-06-10T10:00:00Z",
        "acquisition_date": "2024-06-10",
        "sensor": "LRO NAC",
        "source_name": "Test archive",
        "illumination": {"sun_azimuth_deg": 45.0, "sun_elevation_deg": 12.0},
        "view_geometry": {"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}},
        "metadata_coordinates": {"lon": 12.3, "lat": 4.5},
        "metadata_quality": "high",
        "validation_status": "validated",
        "warnings": (),
        "notes": "Synthetic fixture for Phase 11.4 correspondence testing.",
    }


def _make_landmark(crater_id: str, *, quality_score: float = 0.9, synthetic: bool = False, lat: float = 12.0, lon: float = 34.0):
    quality = LandmarkQuality(
        detection_score=quality_score,
        geometry_score=quality_score,
        profile_score=quality_score,
        overall_score=quality_score,
        classification="HIGH" if quality_score >= 0.8 else "MEDIUM",
    )
    return CraterLandmark(
        crater_id=crater_id,
        latitude_deg=lat,
        longitude_deg=lon,
        diameter_m=50.0,
        dem_profile=DEMProfile(distances_m=[0.0, 10.0], elevations_m=[-5.0, 0.0]),
        quality=quality,
        source_type="synthetic" if synthetic else "real",
        label="synthetic" if synthetic else "real",
        metadata={
            "reference_image_id": f"ref-{crater_id}",
            "reference_image_reference": f"refs/{crater_id}.tif",
            "source": "test_landmark_source",
            "sensor": "LRO NAC",
            "gsd_m": 0.5,
            "landmark_type": "crater",
        },
    )


def _make_feature_set(image_path: str, *, detector: str = "sift"):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read image for feature extraction: {image_path}")
    detector_impl = cv2.SIFT_create() if detector == "sift" else cv2.AKAZE_create()
    keypoints, descriptors = detector_impl.detectAndCompute(image, None)
    assert descriptors is not None
    return {
        "feature_type": detector,
        "keypoints": [(kp.pt[0], kp.pt[1]) for kp in keypoints],
        "descriptors": descriptors.tolist(),
        "descriptor_dim": descriptors.shape[1],
        "feature_count": len(keypoints),
    }


def test_valid_unknown_image_with_valid_retrieved_landmark_features(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-101")])),
    ))
    feature_set = _make_feature_set(str(reference_image_file))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-101": feature_set},
        ratio_threshold=0.75,
        min_matches=3,
    )
    result = compute_landmark_correspondence(request)
    assert result.status is CorrespondenceStatus.SUCCESS
    assert result.records[0].candidate_id == "C-101"
    assert result.records[0].surviving_match_count >= 1


def test_successful_tentative_correspondence(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-102")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-102": _make_feature_set(str(reference_image_file))},
        ratio_threshold=0.75,
        min_matches=1,
    )
    result = compute_landmark_correspondence(request)
    assert result.status is CorrespondenceStatus.SUCCESS
    assert result.records[0].tentative_match_count >= 1
    assert result.records[0].geometric_verification_performed is False


def test_zero_matches_are_reported_no_correspondences(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-103")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-103": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[float(i) for i in range(128)]], "descriptor_dim": 128, "feature_count": 1}},
        ratio_threshold=0.75,
        min_matches=2,
    )
    result = compute_landmark_correspondence(request)
    assert result.status in {CorrespondenceStatus.NO_CORRESPONDENCES, CorrespondenceStatus.PARTIAL_CORRESPONDENCE}


def test_missing_unknown_image_local_input():
    req = LandmarkCorrespondenceRequest(
        image=UnknownImage(
            image_id="IMG-11-4-02",
            image_reference="https://example.com/image.tif",
            image_reference_type=UnknownImageReferenceType.EXTERNAL_REFERENCE,
            provenance=DataProvenance.REAL,
            provenance_source="tests/test_m4_11_4_landmark_correspondence.py",
            is_real_data=True,
            external_reference="https://example.com/image.tif",
            validation_status="validated",
        ),
        retrieval_result=LandmarkRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            request=LandmarkRetrievalRequest(
                image=UnknownImage(
                    image_id="IMG-11-4-02",
                    image_reference="https://example.com/image.tif",
                    image_reference_type=UnknownImageReferenceType.EXTERNAL_REFERENCE,
                    provenance=DataProvenance.REAL,
                    provenance_source="tests/test_m4_11_4_landmark_correspondence.py",
                    is_real_data=True,
                    external_reference="https://example.com/image.tif",
                    validation_status="validated",
                )
            ),
            query=None,
            candidates=(LandmarkCandidate(landmark_id="C-104", source_id="src-1", source_database="db", reference_image_id="ref-104", reference_image_reference="refs/C-104.tif", latitude_deg=12.0, longitude_deg=34.0, crs="Lunar 2015", sensor="LRO NAC", gsd_m=0.5, landmark_type="crater", provenance=DataProvenance.REAL, retrieval_reason="retrieved", retrieval_rank=1),),
        ),
        reference_features={"C-104": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[1.0, 2.0]], "descriptor_dim": 2, "feature_count": 1}},
    )
    result = compute_landmark_correspondence(req)
    assert result.status is CorrespondenceStatus.IMAGE_UNAVAILABLE


def test_missing_reference_features(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-105")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={},
    )
    result = compute_landmark_correspondence(request)
    assert result.status is CorrespondenceStatus.REFERENCE_FEATURES_UNAVAILABLE


def test_incompatible_descriptor_dimensions(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-106")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-106": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[1.0, 2.0]], "descriptor_dim": 2, "feature_count": 1}},
    )
    result = compute_landmark_correspondence(request)
    assert result.status is CorrespondenceStatus.INCOMPATIBLE_FEATURES


def test_invalid_input():
    with pytest.raises(TypeError):
        compute_landmark_correspondence(object())


def test_multiple_retrieved_candidates(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-201"), _make_landmark("C-202")])),
    ))
    feature_map = {"C-201": _make_feature_set(str(reference_image_file)), "C-202": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[1.0, 2.0]], "descriptor_dim": 2, "feature_count": 1}}
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features=feature_map,
        min_matches=1,
    ))
    assert [record.candidate_id for record in result.records] == ["C-201", "C-202"]


def test_retrieved_candidate_without_correspondence(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-203")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-203": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[float(i) for i in range(128)]], "descriptor_dim": 128, "feature_count": 1}},
        min_matches=2,
    )
    result = compute_landmark_correspondence(request)
    assert result.records[0].status in {CorrespondenceStatus.NO_CORRESPONDENCES, CorrespondenceStatus.PARTIAL_CORRESPONDENCE}


def test_deterministic_ordering_and_repeatability(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-301"), _make_landmark("C-302")])),
    ))
    features = {"C-301": _make_feature_set(str(reference_image_file)), "C-302": _make_feature_set(str(reference_image_file))}
    result1 = compute_landmark_correspondence(LandmarkCorrespondenceRequest(image=unknown, retrieval_result=query, reference_features=features))
    result2 = compute_landmark_correspondence(LandmarkCorrespondenceRequest(image=unknown, retrieval_result=query, reference_features=features))
    assert [r.candidate_id for r in result1.records] == [r.candidate_id for r in result2.records]


def test_provenance_is_preserved(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-303", synthetic=True)])),
    ))
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(image=unknown, retrieval_result=query, reference_features={"C-303": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[1.0, 2.0, 3.0]], "descriptor_dim": 3, "feature_count": 1}}, min_matches=1))
    assert result.provenance["unknown_image_provenance"] == DataProvenance.REAL
    assert result.provenance["candidate_provenance"] == DataProvenance.SYNTHETIC


def test_synthetic_fixture_remains_synthetic(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-304", synthetic=True)])),
    ))
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-304": {"feature_type": "sift", "keypoints": [(0.0, 0.0), (1.0, 1.0)], "descriptors": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "descriptor_dim": 3, "feature_count": 2}},
        min_matches=1,
    ))
    assert result.provenance["candidate_provenance"] is DataProvenance.SYNTHETIC


def test_no_coordinate_estimation_is_produced(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-305")])),
    ))
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-305": _make_feature_set(str(reference_image_file))},
        min_matches=1,
    ))
    payload = result.to_dict()
    assert "estimated_coordinates" not in payload
    assert not result.claims_localization


def test_threshold_configuration_changes_match_selection(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-306")])),
    ))
    low = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-306": _make_feature_set(str(reference_image_file))},
        ratio_threshold=0.95,
        min_matches=10,
    ))
    high = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-306": _make_feature_set(str(reference_image_file))},
        ratio_threshold=0.60,
        min_matches=1,
    ))
    assert low.records[0].surviving_match_count >= high.records[0].surviving_match_count


def test_malformed_feature_data_rejected(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    query = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-307")])),
    ))
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=query,
        reference_features={"C-307": {"feature_type": "sift", "keypoints": "bad", "descriptors": [[1.0, 2.0]], "descriptor_dim": 2, "feature_count": 1}},
    ))
    assert result.records[0].status is CorrespondenceStatus.INVALID_INPUT
