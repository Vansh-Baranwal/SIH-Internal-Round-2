import cv2
import numpy as np
import pytest

from lunar_hazard_mapper.m4_terrain import DataProvenance, UnknownImage, UnknownImageReferenceType
from lunar_hazard_mapper.m4_terrain.anchor_selection import (
    AnchorSelectionConfig,
    AnchorSelectionStatus,
    select_anchors,
)
from lunar_hazard_mapper.m4_terrain.landmark_correspondence import (
    LandmarkCorrespondenceRequest,
    compute_landmark_correspondence,
)
from lunar_hazard_mapper.m4_terrain.landmark_retrieval import (
    LandmarkRetrievalRequest,
    retrieve_landmarks,
)
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterLandmark,
    CraterLandmarkDatabase,
    CraterLandmarkNetwork,
    DEMProfile,
    LandmarkQuality,
)


@pytest.fixture
def synthetic_image_file(tmp_path):
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.circle(arr, (80, 80), 25, (200, 200, 200), -1)
    cv2.circle(arr, (150, 150), 35, (180, 180, 180), -1)
    cv2.circle(arr, (120, 180), 20, (220, 220, 220), -1)
    path = tmp_path / "anchor_test.tif"
    cv2.imwrite(str(path), arr)
    return path


@pytest.fixture
def reference_image_file(tmp_path):
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.circle(arr, (82, 82), 25, (200, 200, 200), -1)
    cv2.circle(arr, (152, 152), 35, (180, 180, 180), -1)
    cv2.circle(arr, (120, 178), 20, (220, 220, 220), -1)
    path = tmp_path / "ref_anchor_test.tif"
    cv2.imwrite(str(path), arr)
    return path


@pytest.fixture
def synthetic_unknown_image(synthetic_image_file):
    return {
        "image_id": "IMG-11-5-01",
        "image_reference": "images/IMG-11-5-01.tif",
        "image_reference_type": UnknownImageReferenceType.LOCAL_AVAILABLE,
        "provenance": DataProvenance.REAL,
        "provenance_source": "tests/test_m4_11_5_anchor_selection.py",
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
        "notes": "Synthetic fixture for Phase 11.5 anchor selection testing.",
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


def _make_correspondence_result(unknown, feature_map, *, min_matches=1):
    retrieval = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("A-001"), _make_landmark("A-002")])),
    ))
    request = LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=retrieval,
        reference_features=feature_map,
        min_matches=min_matches,
    )
    return compute_landmark_correspondence(request)


def test_select_single_anchor_from_eligible_candidate(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    result = _make_correspondence_result(unknown, {"A-001": _make_feature_set(str(reference_image_file)), "A-002": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[1.0, 2.0, 3.0]], "descriptor_dim": 3, "feature_count": 1}}, min_matches=1)
    anchor_result = select_anchors(result)
    assert anchor_result.status in {AnchorSelectionStatus.SINGLE_ANCHOR_SELECTED, AnchorSelectionStatus.SUCCESS}
    assert anchor_result.selected_anchor_ids == ["A-001"]
    assert not anchor_result.claims_localization
    assert not anchor_result.claims_geometric_verification


def test_select_multiple_anchors_when_configured(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    result = _make_correspondence_result(unknown, {"A-001": _make_feature_set(str(reference_image_file)), "A-002": _make_feature_set(str(reference_image_file))}, min_matches=1)
    anchor_result = select_anchors(result, config=AnchorSelectionConfig(max_anchors=2, min_surviving_matches=1))
    assert anchor_result.status in {AnchorSelectionStatus.MULTIPLE_ANCHORS_SELECTED, AnchorSelectionStatus.SUCCESS}
    assert set(anchor_result.selected_anchor_ids).issubset({"A-001", "A-002"})


def test_no_eligible_anchor_when_zero_matches(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    retrieval = retrieve_landmarks(LandmarkRetrievalRequest(
        image=unknown,
        landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("B-001")])),
    ))
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=retrieval,
        reference_features={"B-001": {"feature_type": "sift", "keypoints": [(0.0, 0.0)], "descriptors": [[float(i) for i in range(128)]], "descriptor_dim": 128, "feature_count": 1}},
        min_matches=2,
    ))
    anchor_result = select_anchors(result)
    assert anchor_result.status in {AnchorSelectionStatus.NO_ELIGIBLE_ANCHORS, AnchorSelectionStatus.NO_CORRESPONDENCE}
    assert anchor_result.selected_anchor_ids == []


def test_invalid_input_is_rejected():
    with pytest.raises(TypeError):
        select_anchors(object())


def test_provenance_is_preserved(synthetic_unknown_image):
    unknown = UnknownImage(**synthetic_unknown_image)
    result = compute_landmark_correspondence(LandmarkCorrespondenceRequest(
        image=unknown,
        retrieval_result=retrieve_landmarks(LandmarkRetrievalRequest(
            image=unknown,
            landmark_source=CraterLandmarkDatabase(network=CraterLandmarkNetwork([_make_landmark("C-001", synthetic=True)])),
        )),
        reference_features={"C-001": {"feature_type": "sift", "keypoints": [(0.0, 0.0), (1.0, 1.0)], "descriptors": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "descriptor_dim": 3, "feature_count": 2}},
        min_matches=1,
    ))
    anchor = select_anchors(result)
    assert anchor.provenance["unknown_image_provenance"] == DataProvenance.REAL
    assert anchor.provenance["candidate_provenance"] == DataProvenance.SYNTHETIC


def test_deterministic_ordering_and_repeatability(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    result = _make_correspondence_result(unknown, {"A-001": _make_feature_set(str(reference_image_file)), "A-002": _make_feature_set(str(reference_image_file))}, min_matches=1)
    first = select_anchors(result)
    second = select_anchors(result)
    assert first.selected_anchor_ids == second.selected_anchor_ids
    assert first.ranking == second.ranking


def test_no_coordinate_estimation_or_geometric_verification_in_output(synthetic_unknown_image, reference_image_file):
    unknown = UnknownImage(**synthetic_unknown_image)
    result = _make_correspondence_result(unknown, {"A-001": _make_feature_set(str(reference_image_file))}, min_matches=1)
    anchor_result = select_anchors(result)
    payload = anchor_result.to_dict()
    assert "estimated_coordinates" not in payload
    assert not anchor_result.claims_geometric_verification
    assert not anchor_result.claims_localization
    assert not anchor_result.claims_localization_confidence
