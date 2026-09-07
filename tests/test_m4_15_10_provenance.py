"""
Test suite for Phase 15.10 — Synthetic-vs-Real Separation Validation

Tests the centralized provenance registry to ensure:
1. All M4 data outputs are properly classified
2. Synthetic data is never presented as real
3. Provenance information is complete and auditable
4. Data status labels are unambiguous
"""

import pytest
from lunar_hazard_mapper.m4_terrain.provenance import (
    DataProvenance,
    ProvenanceMetadata,
    M4DataProvenanceRegistry,
    get_provenance_registry,
)


class TestDataProvenance:
    """Test the DataProvenance enum and classifications."""

    def test_provenance_enum_values(self):
        """Verify all expected provenance classifications exist."""
        assert DataProvenance.REAL == "real"
        assert DataProvenance.SYNTHETIC == "synthetic"
        assert DataProvenance.ESTIMATED == "estimated"
        assert DataProvenance.ILLUSTRATIVE == "illustrative"
        assert DataProvenance.DEFERRED == "deferred"
        assert DataProvenance.UNAVAILABLE == "unavailable"

    def test_provenance_enum_uniqueness(self):
        """Ensure no duplicate provenance values."""
        values = [e.value for e in DataProvenance]
        assert len(values) == len(set(values))


class TestProvenanceMetadata:
    """Test the ProvenanceMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating provenance metadata."""
        meta = ProvenanceMetadata(
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_1_test",
            data_type="Test Data",
            description="Test description",
            notes="Test notes",
        )
        assert meta.classification == DataProvenance.SYNTHETIC
        assert meta.source_module == "m4_12_1_test"
        assert meta.data_type == "Test Data"

    def test_metadata_ui_labels(self):
        """Test UI label generation for each classification."""
        classifications = [
            (DataProvenance.REAL, "Real Authoritative Data"),
            (DataProvenance.SYNTHETIC, "Synthetic Development Data"),
            (DataProvenance.ESTIMATED, "Model Estimated Data"),
            (DataProvenance.ILLUSTRATIVE, "Illustrative Example"),
            (DataProvenance.DEFERRED, "Deferred / Unimplemented"),
            (DataProvenance.UNAVAILABLE, "Unavailable / Missing"),
        ]
        for classification, expected_label in classifications:
            meta = ProvenanceMetadata(
                classification=classification,
                source_module="test",
                data_type="test",
                description="test",
                notes="test",
            )
            assert meta.ui_label == expected_label

    def test_metadata_to_dict(self):
        """Test conversion to dictionary for JSON serialization."""
        meta = ProvenanceMetadata(
            classification=DataProvenance.SYNTHETIC,
            source_module="m4_12_1_test",
            data_type="Test Data",
            description="Test description",
            notes="Test notes",
        )
        result = meta.to_dict()
        assert result["classification"] == "synthetic"
        assert result["source_module"] == "m4_12_1_test"
        assert result["data_type"] == "Test Data"


class TestM4DataProvenanceRegistry:
    """Test the centralized provenance registry."""

    def test_registry_initialization(self):
        """Test that registry initializes with all expected entries."""
        registry = M4DataProvenanceRegistry()
        # Should have at least all the core M4 outputs
        expected_keys = [
            "terrain_dem",
            "camera_tmc",
            "camera_ohrc",
            "camera_iirs",
            "landmarks",
            "hazards",
            "spectral_overlay",
            "water_ice_overlay",
            "registration_engine",
            "temporal_change",
            "mission_status",
        ]
        for key in expected_keys:
            assert registry.get(key) is not None, f"Missing registry entry: {key}"

    def test_get_nonexistent_entry(self):
        """Test retrieving a non-existent entry returns None."""
        registry = M4DataProvenanceRegistry()
        assert registry.get("nonexistent_key") is None

    def test_synthetic_classification(self):
        """Verify all expected outputs are classified as synthetic."""
        registry = M4DataProvenanceRegistry()
        synthetic_keys = [
            "terrain_dem",
            "camera_tmc",
            "camera_ohrc",
            "camera_iirs",
            "landmarks",
            "hazards",
            "spectral_overlay",
            "water_ice_overlay",
        ]
        for key in synthetic_keys:
            assert (
                registry.is_synthetic(key)
            ), f"{key} should be classified as synthetic"

    def test_unavailable_classification(self):
        """Verify all expected outputs are classified as unavailable."""
        registry = M4DataProvenanceRegistry()
        unavailable_keys = ["registration_engine", "mission_status"]
        for key in unavailable_keys:
            assert (
                registry.is_available(key) is False
            ), f"{key} should be classified as unavailable"

    def test_deferred_classification(self):
        """Verify all expected outputs are classified as deferred."""
        registry = M4DataProvenanceRegistry()
        deferred_keys = ["temporal_change"]
        for key in deferred_keys:
            meta = registry.get(key)
            assert meta is not None
            assert (
                meta.classification == DataProvenance.DEFERRED
            ), f"{key} should be classified as deferred"

    def test_no_real_outputs_currently(self):
        """Verify no outputs are currently classified as REAL."""
        registry = M4DataProvenanceRegistry()
        real_outputs = registry.get_all_real()
        assert (
            len(real_outputs) == 0
        ), "No REAL outputs should be available in current build"

    def test_is_synthetic_method(self):
        """Test the is_synthetic() method."""
        registry = M4DataProvenanceRegistry()
        assert registry.is_synthetic("terrain_dem") is True
        assert registry.is_synthetic("registration_engine") is False
        assert registry.is_synthetic("nonexistent") is False

    def test_is_real_method(self):
        """Test the is_real() method."""
        registry = M4DataProvenanceRegistry()
        assert registry.is_real("terrain_dem") is False
        assert registry.is_real("registration_engine") is False

    def test_is_available_method(self):
        """Test the is_available() method."""
        registry = M4DataProvenanceRegistry()
        assert registry.is_available("terrain_dem") is True
        assert registry.is_available("registration_engine") is False
        assert registry.is_available("temporal_change") is False

    def test_get_all_synthetic(self):
        """Test retrieval of all synthetic outputs."""
        registry = M4DataProvenanceRegistry()
        synthetic = registry.get_all_synthetic()
        # Should have at least 8 synthetic outputs
        assert len(synthetic) >= 8
        for meta in synthetic.values():
            assert meta.classification == DataProvenance.SYNTHETIC

    def test_get_all_unavailable(self):
        """Test retrieval of all unavailable outputs."""
        registry = M4DataProvenanceRegistry()
        unavailable = registry.get_all_unavailable()
        # Should have at least 2 unavailable outputs
        assert len(unavailable) >= 2
        for meta in unavailable.values():
            assert meta.classification == DataProvenance.UNAVAILABLE

    def test_get_all_deferred(self):
        """Test retrieval of all deferred outputs."""
        registry = M4DataProvenanceRegistry()
        deferred = registry.get_all_deferred()
        # Should have at least 1 deferred output
        assert len(deferred) >= 1
        for meta in deferred.values():
            assert meta.classification == DataProvenance.DEFERRED

    def test_provenance_metadata_completeness(self):
        """Verify all registered outputs have complete metadata."""
        registry = M4DataProvenanceRegistry()
        for key, meta in registry._registry.items():
            assert meta.classification is not None
            assert meta.source_module, f"{key} missing source_module"
            assert meta.data_type, f"{key} missing data_type"
            assert meta.notes, f"{key} missing notes"
            # Notes should make it clear if synthetic, unavailable, or deferred
            note_lower = meta.notes.lower()
            if meta.classification == DataProvenance.SYNTHETIC:
                assert (
                    "synthetic" in note_lower or "not real" in note_lower
                ), f"{key} synthetic note should explain it's not real"

    def test_synthetic_notes_are_clear(self):
        """Verify synthetic data notes clearly state they are not real."""
        registry = M4DataProvenanceRegistry()
        synthetic = registry.get_all_synthetic()
        # Forbidden phrases that would CLAIM something is real (not cautious about "real" in negation)
        forbidden_phrases = [
            "from real observation",
            "real observation data",
            "real spacecraft observation",
            "authoritative measurement",
            "ground truth data",
            "validated observation",
        ]
        for key, meta in synthetic.items():
            note_lower = meta.notes.lower()
            for phrase in forbidden_phrases:
                assert (
                    phrase not in note_lower
                ), f"{key} synthetic note falsely claims: {phrase}"
            # But it SHOULD mention it's not real
            assert (
                "not real" in note_lower or "synthetic" in note_lower
            ), f"{key} should explicitly state it's not real"

    def test_audit_report_generation(self):
        """Test that audit report can be generated without errors."""
        registry = M4DataProvenanceRegistry()
        report = registry.audit_report()
        assert report is not None
        assert isinstance(report, str)
        assert "M4 Data Provenance Audit Report" in report
        assert "SYNTHETIC OUTPUTS" in report
        assert "REAL OUTPUTS" in report
        assert "UNAVAILABLE OUTPUTS" in report
        assert "DEFERRED OUTPUTS" in report

    def test_global_registry_singleton(self):
        """Test that get_provenance_registry() returns a singleton."""
        reg1 = get_provenance_registry()
        reg2 = get_provenance_registry()
        assert reg1 is reg2

    def test_register_custom_entry(self):
        """Test adding a custom provenance entry."""
        registry = M4DataProvenanceRegistry()
        registry.register(
            key="test_custom_output",
            classification=DataProvenance.SYNTHETIC,
            source_module="test_module",
            data_type="Test Type",
            description="Test description",
            notes="Test notes - not real data",
        )
        assert registry.is_synthetic("test_custom_output") is True
        meta = registry.get("test_custom_output")
        assert meta is not None
        assert meta.data_type == "Test Type"


class TestProvenanceGuardrails:
    """Test guardrails to prevent accidental misclassification."""

    def test_no_synthetic_labeled_as_real(self):
        """Verify synthetic data is not labeled as real."""
        registry = M4DataProvenanceRegistry()
        synthetic = registry.get_all_synthetic()
        for key, meta in synthetic.items():
            assert (
                meta.classification != DataProvenance.REAL
            ), f"{key} is incorrectly marked as REAL"

    def test_unavailable_not_marked_synthetic(self):
        """Verify unavailable features are not marked synthetic."""
        registry = M4DataProvenanceRegistry()
        unavailable = registry.get_all_unavailable()
        for key, meta in unavailable.items():
            assert (
                meta.classification != DataProvenance.SYNTHETIC
            ), f"{key} should not be marked SYNTHETIC if unavailable"

    def test_classification_consistency(self):
        """Verify classification consistency across all entries."""
        registry = M4DataProvenanceRegistry()
        valid_classifications = {c.value for c in DataProvenance}
        for key, meta in registry._registry.items():
            assert (
                meta.classification.value in valid_classifications
            ), f"{key} has invalid classification: {meta.classification}"


class TestProvenanceDocumentation:
    """Test that provenance information is well-documented."""

    def test_all_entries_have_descriptions(self):
        """Verify all registered entries have meaningful descriptions."""
        registry = M4DataProvenanceRegistry()
        for key, meta in registry._registry.items():
            assert (
                len(meta.description) > 10
            ), f"{key} has insufficient description"

    def test_all_entries_have_source_modules(self):
        """Verify all entries reference their source module."""
        registry = M4DataProvenanceRegistry()
        for key, meta in registry._registry.items():
            assert (
                meta.source_module.startswith("m4_")
            ), f"{key} source module should start with m4_"

    def test_provenance_module_references(self):
        """Verify source modules reference actual M4 phases."""
        registry = M4DataProvenanceRegistry()
        valid_phases = {
            "m4_12_1",  # Terrain
            "m4_12_3",  # TMC Camera
            "m4_12_4",  # OHRC Camera
            "m4_12_5",  # IIRS Footprint
            "m4_12_6",  # Landmarks
            "m4_12_7",  # Sun Control
            "m4_12_9",  # Hazards
            "m4_12_10",  # Spectral
            "m4_12_11",  # Water-Ice
            "m4_13_11",  # Registration
            "m4_13",  # Other phase 13 items
        }
        for key, meta in registry._registry.items():
            module = meta.source_module
            # Check if module starts with any valid phase
            valid = any(module.startswith(phase) for phase in valid_phases)
            assert valid, f"{key} references unknown module: {module}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
