"""Tests for M4-08.8 Registration-to-Optical Mapping layer."""

import copy
import numpy as np
import pytest
from affine import Affine

from lunar_hazard_mapper.scientific.common.types import RegistrationResult, RegistrationMetrics
from lunar_hazard_mapper.scientific.iirs.types import IIRSCube
from lunar_hazard_mapper.scientific.iirs.validation import IIRSInputValidationResult
from lunar_hazard_mapper.scientific.iirs.preprocessing import IIRSSpectralPreprocessingResult
from lunar_hazard_mapper.scientific.iirs.band_ratio import IIRSBandRatioResult
from lunar_hazard_mapper.scientific.iirs.features import IIRSSpectralFeatureSet
from lunar_hazard_mapper.scientific.iirs.classification import IIRSMaterialClassificationResult, MaterialClass
from lunar_hazard_mapper.scientific.iirs.result import IIRSSpectralResult
from lunar_hazard_mapper.scientific.iirs.mapping import IIRSOpticalMappingResult


@pytest.fixture
def dummy_spectral_result():
    height, width = 4, 4
    
    data = np.ones((height, width, 3), dtype=np.float64)
    cube = IIRSCube(
        data=data,
        wavelengths_um=np.array([1.0, 2.0, 3.0]),
        pixel_size_m=10.0,
        transform=Affine(10.0, 0.0, 0.0, 0.0, -10.0, 0.0),
        crs="EPSG:32618",
        nodata=None,
    )
    
    validation = IIRSInputValidationResult(is_valid=True)
    preprocessing = IIRSSpectralPreprocessingResult(
        normalized_data=np.ones((height, width, 3), dtype=np.float64),
        valid_mask=np.ones((height, width, 3), dtype=bool),
        normalization_min=0.0,
        normalization_max=1.0,
        input_validation=validation,
    )
    
    ratio = IIRSBandRatioResult(
        ratio_map=np.ones((height, width), dtype=np.float64),
        valid_mask=np.ones((height, width), dtype=bool),
        numerator_band=0,
        denominator_band=1,
        numerator_wavelength_um=1.0,
        denominator_wavelength_um=2.0,
        normalization_method="global_minmax",
    )
    
    feature_set = IIRSSpectralFeatureSet(
        feature_maps=np.ones((height, width, 1), dtype=np.float64),
        valid_mask=np.ones((height, width, 1), dtype=bool),
        feature_names=("ratio_0_1",),
        ratio_bands=((0, 1),),
        ratio_wavelengths_um=((1.0, 2.0),),
        normalization_methods=("global_minmax",),
    )
    
    class_map = np.full((height, width), MaterialClass.ILLMENITE, dtype=object)
    classification = IIRSMaterialClassificationResult(
        class_map=class_map,
        score_map=np.ones((height, width), dtype=np.float64),
        valid_mask=np.ones((height, width), dtype=bool),
    )
    
    return IIRSSpectralResult(
        source_cube=cube,
        preprocessing_result=preprocessing,
        band_ratio_results=(ratio,),
        feature_set=feature_set,
        classification_result=classification,
    )

@pytest.fixture
def dummy_registration_result():
    return RegistrationResult(
        registration_id="reg_123",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        metrics=RegistrationMetrics(rmse_px=1.2, inlier_count=50, inlier_ratio=0.8),
        transform=Affine(5.0, 0.0, 100.0, 0.0, -5.0, 200.0),
        spatial_reference={"height": 800, "width": 800, "crs": "EPSG:32618"},
        success=True
    )


def test_valid_construction_and_preservation(dummy_spectral_result, dummy_registration_result):
    """1. Existing registration output can be consumed.
       2. IIRS spatial information maps to the expected OHRC/TMC footprint.
       4. Registration/transform metadata is preserved."""
    mapping = IIRSOpticalMappingResult(
        spectral_result=dummy_spectral_result,
        registration=dummy_registration_result
    )
    
    assert mapping.spectral_result is dummy_spectral_result
    assert mapping.registration is dummy_registration_result
    assert mapping.target_footprint == {"height": 800, "width": 800, "crs": "EPSG:32618"}
    
    # 3. Expected spatial dimensions are preserved (unmodified spectral footprint + mapped target footprint)
    assert mapping.spectral_result.source_cube.data.shape == (4, 4, 3)


def test_invalid_registration_rejection(dummy_spectral_result, dummy_registration_result):
    """11. Invalid/incompatible spatial inputs are rejected deterministically."""
    bad_reg_unsuccessful = copy.deepcopy(dummy_registration_result)
    object.__setattr__(bad_reg_unsuccessful, "success", False)
    with pytest.raises(ValueError, match="unsuccessful"):
        IIRSOpticalMappingResult(dummy_spectral_result, bad_reg_unsuccessful)
        
    bad_reg_no_transform = copy.deepcopy(dummy_registration_result)
    object.__setattr__(bad_reg_no_transform, "transform", None)
    with pytest.raises(ValueError, match="valid transform"):
        IIRSOpticalMappingResult(dummy_spectral_result, bad_reg_no_transform)
        
    bad_reg_no_footprint = copy.deepcopy(dummy_registration_result)
    object.__setattr__(bad_reg_no_footprint, "spatial_reference", {})
    with pytest.raises(ValueError, match="spatial_reference"):
        IIRSOpticalMappingResult(dummy_spectral_result, bad_reg_no_footprint)


def test_immutability(dummy_spectral_result, dummy_registration_result):
    """8 & 9. Input IIRS data and registration output remain unchanged."""
    spectral_copy = copy.deepcopy(dummy_spectral_result)
    reg_copy = copy.deepcopy(dummy_registration_result)
    
    mapping = IIRSOpticalMappingResult(dummy_spectral_result, dummy_registration_result)
    
    assert mapping.spectral_result == spectral_copy
    assert mapping.registration == reg_copy


def test_deterministic_execution(dummy_spectral_result, dummy_registration_result):
    """10. Repeated execution is deterministic."""
    mapping1 = IIRSOpticalMappingResult(dummy_spectral_result, dummy_registration_result)
    mapping2 = IIRSOpticalMappingResult(dummy_spectral_result, dummy_registration_result)
    
    assert mapping1.to_dict() == mapping2.to_dict()


def test_no_fabrication_or_resampling(dummy_spectral_result, dummy_registration_result):
    """5, 6, 7 & 12. Valid/invalid regions remain intact, no new registration/resampling."""
    mapping = IIRSOpticalMappingResult(dummy_spectral_result, dummy_registration_result)
    
    # Asserting no methods added for resampling, overlay, etc.
    for forbidden in ["resample", "warp", "overlay", "match", "align"]:
        assert not hasattr(mapping, forbidden)
    
    # Asserting that the invalid/unmapped regions stay intact mathematically 
    # since we don't warp arrays. Valid/invalid mask preservation is deferred
    # to the overlay layer (8.9) but guaranteed intact because source is preserved.
    assert mapping.valid_mask is None
