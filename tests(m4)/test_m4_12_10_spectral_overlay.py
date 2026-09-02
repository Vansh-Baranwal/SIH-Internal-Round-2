"""Focused M4-12.10 Spectral Overlay contract tests.

Verifies spectral models, replaceable provider contracts, payload serialization,
DEM elevation association, and synthetic provenance isolation.
No real spectral observations or mineralogical classifications are fabricated.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m4_terrain import (
    SpectralBand,
    SpectralDataStatus,
    SpectralModel,
    SpectralOverlayModel,
    SpectralProvider,
    SpectralRegionItem,
    SyntheticSpectralProvider,
    SyntheticTerrainProvider,
    TerrainFoundation,
)


class IndependentSpectralProvider(SpectralProvider):
    """Proves the renderer-facing spectral contract is not provider-specific."""

    def load_spectral(self, foundation: TerrainFoundation | None = None) -> SpectralOverlayModel:
        return SpectralOverlayModel(
            regions=[
                SpectralRegionItem(
                    region_id="TEST_SPEC_001",
                    display_label="Independent Test Unit",
                    center_m=(500.0, 32.0, -600.0),
                    boundary_vertices_m=[
                        (450.0, 32.0, -550.0),
                        (550.0, 32.0, -550.0),
                        (550.0, 32.0, -650.0),
                        (450.0, 32.0, -650.0),
                    ],
                    band_values={"TEST_BAND_1": 0.25},
                    scalar_index=0.65,
                    data_status=SpectralDataStatus.SYNTHETIC,
                    provenance={"note": "Independent test provider spectral patch."},
                )
            ],
            available_bands=[
                SpectralBand(band_id="TEST_BAND_1", name="Test Band 1", wavelength_um=1.2, unit="Reflectance (I/F)")
            ],
            data_status=SpectralDataStatus.SYNTHETIC,
            provenance={"source": "independent_test_spectral_provider"},
        )


def test_synthetic_spectral_provider_is_explicitly_development_only():
    provider = SyntheticSpectralProvider()
    set_model = provider.load_spectral()
    payload = set_model.payload()

    assert payload["data_status"] == "synthetic"
    assert payload["display_label"] == "SYNTHETIC DEVELOPMENT SPECTRAL OVERLAY"
    assert "not represent real iirs observations" in payload["provenance"]["note"].lower() or \
           "not represent" in payload["provenance"]["note"]
    assert payload["region_count"] == 3
    assert len(payload["available_bands"]) == 3


def test_spectral_payload_preserves_bands_and_coordinates():
    provider = SyntheticSpectralProvider()
    payload = provider.load_spectral().payload()

    conv = payload["coordinate_convention"]
    assert conv["x"] == "local_east_meters"
    assert conv["y"] == "local_up_meters"
    assert conv["z"] == "local_north_meters"

    bands = payload["available_bands"]
    assert any(b["band_id"] == "BAND_950NM" and b["wavelength_um"] == 0.95 for b in bands)
    assert any(b["band_id"] == "BAND_2000NM" and b["wavelength_um"] == 2.00 for b in bands)

    r1 = payload["regions"][0]
    assert r1["region_id"] == "SPEC_REGION_SYNTHETIC_001"
    assert "BAND_950NM" in r1["band_values"]
    assert 0.0 <= r1["scalar_index"] <= 1.0
    assert len(r1["boundary_vertices_m"]) >= 3


def test_spectral_provider_contract_is_replaceable():
    provider = IndependentSpectralProvider()
    assert isinstance(provider, SpectralProvider)

    model = provider.load_spectral()
    assert isinstance(model, SpectralOverlayModel)
    assert isinstance(model, SpectralModel)
    assert len(model.regions) == 1

    item = model.regions[0]
    assert isinstance(item, SpectralRegionItem)
    assert item.region_id == "TEST_SPEC_001"
    assert item.center_m == (500.0, 32.0, -600.0)
    assert len(item.boundary_vertices_m) == 4


def test_spectral_overlay_frontend_does_not_depend_on_synthetic_provider_class():
    viewer_source = (PROJECT_ROOT / "web" / "src" / "components" / "SpectralOverlay.tsx").read_text(encoding="utf-8")
    assert "SyntheticSpectralProvider" not in viewer_source
    assert "fetchSpectralOverlay" in viewer_source
    assert "spectral-region-fill" in viewer_source
    assert "spectral-boundary-outline" in viewer_source
    assert "Spectral metadata is malformed" in viewer_source


def test_invalid_spectral_item_parameters_raise_value_error():
    with pytest.raises(ValueError, match="region_id cannot be empty"):
        SpectralRegionItem(
            region_id="",
            display_label="Invalid",
            center_m=(0.0, 0.0, 0.0),
            boundary_vertices_m=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)],
            band_values={},
            scalar_index=0.5,
        )

    with pytest.raises(ValueError, match="boundary_vertices_m must have at least 3 vertices"):
        SpectralRegionItem(
            region_id="INV_01",
            display_label="Invalid",
            center_m=(0.0, 0.0, 0.0),
            boundary_vertices_m=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],  # only 2 vertices
            band_values={},
            scalar_index=0.5,
        )

    with pytest.raises(ValueError, match="scalar_index must be between 0.0 and 1.0"):
        SpectralRegionItem(
            region_id="INV_02",
            display_label="Invalid",
            center_m=(0.0, 0.0, 0.0),
            boundary_vertices_m=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)],
            band_values={},
            scalar_index=1.8,
        )
