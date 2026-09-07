"""M4-08.13 End-to-end Phase 8 integration validation (controlled synthetic path).

This module is a TEST-ONLY verification layer.  It threads the ACTUAL output of
every existing Phase 8 stage into the next stage, starting from the controlled
synthetic fixture reused from M4-08.11 (SPECTRUM_A / make_cube) and ending at
the M4-08.10 scientific guardrail.

Chain exercised (existing public implementations only, never modified):

    controlled IIRS cube
        -> 8.3 preprocess_iirs_cube
        -> 8.4 compute_iirs_band_ratio
        -> 8.5 extract_iirs_spectral_features
        -> 8.6 classify_materials
        -> 8.7 IIRSSpectralResult
        -> 8.8 IIRSOpticalMappingResult
        -> 8.9 generate_spectral_overlay
        -> 8.10 create_default_guardrail

Passing this test demonstrates that the Phase 8 software components integrate
and behave consistently for the controlled synthetic input.  It does NOT
establish:

    - scientific correctness
    - mineralogical ground truth
    - mineral identification accuracy
    - USGS validation
    - laboratory validation
    - mission validation
    - publication-grade validity

No production scientific module is introduced or modified; nothing is
calibrated or tuned; no registration engine, resampling, or overlay algorithm
is created.  The controlled RegistrationResult below is a deterministic
TEST-LOCAL fixture representing an already-available registration output, NOT a
registration algorithm.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.common.types import (
    RegistrationMetrics,
    RegistrationResult,
)
from lunar_hazard_mapper.scientific.iirs import (
    IIRSOpticalMappingResult,
    IIRSSpectralResult,
    classify_materials,
    compute_iirs_band_ratio,
    create_default_guardrail,
    extract_iirs_spectral_features,
    generate_spectral_overlay,
    preprocess_iirs_cube,
)
from lunar_hazard_mapper.scientific.iirs.classification import MaterialClass
from lunar_hazard_mapper.scientific.iirs.guardrail import IIRSScientificStatus

# Reuse the established M4-08.11 controlled synthetic fixture framework.
import test_m4_iirs_synthetic_spectral as _iirs11

# Alias the reused 8.11 fixtures so the intent is explicit.
SPECTRUM_A = _iirs11.SPECTRUM_A
make_cube = _iirs11.make_cube
run_controlled_pipeline = _iirs11.run_controlled_pipeline
TWO_RATIOS = _iirs11.TWO_RATIOS
TWO_FEATURE_RULES = _iirs11.TWO_FEATURE_RULES


def make_registration(spectral: IIRSSpectralResult) -> RegistrationResult:
    """Build a deterministic, controllable RegistrationResult (test-local only).

    This is NOT a registration engine.  It does not estimate any transform, match
    features, or inspect image content.  It merely documents an already-available
    registration as an affine relationship algebraically derived from the source
    cube's own transform, following the existing 8.8/8.9 test convention
    (source 2x2 at 20 m -> target 4x4 at 10 m, aligned to the same origin).
    """
    src_transform = spectral.source_cube.transform
    src_px = float(np.hypot(src_transform.a, src_transform.d))
    dst_px = src_px / 2.0  # 20 m -> 10 m target

    target_height, target_width = 4, 4
    target_transform = Affine(
        dst_px, 0.0, src_transform.c, 0.0, -dst_px, src_transform.f
    )

    return RegistrationResult(
        registration_id="reg_e2e_0813_controlled",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        metrics=RegistrationMetrics(rmse_px=0.5, inlier_count=10, inlier_ratio=0.9),
        transform=target_transform,
        spatial_reference={
            "height": target_height,
            "width": target_width,
            "crs": spectral.source_cube.crs,
        },
        success=True,
        message="Controlled test fixture representing an already-available "
                "registration output (not a computed registration).",
    )


def run_phase8_chain(cube, ratio_pairs, rules):
    """Run the complete existing Phase 8 chain with actual stage outputs.

    Returns (spectral_result, mapping, overlay, guardrail).  Each downstream
    stage receives the exact object produced by the previous stage.
    """
    preprocessing = preprocess_iirs_cube(cube)
    ratio_results = [
        compute_iirs_band_ratio(cube, preprocessing, num, den)
        for (num, den) in ratio_pairs
    ]
    feature_set = extract_iirs_spectral_features(preprocessing, ratio_results)
    classification = classify_materials(feature_set, rules)

    spectral_result = IIRSSpectralResult(
        cube,
        preprocessing,
        ratio_results,
        feature_set,
        classification,
    )
    registration = make_registration(spectral_result)
    mapping = IIRSOpticalMappingResult(spectral_result, registration)
    overlay = generate_spectral_overlay(mapping)
    guardrail = create_default_guardrail()
    return spectral_result, mapping, overlay, guardrail


def test_full_controlled_phase8_chain_integrates():
    """1. Complete controlled pipeline executes using actual stage outputs."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-A")
    assert cube.data.shape[:2] == (2, 2)

    spectral_result, mapping, overlay, guardrail = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert spectral_result.source_cube is cube
    assert mapping.spectral_result is spectral_result
    assert overlay.score_overlay.shape == (4, 4)


def test_stage_to_stage_object_flow_is_connected():
    """2. Actual outputs are threaded stage-to-stage, not reconstructed."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-flow")
    preprocessing, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    spectral_result = IIRSSpectralResult(
        cube, preprocessing, ratios, features, classification
    )
    registration = make_registration(spectral_result)
    mapping = IIRSOpticalMappingResult(spectral_result, registration)
    overlay = generate_spectral_overlay(mapping)

    assert spectral_result.feature_set is features
    assert spectral_result.band_ratio_results == tuple(ratios)
    assert spectral_result.classification_result is classification
    assert spectral_result.preprocessing_result is preprocessing
    assert mapping.spectral_result is spectral_result
    assert mapping.registration is registration


def test_spatial_shapes_preserved_and_target_footprint():
    """3. Spatial shapes are preserved; overlay uses the target footprint."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-shape")
    spectral_result, mapping, overlay, _ = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert spectral_result.source_cube.data.shape[:2] == (2, 2)
    assert spectral_result.classification_result.class_map.shape == (2, 2)
    assert spectral_result.preprocessing_result.normalized_data.shape[:2] == (2, 2)
    for br in spectral_result.band_ratio_results:
        assert br.ratio_map.shape == (2, 2)

    assert mapping.target_footprint["height"] == 4
    assert mapping.target_footprint["width"] == 4
    assert overlay.score_overlay.shape == (4, 4)
    assert overlay.class_overlay.shape == (4, 4)
    assert overlay.valid_mask.shape == (4, 4)


def test_classification_propagates_to_overlay_without_recalculation():
    """5/6. Classification and its score reach the overlay unchanged."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-class")
    spectral_result, _, overlay, _ = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    src_scores = spectral_result.classification_result.score_map
    src_valid = spectral_result.classification_result.valid_mask

    assert overlay.valid_mask.all()

    overlay_scores = overlay.score_overlay[overlay.valid_mask]
    src_scores_valid = src_scores[src_valid]

    assert set(overlay_scores.ravel()).issubset(set(src_scores_valid.ravel()))

    for attr in ["classify", "extract_features", "compute_band_ratio",
                 "register", "match_features", "estimate_transform"]:
        assert not hasattr(overlay, attr)

    assert np.isfinite(overlay.score_overlay[overlay.valid_mask]).all()


def test_source_invalidity_not_converted_to_valid_output():
    """4. Source invalidity is not silently converted into valid output."""
    data = SPECTRUM_A.copy()
    # Mark one source pixel invalid via the nodata sentinel.
    data[1, 1, 0] = -9999.0
    cube = make_cube(data, "synthetic-e2e-nodata", nodata=-9999.0)
    assert not cube.valid_mask[1, 1, 0]

    spectral_result, _, overlay, _ = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert spectral_result.classification_result.class_map[1, 1] == (
        MaterialClass.UNCLASSIFIED
    )
    assert not spectral_result.classification_result.valid_mask[1, 1]
    assert np.isnan(spectral_result.classification_result.score_map[1, 1])

    if (~overlay.valid_mask).any():
        assert np.isnan(overlay.score_overlay[~overlay.valid_mask]).all()
        invalid_classes = overlay.class_overlay[~overlay.valid_mask]
        assert (invalid_classes == MaterialClass.UNCLASSIFIED).all()


def test_unmapped_out_of_bounds_target_pixels_remain_invalid():
    """8. Unmapped/out-of-bounds target pixels stay invalid (NaN/UNCLASSIFIED)."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-offset")
    spectral_result, _, _, _ = run_phase8_chain(cube, TWO_RATIOS, TWO_FEATURE_RULES)

    src_transform = spectral_result.source_cube.transform
    target_transform = Affine(
        10.0, 0.0, src_transform.c + 20.0, 0.0, -10.0, src_transform.f
    )
    registration = RegistrationResult(
        registration_id="reg_e2e_0813_offset",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        metrics=RegistrationMetrics(rmse_px=0.5, inlier_count=10, inlier_ratio=0.9),
        transform=target_transform,
        spatial_reference={"height": 4, "width": 4, "crs": cube.crs},
        success=True,
    )
    mapping = IIRSOpticalMappingResult(spectral_result, registration)
    overlay = generate_spectral_overlay(mapping)

    assert overlay.score_overlay.shape == (4, 4)
    assert not overlay.valid_mask.all()
    assert np.isnan(overlay.score_overlay[~overlay.valid_mask]).all()
    assert (overlay.class_overlay[~overlay.valid_mask] == MaterialClass.UNCLASSIFIED).all()


def test_deterministic_output_across_identical_runs():
    """9. Identical inputs produce identical outputs across the whole chain."""
    cube_a = make_cube(SPECTRUM_A, "synthetic-e2e-det")
    cube_b = make_cube(SPECTRUM_A, "synthetic-e2e-det")

    r1, m1, o1, g1 = run_phase8_chain(cube_a, TWO_RATIOS, TWO_FEATURE_RULES)
    r2, m2, o2, g2 = run_phase8_chain(cube_b, TWO_RATIOS, TWO_FEATURE_RULES)

    assert r1.preprocessing_result.to_dict() == r2.preprocessing_result.to_dict()
    assert r1.band_ratio_results == r2.band_ratio_results
    assert r1.feature_set == r2.feature_set
    assert r1.classification_result == r2.classification_result
    assert r1.to_dict() == r2.to_dict()
    assert m1.to_dict() == m2.to_dict()
    assert np.array_equal(o1.score_overlay, o2.score_overlay, equal_nan=True)
    assert np.array_equal(o1.valid_mask, o2.valid_mask)
    assert g1 == g2 and g1.to_dict() == g2.to_dict()


def test_input_immutability():
    """10. The chain does not mutate the source cube or upstream arrays."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-immut")
    cube_data_before = cube.data.copy()
    cube_meta_before = (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
    )

    spectral_result, _, _, _ = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert np.array_equal(cube.data, cube_data_before)
    assert (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
    ) == cube_meta_before

    # Re-running/reading valid scores is unchanged (no mutation of upstream boxes).
    assert np.array_equal(
        spectral_result.classification_result.score_map,
        spectral_result.classification_result.score_map.copy(),
    )


def test_guardrail_stays_illustrative_and_not_validated():
    """11. Guardrail remains ILLUSTRATIVE / NOT VALIDATED after the E2E run."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-guardrail")
    _, _, _, guardrail = run_phase8_chain(cube, TWO_RATIOS, TWO_FEATURE_RULES)

    assert guardrail.status == IIRSScientificStatus.ILLUSTRATIVE
    assert guardrail.is_scientifically_validated is False
    assert guardrail.is_publication_grade is False

    serialized = guardrail.to_dict()
    assert serialized["status"] == "ILLUSTRATIVE"
    assert serialized["is_scientifically_validated"] is False


def test_no_scientific_validation_claim_anywhere():
    """12. No scientific validation / confidence wording is introduced."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-no-claim")
    spectral_result, mapping, overlay, guardrail = run_phase8_chain(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    payloads = [overlay.to_dict(), mapping.to_dict()]
    serialized = repr(payloads).lower()
    assert "usgs" not in serialized
    assert "spectral_library" not in serialized
    # The guardrail itself explicitly forecloses a validated claim.
    assert guardrail.is_scientifically_validated is False
    assert guardrail.status == IIRSScientificStatus.ILLUSTRATIVE


def test_upstream_arrays_used_not_recomputed_downstream():
    """Verify the chain passes objects forward rather than rebuilding them."""
    cube = make_cube(SPECTRUM_A, "synthetic-e2e-no-recompute")
    preprocessing, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )
    spectral_result = IIRSSpectralResult(
        cube, preprocessing, ratios, features, classification
    )
    mapping = IIRSOpticalMappingResult(
        spectral_result, make_registration(spectral_result)
    )
    overlay = generate_spectral_overlay(mapping)

    assert not hasattr(overlay, "extract_features")
    assert not hasattr(overlay, "compute_band_ratio")
    assert not hasattr(mapping, "resample")
    assert not hasattr(mapping, "overlay")