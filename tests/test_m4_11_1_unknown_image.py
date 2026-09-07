import json

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    UnknownImage,
    UnknownImageContractError,
    UnknownImageReferenceType,
)


def make_unknown_image(**overrides):
    payload = {
        "image_id": "IMG-001",
        "image_reference": "images/IMG-001.tif",
        "image_reference_type": UnknownImageReferenceType.UNKNOWN,
        "provenance": DataProvenance.UNAVAILABLE,
        "provenance_source": "tests/test_m4_11_1_unknown_image.py",
        "is_real_data": False,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "image_format": "TIFF",
        "metadata_quality": "partial",
        "validation_status": "unvalidated",
        "warnings": ("missing_gsd",),
        "notes": "Image is under review for GPS localization.",
    }
    payload.update(overrides)
    return UnknownImage(**payload)


def test_valid_unknown_image_with_required_fields_only():
    item = make_unknown_image(
        image_reference_type=UnknownImageReferenceType.UNAVAILABLE,
        width=None,
        height=None,
        channels=None,
        image_format=None,
        provenance=DataProvenance.UNAVAILABLE,
        is_real_data=False,
        metadata_quality=None,
        warnings=(),
        notes=None,
    )
    assert item.image_id == "IMG-001"
    assert item.provenance is DataProvenance.UNAVAILABLE
    assert item.image_reference_type is UnknownImageReferenceType.UNAVAILABLE
    assert item.width is None
    assert item.crs is None
    assert item.gsd_m is None


def test_valid_unknown_image_with_complete_metadata():
    item = make_unknown_image(
        source_id="source-7",
        product_id="product-9",
        local_path="/tmp/IMG-001.tif",
        external_reference="https://example.test/IMG-001.tif",
        provenance=DataProvenance.REAL,
        is_real_data=True,
        width=2048,
        height=1024,
        channels=1,
        image_format="NITF",
        dtype="uint16",
        bit_depth=16,
        gsd_m=0.5,
        crs="Lunar 2015",
        geospatial_reference={"epsg": "LUNAR-2015"},
        footprint={"bounds": {"west": -1.0, "south": -1.0, "east": 1.0, "north": 1.0}},
        acquisition_timestamp="2024-12-15T12:00:00Z",
        acquisition_date="2024-12-15",
        sensor="LRO NAC",
        illumination={"sun_azimuth_deg": 45.0, "sun_elevation_deg": 15.5},
        view_geometry={"position_m": {"x": 1.0, "y": 2.0, "z": 3.0}},
        metadata_quality="high",
        validation_status="validated",
        metadata_coordinates={"lon": 12.0, "lat": 3.0},
    )
    assert item.is_real_data is True
    assert item.provenance is DataProvenance.REAL
    assert item.gsd_m == 0.5
    assert item.metadata_coordinates == {"lon": 12.0, "lat": 3.0}


def test_missing_optional_metadata_is_allowed():
    item = make_unknown_image(crs=None, footprint=None, gsd_m=None, sensor=None, acquisition_timestamp=None, illumination=None, view_geometry=None)
    assert item.crs is None
    assert item.footprint is None
    assert item.gsd_m is None
    assert item.sensor is None


def test_missing_coordinates_are_allowed_and_not_fabricated():
    item = make_unknown_image(metadata_coordinates=None)
    assert item.metadata_coordinates is None
    assert not hasattr(item, "estimated_coordinates")


def test_missing_crs_is_allowed():
    item = make_unknown_image(crs=None)
    assert item.crs is None


def test_missing_gsd_is_allowed():
    item = make_unknown_image(gsd_m=None)
    assert item.gsd_m is None


def test_missing_footprint_is_allowed():
    item = make_unknown_image(footprint=None)
    assert item.footprint is None


def test_missing_acquisition_timestamp_is_allowed():
    item = make_unknown_image(acquisition_timestamp=None)
    assert item.acquisition_timestamp is None


def test_missing_sensor_metadata_is_allowed():
    item = make_unknown_image(sensor=None, source_name=None)
    assert item.sensor is None
    assert item.source_name is None


def test_genuine_real_data_provenance_is_supported():
    item = make_unknown_image(provenance=DataProvenance.REAL, is_real_data=True)
    assert item.provenance is DataProvenance.REAL
    assert item.is_real_data is True


def test_synthetic_test_provenance_is_preserved():
    item = make_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=False, notes="Synthetic fixture")
    assert item.provenance is DataProvenance.SYNTHETIC
    assert item.is_real_data is False


def test_unknown_provenance_defaults_to_unavailable():
    item = make_unknown_image(provenance=DataProvenance.UNAVAILABLE)
    assert item.provenance is DataProvenance.UNAVAILABLE


def test_valid_local_image_reference():
    local_path = "./tests/fixtures/does_not_exist.tif"
    item = make_unknown_image(
        image_reference=local_path,
        local_path=local_path,
        image_reference_type=UnknownImageReferenceType.LOCAL_AVAILABLE,
    )
    assert item.local_path == local_path
    assert item.image_reference_type is UnknownImageReferenceType.LOCAL_AVAILABLE


def test_external_image_reference_is_supported():
    item = make_unknown_image(
        image_reference="https://example.test/image.tif",
        external_reference="https://example.test/image.tif",
        image_reference_type=UnknownImageReferenceType.EXTERNAL_REFERENCE,
    )
    assert item.image_reference_type is UnknownImageReferenceType.EXTERNAL_REFERENCE
    assert item.external_reference == "https://example.test/image.tif"


def test_unavailable_image_reference_is_explicit():
    item = make_unknown_image(
        image_reference="missing/IMG-404.tif",
        local_path="missing/IMG-404.tif",
        image_reference_type=UnknownImageReferenceType.LOCAL_MISSING,
    )
    assert item.image_reference_type is UnknownImageReferenceType.LOCAL_MISSING


def test_invalid_image_reference_is_rejected():
    with pytest.raises(UnknownImageContractError, match="image_reference"):
        make_unknown_image(image_reference=" ")


def test_invalid_image_id_is_rejected():
    with pytest.raises(UnknownImageContractError, match="image_id"):
        make_unknown_image(image_id=" ")


def test_invalid_width_is_rejected():
    with pytest.raises(UnknownImageContractError, match="width"):
        make_unknown_image(width=-10)


def test_invalid_height_is_rejected():
    with pytest.raises(UnknownImageContractError, match="height"):
        make_unknown_image(height=0)


def test_zero_dimensions_are_rejected():
    with pytest.raises(UnknownImageContractError, match="width|height"):
        make_unknown_image(width=0, height=100)


def test_invalid_channel_count_is_rejected():
    with pytest.raises(UnknownImageContractError, match="channels"):
        make_unknown_image(channels=0)


def test_malformed_metadata_is_rejected():
    with pytest.raises(UnknownImageContractError, match="geospatial_reference"):
        make_unknown_image(geospatial_reference=[])


def test_serialization_round_trip():
    item = make_unknown_image(
        metadata_coordinates={"lon": 1.5, "lat": 2.5},
        warnings=("missing_gsd", "missing_crs"),
        notes="Keep this note.",
    )
    payload = item.to_dict()
    restored = UnknownImage.from_dict(payload)
    assert restored.to_dict() == payload
    assert restored.notes == "Keep this note."


def test_malformed_deserialization_raises_contract_error():
    with pytest.raises(UnknownImageContractError, match="dictionary"):
        UnknownImage.from_dict([])


def test_deterministic_serialization():
    item = make_unknown_image(notes="Stable output.", warnings=("warn_a", "warn_b"))
    payload_a = item.to_dict()
    payload_b = json.loads(json.dumps(payload_a, sort_keys=True))
    assert payload_b == payload_a
    assert list(payload_a.keys()) == list(item.__dict__.keys())


def test_metadata_coordinates_remain_metadata_only():
    item = make_unknown_image(metadata_coordinates={"lon": 1.0, "lat": 2.0})
    assert item.metadata_coordinates == {"lon": 1.0, "lat": 2.0}
    assert "estimated_coordinates" not in item.to_dict()


def test_no_estimated_coordinates_are_created_by_contract():
    item = make_unknown_image()
    assert "estimated_coordinates" not in item.to_dict()


def test_synthetic_test_image_cannot_silently_become_real_data():
    with pytest.raises(UnknownImageContractError, match="REAL provenance"):
        make_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=True)


def test_provenance_is_preserved_through_serialization():
    item = make_unknown_image(provenance=DataProvenance.SYNTHETIC, is_real_data=False)
    payload = item.to_dict()
    restored = UnknownImage.from_dict(payload)
    assert restored.provenance is DataProvenance.SYNTHETIC


def test_warnings_and_notes_are_preserved():
    item = make_unknown_image(warnings=("missing_crs", "missing_gsd"), notes="Preserve this note")
    payload = item.to_dict()
    assert payload["warnings"] == ["missing_crs", "missing_gsd"]
    assert payload["notes"] == "Preserve this note"
    restored = UnknownImage.from_dict(payload)
    assert restored.warnings == ("missing_crs", "missing_gsd")
    assert restored.notes == "Preserve this note"


def test_invalid_reference_status_enum_is_rejected():
    with pytest.raises(UnknownImageContractError, match="image_reference_type"):
        make_unknown_image(image_reference_type="not-a-status")


def test_missing_local_path_is_rejected_for_local_available_reference():
    with pytest.raises(UnknownImageContractError, match="local_path"):
        make_unknown_image(
            image_reference="images/IMG-005.tif",
            image_reference_type=UnknownImageReferenceType.LOCAL_AVAILABLE,
            local_path=None,
        )


def test_missing_external_reference_is_rejected_for_external_reference():
    with pytest.raises(UnknownImageContractError, match="external_reference"):
        make_unknown_image(
            image_reference="https://example.test/image.tif",
            image_reference_type=UnknownImageReferenceType.EXTERNAL_REFERENCE,
            external_reference=None,
        )


def test_invalid_gsd_is_rejected():
    with pytest.raises(UnknownImageContractError, match="gsd_m"):
        make_unknown_image(gsd_m=0)


def test_invalid_malformed_footprint_is_rejected():
    with pytest.raises(UnknownImageContractError, match="footprint"):
        make_unknown_image(footprint={"coordinates": []})


def test_invalid_view_geometry_is_rejected():
    with pytest.raises(UnknownImageContractError, match="view_geometry"):
        make_unknown_image(view_geometry={"position_m": [1.0, 2.0]})


def test_invalid_metadata_quality_is_rejected_when_blank():
    with pytest.raises(UnknownImageContractError, match="metadata_quality"):
        make_unknown_image(metadata_quality=" ")


def test_validation_status_must_be_non_empty_string():
    with pytest.raises(UnknownImageContractError, match="validation_status"):
        make_unknown_image(validation_status=" ")
