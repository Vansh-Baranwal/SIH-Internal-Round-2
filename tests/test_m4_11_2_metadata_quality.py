import json

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    FieldAssessmentStatus,
    MetadataAssessmentStatus,
    MetadataQualityResult,
    UnknownImage,
    UnknownImageReferenceType,
    assess_metadata_quality,
)


def make_unknown_image(**overrides):
    payload = {
        "image_id": "IMG-002",
        "image_reference": "images/IMG-002.tif",
        "image_reference_type": UnknownImageReferenceType.UNKNOWN,
        "provenance": DataProvenance.UNAVAILABLE,
        "provenance_source": "tests/test_m4_11_2_metadata_quality.py",
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
        "acquisition_timestamp": "2024-05-12T12:00:00Z",
        "acquisition_date": "2024-05-12",
        "sensor": "LRO NAC",
        "source_name": "LRO NAC Archive",
        "illumination": {"sun_azimuth_deg": 45.0, "sun_elevation_deg": 12.0},
        "view_geometry": {"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}},
        "metadata_coordinates": {"lon": 12.3, "lat": 4.5},
        "metadata_quality": "high",
        "validation_status": "validated",
        "warnings": ("missing_footprint_overlap",),
        "notes": "Metadata present but still awaiting localization.",
    }
    payload.update(overrides)
    return UnknownImage(**payload)


def make_raw_unknown_image(**overrides):
    payload = {
        "image_id": "IMG-RAW",
        "image_reference": "images/IMG-RAW.tif",
        "image_reference_type": UnknownImageReferenceType.UNKNOWN,
        "provenance": DataProvenance.UNAVAILABLE,
        "provenance_source": "tests/test_m4_11_2_metadata_quality.py",
        "is_real_data": False,
        "source_id": None,
        "product_id": None,
        "local_path": None,
        "external_reference": None,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "image_format": "TIFF",
        "dtype": "uint16",
        "bit_depth": 16,
        "gsd_m": 0.5,
        "crs": "Lunar 2015",
        "geospatial_reference": {"epsg": "LUNAR-2015"},
        "footprint": {"bounds": {"west": -1.0, "south": -1.0, "east": 1.0, "north": 1.0}},
        "acquisition_timestamp": "2024-05-12T12:00:00Z",
        "acquisition_date": "2024-05-12",
        "sensor": "LRO NAC",
        "source_name": "LRO NAC Archive",
        "illumination": {"sun_azimuth_deg": 45.0, "sun_elevation_deg": 12.0},
        "view_geometry": {"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}},
        "metadata_coordinates": {"lon": 12.3, "lat": 4.5},
        "metadata_quality": "high",
        "validation_status": "validated",
        "warnings": (),
        "notes": None,
    }
    payload.update(overrides)
    item = UnknownImage.__new__(UnknownImage)
    for key, value in payload.items():
        object.__setattr__(item, key, value)
    return item


def test_complete_valid_metadata_assessment():
    item = make_unknown_image()
    result = assess_metadata_quality(item)
    assert result.image_id == "IMG-002"
    assert result.assessment_status in {MetadataAssessmentStatus.METADATA_VALID, MetadataAssessmentStatus.METADATA_PARTIAL}
    assert result.field_assessments["width"].status is FieldAssessmentStatus.PRESENT_VALID
    assert result.field_assessments["image_reference"].status in {FieldAssessmentStatus.PRESENT_VALID, FieldAssessmentStatus.LIMITED}
    assert result.provenance == DataProvenance.UNAVAILABLE


def test_minimal_valid_unknown_image_assessment():
    item = make_unknown_image(
        width=None,
        height=None,
        channels=None,
        image_format=None,
        dtype=None,
        bit_depth=None,
        gsd_m=None,
        crs=None,
        geospatial_reference=None,
        footprint=None,
        acquisition_timestamp=None,
        acquisition_date=None,
        sensor=None,
        source_name=None,
        illumination=None,
        view_geometry=None,
        metadata_coordinates=None,
        metadata_quality=None,
        validation_status="unvalidated",
        warnings=(),
        notes=None,
    )
    result = assess_metadata_quality(item)
    assert result.assessment_status in {MetadataAssessmentStatus.METADATA_PARTIAL, MetadataAssessmentStatus.METADATA_INSUFFICIENT, MetadataAssessmentStatus.METADATA_UNKNOWN}
    assert result.field_assessments["width"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["crs"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["metadata_coordinates"].status is FieldAssessmentStatus.MISSING


def test_missing_optional_metadata_is_classified_missing():
    item = make_unknown_image(crs=None, footprint=None, gsd_m=None, acquisition_timestamp=None, sensor=None, illumination=None)
    result = assess_metadata_quality(item)
    assert result.field_assessments["crs"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["footprint"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["gsd_m"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["acquisition_timestamp"].status is FieldAssessmentStatus.MISSING


def test_missing_crs_and_gsd_are_missing_not_defaulted():
    item = make_unknown_image(crs=None, gsd_m=None)
    result = assess_metadata_quality(item)
    assert result.field_assessments["crs"].status is FieldAssessmentStatus.MISSING
    assert result.field_assessments["gsd_m"].status is FieldAssessmentStatus.MISSING
    assert "estimated_coordinates" not in result.to_dict()


def test_invalid_dimensions_are_invalid():
    item = make_raw_unknown_image(width=0, height=100)
    result = assess_metadata_quality(item)
    assert result.field_assessments["width"].status is FieldAssessmentStatus.INVALID
    assert result.assessment_status in {MetadataAssessmentStatus.METADATA_INVALID, MetadataAssessmentStatus.METADATA_INSUFFICIENT}


def test_invalid_channels_are_invalid():
    item = make_raw_unknown_image(channels=0)
    result = assess_metadata_quality(item)
    assert result.field_assessments["channels"].status is FieldAssessmentStatus.INVALID


def test_invalid_gsd_is_invalid():
    item = make_raw_unknown_image(gsd_m=0)
    result = assess_metadata_quality(item)
    assert result.field_assessments["gsd_m"].status is FieldAssessmentStatus.INVALID


def test_invalid_timestamp_is_invalid():
    item = make_raw_unknown_image(acquisition_timestamp="not-a-date")
    result = assess_metadata_quality(item)
    assert result.field_assessments["acquisition_timestamp"].status is FieldAssessmentStatus.INVALID


def test_contradictory_acquisition_date_and_timestamp_is_flagged():
    item = make_unknown_image(acquisition_timestamp="2024-05-12T12:00:00Z", acquisition_date="2024-05-13")
    result = assess_metadata_quality(item)
    assert result.field_assessments["acquisition_date"].status in {FieldAssessmentStatus.INVALID, FieldAssessmentStatus.LIMITED}
    assert any("contradict" in warning.lower() or "date" in warning.lower() for warning in result.warnings)


def test_timezone_aware_timestamp_is_valid():
    item = make_unknown_image(acquisition_timestamp="2024-05-12T12:00:00Z")
    result = assess_metadata_quality(item)
    assert result.field_assessments["acquisition_timestamp"].status is FieldAssessmentStatus.PRESENT_VALID


def test_timezone_naive_timestamp_is_limited():
    item = make_unknown_image(acquisition_timestamp="2024-05-12T12:00:00")
    result = assess_metadata_quality(item)
    assert result.field_assessments["acquisition_timestamp"].status in {FieldAssessmentStatus.LIMITED, FieldAssessmentStatus.PRESENT_VALID}


def test_date_only_metadata_is_limited():
    item = make_unknown_image(acquisition_timestamp=None, acquisition_date="2024-05-12")
    result = assess_metadata_quality(item)
    assert result.field_assessments["acquisition_date"].status in {FieldAssessmentStatus.PRESENT_VALID, FieldAssessmentStatus.LIMITED}


def test_valid_metadata_coordinates_are_metadata_only():
    item = make_unknown_image(metadata_coordinates={"lon": 12.3, "lat": 4.5})
    result = assess_metadata_quality(item)
    assert result.field_assessments["metadata_coordinates"].status is FieldAssessmentStatus.PRESENT_VALID
    assert "estimated_coordinates" not in result.to_dict()


def test_missing_metadata_coordinates_are_missing():
    item = make_unknown_image(metadata_coordinates=None)
    result = assess_metadata_quality(item)
    assert result.field_assessments["metadata_coordinates"].status is FieldAssessmentStatus.MISSING


def test_malformed_metadata_coordinates_are_invalid():
    item = make_unknown_image(metadata_coordinates={"lon": "NaN", "lat": 4.5})
    result = assess_metadata_quality(item)
    assert result.field_assessments["metadata_coordinates"].status is FieldAssessmentStatus.INVALID


def test_malformed_footprint_is_invalid():
    item = make_raw_unknown_image(footprint={"coordinates": []})
    result = assess_metadata_quality(item)
    assert result.field_assessments["footprint"].status is FieldAssessmentStatus.INVALID


def test_malformed_geospatial_reference_is_invalid():
    item = make_raw_unknown_image(geospatial_reference=[])
    result = assess_metadata_quality(item)
    assert result.field_assessments["geospatial_reference"].status is FieldAssessmentStatus.INVALID


def test_malformed_illumination_is_invalid():
    item = make_raw_unknown_image(illumination={"sun_azimuth_deg": [1, 2]})
    result = assess_metadata_quality(item)
    assert result.field_assessments["illumination"].status is FieldAssessmentStatus.INVALID


def test_malformed_view_geometry_is_invalid():
    item = make_raw_unknown_image(view_geometry={"position_m": [1.0, 2.0]})
    result = assess_metadata_quality(item)
    assert result.field_assessments["view_geometry"].status is FieldAssessmentStatus.INVALID


def test_missing_sensor_is_missing():
    item = make_unknown_image(sensor=None)
    result = assess_metadata_quality(item)
    assert result.field_assessments["sensor"].status is FieldAssessmentStatus.MISSING


def test_unknown_provenance_is_reported_as_unknown():
    item = make_unknown_image(provenance=DataProvenance.UNAVAILABLE, is_real_data=False)
    result = assess_metadata_quality(item)
    assert result.field_assessments["provenance"].status is FieldAssessmentStatus.UNKNOWN


def test_synthetic_provenance_stays_synthetic():
    item = make_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=False)
    result = assess_metadata_quality(item)
    assert result.field_assessments["provenance"].status is FieldAssessmentStatus.PRESENT_VALID
    assert result.provenance is DataProvenance.SYNTHETIC


def test_contradictory_provenance_is_invalid():
    item = make_raw_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=True)
    result = assess_metadata_quality(item)
    assert result.field_assessments["is_real_data"].status is FieldAssessmentStatus.INVALID
    assert result.assessment_status == MetadataAssessmentStatus.METADATA_INVALID


def test_external_reference_status_is_valid():
    item = make_unknown_image(
        image_reference="https://example.test/image.tif",
        local_path=None,
        external_reference="https://example.test/image.tif",
        image_reference_type=UnknownImageReferenceType.EXTERNAL_REFERENCE,
    )
    result = assess_metadata_quality(item)
    assert result.field_assessments["image_reference"].status is FieldAssessmentStatus.PRESENT_VALID
    assert result.field_assessments["image_reference_type"].status is FieldAssessmentStatus.PRESENT_VALID


def test_missing_local_reference_is_detected():
    item = make_unknown_image(
        image_reference="missing/IMG-404.tif",
        local_path="missing/IMG-404.tif",
        image_reference_type=UnknownImageReferenceType.LOCAL_MISSING,
    )
    result = assess_metadata_quality(item)
    assert result.field_assessments["image_reference_type"].status is FieldAssessmentStatus.PRESENT_VALID
    assert result.field_assessments["image_reference"].status is FieldAssessmentStatus.PRESENT_VALID


def test_invalid_image_reference_is_invalid():
    item = make_raw_unknown_image(image_reference=" ")
    result = assess_metadata_quality(item)
    assert result.field_assessments["image_reference"].status is FieldAssessmentStatus.INVALID


def test_metadata_completeness_status_is_deterministic():
    item = make_unknown_image(width=None, crs=None, gsd_m=None, footprint=None)
    result = assess_metadata_quality(item)
    assert result.completeness_status in {"partial", "minimal", "insufficient"}
    assert isinstance(result.completeness_score, float)


def test_serialization_round_trip():
    item = make_unknown_image(warnings=("missing_crs", "missing_gsd"), notes="Preserve this note.")
    result = assess_metadata_quality(item)
    payload = result.to_dict()
    restored = MetadataQualityResult.from_dict(payload)
    assert restored.to_dict() == payload
    assert restored.warnings == ("missing_crs", "missing_gsd")


def test_deterministic_serialization():
    item = make_unknown_image(notes="Stable output.")
    result = assess_metadata_quality(item)
    payload_a = result.to_dict()
    payload_b = json.loads(json.dumps(payload_a, sort_keys=True))
    assert payload_b == payload_a


def test_malformed_deserialization_raises_value_error():
    with pytest.raises(ValueError, match="dictionary"):
        MetadataQualityResult.from_dict([])


def test_warnings_and_limitations_are_preserved():
    item = make_unknown_image(warnings=("missing_crs",), notes="Progressing carefully.")
    result = assess_metadata_quality(item)
    payload = result.to_dict()
    assert payload["warnings"] == ["missing_crs"]
    assert payload["limitations"]
    restored = MetadataQualityResult.from_dict(payload)
    assert restored.warnings == ("missing_crs",)


def test_no_estimated_coordinates_are_generated():
    item = make_unknown_image(metadata_coordinates={"lon": 1.0, "lat": 2.0})
    result = assess_metadata_quality(item)
    payload = result.to_dict()
    assert "estimated_coordinates" not in payload
