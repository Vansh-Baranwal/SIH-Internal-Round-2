"""M4-08.11 Controlled / synthetic spectral pipeline tests.

This module is a TESTING/VERIFICATION layer for the ALREADY-IMPLEMENTED
IIRS spectral pipeline:

    8.4 band-ratio logic -> 8.5 feature extraction -> 8.6 classification

It feeds small, explicitly synthetic, deterministic numerical fixtures through
the existing public API and asserts the expected IMPLEMENTATION BEHAVIOUR that
is derived directly from the existing 8.4-8.6 code.  The fixtures are NOT real
IIRS measurements, NOT laboratory spectra, NOT USGS reference spectra, and NOT
mineral ground truth.  No production scientific module is introduced or
modified; nothing is calibrated or tuned; nothing is scientifically validated.

Passing these controlled synthetic tests demonstrates deterministic software
behaviour for the tested synthetic inputs.  It does NOT constitute scientific,
mineralogical, USGS, laboratory, mission, or publication-grade validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from affine import Affine

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lunar_hazard_mapper.scientific.iirs import (
    IIRSCube,
    classify_materials,
    compute_iirs_band_ratio,
    create_default_guardrail,
    extract_iirs_spectral_features,
    preprocess_iirs_cube,
)
from lunar_hazard_mapper.scientific.iirs.classification import (
    IllustrativeClassificationRule,
    MaterialClass,
)
from lunar_hazard_mapper.scientific.iirs.guardrail import IIRSScientificStatus


# ---------------------------------------------------------------------------
# Controlled fixture factories
# ---------------------------------------------------------------------------
# All fixtures are explicitly synthetic.  The spatial footprint is (2, 2) so the
# expected shapes ((2,2), (2,2), (2,2,2), (2,2)) are easy to inspect by hand.
_WAVELENGTHS_UM = np.array([0.8, 1.2, 2.0], dtype=np.float32)


def make_cube(data: np.ndarray, name: str, nodata: float | None = -9999.0) -> IIRSCube:
    """Return a small controlled synthetic IIRS cube, not a real measurement."""
    return IIRSCube(
        data=np.asarray(data, dtype=np.float32),
        wavelengths_um=_WAVELENGTHS_UM,
        pixel_size_m=20.0,
        transform=Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
        crs="LOCAL_METER_FRAME",
        nodata=nodata,
        dataset_name=name,
        sensor="IIRS",
        observation_date="2026-01-01",
        orbit_id="fixture-orbit",
        notes="Controlled synthetic test data only; not a real IIRS measurement.",
        extra={"synthetic": True, "controlled_test": True},
    )


def corrupt(cube: IIRSCube, **changes: object) -> IIRSCube:
    """Inject deliberately invalid data without changing production contracts."""
    for attribute, value in changes.items():
        object.__setattr__(cube, attribute, value)
    return cube


def run_controlled_pipeline(cube, ratio_pairs, rules):
    """Drive the existing 8.3->8.4->8.5->8.6 chain on a controlled cube.

    Returns (preprocessed, ratio_results, feature_set, classification).
    The existing public implementation is only CALLED, never modified.
    """
    preprocessed = preprocess_iirs_cube(cube)
    ratio_results = [
        compute_iirs_band_ratio(cube, preprocessed, num, den)
        for (num, den) in ratio_pairs
    ]
    feature_set = extract_iirs_spectral_features(preprocessed, ratio_results)
    classification = classify_materials(feature_set, rules)
    return preprocessed, ratio_results, feature_set, classification


# ---------------------------------------------------------------------------
# Controlled numerical fixtures (shape (2,2,3): height, width, bands)
# ---------------------------------------------------------------------------

# Spectrum A: min 0, max 8 -> normalized = raw / 8.
#   pixel values = [band0, band1, band2]
#   band0n=[[0.5,1.0],[0.75,0.25]]  band1n=[[0.25,0.5],[0.375,0.125]]
#   ratio(0,1)=2.0 everywhere ; ratio(1,0)=0.5 everywhere.
SPECTRUM_A = np.array(
    [
        [[4.0, 2.0, 0.0], [8.0, 4.0, 0.0]],   # row 0
        [[6.0, 3.0, 0.0], [2.0, 1.0, 0.0]],   # row 1
    ],
    dtype=np.float32,
)

# Spectrum B: min 0, max 8.  Bands 0 and 1 are swapped versus Spectrum A.
#   ratio(0,1)=0.5 everywhere ; ratio(1,0)=2.0 everywhere.
SPECTRUM_B = np.array(
    [
        [[2.0, 4.0, 0.0], [4.0, 8.0, 0.0]],   # row 0
        [[3.0, 6.0, 0.0], [1.0, 2.0, 0.0]],   # row 1
    ],
    dtype=np.float32,
)

# Two-feature illustrative rules (engineering configuration, NOT USGS).
_RULE_PYROXENE = IllustrativeClassificationRule(
    feature_name="ratio_band_0_over_band_1",
    target_class=MaterialClass.PYROXENE,
    min_threshold=1.5,
)
_RULE_ILLMENITE = IllustrativeClassificationRule(
    feature_name="ratio_band_1_over_band_0",
    target_class=MaterialClass.ILLMENITE,
    min_threshold=0.6,
)
TWO_FEATURE_RULES = [_RULE_PYROXENE, _RULE_ILLMENITE]

# The two ratio maps we feed through the pipeline for the two-feature cases.
TWO_RATIOS = [(0, 1), (1, 0)]

# ---------------------------------------------------------------------------
# 1. Known valid controlled spectrum A -> expected implementation behaviour
# ---------------------------------------------------------------------------

def test_controlled_spectrum_A_full_chain_expected_behaviour():
    cube = make_cube(SPECTRUM_A, "synthetic-spectrum-A")
    assert cube.data.shape[:2] == (2, 2)

    preprocessed, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    # 8.4 band-ratio behaviour derived from normalized values.
    assert ratios[0].ratio_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]
    assert ratios[1].ratio_map.tolist() == [[0.5, 0.5], [0.5, 0.5]]
    assert ratios[0].valid_mask.all()

    # 8.5 feature maps reuse the ratio maps without recalculation.
    assert features.feature_maps.shape == (2, 2, 2)
    assert features.feature_maps[:, :, 0].tolist() == [[2.0, 2.0], [2.0, 2.0]]
    assert features.feature_maps[:, :, 1].tolist() == [[0.5, 0.5], [0.5, 0.5]]

    # 8.6 existing rule outcome: feature0 (2.0 >= 1.5) wins -> PYROXENE.
    assert classification.class_map.shape == (2, 2)
    assert (classification.class_map == MaterialClass.PYROXENE).all()
    assert classification.valid_mask.all()
    assert classification.score_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]

    assert preprocessed.valid_mask.all()


# ---------------------------------------------------------------------------
# 2. A second distinct controlled spectrum -> different existing rule outcome
# ---------------------------------------------------------------------------

def test_controlled_spectrum_B_different_rule_outcome():
    cube = make_cube(SPECTRUM_B, "synthetic-spectrum-B")

    _, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    # 8.4: swapped bands invert the ratio probe.
    assert ratios[0].ratio_map.tolist() == [[0.5, 0.5], [0.5, 0.5]]
    assert ratios[1].ratio_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]
    assert features.feature_maps[:, :, 0].tolist() == [[0.5, 0.5], [0.5, 0.5]]
    assert features.feature_maps[:, :, 1].tolist() == [[2.0, 2.0], [2.0, 2.0]]

    # 8.6: feature1 (2.0 >= 0.6) now wins -> ILLMENITE, a different class.
    assert (classification.class_map == MaterialClass.ILLMENITE).all()
    assert classification.score_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]
    assert classification.valid_mask.all()


# ---------------------------------------------------------------------------
# 3. Below-threshold -> existing UNCLASSIFIED behaviour
# ---------------------------------------------------------------------------

def test_controlled_below_threshold_is_unclassified():
    # Spectrum A feature0 == 2.0 anywhere.  A threshold above 2.0 (2.5) leaves
    # every pixel below it -> UNCLASSIFIED.
    cube = make_cube(SPECTRUM_A, "synthetic-below-threshold")
    rule = IllustrativeClassificationRule(
        feature_name="ratio_band_0_over_band_1",
        target_class=MaterialClass.PYROXENE,
        min_threshold=2.5,
    )

    _, _, _, classification = run_controlled_pipeline(cube, [(0, 1)], [rule])

    assert (classification.class_map == MaterialClass.UNCLASSIFIED).all()
    assert not classification.valid_mask.any()
    assert np.isnan(classification.score_map).all()


# ---------------------------------------------------------------------------
# 4. Boundary-threshold -> exact inclusive (>=) behaviour of the implementation
# ---------------------------------------------------------------------------

def test_controlled_boundary_threshold_is_inclusive():
    # The classifier defines passes_threshold as feat >= threshold.  With a
    # threshold exactly equal to the feature value (2.0), the pixel IS
    # classified (not UNCLASSIFIED), because the comparison is inclusive.
    cube = make_cube(SPECTRUM_A, "synthetic-boundary-threshold")
    rule = IllustrativeClassificationRule(
        feature_name="ratio_band_0_over_band_1",
        target_class=MaterialClass.PYROXENE,
        min_threshold=2.0,
    )

    _, _, _, classification = run_controlled_pipeline(cube, [(0, 1)], [rule])

    assert (classification.class_map == MaterialClass.PYROXENE).all()
    assert classification.valid_mask.all()
    assert classification.score_map.tolist() == [[2.0, 2.0], [2.0, 2.0]]


# ---------------------------------------------------------------------------
# 5. Invalid / non-finite source values -> propagate as UNCLASSIFIED
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_source_value_propagates_to_unclassified(invalid_value):
    cube = make_cube(SPECTRUM_A, "synthetic-nonfinite")
    data = cube.data.copy()
    data[1, 1, 0] = invalid_value
    # IIRSCube rejects inf at construction, so bypass via the test-only setter
    # used consistently by the other IIRS test modules.
    cube = corrupt(cube, data=data, dataset_name="synthetic-nonfinite")

    _, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    # The corrupted sample is invalid through band-ratio -> feature -> class.
    assert not ratios[0].valid_mask[1, 1]
    assert np.isnan(ratios[0].ratio_map[1, 1])
    assert not features.valid_mask[1, 1, 0]
    assert classification.class_map[1, 1] == MaterialClass.UNCLASSIFIED
    assert not classification.valid_mask[1, 1]
    assert np.isnan(classification.score_map[1, 1])

    # A still-valid pixel is unaffected and keeps its expected implementation
    # outcome (PYROXENE), confirming the invalidity is localized not global.
    assert classification.class_map[0, 0] == MaterialClass.PYROXENE
    assert classification.valid_mask[0, 0]


# ---------------------------------------------------------------------------
# 6. Masked / nodata case -> invalidity propagates through existing pipeline
# ---------------------------------------------------------------------------

def test_nodata_sentinel_propagates_to_unclassified():
    data = SPECTRUM_A.copy()
    # Mark one sample as the nodata sentinel so cube.valid_mask is False there.
    data[0, 1, 0] = -9999.0
    cube = make_cube(data, "synthetic-nodata", nodata=-9999.0)
    assert not cube.valid_mask[0, 1, 0]

    _, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert not ratios[0].valid_mask[0, 1]
    assert np.isnan(ratios[0].ratio_map[0, 1])
    assert not features.valid_mask[0, 1, 0]
    assert classification.class_map[0, 1] == MaterialClass.UNCLASSIFIED
    assert not classification.valid_mask[0, 1]
    assert np.isnan(classification.score_map[0, 1])


# ---------------------------------------------------------------------------
# 7. Repeated identical input -> exact deterministic result across runs
# ---------------------------------------------------------------------------

def test_repeated_identical_input_is_deterministic():
    cube_a = make_cube(SPECTRUM_A, "synthetic-det-a")
    cube_b = make_cube(SPECTRUM_A, "synthetic-det-b")

    run1 = run_controlled_pipeline(cube_a, TWO_RATIOS, TWO_FEATURE_RULES)
    run2 = run_controlled_pipeline(cube_b, TWO_RATIOS, TWO_FEATURE_RULES)

    for r1, r2 in zip(run1[1], run2[1]):
        assert r1 == r2
        assert r1.to_dict() == r2.to_dict()
    assert run1[2] == run2[2]
    assert run1[3] == run2[3]
    # Preprocessing serialization is also deterministic.
    assert run1[0].to_dict() == run2[0].to_dict()


# ---------------------------------------------------------------------------
# 8. Invalid structural input -> existing validation/rejection behaviour
# ---------------------------------------------------------------------------

def test_invalid_band_index_is_rejected():
    cube = make_cube(SPECTRUM_A, "synthetic-bad-band")
    preprocessed = preprocess_iirs_cube(cube)
    # Only 3 bands exist; band index 9 must be rejected by the existing API.
    with pytest.raises(ValueError):
        compute_iirs_band_ratio(cube, preprocessed, 0, 9)


def test_band_count_wavelength_mismatch_is_rejected():
    # A cube whose wavelengths length does not match its band count must fail
    # at the existing structural contract.
    with pytest.raises(ValueError):
        IIRSCube(
            data=SPECTRUM_A.copy(),
            wavelengths_um=np.array([0.8, 1.2], dtype=np.float32),  # wrong length
            pixel_size_m=20.0,
            transform=Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
            crs="LOCAL_METER_FRAME",
            nodata=-9999.0,
            dataset_name="synthetic-bad-wavelengths",
        )


def test_classify_materials_rejects_non_feature_set():
    with pytest.raises(TypeError):
        classify_materials("not-a-feature-set", TWO_FEATURE_RULES)


# ---------------------------------------------------------------------------
# 9. Spatial shape preservation through the controlled pipeline
# ---------------------------------------------------------------------------

def test_spatial_shape_preserved_through_pipeline():
    cube = make_cube(SPECTRUM_A, "synthetic-shapes")
    assert cube.data.shape[:2] == (2, 2)

    preprocessed, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )

    assert preprocessed.normalized_data.shape == (2, 2, 3)
    assert len(ratios) == 2
    assert all(r.ratio_map.shape == (2, 2) for r in ratios)
    assert features.feature_maps.shape == (2, 2, 2)
    assert features.valid_mask.shape == (2, 2, 2)
    assert classification.class_map.shape == (2, 2)
    assert classification.score_map.shape == (2, 2)
    assert classification.valid_mask.shape == (2, 2)


# ---------------------------------------------------------------------------
# 10. Input immutability -> existing pipeline does not mutate source inputs
# ---------------------------------------------------------------------------

def test_controlled_pipeline_does_not_mutate_inputs():
    cube = make_cube(SPECTRUM_A, "synthetic-immutability")
    original_cube_data = cube.data.copy()
    original_cube_metadata = (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        dict(cube.extra),
    )
    preprocessed, ratios, features, classification = run_controlled_pipeline(
        cube, TWO_RATIOS, TWO_FEATURE_RULES
    )
    original_pre = (preprocessed.normalized_data.copy(), preprocessed.valid_mask.copy())
    original_ratios = [(r.ratio_map.copy(), r.valid_mask.copy()) for r in ratios]
    original_features = (features.feature_maps.copy(), features.valid_mask.copy())
    original_classes = (
        classification.class_map.copy(),
        classification.score_map.copy(),
        classification.valid_mask.copy(),
    )

    # Re-running is a read-only no-op exercise of the existing pipeline.
    run_controlled_pipeline(cube, TWO_RATIOS, TWO_FEATURE_RULES)

    assert np.array_equal(cube.data, original_cube_data)
    assert (
        cube.pixel_size_m,
        tuple(cube.transform),
        cube.crs,
        cube.nodata,
        cube.dataset_name,
        cube.sensor,
        cube.observation_date,
        cube.orbit_id,
        cube.notes,
        dict(cube.extra),
    ) == original_cube_metadata
    assert np.array_equal(preprocessed.normalized_data, original_pre[0])
    assert np.array_equal(preprocessed.valid_mask, original_pre[1])
    for i, (rm, vm) in enumerate(original_ratios):
        assert np.array_equal(ratios[i].ratio_map, rm)
        assert np.array_equal(ratios[i].valid_mask, vm)
    assert np.array_equal(features.feature_maps, original_features[0])
    assert np.array_equal(features.valid_mask, original_features[1])
    assert np.array_equal(classification.class_map, original_classes[0])
    assert np.array_equal(classification.score_map, original_classes[1])
    assert np.array_equal(classification.valid_mask, original_classes[2])


# ---------------------------------------------------------------------------
# 11. 8.10 guardrail stays ILLUSTRATIVE / NOT VALIDATED after synthetic runs
# ---------------------------------------------------------------------------

def test_synthetic_pipeline_does_not_change_guardrail_status():
    # Running the controlled pipeline must not silently upgrade the 8.10
    # scientific status.  The current Phase-8 default remains ILLUSTRATIVE and
    # NOT SCIENTIFICALLY VALIDATED.
    run_controlled_pipeline(
        make_cube(SPECTRUM_A, "synthetic-guardrail-a"), TWO_RATIOS, TWO_FEATURE_RULES
    )
    run_controlled_pipeline(
        make_cube(SPECTRUM_B, "synthetic-guardrail-b"), TWO_RATIOS, TWO_FEATURE_RULES
    )

    guardrail = create_default_guardrail()
    assert guardrail.status == IIRSScientificStatus.ILLUSTRATIVE
    assert guardrail.is_scientifically_validated is False
    assert guardrail.is_publication_grade is False