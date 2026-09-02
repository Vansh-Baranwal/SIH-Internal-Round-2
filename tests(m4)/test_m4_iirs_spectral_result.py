"""Tests for M4-08.7 IIRS Spectral Result Contract."""

import copy
import numpy as np
import pytest
from affine import Affine

from lunar_hazard_mapper.scientific.iirs.types import IIRSCube
from lunar_hazard_mapper.scientific.iirs.validation import IIRSInputValidationResult
from lunar_hazard_mapper.scientific.iirs.preprocessing import IIRSSpectralPreprocessingResult
from lunar_hazard_mapper.scientific.iirs.band_ratio import IIRSBandRatioResult
from lunar_hazard_mapper.scientific.iirs.features import IIRSSpectralFeatureSet
from lunar_hazard_mapper.scientific.iirs.classification import IIRSMaterialClassificationResult, MaterialClass
from lunar_hazard_mapper.scientific.iirs.result import IIRSSpectralResult


@pytest.fixture
def dummy_components():
    """Create a set of valid, matching components for testing."""
    height, width = 4, 4
    
    # 1. Source Cube
    data = np.ones((height, width, 3), dtype=np.float64)
    cube = IIRSCube(
        data=data,
        wavelengths_um=np.array([1.0, 2.0, 3.0]),
        pixel_size_m=10.0,
        transform=Affine(10.0, 0.0, 0.0, 0.0, -10.0, 0.0),
        crs="EPSG:32618",
        nodata=None,
    )
    
    # 2. Preprocessing Result
    validation = IIRSInputValidationResult(is_valid=True)
    preprocessing = IIRSSpectralPreprocessingResult(
        normalized_data=np.ones((height, width, 3), dtype=np.float64),
        valid_mask=np.ones((height, width, 3), dtype=bool),
        normalization_min=0.0,
        normalization_max=1.0,
        input_validation=validation,
    )
    
    # 3. Band Ratio Result
    ratio = IIRSBandRatioResult(
        ratio_map=np.ones((height, width), dtype=np.float64),
        valid_mask=np.ones((height, width), dtype=bool),
        numerator_band=0,
        denominator_band=1,
        numerator_wavelength_um=1.0,
        denominator_wavelength_um=2.0,
        normalization_method="global_minmax",
    )
    
    # 4. Feature Set
    feature_set = IIRSSpectralFeatureSet(
        feature_maps=np.ones((height, width, 1), dtype=np.float64),
        valid_mask=np.ones((height, width, 1), dtype=bool),
        feature_names=("ratio_0_1",),
        ratio_bands=((0, 1),),
        ratio_wavelengths_um=((1.0, 2.0),),
        normalization_methods=("global_minmax",),
    )
    
    # 5. Classification Result
    class_map = np.full((height, width), MaterialClass.ILLMENITE, dtype=object)
    classification = IIRSMaterialClassificationResult(
        class_map=class_map,
        score_map=np.ones((height, width), dtype=np.float64),
        valid_mask=np.ones((height, width), dtype=bool),
    )
    
    return cube, preprocessing, [ratio], feature_set, classification


def test_valid_construction_and_preservation(dummy_components):
    """Valid components construct successfully and are preserved."""
    cube, pre, ratios, feats, cls = dummy_components
    result = IIRSSpectralResult(
        source_cube=cube,
        preprocessing_result=pre,
        band_ratio_results=ratios,
        feature_set=feats,
        classification_result=cls,
    )
    
    assert result.source_cube is cube
    assert result.preprocessing_result is pre
    assert result.band_ratio_results[0] is ratios[0]
    assert result.feature_set is feats
    assert result.classification_result is cls


def test_spatial_shape_validation(dummy_components):
    """Mismatched spatial shapes are rejected."""
    cube, pre, ratios, feats, cls = dummy_components
    
    # Mismatch preprocessing
    bad_pre = IIRSSpectralPreprocessingResult(
        normalized_data=np.ones((5, 5, 3)),
        valid_mask=np.ones((5, 5, 3), dtype=bool),
        normalization_min=0.0,
        normalization_max=1.0,
        input_validation=pre.input_validation,
    )
    with pytest.raises(ValueError, match="shape differs"):
        IIRSSpectralResult(cube, bad_pre, ratios, feats, cls)


def test_serialization_round_trip(dummy_components):
    """Result can be serialized and deserialized deterministically."""
    cube, pre, ratios, feats, cls = dummy_components
    
    # Introduce NaN and UNCLASSIFIED to verify they serialize correctly
    cls.class_map[0, 0] = MaterialClass.UNCLASSIFIED
    cls.score_map[0, 0] = np.nan
    cls.valid_mask[0, 0] = False
    
    result1 = IIRSSpectralResult(cube, pre, ratios, feats, cls)
    
    payload = result1.to_dict()
    result2 = IIRSSpectralResult.from_dict(payload)
    
    assert result1 == result2


def test_repeated_construction_equivalence(dummy_components):
    """Identical inputs produce identical result objects."""
    cube, pre, ratios, feats, cls = dummy_components
    result1 = IIRSSpectralResult(cube, pre, ratios, feats, cls)
    result2 = IIRSSpectralResult(cube, pre, ratios, feats, cls)
    assert result1 == result2


def test_immutability(dummy_components):
    """Contract construction does not modify inputs."""
    cube, pre, ratios, feats, cls = dummy_components
    cube_copy = copy.deepcopy(cube)
    
    _ = IIRSSpectralResult(cube, pre, ratios, feats, cls)
    
    assert cube == cube_copy


def test_no_registration_or_overlay(dummy_components):
    """Ensure result does not implement 8.8 or 8.9 features."""
    cube, pre, ratios, feats, cls = dummy_components
    result = IIRSSpectralResult(cube, pre, ratios, feats, cls)
    
    # Verify it doesn't expose any of the forbidden APIs
    for forbidden in ["register", "align", "overlay", "homography", "render"]:
        assert not hasattr(result, forbidden)
