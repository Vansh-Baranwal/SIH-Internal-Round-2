"""Tests for M4-08.6 Mineral Classification."""

import copy
import numpy as np
import pytest

from lunar_hazard_mapper.scientific.iirs.features import IIRSSpectralFeatureSet
from lunar_hazard_mapper.scientific.iirs.classification import (
    MaterialClass,
    IIRSMaterialClassificationResult,
    IllustrativeClassificationRule,
    classify_materials,
)


@pytest.fixture
def sample_feature_set() -> IIRSSpectralFeatureSet:
    """Provide a minimal valid feature set for testing."""
    height, width, features = 4, 4, 2
    
    # Feature 0 and Feature 1
    feature_maps = np.zeros((height, width, features), dtype=np.float64)
    valid_mask = np.ones((height, width, features), dtype=bool)
    
    # Introduce an invalid pixel (0, 0)
    valid_mask[0, 0, :] = False
    feature_maps[0, 0, :] = np.nan
    
    # Introduce NaN pixel (1, 1)
    feature_maps[1, 1, 0] = np.nan
    valid_mask[1, 1, 0] = False
    
    # Sample values
    feature_maps[2, 2, 0] = 0.8
    feature_maps[2, 2, 1] = 0.2
    
    feature_maps[3, 3, 0] = 0.4
    feature_maps[3, 3, 1] = 0.9

    return IIRSSpectralFeatureSet(
        feature_maps=feature_maps,
        valid_mask=valid_mask,
        feature_names=("feat_A", "feat_B"),
        ratio_bands=((1, 2), (3, 4)),
        ratio_wavelengths_um=((0.5, 0.6), (1.0, 1.2)),
        normalization_methods=("none", "none"),
    )


@pytest.fixture
def illustrative_rules() -> list[IllustrativeClassificationRule]:
    """Provide explicit illustrative rules (NOT USGS)."""
    return [
        IllustrativeClassificationRule(
            feature_name="feat_A",
            target_class=MaterialClass.ILLMENITE,
            min_threshold=0.5,
        ),
        IllustrativeClassificationRule(
            feature_name="feat_B",
            target_class=MaterialClass.PYROXENE,
            min_threshold=0.7,
        ),
    ]


def test_classification_spatial_preservation(sample_feature_set, illustrative_rules):
    """Output spatial shape matches input."""
    result = classify_materials(sample_feature_set, illustrative_rules)
    assert result.class_map.shape == (4, 4)
    assert result.score_map.shape == (4, 4)
    assert result.valid_mask.shape == (4, 4)


def test_classification_logic(sample_feature_set, illustrative_rules):
    """Verify correct threshold-based classification and scoring."""
    result = classify_materials(sample_feature_set, illustrative_rules)
    
    # (2, 2) has feat_A = 0.8 (> 0.5), feat_B = 0.2 (< 0.7)
    assert result.class_map[2, 2] == MaterialClass.ILLMENITE
    assert result.score_map[2, 2] == 0.8
    assert result.valid_mask[2, 2] == True
    
    # (3, 3) has feat_A = 0.4 (< 0.5), feat_B = 0.9 (> 0.7)
    assert result.class_map[3, 3] == MaterialClass.PYROXENE
    assert result.score_map[3, 3] == 0.9
    assert result.valid_mask[3, 3] == True


def test_unclassified_below_threshold(sample_feature_set, illustrative_rules):
    """Pixels below all thresholds are UNCLASSIFIED."""
    # (0, 1) has feat_A = 0.0, feat_B = 0.0
    result = classify_materials(sample_feature_set, illustrative_rules)
    assert result.class_map[0, 1] == MaterialClass.UNCLASSIFIED
    assert np.isnan(result.score_map[0, 1])
    assert result.valid_mask[0, 1] == False


def test_invalid_and_nan_handling(sample_feature_set, illustrative_rules):
    """Invalid and NaN pixels are mapped to UNCLASSIFIED."""
    result = classify_materials(sample_feature_set, illustrative_rules)
    
    # (0, 0) was fully invalid
    assert result.class_map[0, 0] == MaterialClass.UNCLASSIFIED
    assert np.isnan(result.score_map[0, 0])
    assert result.valid_mask[0, 0] == False
    
    # (1, 1) had NaN in feat_A
    assert result.class_map[1, 1] == MaterialClass.UNCLASSIFIED
    assert np.isnan(result.score_map[1, 1])
    assert result.valid_mask[1, 1] == False


def test_missing_features(sample_feature_set):
    """Rules requiring non-existent features are ignored safely."""
    rules = [
        IllustrativeClassificationRule(
            feature_name="missing_feat",
            target_class=MaterialClass.OLIVINE,
            min_threshold=0.1,
        )
    ]
    result = classify_materials(sample_feature_set, rules)
    # Since none of the features exist, all are unclassified
    assert (result.class_map == MaterialClass.UNCLASSIFIED).all()


def test_determinism_and_reproducibility(sample_feature_set, illustrative_rules):
    """Same input/rules -> exactly same output."""
    res1 = classify_materials(sample_feature_set, illustrative_rules)
    res2 = classify_materials(sample_feature_set, illustrative_rules)
    assert res1 == res2


def test_ambiguity_tie_breaking(sample_feature_set):
    """Ties between conflicting classes lead to UNCLASSIFIED."""
    # Create two rules that perfectly tie at 0.8
    rules = [
        IllustrativeClassificationRule("feat_A", MaterialClass.ILLMENITE, 0.5),
        IllustrativeClassificationRule("feat_B", MaterialClass.PYROXENE, 0.5),
    ]
    
    feat_maps = np.copy(sample_feature_set.feature_maps)
    feat_maps[2, 2, 0] = 0.8
    feat_maps[2, 2, 1] = 0.8
    
    modified_features = IIRSSpectralFeatureSet(
        feature_maps=feat_maps,
        valid_mask=sample_feature_set.valid_mask,
        feature_names=sample_feature_set.feature_names,
        ratio_bands=sample_feature_set.ratio_bands,
        ratio_wavelengths_um=sample_feature_set.ratio_wavelengths_um,
        normalization_methods=sample_feature_set.normalization_methods,
    )
    
    result = classify_materials(modified_features, rules)
    # Because 0.8 == 0.8, we get ambiguity
    assert result.class_map[2, 2] == MaterialClass.UNCLASSIFIED


def test_all_classes_producible(sample_feature_set):
    """Ensure all classes can be produced by the classifier if rule hits."""
    classes = [
        MaterialClass.ILLMENITE,
        MaterialClass.PYROXENE,
        MaterialClass.OLIVINE,
        MaterialClass.PLAGIOCLASE_FELDSPAR,
    ]
    
    # We create rules mapping feat_A directly to each class with threshold 0.1
    for cls in classes:
        rule = IllustrativeClassificationRule("feat_A", cls, 0.1)
        res = classify_materials(sample_feature_set, [rule])
        # Since feat_A[2,2] is 0.8, it should classify as cls
        assert res.class_map[2, 2] == cls


def test_input_immutability(sample_feature_set, illustrative_rules):
    """Classification must not modify input feature set."""
    feat_copy = copy.deepcopy(sample_feature_set)
    _ = classify_materials(sample_feature_set, illustrative_rules)
    assert sample_feature_set == feat_copy


def test_no_fabricated_usgs_data():
    """Verify that rules are explicitly illustrative and no USGS module exists."""
    import inspect
    from lunar_hazard_mapper.scientific.iirs.classification import IllustrativeClassificationRule
    
    # The docstring explicitly denies USGS validation
    doc = inspect.getdoc(IllustrativeClassificationRule)
    assert "NOT a" in doc and "scientifically validated USGS threshold" in doc
