#!/usr/bin/env python3
"""Generate M1 GeoTIFF inspection manifests for the selected SIH reference data."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from tabulate import tabulate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lunar_hazard_mapper.m1_data.metadata import inspect_directory, summarise  # noqa: E402
from lunar_hazard_mapper.m1_data.loader import parse_iirs_corners  # noqa: E402


DATASETS = {
    "TMCORTHO5-1": "tmc_source",
    "ORTHONAC0.5-1": "hr_source",
    "NAC": "nac_source",
    "TMCDTM": "dem_source",
}


def load_paths() -> dict[str, Any]:
    """Load path configuration and resolve the canonical SIH root."""
    with (PROJECT_ROOT / "configs" / "paths.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    configured_root = Path(os.environ.get("SIH_ROOT", config["sih_root"]))
    config["sih_root"] = configured_root if configured_root.is_absolute() else PROJECT_ROOT / configured_root
    return config


def _attach_ohrc_real_footprint(records: list[dict[str, Any]]) -> None:
    """
    OHRC's raw .img is opened via its .xml label through GDAL's PDS4 driver
    (see FILE_PATTERNS below -- '*_d_img_*.xml', not '*.img', since the
    .img alone isn't a GDAL-readable format on its own).

    That PDS4-driver open gives real PIXEL DATA but crs=None and an identity
    transform -- rasterio has no map-projection info for this product, so
    dataset.bounds comes back as raw pixel-index numbers (e.g. east=12000,
    the image WIDTH in pixels), not degrees. Comparing that against TMC's
    real lon/lat bounds in catalogue.py's overlap math can never match --
    not because the data doesn't overlap, but because one side is pixels
    and the other is degrees.

    Fix: replace the meaningless pixel-space bounds with OHRC's REAL lat/lon
    footprint, parsed from the same .xml label's ISDA Geometry_Parameters
    corners (already proven to work in check_ohrc.py -- OHRC shares IIRS's
    corner-tag schema). catalogue.py/overlap.py already know how to consume
    record["corners"] (see overlap.py's _footprint_area/_corners_bounds and
    coordinates.py's _footprint_polygon) -- so once corners is populated
    correctly here, the existing verified-overlap machinery picks it up
    without any further changes downstream.

    Also fixes the file-size figure: summarise() was reporting the tiny
    .xml label's size (~0.01 MB) since that's the file path GDAL opened,
    not the real ~1GB .img pixel data behind it -- misleading for anything
    that reads the manifest later (e.g. the final summary doc).
    """
    for record in records:
        xml_path = Path(record["file_path"])

        try:
            corners = parse_iirs_corners(xml_path)
            record["corners"] = corners
            record.pop("bounds", None)  # pixel-space bounds are meaningless here -- corners is the real footprint
            record["has_valid_crs"] = True  # we DO have a real footprint, just not from dataset.crs/dataset.bounds
        except (ValueError, FileNotFoundError) as e:
            print(f"  WARNING: could not attach real corners to {xml_path.name}: {e}")
            continue

        img_path = xml_path.with_name(xml_path.name.replace(".xml", ".img"))
        if img_path.exists():
            record["file_size_mb"] = img_path.stat().st_size / (1024 * 1024)


def main() -> int:
    """Inspect all configured datasets and write manifests."""
    config = load_paths()
    manifest_dir = PROJECT_ROOT / config.get("manifests", "data/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    all_summaries: dict[str, dict[str, Any]] = {}

    for label, config_key in DATASETS.items():
        source = Path(config["sih_root"]) / config[config_key]
        if not source.is_dir():
            raise FileNotFoundError(f"Configured {label} directory does not exist: {source}")

        # OHRC ships as raw .img, which isn't GDAL-readable on its own --
        # its .xml label opens fine through GDAL's PDS4 driver, so glob for
        # that instead.
        FILE_PATTERNS = {"ORTHONAC0.5-1": "*_d_img_*.xml"}
        pattern = FILE_PATTERNS.get(label, "*.tif")
        try:
            records = inspect_directory(source, pattern=pattern)
        except Exception as e:
            print(f"  SKIPPED {label}: {type(e).__name__}: {e}")
            records = []

        if label == "ORTHONAC0.5-1" and records:
            _attach_ohrc_real_footprint(records)

        summary = summarise(records)
        all_summaries[label] = summary
        payload = {"dataset": label, "source": source.as_posix(), "records": records, "summary": summary}
        output = manifest_dir / f"inspection_{label}.json"
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(tabulate([[label, summary["total_files"], summary["total_size_mb"], summary["pixel_size_range"]]], headers=["dataset", "files", "size_mb", "pixel_size_m"]))

    combined = manifest_dir / "inspection_summary.json"
    combined.write_text(json.dumps(all_summaries, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote inspection manifests to {manifest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())