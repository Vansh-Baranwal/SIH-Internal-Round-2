"""Focused tests for the runtime /api/spectral Phase 8 classification adapter."""

from lunar_hazard_mapper.api import main
from lunar_hazard_mapper.m4_terrain import iirs_runtime
from lunar_hazard_mapper.m4_terrain.iirs_runtime import SyntheticIirsClassificationProvider


def test_runtime_classification_uses_existing_classifier(monkeypatch):
    calls = []
    original_classifier = iirs_runtime.classify_materials

    def classifier_wrapper(features, rules):
        calls.append(True)
        return original_classifier(features, rules)

    monkeypatch.setattr(iirs_runtime, "classify_materials", classifier_wrapper)
    payload = main.get_spectral()

    assert calls == [True]
    assert payload["classification"]["provenance"]["pipeline"][-1] == "classify_materials"


def test_spectral_response_preserves_values_and_exposes_honest_classification():
    payload = main.get_spectral()
    classification = payload["classification"]

    assert payload["region_count"] == 3
    assert payload["regions"][0]["band_values"]["BAND_950NM"] == 0.14
    assert payload["regions"][1]["band_values"]["BAND_950NM"] == 0.18
    assert payload["regions"][2]["band_values"]["BAND_950NM"] == 0.09
    assert classification["status"] == "illustrative"
    assert classification["source_type"] == "synthetic"
    assert classification["classes"] == ["PYROXENE"]
    assert classification["class_map"] == [["PYROXENE", "PYROXENE"], ["PYROXENE", "PYROXENE"]]
    assert classification["valid_mask"] == [[True, True], [True, True]]
    assert "probability" not in classification
    assert "confidence" not in classification
    assert classification["score_semantics"].endswith("not probability or confidence")
    assert classification["provenance"]["guardrail"]["status"] == "ILLUSTRATIVE"


def test_runtime_provider_serializes_only_classes_present_in_grid():
    classification = SyntheticIirsClassificationProvider().load_classification()

    summary_names = [item["class_name"] for item in classification["summary"]]
    assert summary_names == classification["classes"]
    assert classification["summary"][0]["valid_pixel_count"] == 4
    assert classification["summary"][0]["valid_pixel_percentage"] == 100.0