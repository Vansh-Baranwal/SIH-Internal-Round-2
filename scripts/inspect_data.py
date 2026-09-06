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
    "IIRSRAW-1": "iirs_source",
    "SELENE_TCO": "selene_source",
}

# Products whose raw file isn't independently readable (or isn't
# georeferenced) on its own -- glob for the sibling PDS4 .xml / .qub instead
# of the raw .img, and attach a corner-derived footprint afterward.

FILE_PATTERNS = {
    "ORTHONAC0.5-1": "*_d_img_*.xml",
    "IIRSRAW-1": "*.qub",
    "NAC": "*.IMG",
    "SELENE_TCO": "*.lbl",
}
# NAC CDR files carry NO embedded corner/geometry metadata at all (unlike
# OHRC/IIRS PDS4 labels, which have parseable corner tags). This scene's
# real footprint comes from ODE's (Lunar Orbital Data Explorer) own
# spatial index shown on its product detail page -- NOT parsed from the
# file itself, since the file genuinely doesn't carry it.
NAC_MANUAL_FOOTPRINTS = {
    "M101993185LC": [
        (24.98, -8.31),    # upper_left  (west, north)
        (25.17, -8.31),    # upper_right (east, north)
        (25.17, -10.15),   # lower_right (east, south)
        (24.98, -10.15),   # lower_left  (west, south)
    ],
}


def _attach_manual_nac_footprint(records: list[dict[str, Any]]) -> None:
    """Attach ODE-sourced corner coordinates for NAC files with no embedded geometry."""
    for record in records:
        stem = Path(record["file_path"]).stem.upper()
        corners = NAC_MANUAL_FOOTPRINTS.get(stem)
        if corners is None:
            print(f"  WARNING: no manual footprint recorded for NAC file {stem}; leaving unlocated")
            continue
        record["corners"] = corners
        record.pop("bounds", None)
        record["has_derived_footprint"] = True

# Which labels need a corner-derived real-world footprint attached after
# inspect_directory() returns (both currently open with crs=None / an
# identity transform and no usable dataset.bounds).

NEEDS_CORNER_FOOTPRINT = {"ORTHONAC0.5-1", "IIRSRAW-1", "NAC"}

def load_paths() -> dict[str, Any]:
    """Load path configuration and resolve the canonical SIH root."""
    with (PROJECT_ROOT / "configs" / "paths.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    configured_root = Path(os.environ.get("SIH_ROOT", config["sih_root"]))
    config["sih_root"] = configured_root if configured_root.is_absolute() else PROJECT_ROOT / configured_root
    return config


def _attach_real_footprint_from_corners(records: list[dict[str, Any]]) -> None:
    """
    Replaces a meaningless pixel-space `bounds` (raw pixel-index numbers,
    since the file itself carries no map projection) with a real lat/lon
    `corners` footprint parsed from the product's PDS4 label.

    Works for BOTH OHRC and IIRS: OHRC's inspected file_path IS the .xml
    (see FILE_PATTERNS above), IIRS's inspected file_path is the .qub with
    a sibling .xml -- this handles both by checking the actual suffix
    rather than assuming which one it is.

    Sets `has_derived_footprint = True` rather than falsely claiming
    `has_valid_crs`/`has_valid_transform` -- there IS no real embedded
    geodetic CRS here, we've derived usable geometry from label corners
    instead. catalogue.py's inclusion logic checks this flag explicitly
    (see the OHRC-exclusion fix below) so a record can be legitimately
    included without pretending its raw metadata says something it doesn't.
    """
    for record in records:
        file_path = Path(record["file_path"])
        xml_path = file_path if file_path.suffix.lower() == ".xml" else file_path.with_suffix(".xml")

        try:
            corners = parse_iirs_corners(xml_path)
            record["corners"] = corners
            record.pop("bounds", None)  # pixel-space bounds are meaningless here -- corners is the real footprint
            record["has_derived_footprint"] = True
        except (ValueError, FileNotFoundError) as e:
            print(f"  WARNING: could not attach real corners to {xml_path.name}: {e}")
            continue

        # OHRC-specific: the file we opened (.xml, via PDS4 driver) is tiny;
        # the real pixel data lives in the sibling .img. Report the real size.
        if file_path.suffix.lower() == ".xml":
            img_path = file_path.with_name(file_path.name.replace(".xml", ".img"))
            if img_path.exists():
                record["file_size_mb"] = img_path.stat().st_size / (1024 * 1024)
        # IIRS: file_path is already the real .qub -- its own size is already correct.


def main() -> int:
    """Inspect all configured datasets and write manifests."""
    config = load_paths()
    manifest_dir = PROJECT_ROOT / config.get("manifests", "data/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    all_summaries: dict[str, dict[str, Any]] = {}

    for label, config_key in DATASETS.items():
        if config_key not in config:
            print(f"  SKIPPED {label}: no '{config_key}' entry in configs/paths.yaml yet")
            continue
        source = Path(config["sih_root"]) / config[config_key]
        if not source.is_dir():
            raise FileNotFoundError(f"Configured {label} directory does not exist: {source}")

        pattern = FILE_PATTERNS.get(label, "*.tif")
        try:
            records = inspect_directory(source, pattern=pattern)
        except Exception as e:
            print(f"  SKIPPED {label}: {type(e).__name__}: {e}")
            records = []

        # if label in NEEDS_CORNER_FOOTPRINT and records:
        #     _attach_real_footprint_from_corners(records)
        if label in NEEDS_CORNER_FOOTPRINT and records:
            if label == "NAC":
                _attach_manual_nac_footprint(records)
            else:
                _attach_real_footprint_from_corners(records)

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