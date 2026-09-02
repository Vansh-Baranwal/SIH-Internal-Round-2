"""TEST ONLY: real-data-shaped fixture for Phase 12 replaceability checks.

This is deliberately fabricated structural test data. It is not a lunar
measurement, image product, or scientifically meaningful terrain model.
"""

import numpy as np

from lunar_hazard_mapper.m3_terrain.dem import generate_dem


def make_real_data_shaped_dem():
    """Return a translated, non-square, partially invalid contract fixture."""
    rows, columns = 5, 7
    row_grid, column_grid = np.indices((rows, columns), dtype=np.float32)
    elevation = 12.0 + row_grid * 1.75 + column_grid * 0.6
    elevation[1, 2] = -32768.0
    elevation[3, 5] = np.nan
    return generate_dem(
        {
            "elevation": elevation,
            "pixel_size_m": 7.5,
            "source_type": "real_data_shaped_fixture",
            "fixture_name": "phase12_real_data_shaped_test",
            "coordinate_reference": "TEST_LOCAL_LUNAR_FRAME",
            "validity_note": "Fabricated structural fixture; not lunar data.",
        },
        origin_xy=(120.0, 80.0),
        nodata=-32768.0,
        crs="TEST:LOCAL_LUNAR_FRAME",
        notes="REAL-DATA-SHAPED TEST FIXTURE ONLY; not real lunar measurements.",
    )