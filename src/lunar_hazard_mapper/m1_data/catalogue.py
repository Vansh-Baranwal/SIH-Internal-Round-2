"""Master source catalogue construction owned by Member 1 (M1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rasterio.crs import CRS
from rasterio.warp import transform_bounds

from lunar_hazard_mapper.m1_data.overlap import verify_real_overlap


PRODUCTS = {
    "TMCORTHO5-1": "TMC_ORTHO",
    "ORTHONAC0.5-1": "HR_ORTHO",
    "NAC": "NAC",
    "TMCDTM": "DEM",
    "IIRSRAW-1": "IIRS",
    "SELENE_TCO": "SELENE",
}

# Products checked as candidate reference tiles against TMC_ORTHO. Kept as a
# separate set (not just "everything in PRODUCTS") because DEM/NAC aren't
# meaningful "does this overlap TMC for registration purposes" candidates
# the way OHRC/IIRS are.
REFERENCE_PRODUCTS = {"HR_ORTHO", "IIRS"}


def _area(bounds: dict[str, float]) -> float:
    """Return the area of a bounding box."""
    return max(0.0, bounds["east"] - bounds["west"]) * max(0.0, bounds["north"] - bounds["south"])


def _comparable_bounds(record: dict[str, Any], target_crs: CRS) -> dict[str, float] | None:
    """Transform record bounds into target CRS when both CRS values are usable."""
    try:
        source_crs = CRS.from_wkt(record["crs"])
        bounds = record["bounds"]
        west, south, east, north = transform_bounds(
            source_crs, target_crs, bounds["west"], bounds["south"], bounds["east"], bounds["north"]
        )
        return {"west": west, "south": south, "east": east, "north": north}
    except (KeyError, TypeError, ValueError):
        return None


def _record_bounds(record: dict[str, Any]) -> dict[str, float] | None:
    """Get a comparable bbox from a record, whether it has real `bounds` or
    a corner-derived footprint (OHRC/IIRS -- see inspect_data.py's
    _attach_real_footprint_from_corners)."""
    if record.get("bounds"):
        return record["bounds"]
    if record.get("corners"):
        lons = [c[0] for c in record["corners"]]
        lats = [c[1] for c in record["corners"]]
        return {"west": min(lons), "south": min(lats), "east": max(lons), "north": max(lats)}
    return None


def find_overlapping_hr_tiles(
    tmc_record: dict[str, Any],
    hr_records: list[dict[str, Any]],
    min_overlap_fraction: float = 0.1,
) -> list[str]:
    """Find HR/IIRS tiles covering at least a fraction of a TMC tile's area.

    FIX (bbox-threshold bug): this used to divide the intersection area by
    the TMC tile's own area unconditionally. For real Chandrayaan-2 data,
    TMC tiles are physically enormous compared to OHRC/IIRS tiles -- a small
    footprint fully contained inside a TMC tile intersects only ~1% of the
    TMC area, which never clears a 10% threshold no matter how good the real
    overlap is. Now divides by whichever tile (TMC or the candidate) is
    smaller, which is the correct question ("how much of the smaller tile
    does this cover").

    FIX (corners bug): this used to read `hr_record.get("bounds")` only --
    OHRC/IIRS records built from corner data (not embedded CRS) have no
    `bounds` key at all, so they were silently skipped here regardless of
    real overlap. Now falls back to a corner-derived bbox via
    `_record_bounds()`.
    """
    try:
        tmc_crs = CRS.from_wkt(tmc_record["crs"])
    except (KeyError, TypeError, ValueError):
        tmc_bounds = tmc_record["bounds"]
        tmc_area = _area(tmc_bounds)
        if tmc_area <= 0:
            return []
        overlaps = []
        for hr_record in hr_records:
            hr_bounds = _record_bounds(hr_record)
            if not hr_bounds:
                continue
            width = min(tmc_bounds["east"], hr_bounds["east"]) - max(tmc_bounds["west"], hr_bounds["west"])
            height = min(tmc_bounds["north"], hr_bounds["north"]) - max(tmc_bounds["south"], hr_bounds["south"])
            hr_area = _area(hr_bounds)
            denominator = min(tmc_area, hr_area) if hr_area > 0 else tmc_area
            if width > 0 and height > 0 and denominator > 0 and (width * height) / denominator >= min_overlap_fraction:
                overlaps.append(str(hr_record["file_path"]))
        return overlaps
    tmc_bounds = tmc_record["bounds"]
    tmc_area = _area(tmc_bounds)
    if tmc_area <= 0:
        return []
    overlaps: list[str] = []
    for hr_record in hr_records:
        hr_bounds = _comparable_bounds(hr_record, tmc_crs) or _record_bounds(hr_record)
        if not hr_bounds:
            continue
        width = min(tmc_bounds["east"], hr_bounds["east"]) - max(tmc_bounds["west"], hr_bounds["west"])
        height = min(tmc_bounds["north"], hr_bounds["north"]) - max(tmc_bounds["south"], hr_bounds["south"])
        hr_area = _area(hr_bounds)
        denominator = min(tmc_area, hr_area) if hr_area > 0 else tmc_area
        if width > 0 and height > 0 and denominator > 0 and (width * height) / denominator >= min_overlap_fraction:
            overlaps.append(str(hr_record["file_path"]))
    return overlaps


def _crs_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    try:
        return CRS.from_wkt(left["crs"]) == CRS.from_wkt(right["crs"])
    except (KeyError, TypeError, ValueError):
        return False


def _find_reference_tiles(tmc_record: dict[str, Any], hr_records: list[dict[str, Any]], min_overlap_fraction: float) -> list[str]:
    """Find overlaps after converting HR footprints, including lunar projection differences."""
    matches = find_overlapping_hr_tiles(tmc_record, hr_records, min_overlap_fraction)
    if matches:
        return matches
    # HR and TMC use different lunar coordinate frames; derive a common geographic frame.
    try:
        tmc_crs = CRS.from_wkt(tmc_record["crs"])
    except (KeyError, TypeError, ValueError):
        return []
    tmc_bounds = tmc_record["bounds"]
    tmc_area = _area(tmc_bounds)
    if tmc_area <= 0:
        return []
    for hr in hr_records:
        try:
            hr_crs = CRS.from_wkt(hr["crs"])
            h = hr["bounds"]
            west, south, east, north = transform_bounds(hr_crs, tmc_crs, h["west"], h["south"], h["east"], h["north"])
        except (KeyError, TypeError, ValueError):
            continue
        width = min(tmc_bounds["east"], east) - max(tmc_bounds["west"], west)
        height = min(tmc_bounds["north"], north) - max(tmc_bounds["south"], south)
        if width > 0 and height > 0 and width * height / tmc_area >= min_overlap_fraction:
            matches.append(str(hr["file_path"]))
    return matches


def _verified_reference_tiles(
    tmc_record: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    min_overlap_fraction: float = 0.1,
) -> dict[str, Any]:
    """
    Two-stage check for any reference product (OHRC or IIRS) against TMC:

      1. Fast bbox pre-filter (_find_reference_tiles) narrows the full
         candidate catalogue down to plausible pairs.
      2. Each surviving candidate is re-checked with
         overlap.verify_real_overlap(), which reads real pixel data at the
         claimed intersection region on both sides.

    Returns both the bbox candidate list and the verified subset, plus the
    verification detail for each candidate.
    """
    bbox_candidate_paths = _find_reference_tiles(tmc_record, candidate_records, min_overlap_fraction)
    if not bbox_candidate_paths:
        return {"bbox_candidates": [], "verified_paths": [], "verification_detail": []}

    by_path = {str(r["file_path"]): r for r in candidate_records}
    verified_paths: list[str] = []
    detail: list[dict[str, Any]] = []
    for path in bbox_candidate_paths:
        candidate_record = by_path.get(path)
        if candidate_record is None:
            continue
        try:
            result = verify_real_overlap(tmc_record, candidate_record)
        except (OSError, ValueError) as exc:
            result = {"verified": False, "reason": f"verification error: {exc}"}
        detail.append({"file_path": path, **result})
        if result.get("verified"):
            verified_paths.append(path)

    return {
        "bbox_candidates": bbox_candidate_paths,
        "verified_paths": verified_paths,
        "verification_detail": detail,
    }


def validate_crs_consistency(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Check whether each source product uses one CRS value."""
    grouped: dict[str, set[str]] = {}
    for record in records:
        grouped.setdefault(str(record["source_product"]), set()).add(str(record.get("crs")))
    return {
        product: {"crs_values": sorted(values), "is_consistent": len(values) <= 1}
        for product, values in sorted(grouped.items())
    }


def build_catalogue(inspection_dir: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the authoritative catalogue from Phase 1 inspection manifests."""
    del config  # Reserved for future catalogue policy configuration.
    inspection_dir = Path(inspection_dir)
    source_records: list[dict[str, Any]] = []
    reference_records: list[dict[str, Any]] = []  # OHRC + IIRS pool, checked against TMC
    payloads: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(inspection_dir.glob("inspection_*.json")):
        if path.name == "inspection_summary.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        label = str(payload["dataset"])
        payloads.append((label, payload))
        if PRODUCTS.get(label) in REFERENCE_PRODUCTS:
            reference_records.extend(payload.get("records", []))

    for label, payload in payloads:
        product = PRODUCTS.get(label)
        if product is None:
            continue
        for original in payload.get("records", []):
            record = dict(original)
            record["source_product"] = product
            record["processing_status"] = "pending"

            # FIX (OHRC-excluded bug): this used to require BOTH
            # has_valid_crs AND has_valid_transform, which is correct for
            # products with real embedded georeferencing (TMC, DEM) but
            # wrongly excludes OHRC/IIRS -- those genuinely have no real
            # embedded transform (they open with an identity transform),
            # even though inspect_data.py has since derived a real, usable
            # footprint for them from PDS4 label corners
            # (has_derived_footprint). A record with a derived footprint is
            # just as usable for overlap/registration purposes as one with
            # a native CRS -- it was only ever "excluded" because the check
            # was looking for the wrong kind of evidence.
            has_native_georef = bool(record.get("has_valid_crs") and record.get("has_valid_transform"))
            has_derived_georef = bool(record.get("has_derived_footprint"))
            record["include"] = has_native_georef or has_derived_georef
            if record["include"]:
                record["exclusion_reason"] = None
            else:
                record["exclusion_reason"] = "missing or invalid CRS/transform"

            if product == "TMC_ORTHO":
                references = _verified_reference_tiles(record, reference_records)
                record["reference_available"] = bool(references["verified_paths"])
                record["reference_hr_paths"] = references["verified_paths"]
                record["reference_hr_bbox_candidates"] = references["bbox_candidates"]
                record["reference_verification_detail"] = references["verification_detail"]
            else:
                record["reference_available"] = False
                record["reference_hr_paths"] = []
            source_records.append(record)

    stats: dict[str, Any] = {product: {"total": 0, "reference_available": 0, "excluded": 0} for product in PRODUCTS.values()}
    for record in source_records:
        product_stats = stats[record["source_product"]]
        product_stats["total"] += 1
        product_stats["reference_available"] += int(record["reference_available"])
        product_stats["excluded"] += int(not record["include"])
    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": source_records,
        "stats": stats,
        "crs_consistency": validate_crs_consistency(source_records),
    }


def save_catalogue(catalogue: dict[str, Any], output_path: Path) -> None:
    """Save a catalogue as formatted JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8")