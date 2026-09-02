"""M4-09.4 Focused tests for Spatial Normalization Utility.

These tests use synthetic data only and strictly avoid real lunar data
to verify the spatial normalization boundary.
"""

import copy

import numpy as np
import pytest
from affine import Affine
from rasterio.warp import Resampling

from lunar_hazard_mapper.scientific.common.types import RegistrationMetrics, RegistrationResult
from lunar_hazard_mapper.scientific.water_ice.normalization import (
    normalize_evidence_layer,
    normalize_with_registration,
)
from lunar_hazard_mapper.scientific.water_ice.types import WaterIceEvidenceLayer, WaterIceEvidenceSource


@pytest.fixture
def source_layer() -> WaterIceEvidenceLayer:
    """Fixture providing a synthetic source evidence layer (5x5)."""
    values = np.arange(25, dtype=np.float64).reshape((5, 5))
    values[0, 0] = np.nan  # One invalid cell
    mask = np.ones((5, 5), dtype=bool)
    mask[0, 0] = False
    
    return WaterIceEvidenceLayer(
        source=WaterIceEvidenceSource.IIRS_HYDRATION_SIGNAL,
        values=values,
        valid_mask=mask,
        pixel_size_m=20.0,
        transform=Affine.translation(100.0, 500.0) * Affine.scale(20.0, -20.0),
        crs="EPSG:32618",
        nodata=np.nan,
        dataset_name="Synthetic_Source",
        sensor="IIRS",
        observation_date="2024-01-01",
        orbit_id="ORB001",
        notes="Synthetic layer for testing.",
    )


@pytest.fixture
def target_transform() -> Affine:
    """Target transform for resampling tests (slightly shifted, half resolution)."""
    return Affine.translation(110.0, 490.0) * Affine.scale(40.0, -40.0)


def test_basic_normalization_same_crs(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies basic normalization to a new transform, shape, and pixel size."""
    original_source = copy.deepcopy(source_layer)
    
    result = normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=target_transform,
        target_shape=(3, 3),
        target_crs="EPSG:32618",
        target_pixel_size_m=40.0,
        resampling_method=Resampling.nearest,
    )
    
    # 7. source object is not mutated
    assert source_layer == original_source
    
    # 2. changed target shape
    assert result.values.shape == (3, 3)
    assert result.valid_mask.shape == (3, 3)
    
    # 3. target transform preservation
    assert result.transform == target_transform
    
    # 4. target pixel-size preservation
    assert result.pixel_size_m == 40.0
    
    # 5. valid-mask propagation (mask boolean logic is preserved)
    assert result.valid_mask.dtype == bool
    
    # 6. nodata semantics (NaN preservation)
    assert np.isnan(result.nodata)
    assert np.isnan(result.values[~result.valid_mask]).all()
    
    # Provenance propagation
    assert "Synthetic_Source" in result.dataset_name
    assert result.sensor == "IIRS"


def test_mask_is_handled_separately_from_values(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies that mask interpolation uses nearest-neighbor to prevent smearing."""
    # Resample with bilinear to intentionally interpolate values
    result = normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=target_transform,
        target_shape=(3, 3),
        target_crs="EPSG:32618",
        target_pixel_size_m=40.0,
        resampling_method=Resampling.bilinear,
    )
    # But mask must remain strictly boolean (this is tested by WaterIceEvidenceLayer validation implicitly,
    # but we assert it explicitly anyway).
    assert result.valid_mask.dtype == bool
    # And invalid cells MUST exactly match nodata
    assert np.isnan(result.values[~result.valid_mask]).all()


def test_crs_handling(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies CRS transformation if the CRS differs."""
    result = normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=target_transform,
        target_shape=(3, 3),
        target_crs="EPSG:4326",  # Different CRS
        target_pixel_size_m=40.0,
        resampling_method=Resampling.nearest,
    )
    assert result.crs == "EPSG:4326"


def test_deterministic_execution(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies that repeated execution yields identical objects."""
    result1 = normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=target_transform,
        target_shape=(3, 3),
        target_crs="EPSG:32618",
        target_pixel_size_m=40.0,
    )
    result2 = normalize_evidence_layer(
        source_layer=source_layer,
        target_transform=target_transform,
        target_shape=(3, 3),
        target_crs="EPSG:32618",
        target_pixel_size_m=40.0,
    )
    assert result1 == result2


def test_invalid_target_dimensions(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies rejection of invalid target shapes."""
    with pytest.raises(ValueError, match="target_shape must be positive integers"):
        normalize_evidence_layer(
            source_layer=source_layer,
            target_transform=target_transform,
            target_shape=(0, 3),
            target_crs="EPSG:32618",
            target_pixel_size_m=40.0,
        )


def test_inconsistent_pixel_size_handling(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies that inconsistent pixel_size_m vs transform fails."""
    # WaterIceEvidenceLayer contract enforces this on construction.
    with pytest.raises(ValueError, match="transform pixel scale must match pixel_size_m"):
        normalize_evidence_layer(
            source_layer=source_layer,
            target_transform=target_transform,  # Scale is 40.0
            target_shape=(3, 3),
            target_crs="EPSG:32618",
            target_pixel_size_m=99.0,  # Deliberately mismatching
        )


def test_invalid_target_transform(source_layer: WaterIceEvidenceLayer) -> None:
    """Verifies rejection of non-Affine transforms."""
    with pytest.raises(TypeError, match="target_transform must be an Affine instance"):
        normalize_evidence_layer(
            source_layer=source_layer,
            target_transform="Not an Affine",  # type: ignore
            target_shape=(3, 3),
            target_crs="EPSG:32618",
            target_pixel_size_m=40.0,
        )


def test_invalid_resampling_policy(source_layer: WaterIceEvidenceLayer, target_transform: Affine) -> None:
    """Verifies explicit resampling policy typing."""
    with pytest.raises(TypeError, match="resampling_method must be a rasterio.warp.Resampling enum"):
        normalize_evidence_layer(
            source_layer=source_layer,
            target_transform=target_transform,
            target_shape=(3, 3),
            target_crs="EPSG:32618",
            target_pixel_size_m=40.0,
            resampling_method="nearest",  # type: ignore
        )


# ---- RegistrationResult interaction tests ----

@pytest.fixture
def valid_registration(target_transform: Affine) -> RegistrationResult:
    """Fixture providing a valid RegistrationResult."""
    return RegistrationResult(
        registration_id="REG001",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        success=True,
        transform=target_transform,
        spatial_reference={"height": 3, "width": 3, "crs": "EPSG:32618"},
    )


def test_registration_normalization_valid(source_layer: WaterIceEvidenceLayer, valid_registration: RegistrationResult, target_transform: Affine) -> None:
    """Verifies normalization using a valid RegistrationResult."""
    result = normalize_with_registration(
        source_layer=source_layer,
        registration=valid_registration,
        target_pixel_size_m=40.0,
    )
    assert result.transform == target_transform
    assert result.shape == (3, 3)
    assert result.crs == "EPSG:32618"


def test_registration_normalization_missing_transform(source_layer: WaterIceEvidenceLayer, valid_registration: RegistrationResult) -> None:
    """Verifies failure when transform is missing/None."""
    # Modify the generic fixture
    bad_reg = RegistrationResult(
        registration_id="REG001",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        success=True,
        transform=None,
        spatial_reference={"height": 3, "width": 3},
    )
    with pytest.raises(TypeError, match="transform must be an explicitly validated Affine"):
        normalize_with_registration(source_layer, bad_reg, 40.0)


def test_registration_normalization_invalid_transform_type(source_layer: WaterIceEvidenceLayer, valid_registration: RegistrationResult) -> None:
    """Verifies failure when transform is not an Affine."""
    bad_reg = RegistrationResult(
        registration_id="REG001",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        success=True,
        transform=[1, 0, 0, 0, 1, 0],  # Invalid type (list)
        spatial_reference={"height": 3, "width": 3},
    )
    with pytest.raises(TypeError, match="transform must be an explicitly validated Affine"):
        normalize_with_registration(source_layer, bad_reg, 40.0)


def test_registration_normalization_missing_spatial_reference(source_layer: WaterIceEvidenceLayer, valid_registration: RegistrationResult, target_transform: Affine) -> None:
    """Verifies failure when spatial_reference lacks height/width."""
    bad_reg = RegistrationResult(
        registration_id="REG001",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        success=True,
        transform=target_transform,
        spatial_reference={"crs": "EPSG:32618"},  # Missing height/width
    )
    with pytest.raises(ValueError, match="spatial_reference must define positive integer 'height' and 'width'"):
        normalize_with_registration(source_layer, bad_reg, 40.0)
