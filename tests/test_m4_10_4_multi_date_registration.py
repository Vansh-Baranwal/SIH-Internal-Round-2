"""Mocked integration tests for M4 Phase 10.4 around the existing M2 API.

The observations and metric objects in this file are test fixtures only. No
scientific registration result or lunar observation is asserted as real.
"""

from types import SimpleNamespace

import pytest

from lunar_hazard_mapper.m4_terrain import (
    DataProvenance,
    PairEligibility,
    RegistrationConfig,
    RegistrationStatus,
    TemporalRegistrationRequest,
    evaluate_pair,
    register_observation_pair,
)
from lunar_hazard_mapper.m4_terrain.temporal_observation import LunarObservation, ObservationPair


def observation(identifier: str, timestamp: str, **overrides) -> LunarObservation:
    values = {
        "observation_id": identifier,
        "source": "TMC test fixture",
        "image_reference": "unused.tif",
        "acquisition_timestamp": timestamp,
        "provenance_source": "tests/test_m4_10_4_multi_date_registration.py",
        "provenance": DataProvenance.REAL,
        "is_real_data": True,
    }
    values.update(overrides)
    return LunarObservation(**values)


def pair_with_local_inputs(tmp_path):
    source = tmp_path / "source.png"
    reference = tmp_path / "reference.png"
    source.write_bytes(b"test-only source")
    reference.write_bytes(b"test-only reference")
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00Z", image_reference=str(source)),
        observation("b", "2024-02-01T00:00:00Z", image_reference=str(reference)),
    )
    return pair


def metrics(**overrides):
    values = {
        "total_matches": 20,
        "inlier_count": 15,
        "inlier_ratio": 0.75,
        "rmse": 0.42,
        "spatial_coverage": 0.6,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_eligible_pair_reaches_existing_m2_pipeline(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    config = RegistrationConfig(output_dir=tmp_path / "output")
    calls = {}

    def fake_run_pipeline(source, reference, output_dir, **kwargs):
        calls.update(source=source, reference=reference, output_dir=output_dir, kwargs=kwargs)
        output = tmp_path / "output"
        output.mkdir()
        (output / "warped_source.png").write_bytes(b"test-only output")
        (output / "matches.json").write_text("{}")
        return metrics()

    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", fake_run_pipeline)
    result = register_observation_pair(pair, config)

    assert result.status is RegistrationStatus.SUCCESS
    assert calls["source"] == str(tmp_path / "source.png")
    assert calls["reference"] == str(tmp_path / "reference.png")
    assert calls["kwargs"]["matcher"] == "sift"
    assert calls["kwargs"]["geo_model"] == "affine"


def test_ineligible_selection_blocks_m2_before_invocation(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    selection = evaluate_pair(pair.observation_a, pair.observation_b)
    rejected = selection.__class__(
        **{**selection.__dict__, "eligibility": PairEligibility.REJECTED, "hard_rejection_reasons": ("same_observation",)}
    )
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: pytest.fail("M2 must not be invoked"))
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"), rejected)
    assert result.status is RegistrationStatus.BLOCKED
    assert result.failure_reasons == ("ineligible_pair", "same_observation")


def test_missing_local_input_fails_cleanly(tmp_path, monkeypatch) -> None:
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00Z", image_reference=str(tmp_path / "missing-a.tif")),
        observation("b", "2024-02-01T00:00:00Z", image_reference=str(tmp_path / "missing-b.tif")),
    )
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: pytest.fail("M2 must not be invoked"))
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"))
    assert result.status is RegistrationStatus.BLOCKED
    assert result.failure_reasons == ("missing_image_input", "missing_image_input")


def test_external_reference_is_not_passed_as_local_m2_path(tmp_path, monkeypatch) -> None:
    pair = ObservationPair(
        observation("a", "2024-01-01T00:00:00Z", image_reference="https://example.test/a.tif"),
        observation("b", "2024-02-01T00:00:00Z", image_reference="https://example.test/b.tif"),
    )
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: pytest.fail("M2 must not receive a URI"))
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"))
    assert result.failure_reasons == ("external_image_reference_unsupported_by_m2", "external_image_reference_unsupported_by_m2")


def test_m2_metrics_and_artifacts_are_adapted(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    output = tmp_path / "output"

    def fake_run(*args, **kwargs):
        output.mkdir()
        (output / "warped_source.png").write_bytes(b"test-only output")
        (output / "matches.json").write_text("{}")
        return metrics()

    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", fake_run)
    result = register_observation_pair(pair, RegistrationConfig(output_dir=output, geo_model="homography"))
    assert result.transformation_model == "homography"
    assert result.transformation_parameters is None
    assert result.initial_match_count == 20
    assert result.verified_inlier_count == 15
    assert result.inlier_ratio == 0.75
    assert result.registration_rmse == 0.42
    assert result.spatial_coverage == 0.6
    assert result.subpixel_refinement_available is True
    assert result.subpixel_refinement_status == "executed"
    assert result.registered_output_reference == str(output / "warped_source.png")
    assert result.match_point_output_reference == str(output / "matches.json")


def test_missing_optional_m2_metrics_remain_unavailable(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    output = tmp_path / "output"

    def fake_run(*args, **kwargs):
        output.mkdir()
        (output / "warped_source.png").write_bytes(b"test-only output")
        return metrics(inlier_ratio=None, rmse=None, spatial_coverage=None)

    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", fake_run)
    result = register_observation_pair(pair, RegistrationConfig(output_dir=output))
    assert result.status is RegistrationStatus.SUCCESS
    assert result.inlier_ratio is None
    assert result.registration_rmse is None
    assert result.spatial_coverage is None
    assert result.registration_quality_status == "partial_metrics"


@pytest.mark.parametrize("field", ["rmse", "inlier_ratio", "spatial_coverage"])
def test_nan_or_infinite_m2_metric_is_rejected(tmp_path, monkeypatch, field) -> None:
    pair = pair_with_local_inputs(tmp_path)
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: metrics(**{field: float("nan")}))
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"))
    assert result.status is RegistrationStatus.FAILED
    assert result.failure_reasons == ("invalid_registration_metrics",)


def test_m2_execution_failure_is_explicit(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("test failure")))
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"))
    assert result.status is RegistrationStatus.FAILED
    assert result.failure_reasons == ("registration_execution_failed",)


def test_m2_none_result_is_insufficient_matches(tmp_path, monkeypatch) -> None:
    pair = pair_with_local_inputs(tmp_path)
    import lunar_hazard_mapper.correspondence_engine.registration.pipeline as m2_pipeline
    monkeypatch.setattr(m2_pipeline, "run_pipeline", lambda *args, **kwargs: None)
    result = register_observation_pair(pair, RegistrationConfig(output_dir=tmp_path / "output"))
    assert result.failure_reasons == ("insufficient_matches",)


def test_invalid_transform_model_is_rejected_before_m2(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported registration model"):
        RegistrationConfig(output_dir=tmp_path, geo_model="invalid")


def test_request_requires_matching_eligible_selection(tmp_path) -> None:
    pair = pair_with_local_inputs(tmp_path)
    selection = evaluate_pair(pair.observation_a, pair.observation_b)
    TemporalRegistrationRequest(pair, selection, RegistrationConfig(output_dir=tmp_path))