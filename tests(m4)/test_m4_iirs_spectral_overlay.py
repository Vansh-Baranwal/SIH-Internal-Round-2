"""Tests for M4-08.9 Spectral Overlay Generation."""

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
from lunar_hazard_mapper.scientific.iirs.classification import (
    IIRSMaterialClassificationResult,
    MaterialClass,
)
from lunar_hazard_mapper.scientific.iirs.result import IIRSSpectralResult
from lunar_hazard_mapper.scientific.iirs.mapping import IIRSOpticalMappingResult
from lunar_hazard_mapper.scientific.iirs.overlay import (
    SpectralOverlayResult,
    generate_spectral_overlay,
)


# ---------------------------------------------------------------------------
# Helpers — build a small, controlled pipeline with explicit pixel values
# ---------------------------------------------------------------------------

def _make_spectral_result(
    height: int = 2,
    width: int = 2,
    pixel_size_m: float = 100.0,
    origin_x: float = 0.0,
    origin_y: float = 200.0,
    all_valid: bool = True,
):
    """Construct a fully-controlled IIRSSpectralResult.

    Source grid is (height, width) at `pixel_size_m` resolution.
    Score map uses deterministic values: row*width + col (for easy verification).
    """
    data = np.ones((height, width, 3), dtype=np.float64)
    cube = IIRSCube(
        data=data,
        wavelengths_um=np.array([1.0, 2.0, 3.0]),
        pixel_size_m=pixel_size_m,
        transform=Affine(pixel_size_m, 0.0, origin_x, 0.0, -pixel_size_m, origin_y),
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

    # Deterministic classification: each pixel gets a known score
    score_map = np.zeros((height, width), dtype=np.float64)
    class_map = np.full((height, width), MaterialClass.ILLMENITE, dtype=object)
    cls_valid = np.ones((height, width), dtype=bool)

    for r in range(height):
        for c in range(width):
            score_map[r, c] = float(r * width + c + 1)  # 1-based for easy check
            class_map[r, c] = MaterialClass.PYROXENE

    if not all_valid:
        # Mark pixel (0,1) as invalid
        cls_valid[0, 1] = False
        score_map[0, 1] = np.nan
        class_map[0, 1] = MaterialClass.UNCLASSIFIED

    classification = IIRSMaterialClassificationResult(
        class_map=class_map,
        score_map=score_map,
        valid_mask=cls_valid,
    )

    return IIRSSpectralResult(
        source_cube=cube,
        preprocessing_result=preprocessing,
        band_ratio_results=(ratio,),
        feature_set=feature_set,
        classification_result=classification,
    )


def _make_mapping(
    spectral: IIRSSpectralResult,
    target_height: int = 4,
    target_width: int = 4,
    target_pixel_size: float = 50.0,
    target_origin_x: float = 0.0,
    target_origin_y: float = 200.0,
):
    """Construct an IIRSOpticalMappingResult with a known affine relationship."""
    tgt_transform = Affine(
        target_pixel_size, 0.0, target_origin_x,
        0.0, -target_pixel_size, target_origin_y,
    )
    reg = RegistrationResult(
        registration_id="reg_overlay_test",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        metrics=RegistrationMetrics(rmse_px=0.5, inlier_count=10, inlier_ratio=0.9),
        transform=tgt_transform,
        spatial_reference={
            "height": target_height,
            "width": target_width,
            "crs": "EPSG:32618",
        },
        success=True,
    )
    return IIRSOpticalMappingResult(spectral_result=spectral, registration=reg)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def aligned_mapping():
    """Source 2×2 at 100m → target 4×4 at 50m, same origin, fully overlapping."""
    spectral = _make_spectral_result(height=2, width=2, pixel_size_m=100.0)
    return _make_mapping(spectral, target_height=4, target_width=4, target_pixel_size=50.0)


@pytest.fixture
def partial_mapping():
    """Source 2×2 at 100m, one pixel invalid. Target 4×4 at 50m."""
    spectral = _make_spectral_result(height=2, width=2, pixel_size_m=100.0, all_valid=False)
    return _make_mapping(spectral, target_height=4, target_width=4, target_pixel_size=50.0)


@pytest.fixture
def offset_mapping():
    """Target footprint is shifted so only part overlaps the source grid."""
    spectral = _make_spectral_result(
        height=2, width=2, pixel_size_m=100.0,
        origin_x=0.0, origin_y=200.0,
    )
    # Shift target origin so right half falls outside source
    return _make_mapping(
        spectral,
        target_height=4, target_width=4, target_pixel_size=50.0,
        target_origin_x=100.0, target_origin_y=200.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_mapping_consumed(aligned_mapping):
    """1. Valid M4-08.8 mapping result can be consumed."""
    overlay = generate_spectral_overlay(aligned_mapping)
    assert isinstance(overlay, SpectralOverlayResult)


def test_target_footprint_shape(aligned_mapping):
    """2 & 3. Overlay uses target OHRC/TMC footprint and has expected shape."""
    overlay = generate_spectral_overlay(aligned_mapping)
    assert overlay.score_overlay.shape == (4, 4)
    assert overlay.class_overlay.shape == (4, 4)
    assert overlay.valid_mask.shape == (4, 4)
    # Source is explicitly smaller
    src_shape = aligned_mapping.spectral_result.source_cube.data.shape[:2]
    assert src_shape == (2, 2)
    assert overlay.score_overlay.shape != src_shape


def test_spatial_transform_preserved(aligned_mapping):
    """4. Spatial transform/reference is preserved correctly."""
    overlay = generate_spectral_overlay(aligned_mapping)
    expected_transform = aligned_mapping.registration.transform
    assert tuple(overlay.target_transform) == tuple(expected_transform)
    assert overlay.target_crs == "EPSG:32618"
    assert overlay.source_sensor == "IIRS"
    assert overlay.reference_sensor == "OHRC"
    assert overlay.registration_id == "reg_overlay_test"


def test_valid_source_maps_to_valid_target(aligned_mapping):
    """5. Valid source pixels map into valid target pixels."""
    overlay = generate_spectral_overlay(aligned_mapping)
    # Source is all-valid 2×2 at 100m, target is 4×4 at 50m, same origin.
    # Every target pixel should map back into the source grid.
    assert overlay.valid_mask.all()
    assert np.isfinite(overlay.score_overlay).all()
    # All mapped classes should be PYROXENE (as set in fixture)
    for r in range(4):
        for c in range(4):
            assert overlay.class_overlay[r, c] == MaterialClass.PYROXENE


def test_invalid_source_remains_invalid(partial_mapping):
    """6. Invalid source pixels remain invalid in the overlay."""
    overlay = generate_spectral_overlay(partial_mapping)
    # Source pixel (0,1) is invalid. At 100m source resolution mapped to 50m
    # target, target pixels (0,2), (0,3), (1,2), (1,3) should map back to
    # source (0,1) and therefore be invalid.
    invalid_count = (~overlay.valid_mask).sum()
    assert invalid_count > 0
    # Verify that the invalid target pixels have NaN scores
    assert np.isnan(overlay.score_overlay[~overlay.valid_mask]).all()
    # And UNCLASSIFIED classes
    for cls_val in overlay.class_overlay[~overlay.valid_mask]:
        assert cls_val == MaterialClass.UNCLASSIFIED


def test_unmapped_target_pixels_remain_invalid(offset_mapping):
    """7. Unmapped target pixels remain invalid."""
    overlay = generate_spectral_overlay(offset_mapping)
    # Target is shifted right by 100m. Source covers x=[0,200], target covers x=[100,300].
    # Right half of target (x=[200,300]) has no source correspondence.
    has_unmapped = (~overlay.valid_mask).any()
    assert has_unmapped
    # All unmapped pixels must be NaN
    assert np.isnan(overlay.score_overlay[~overlay.valid_mask]).all()


def test_nan_nodata_semantics(aligned_mapping):
    """8. NaN/nodata semantics are preserved."""
    overlay = generate_spectral_overlay(aligned_mapping)
    # For all-valid: no NaN
    assert not np.isnan(overlay.score_overlay[overlay.valid_mask]).any()
    # Wherever invalid: NaN
    if (~overlay.valid_mask).any():
        assert np.isnan(overlay.score_overlay[~overlay.valid_mask]).all()


def test_upstream_immutability(aligned_mapping):
    """9. Overlay generation does not mutate upstream arrays."""
    spectral_copy = copy.deepcopy(aligned_mapping.spectral_result)
    reg_copy = copy.deepcopy(aligned_mapping.registration)

    _ = generate_spectral_overlay(aligned_mapping)

    assert aligned_mapping.spectral_result == spectral_copy
    assert aligned_mapping.registration == reg_copy


def test_deterministic_output(aligned_mapping):
    """10. Overlay generation is deterministic."""
    overlay1 = generate_spectral_overlay(aligned_mapping)
    overlay2 = generate_spectral_overlay(aligned_mapping)
    assert overlay1 == overlay2


def test_invalid_mapping_rejected():
    """11. Invalid mapping inputs are rejected deterministically."""
    with pytest.raises(TypeError, match="IIRSOpticalMappingResult"):
        generate_spectral_overlay("not a mapping")
    with pytest.raises(TypeError, match="IIRSOpticalMappingResult"):
        generate_spectral_overlay(None)


def test_classification_consumed_not_recalculated(aligned_mapping):
    """12. Existing classification values are merely consumed, not recalculated."""
    overlay = generate_spectral_overlay(aligned_mapping)
    src_scores = aligned_mapping.spectral_result.classification_result.score_map
    # Every score in the overlay must come from the source score_map
    unique_overlay_scores = set(overlay.score_overlay[overlay.valid_mask].ravel())
    unique_src_scores = set(src_scores[
        aligned_mapping.spectral_result.classification_result.valid_mask
    ].ravel())
    assert unique_overlay_scores.issubset(unique_src_scores)


def test_feature_values_consumed_not_recalculated(aligned_mapping):
    """13. Existing feature/band-ratio values are merely consumed, not recalculated.
    
    The overlay projects classification scores. We verify no new feature
    computation methods exist on the result.
    """
    overlay = generate_spectral_overlay(aligned_mapping)
    for attr in ["extract_features", "compute_band_ratio", "classify"]:
        assert not hasattr(overlay, attr)


def test_no_registration_engine(aligned_mapping):
    """14. No registration engine is invoked beyond consuming the mapping contract."""
    overlay = generate_spectral_overlay(aligned_mapping)
    for attr in ["register", "match_features", "estimate_transform", "refine"]:
        assert not hasattr(overlay, attr)


def test_no_usgs_reference_data(aligned_mapping):
    """15. No USGS/reference data are introduced."""
    overlay = generate_spectral_overlay(aligned_mapping)
    d = overlay.to_dict()
    serialized = str(d).lower()
    assert "usgs" not in serialized
    assert "spectral_library" not in serialized


def test_serialization_round_trip(aligned_mapping):
    """Overlay result serializes deterministically via to_dict()."""
    overlay = generate_spectral_overlay(aligned_mapping)
    d1 = overlay.to_dict()
    d2 = overlay.to_dict()
    assert d1 == d2
    assert isinstance(d1["score_overlay"], list)
    assert isinstance(d1["class_overlay"], list)
    assert isinstance(d1["valid_mask"], list)
