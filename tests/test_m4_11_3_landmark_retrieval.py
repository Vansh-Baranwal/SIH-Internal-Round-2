import json

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    UnknownImage,
    UnknownImageReferenceType,
)
from lunar_hazard_mapper.m4_terrain.landmark_retrieval import (
    LandmarkCandidate,
    LandmarkRetrievalRequest,
    LandmarkRetrievalResult,
    RetrievalStatus,
    retrieve_landmarks,
)
from lunar_hazard_mapper.scientific.crater_landmarks import (
    CraterLandmark,
    CraterLandmarkDatabase,
    CraterLandmarkNetwork,
    DEMProfile,
    LandmarkQuality,
)


def make_unknown_image(**overrides):
    payload = {
        "image_id": "IMG-003",
        "image_reference": "images/IMG-003.tif",
        "image_reference_type": UnknownImageReferenceType.UNKNOWN,
        "provenance": DataProvenance.UNAVAILABLE,
        "provenance_source": "tests/test_m4_11_3_landmark_retrieval.py",
        "is_real_data": False,
        "width": 2048,
        "height": 1024,
        "channels": 3,
        "image_format": "TIFF",
        "dtype": "uint16",
        "bit_depth": 16,
        "gsd_m": 0.5,
        "crs": "Lunar 2015",
        "geospatial_reference": {"epsg": "LUNAR-2015"},
        "footprint": {"bounds": {"west": -1.0, "south": -1.0, "east": 1.0, "north": 1.0}},
        "acquisition_timestamp": "2024-06-10T10:00:00Z",
        "acquisition_date": "2024-06-10",
        "sensor": "LRO NAC",
        "source_name": "LRO NAC Archive",
        "illumination": {"sun_azimuth_deg": 45.0, "sun_elevation_deg": 12.0},
        "view_geometry": {"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}},
        "metadata_coordinates": {"lon": 12.3, "lat": 4.5},
        "metadata_quality": "high",
        "validation_status": "validated",
        "warnings": ("metadata_only_coordinates",),
        "notes": "Unknown image waiting for landmark retrieval.",
    }
    payload.update(overrides)
    return UnknownImage(**payload)


def make_landmark(crater_id: str, *, quality_score: float = 0.9, synthetic: bool = False, lat: float = 12.0, lon: float = 34.0):
    quality = LandmarkQuality(
        detection_score=quality_score,
        geometry_score=quality_score,
        profile_score=quality_score,
        overall_score=quality_score,
        classification="HIGH" if quality_score >= 0.8 else "MEDIUM",
    )
    landmark = CraterLandmark(
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
    return landmark


def make_database(*landmarks):
    return CraterLandmarkDatabase(network=CraterLandmarkNetwork(list(landmarks)))


def test_valid_unknown_image_with_available_landmark_source():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("A-001"), make_landmark("A-002")),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert len(result.candidates) == 2
    assert all(c.landmark_id in {"A-001", "A-002"} for c in result.candidates)


def test_valid_retrieval_produces_multiple_candidates():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("B-001"), make_landmark("B-002")),
        max_candidates=10,
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert result.total_candidates == 2
    assert result.candidates[0].landmark_id == "B-001"


def test_zero_candidates_are_reported_empty_result():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("C-001", quality_score=0.2)),
        min_quality_score=0.8,
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.EMPTY_RESULT
    assert result.candidates == []


def test_no_legitimate_retrieval_context_is_explicit():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(sensor=None, gsd_m=None, crs=None),
        landmark_source=make_database(make_landmark("D-001")),
        require_context=True,
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.NO_RETRIEVAL_CONTEXT


def test_unavailable_landmark_source():
    result = retrieve_landmarks(LandmarkRetrievalRequest(image=make_unknown_image(), landmark_source=None))
    assert result.status is RetrievalStatus.LANDMARK_SOURCE_UNAVAILABLE
    assert result.candidates == []


def test_invalid_landmark_source():
    result = retrieve_landmarks(LandmarkRetrievalRequest(image=make_unknown_image(), landmark_source=object()))
    assert result.status is RetrievalStatus.INVALID_LANDMARK_SOURCE


def test_synthetic_landmark_provenance_is_preserved():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("S-001", synthetic=True)),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert result.candidates[0].provenance is DataProvenance.SYNTHETIC
    assert result.candidates[0].is_synthetic is True


def test_unknown_landmark_provenance_defaults_to_unknown():
    landmark = make_landmark("U-001")
    landmark.source_type = "custom"
    request = LandmarkRetrievalRequest(image=make_unknown_image(), landmark_source=make_database(landmark))
    result = retrieve_landmarks(request)
    assert result.candidates[0].provenance is DataProvenance.UNAVAILABLE


def test_synthetic_unknown_image_remains_identified():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=False),
        landmark_source=make_database(make_landmark("X-001")),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert result.is_synthetic is True


def test_provenance_mismatch_is_warned():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(provenance=DataProvenance.REAL, is_real_data=True),
        landmark_source=make_database(make_landmark("M-001", synthetic=True)),
    )
    result = retrieve_landmarks(request)
    assert any("provenance" in warning.lower() for warning in result.warnings)


def test_missing_optional_unknown_image_metadata_is_allowed():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(width=None, height=None, sensor=None, gsd_m=None, crs=None, metadata_coordinates=None),
        landmark_source=make_database(make_landmark("N-001")),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS


def test_metadata_coordinates_are_not_treated_as_estimated_coordinates():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(metadata_coordinates={"lon": 12.3, "lat": 4.5}),
        landmark_source=make_database(make_landmark("P-001")),
    )
    result = retrieve_landmarks(request)
    payload = result.to_dict()
    assert "estimated_coordinates" not in payload
    assert result.query.metadata_coordinates == {"lon": 12.3, "lat": 4.5}


def test_no_filename_or_directory_inference_is_used():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(image_reference="images/abc_dir/IMG-420.tif"),
        landmark_source=make_database(make_landmark("Q-001")),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert result.query.image_reference == "images/abc_dir/IMG-420.tif"


def test_deterministic_candidate_ordering():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("Z-002"), make_landmark("Z-001")),
    )
    result = retrieve_landmarks(request)
    ids = [candidate.landmark_id for candidate in result.candidates]
    assert ids == ["Z-001", "Z-002"]


def test_invalid_landmark_coordinates_are_rejected():
    with pytest.raises(ValueError):
        make_landmark("BAD", lat=91.0, lon=200.0)


def test_retrieval_result_does_not_claim_correspondence_or_localization():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("R-001")),
    )
    result = retrieve_landmarks(request)
    assert result.status is RetrievalStatus.SUCCESS
    assert not result.claims_correspondence
    assert not result.claims_localization
    assert "estimated_coordinates" not in result.to_dict()


def test_serialization_round_trip():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("T-001"), make_landmark("T-002")),
    )
    result = retrieve_landmarks(request)
    payload = result.to_dict()
    restored = LandmarkRetrievalResult.from_dict(payload)
    assert restored.to_dict() == payload
    assert restored.candidates[0].landmark_id == "T-001"


def test_deterministic_serialization():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("V-001")),
    )
    result = retrieve_landmarks(request)
    payload_a = result.to_dict()
    payload_b = json.loads(json.dumps(payload_a, sort_keys=True))
    assert payload_b == payload_a


def test_malformed_deserialization_raises_value_error():
    with pytest.raises(ValueError, match="dictionary"):
        LandmarkRetrievalResult.from_dict([])


def test_provenance_preserved_through_serialization():
    request = LandmarkRetrievalRequest(
        image=make_unknown_image(),
        landmark_source=make_database(make_landmark("W-001", synthetic=True)),
    )
    result = retrieve_landmarks(request)
    payload = result.to_dict()
    assert payload["candidates"][0]["provenance"] == "synthetic"
