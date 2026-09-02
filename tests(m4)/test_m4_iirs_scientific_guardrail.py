"""Tests for M4-08.10 Scientific Guardrails.

These tests verify that IIRS spectral outputs are explicitly qualified as
ILLUSTRATIVE and NOT SCIENTIFICALLY VALIDATED, without modifying any
upstream classification, overlay, or registration logic.
"""

import copy
import numpy as np
import pytest
from affine import Affine

from lunar_hazard_mapper.scientific.iirs.guardrail import (
    IIRSScientificStatus,
    IIRSScientificGuardrail,
    create_default_guardrail,
    _DEFAULT_LIMITATION_STATEMENT,
)
from lunar_hazard_mapper.scientific.iirs.classification import (
    IIRSMaterialClassificationResult,
    MaterialClass,
    IllustrativeClassificationRule,
    classify_materials,
)
from lunar_hazard_mapper.scientific.iirs.features import IIRSSpectralFeatureSet
from lunar_hazard_mapper.scientific.iirs.overlay import (
    SpectralOverlayResult,
)


# ---------------------------------------------------------------------------
# Helpers — minimal deterministic fixtures
# ---------------------------------------------------------------------------

def _make_classification_result():
    """Build a minimal valid IIRSMaterialClassificationResult."""
    height, width = 2, 2
    class_map = np.full((height, width), MaterialClass.PYROXENE, dtype=object)
    score_map = np.array([[0.8, 0.6], [0.7, 0.9]], dtype=np.float64)
    valid_mask = np.ones((height, width), dtype=bool)
    return IIRSMaterialClassificationResult(
        class_map=class_map,
        score_map=score_map,
        valid_mask=valid_mask,
    )


def _make_overlay_result():
    """Build a minimal valid SpectralOverlayResult."""
    height, width = 2, 2
    score_overlay = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    class_overlay = np.full((height, width), MaterialClass.ILLMENITE, dtype=object)
    valid_mask = np.ones((height, width), dtype=bool)
    return SpectralOverlayResult(
        score_overlay=score_overlay,
        class_overlay=class_overlay,
        valid_mask=valid_mask,
        target_transform=Affine(50.0, 0.0, 0.0, 0.0, -50.0, 200.0),
        target_crs="EPSG:32618",
        source_sensor="IIRS",
        reference_sensor="OHRC",
        registration_id="reg_guardrail_test",
    )


# ---------------------------------------------------------------------------
# 1. Current IIRS output defaults to ILLUSTRATIVE
# ---------------------------------------------------------------------------

def test_default_status_is_illustrative():
    guardrail = create_default_guardrail()
    assert guardrail.status == IIRSScientificStatus.ILLUSTRATIVE


# ---------------------------------------------------------------------------
# 2. Current output explicitly reports NOT_SCIENTIFICALLY_VALIDATED
# ---------------------------------------------------------------------------

def test_not_scientifically_validated():
    guardrail = create_default_guardrail()
    assert guardrail.is_scientifically_validated is False
    assert "NOT been scientifically validated" in guardrail.limitation_statement


# ---------------------------------------------------------------------------
# 3. Current output explicitly reports NOT_FOR_PUBLICATION_GRADE_USE
# ---------------------------------------------------------------------------

def test_not_publication_grade():
    guardrail = create_default_guardrail()
    assert guardrail.is_publication_grade is False
    assert "publication-grade mineral identification" in guardrail.limitation_statement


# ---------------------------------------------------------------------------
# 4. Guardrail metadata is deterministic
# ---------------------------------------------------------------------------

def test_guardrail_metadata_deterministic():
    g1 = create_default_guardrail()
    g2 = create_default_guardrail()
    assert g1 == g2
    assert g1.to_dict() == g2.to_dict()


# ---------------------------------------------------------------------------
# 5. Guardrail metadata survives serialization/deserialization
# ---------------------------------------------------------------------------

def test_serialization_round_trip():
    original = create_default_guardrail()
    payload = original.to_dict()
    restored = IIRSScientificGuardrail.from_dict(payload)
    assert restored.status == original.status
    assert restored.limitation_statement == original.limitation_statement
    assert restored.is_scientifically_validated == original.is_scientifically_validated
    assert restored.is_publication_grade == original.is_publication_grade
    assert restored.to_dict() == payload


# ---------------------------------------------------------------------------
# 6. Deserialization does not silently upgrade status
# ---------------------------------------------------------------------------

def test_deserialization_no_silent_upgrade():
    payload = {"status": "ILLUSTRATIVE", "limitation_statement": _DEFAULT_LIMITATION_STATEMENT}
    restored = IIRSScientificGuardrail.from_dict(payload)
    assert restored.status == IIRSScientificStatus.ILLUSTRATIVE
    assert restored.is_scientifically_validated is False

    # Unrecognised status must raise
    with pytest.raises(ValueError, match="Unrecognised scientific status"):
        IIRSScientificGuardrail.from_dict({"status": "APPROVED"})

    # Missing status must raise
    with pytest.raises(ValueError, match="missing required field"):
        IIRSScientificGuardrail.from_dict({})

    # Non-dict must raise
    with pytest.raises(TypeError, match="must be a dictionary"):
        IIRSScientificGuardrail.from_dict("not a dict")


# ---------------------------------------------------------------------------
# 7. Existing class_map remains unchanged
# ---------------------------------------------------------------------------

def test_class_map_unchanged():
    classification = _make_classification_result()
    original_class_map = classification.class_map.copy()
    _ = create_default_guardrail()
    np.testing.assert_array_equal(classification.class_map, original_class_map)


# ---------------------------------------------------------------------------
# 8. Existing score_map remains unchanged
# ---------------------------------------------------------------------------

def test_score_map_unchanged():
    classification = _make_classification_result()
    original_score_map = classification.score_map.copy()
    _ = create_default_guardrail()
    np.testing.assert_array_equal(classification.score_map, original_score_map)


# ---------------------------------------------------------------------------
# 9. Existing overlay values remain unchanged
# ---------------------------------------------------------------------------

def test_overlay_values_unchanged():
    overlay = _make_overlay_result()
    original_scores = overlay.score_overlay.copy()
    original_classes = overlay.class_overlay.copy()
    _ = create_default_guardrail()
    np.testing.assert_array_equal(overlay.score_overlay, original_scores)
    np.testing.assert_array_equal(overlay.class_overlay, original_classes)


# ---------------------------------------------------------------------------
# 10. Existing masks remain unchanged
# ---------------------------------------------------------------------------

def test_masks_unchanged():
    classification = _make_classification_result()
    overlay = _make_overlay_result()
    orig_cls_mask = classification.valid_mask.copy()
    orig_ovl_mask = overlay.valid_mask.copy()
    _ = create_default_guardrail()
    np.testing.assert_array_equal(classification.valid_mask, orig_cls_mask)
    np.testing.assert_array_equal(overlay.valid_mask, orig_ovl_mask)


# ---------------------------------------------------------------------------
# 11. Future validated status cannot be produced without explicit input
# ---------------------------------------------------------------------------

def test_validated_requires_explicit_status():
    # Default is ILLUSTRATIVE
    default = create_default_guardrail()
    assert default.status == IIRSScientificStatus.ILLUSTRATIVE

    # Must explicitly pass VALIDATED to get it
    validated = IIRSScientificGuardrail(
        status=IIRSScientificStatus.VALIDATED,
        limitation_statement="Independently validated by external workflow.",
    )
    assert validated.status == IIRSScientificStatus.VALIDATED
    assert validated.is_scientifically_validated is True
    assert validated.is_publication_grade is True

    # create_default_guardrail never produces VALIDATED
    for _ in range(10):
        assert create_default_guardrail().status == IIRSScientificStatus.ILLUSTRATIVE


# ---------------------------------------------------------------------------
# 12. No USGS data/reference matching is involved
# ---------------------------------------------------------------------------

def test_no_usgs_data():
    guardrail = create_default_guardrail()
    payload = guardrail.to_dict()
    serialized = str(payload).lower()
    # The limitation statement explicitly denies USGS validation
    assert "no usgs" in guardrail.limitation_statement.lower()
    # No USGS matching/library introduced
    for attr_name in dir(guardrail):
        assert "usgs" not in attr_name.lower()


# ---------------------------------------------------------------------------
# 13. No registration logic is involved
# ---------------------------------------------------------------------------

def test_no_registration_logic():
    guardrail = create_default_guardrail()
    for attr in ["register", "match_features", "estimate_transform",
                  "refine", "tie_points", "alignment"]:
        assert not hasattr(guardrail, attr)


# ---------------------------------------------------------------------------
# 14. No overlay recalculation is involved
# ---------------------------------------------------------------------------

def test_no_overlay_recalculation():
    guardrail = create_default_guardrail()
    for attr in ["generate_overlay", "resample", "warp", "reproject"]:
        assert not hasattr(guardrail, attr)


# ---------------------------------------------------------------------------
# 15. No classification recalculation is involved
# ---------------------------------------------------------------------------

def test_no_classification_recalculation():
    guardrail = create_default_guardrail()
    for attr in ["classify", "classify_materials", "compute_band_ratio",
                  "extract_features", "match_spectra"]:
        assert not hasattr(guardrail, attr)
