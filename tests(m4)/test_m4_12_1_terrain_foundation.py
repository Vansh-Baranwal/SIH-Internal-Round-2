"""
M4-12.1 3D Terrain Foundation --- focused tests.

Covers:
  - the replaceable terrain data provider contract
  - the synthetic terrain provider (explicitly synthetic)
  - DEM metadata preservation
  - provenance / source_type / data-status
  - nodata / valid-mask behavior
  - coordinate semantics (local East / North / Up, metres)
  - provider interchangeability (the future real-DEM swap path shares the
    same contract; no fabricated real-lunar data is created here)

This is a standalone script (runs via ``python test_m4_12_1_terrain_foundation.py``)
following the repository's existing M4 test convention. It never claims real-lunar
accuracy; the DEMs involved are synthetic development data.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lunar_hazard_mapper.m3_terrain.dem import DEM  # noqa: E402
from lunar_hazard_mapper.m3_terrain.synthetic import (  # noqa: E402
    create_synthetic_terrain,
)
from lunar_hazard_mapper.m4_terrain import (  # noqa: E402
    TerrainDataProvider,
    SyntheticTerrainProvider,
    DemDataProvider,
    TerrainFoundation,
    TerrainDataStatus,
    status_from_source_type,
    validate_foundation,
)


class LiteralGridProvider(TerrainDataProvider):
    """
    Minimal, independent provider used to prove interchangeability.

    It implements the provider contract but is deliberately *not* a
    SyntheticTerrainProvider, so the test demonstrates that a foundation works
    through the contract regardless of which concrete provider is injected. It
    wraps a freshly generated synthetic DEM.
    """

    def __init__(self, dem: DEM) -> None:
        self._dem = dem

    def load_dem(self) -> DEM:
        return self._dem

    @property
    def source_type(self) -> str:
        return self._dem.source_type

    @property
    def data_status(self) -> TerrainDataStatus:
        return status_from_source_type(self._dem.source_type)

    @property
    def provenance(self) -> dict:
        return {
            "data_status": self.data_status.value,
            "display_label": self.data_status.value.upper(),
            "declared_type": self._dem.source_type,
            "source": "test_literal_grid",
            "note": "Independent test provider; source is synthetic development data.",
        }


def _make_synthetic_dem(kind="combined", size=64, pixel_size_m=5.0):
    return create_synthetic_terrain(kind=kind, size=size, pixel_size_m=pixel_size_m)


def main() -> None:
    print("=== M4-12.1 3D Terrain Foundation Test ===")

    # ------------------------------------------------------------------ #
    # 1. Provider contract
    # ------------------------------------------------------------------ #
    try:
        TerrainDataProvider()  # type: ignore[abstract]
        raised = False
    except TypeError:
        raised = True
    assert raised, "TerrainDataProvider must be abstract (cannot be instantiated)."
    print("Provider contract is abstract: PASS")
    print(
        "Contract satisfied by SyntheticTerrainProvider: "
        f"{isinstance(SyntheticTerrainProvider(), TerrainDataProvider)}"
    )

    # ------------------------------------------------------------------ #
    # 2. Synthetic provider + provenance
    # ------------------------------------------------------------------ #
    provider = SyntheticTerrainProvider(kind="combined", size=64, pixel_size_m=5.0)
    foundation = TerrainFoundation(provider)
    dem = foundation.dem
    assert dem.source_type == "synthetic"
    assert foundation.source_type == "synthetic"
    assert foundation.data_status == TerrainDataStatus.SYNTHETIC
    assert not foundation.is_georeferenced
    prov = provider.provenance
    assert prov["data_status"] == "synthetic"
    assert prov["declared_type"] == "synthetic"
    assert foundation.display_label == "SYNTHETIC DEVELOPMENT DATA"
    assert foundation.metadata()["display_label"] == "SYNTHETIC DEVELOPMENT DATA"
    assert "synthetic" in dem.notes.lower()
    assert "not real lunar" in dem.notes.lower()
    print("Synthetic provider provenance/labels: PASS")

    # ------------------------------------------------------------------ #
    # 3. DEM metadata preservation
    # ------------------------------------------------------------------ #
    meta = foundation.metadata()
    assert meta["pixel_size_m"] == 5.0
    assert meta["width"] == 64 and meta["height"] == 64
    assert meta["vertical_units"] == "meters"
    assert meta["crs"] is None
    assert meta["is_georeferenced"] is False
    assert meta["nodata"] == dem.nodata
    assert dem.transform is not None
    assert meta["coordinate_convention"] == foundation.COORDINATE_CONVENTION
    print("DEM metadata preservation: PASS")

    # ------------------------------------------------------------------ #
    # 4. nodata / valid-mask behavior
    # ------------------------------------------------------------------ #
    # Inject nodata sentinels into a fresh synthetic DEM; the valid-mask must
    # exclude exactly those cells (and never a non-finite cell).
    flat = create_synthetic_terrain(kind="flat", size=16, pixel_size_m=2.0)
    for (r, c) in [(3, 4), (5, 5), (8, 9)]:
        flat.elevation[r, c] = flat.nodata
    flat.elevation[7, 7] = float("nan")
    nodata_foundation = TerrainFoundation(
        DemDataProvider(flat, source="test_nodata")
    )
    vmask = nodata_foundation.valid_mask()
    assert vmask.shape == flat.elevation.shape
    assert not vmask[3, 4]
    assert not vmask[5, 5]
    assert not vmask[8, 9]
    assert not vmask[7, 7]  # non-finite excluded
    assert bool(vmask[0, 0])
    assert nodata_foundation.grid()["valid_mask"].shape == flat.elevation.shape
    print("nodata / valid-mask behavior: PASS")

    # ------------------------------------------------------------------ #
    # 5. coordinate semantics (local East / North / Up, metres)
    # ------------------------------------------------------------------ #
    lf = foundation.local_frame()
    assert set(lf.keys()) == {"x", "y", "z"}
    assert lf["x"].shape == dem.elevation.shape
    assert lf["y"].shape == dem.elevation.shape
    assert lf["z"].shape == dem.elevation.shape
    # x increases to the East, y decreases going South (North-up convention is
    # preserved by the M3 transform). z equals elevation.
    assert lf["x"][0, 1] > lf["x"][0, 0]
    assert lf["y"][1, 0] < lf["y"][0, 0]
    assert float(abs(lf["z"][0, 0] - dem.elevation[0, 0])) < 1e-6
    assert foundation.metadata()["coordinate_convention"]["x"] == "local_east_meters"
    print("Coordinate semantics (east/north/up, m): PASS")

    # ------------------------------------------------------------------ #
    # 6. provider interchangeability (future real-DEM swap readiness)
    # ------------------------------------------------------------------ #
    # A different concrete provider (same contract) is consumed identically.
    literal_provider = LiteralGridProvider(
        _make_synthetic_dem("flat", size=32, pixel_size_m=3.0)
    )
    lit_foundation = TerrainFoundation(literal_provider)
    assert lit_foundation.data_status == TerrainDataStatus.SYNTHETIC
    assert lit_foundation.metadata()["source_type"] == "synthetic"
    assert lit_foundation.metadata()["width"] == 32

    # Wrapping an existing DEM via the generic adapter follows the same path.
    wrapped = TerrainFoundation(
        DemDataProvider(_make_synthetic_dem("crater", size=64, pixel_size_m=4.0))
    )
    assert wrapped.data_status == TerrainDataStatus.SYNTHETIC
    assert wrapped.metadata()["source_type"] == "synthetic"
    assert wrapped.grid()["x"].shape == wrapped.dem.elevation.shape

    # The future real-DEM swap shares the same contract: the status router
    # already recognises a 'measured' (real) source_type. No real data is
    # fabricated here -- this only proves the label routing, not that real
    # data exists.
    assert status_from_source_type("measured") == TerrainDataStatus.REAL
    assert status_from_source_type("synthetic") == TerrainDataStatus.SYNTHETIC
    assert status_from_source_type("sr_estimated") == TerrainDataStatus.UNKNOWN
    print("Provider interchangeability / swap readiness: PASS")

    # ------------------------------------------------------------------ #
    # 7. validation / safety
    # ------------------------------------------------------------------ #
    report = validate_foundation(foundation)
    failed = [k for k, v in report.items() if k != "all_passed" and not v]
    assert report["all_passed"], f"validation failed: {failed}"
    assert report["synthetic_not_presented_as_real"]
    assert report["synthetic_label_explicit"]
    assert report["provenance_explicit"]
    assert report["coordinate_convention_preserved"]
    assert report["nodata_excluded_from_valid"]
    print("Validation / safety checks: PASS")

    print()
    print("PASS: M4-12.1 3D Terrain Foundation is functioning.")


if __name__ == "__main__":
    main()


