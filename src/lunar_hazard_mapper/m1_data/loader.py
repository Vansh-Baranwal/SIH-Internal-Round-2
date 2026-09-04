"""Raster / cube loading utilities owned by Member 1 (M1).

Two sensor families are supported:

* TMC / OHRC — standard single-band georeferenced GeoTIFFs, loaded with rasterio.
* IIRS — a 256-band ENVI-format binary cube (``.qub`` + sidecar ``.hdr``) with
  no map-info in the header, so it carries no automatic georeferencing. Its
  spatial footprint instead comes from corner coordinates in the PDS4 XML
  label, parsed here and handed to coordinates.py to build a real polygon.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np
import rasterio


def load_tmc_tile(path: Path) -> dict[str, Any]:
    """Load a TMC or OHRC GeoTIFF tile and return its array plus core metadata."""
    path = Path(path)
    with rasterio.open(path) as dataset:
        array = dataset.read(1)
        return {
            "file_path": path.as_posix(),
            "array": array,
            "width": int(dataset.width),
            "height": int(dataset.height),
            "crs": dataset.crs.to_wkt() if dataset.crs else None,
            "transform": tuple(dataset.transform)[:6],
            "nodata": dataset.nodata,
            "bounds": {
                "west": float(dataset.bounds.left),
                "south": float(dataset.bounds.bottom),
                "east": float(dataset.bounds.right),
                "north": float(dataset.bounds.top),
            },
        }


def load_iirs_cube(path: Path, bands: list[int] | None = None) -> dict[str, Any]:
    """Load an IIRS ENVI-format hyperspectral cube (.qub, with sidecar .hdr).

    The cube is large (~1.3 GB for a full 256-band scene at 250x10804), so by
    default this reads a small representative subset of bands rather than the
    whole file. Pass ``bands`` (1-indexed) to control exactly which bands load.

    IIRS cubes are NOT georeferenced by their .hdr file (no map info line), so
    ``crs``/``transform`` here will be None/identity. Use
    ``parse_iirs_corners`` on the matching .xml label to get the real footprint.
    """
    path = Path(path)
    hdr_path = path.with_suffix(".hdr")
    if not hdr_path.exists():
        raise FileNotFoundError(f"expected ENVI header alongside cube, not found: {hdr_path}")
    header = _parse_envi_header(hdr_path)
    total_bands = header["bands"]
    band_indices = bands if bands is not None else _default_preview_bands(total_bands)
    with rasterio.open(path) as dataset:
        if dataset.count != total_bands:
            raise ValueError(
                f"'.hdr' declares {total_bands} bands but rasterio sees {dataset.count} in {path.name} "
                "-- header and cube are out of sync, do not proceed without checking this"
            )
        array = dataset.read(band_indices)
        return {
            "file_path": path.as_posix(),
            "array": array,
            "loaded_bands": band_indices,
            "total_bands": total_bands,
            "width": int(dataset.width),
            "height": int(dataset.height),
            "dtype": str(dataset.dtypes[0]),
            "crs": dataset.crs.to_wkt() if dataset.crs else None,
            "transform": tuple(dataset.transform)[:6],
        }


def _default_preview_bands(total_bands: int) -> list[int]:
    """Pick a small spread of bands (near-IR start/mid/end) for quick inspection."""
    if total_bands <= 3:
        return list(range(1, total_bands + 1))
    return [1, total_bands // 2, total_bands]


def _parse_envi_header(hdr_path: Path) -> dict[str, Any]:
    """Parse the small subset of ENVI header fields M1 needs."""
    text = hdr_path.read_text(encoding="utf-8", errors="ignore")
    fields: dict[str, Any] = {}
    for key in ("samples", "lines", "bands", "data type", "header offset"):
        match = re.search(rf"^{re.escape(key)}\s*=\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
        if match:
            fields[key.replace(" ", "_")] = int(match.group(1))
    interleave_match = re.search(r"^interleave\s*=\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
    fields["interleave"] = interleave_match.group(1).lower() if interleave_match else None
    if "bands" not in fields:
        raise ValueError(f"could not parse 'bands' out of ENVI header: {hdr_path}")
    return fields


# --- IIRS PDS4 label parsing --------------------------------------------------
#
# Confirmed against a real ch2_iir_nri_*.xml label: ISRO's ISDA schema stores
# the swath footprint as four explicitly named corners inside
# <isda:Geometry_Parameters>, e.g.:
#
#   <isda:upper_left_latitude unit="deg">-30.375724</isda:upper_left_latitude>
#   <isda:upper_left_longitude unit="deg">25.176954</isda:upper_left_longitude>
#   ... upper_right_*, lower_left_*, lower_right_* ...
#
# These are named corners, not a generic point list, so we read them by name
# and emit them in a fixed perimeter walk order (UL -> UR -> LR -> LL) to
# guarantee a valid (non-self-intersecting) polygon ring regardless of how
# the swath is rotated relative to lat/lon axes.

_PDS_NS_PATTERN = re.compile(r"\{[^}]*\}")

_IIRS_CORNER_ORDER = ("upper_left", "upper_right", "lower_right", "lower_left")


def _strip_namespace(tag: str) -> str:
    return _PDS_NS_PATTERN.sub("", tag)


def parse_iirs_corners(xml_path: Path) -> list[tuple[float, float]]:
    """Parse the four ISDA-named swath corners out of an IIRS PDS4 label.

    Returns [(lon, lat), ...] for upper_left, upper_right, lower_right,
    lower_left, in that perimeter-walk order (a valid polygon ring).
    Raises ValueError if any of the eight expected lat/lon tags is missing.
    """
    xml_path = Path(xml_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    values: dict[str, float] = {}
    for element in root.iter():
        tag = _strip_namespace(element.tag)
        for corner in _IIRS_CORNER_ORDER:
            if tag == f"{corner}_latitude":
                values[f"{corner}_lat"] = _safe_float(element.text)
            elif tag == f"{corner}_longitude":
                values[f"{corner}_lon"] = _safe_float(element.text)

    missing = [
        f"{corner}_{axis}"
        for corner in _IIRS_CORNER_ORDER
        for axis in ("lat", "lon")
        if values.get(f"{corner}_{axis}") is None
    ]
    if missing:
        raise ValueError(
            f"IIRS label {xml_path.name} is missing expected Geometry_Parameters tags: {missing}. "
            "Expected <isda:upper_left_latitude>/<isda:upper_left_longitude> etc. "
            "inside <isda:Geometry_Parameters> -- label structure may differ for this product variant."
        )

    return [(values[f"{corner}_lon"], values[f"{corner}_lat"]) for corner in _IIRS_CORNER_ORDER]


def _safe_float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None