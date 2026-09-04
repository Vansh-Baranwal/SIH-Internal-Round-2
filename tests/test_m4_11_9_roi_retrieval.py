import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

from lunar_hazard_mapper.m4_terrain.coordinate_estimation import CoordinateEstimationResult, CoordinateEstimationStatus, ReferenceImageGeoreferencing
from lunar_hazard_mapper.m4_terrain.roi_retrieval import ROIStatus, ReferenceProduct, ReferenceProductSource, ROIRetrievalRequest, ROIWindow, retrieve_roi


TRANSFORM = (2.0, 0.5, 100.0, 0.25, -3.0, 500.0)
CRS_TEXT = CRS.from_wkt('LOCAL_CS["Synthetic Lunar",UNIT["metre",1]]').to_string()


def georef(**overrides):
    values = dict(reference_image_id="product-1", width=10, height=8, transform=TRANSFORM, crs=CRS_TEXT, coordinate_system="projected", reference_frame="synthetic-lunar-frame", units="metres", axis_order=("easting", "northing"), source="local-fixture", provenance="synthetic")
    values.update(overrides)
    return ReferenceImageGeoreferencing(**values)


def estimation(**overrides):
    values = dict(status=CoordinateEstimationStatus.SUCCESS, unknown_image_id="unknown-1", reference_image_id="product-1", anchor_id="anchor-1", target_pixel=(1.0, 1.0), reference_pixel=(5.0, 4.0), estimated_coordinate=(112.0, 489.5), coordinate_system="projected", reference_frame="synthetic-lunar-frame", units="metres", axis_order=("easting", "northing"), provenance={"upstream": "synthetic"})
    values.update(overrides)
    return CoordinateEstimationResult(**values)


def product(tmp_path, source_type=ReferenceProductSource.LOCAL_AVAILABLE, **kwargs):
    path = tmp_path / "authoritative_fixture.tif"
    data = np.arange(80, dtype=np.int16).reshape(8, 10)
    with rasterio.open(path, "w", driver="GTiff", width=10, height=8, count=1, dtype=data.dtype, crs=CRS_TEXT, transform=Affine(*TRANSFORM)) as output:
        output.write(data, 1)
    return ReferenceProduct(product_id="product-1", source_type=source_type, georeferencing=kwargs.pop("georeferencing", georef()), path=path if source_type is ReferenceProductSource.LOCAL_AVAILABLE else None, external_reference="catalogue://product-1" if source_type is ReferenceProductSource.EXTERNAL_REFERENCE else None, provenance="synthetic", **kwargs)


def request(tmp_path, **kwargs):
    return ROIRetrievalRequest(coordinate_estimation=kwargs.pop("coordinate_estimation", estimation()), reference_product=kwargs.pop("reference_product", product(tmp_path)), roi=kwargs.pop("roi", ROIWindow(3, 3, "pixels")), request_id="roi-request-1", **kwargs)


def test_retrieves_rotated_affine_window_and_preserves_metadata(tmp_path):
    result = retrieve_roi(request(tmp_path))
    assert result.status is ROIStatus.SUCCESS
    assert result.raster_window == (2, 3, 3, 3)
    assert result.roi_data.shape == (1, 3, 3)
    assert result.roi_data.tolist() == [[[23, 24, 25], [33, 34, 35], [43, 44, 45]]]
    assert result.parent_dimensions == (8, 10)
    assert result.roi_transform == tuple(float(value) for value in tuple(Affine(*TRANSFORM) @ Affine.translation(3, 2))[:6])
    assert result.provenance["source_product"] == "product-1"
    assert result.provenance["synthetic"] is True
    assert result.to_dict()["pixels_retrieved"] is True


def test_repeated_retrieval_is_deterministic(tmp_path):
    first = retrieve_roi(request(tmp_path)).to_dict()
    second = retrieve_roi(request(tmp_path)).to_dict()
    assert first == second


def test_boundary_is_out_of_bounds_without_clamping(tmp_path):
    result = retrieve_roi(request(tmp_path, coordinate_estimation=estimation(estimated_coordinate=(100.0, 500.0)), roi=ROIWindow(3, 3, "pixels")))
    assert result.status is ROIStatus.OUT_OF_BOUNDS
    assert result.roi_data is None
    assert result.raster_window is None


def test_partial_clipping_is_explicit_and_keeps_requested_center(tmp_path):
    result = retrieve_roi(request(tmp_path, coordinate_estimation=estimation(estimated_coordinate=(100.0, 500.0)), roi=ROIWindow(3, 3, "pixels", allow_partial=True)))
    assert result.status is ROIStatus.PARTIAL
    assert result.raster_window == (0, 0, 1, 1)
    assert result.requested_center_coordinate == (100.0, 500.0)


def test_coordinate_sized_roi_uses_same_rotated_transform(tmp_path):
    result = retrieve_roi(request(tmp_path, roi=ROIWindow(5.0, 5.0, "coordinate")))
    assert result.status is ROIStatus.SUCCESS
    assert result.roi_dimensions == (2, 4)


def test_missing_and_blocked_estimates_are_not_invented(tmp_path):
    missing = retrieve_roi(request(tmp_path, coordinate_estimation=None))
    blocked = retrieve_roi(request(tmp_path, coordinate_estimation=estimation(status=CoordinateEstimationStatus.ESTIMATION_BLOCKED, estimated_coordinate=None)))
    assert missing.status is ROIStatus.BLOCKED
    assert blocked.status is ROIStatus.BLOCKED
    assert missing.roi_data is None and blocked.roi_data is None


def test_semantics_are_required_and_must_match_product(tmp_path):
    missing_crs = retrieve_roi(request(tmp_path, coordinate_estimation=estimation(coordinate_system=None)))
    mismatch = retrieve_roi(request(tmp_path, coordinate_estimation=estimation(reference_frame="other-frame")))
    assert missing_crs.status is ROIStatus.BLOCKED
    assert mismatch.status is ROIStatus.INVALID_INPUT


def test_unavailable_external_and_missing_products_are_not_fabricated(tmp_path):
    external = retrieve_roi(request(tmp_path, reference_product=product(tmp_path, ReferenceProductSource.EXTERNAL_REFERENCE)))
    missing_path = product(tmp_path)
    missing_path = ReferenceProduct(product_id="product-1", source_type=ReferenceProductSource.LOCAL_MISSING, georeferencing=georef(), provenance="synthetic")
    missing = retrieve_roi(request(tmp_path, reference_product=missing_path))
    assert external.status is ROIStatus.REFERENCE_UNAVAILABLE
    assert missing.status is ROIStatus.REFERENCE_UNAVAILABLE
    assert external.roi_data is None and missing.roi_data is None


def test_invalid_roi_dimensions_and_product_metadata_are_rejected(tmp_path):
    with np.testing.assert_raises(ValueError):
        ROIWindow(0, 2, "pixels")
    invalid_product = product(tmp_path, georeferencing=georef(transform=(1, 0, 0, 0, -1, 0)))
    result = retrieve_roi(request(tmp_path, reference_product=invalid_product))
    assert result.status is ROIStatus.INVALID_INPUT


def test_no_accuracy_or_ground_truth_claims_are_added(tmp_path):
    payload = retrieve_roi(request(tmp_path)).to_dict()
    assert "accuracy" not in payload
    assert "ground_truth" not in payload
    assert "metadata_coordinate" not in payload