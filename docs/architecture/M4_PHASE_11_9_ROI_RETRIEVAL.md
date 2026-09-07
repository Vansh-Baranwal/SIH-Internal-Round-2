# M4 Phase 11.9: ROI Retrieval

## Purpose and Position

Phase 11.9 maps a successful Phase 11.7 estimated coordinate into the explicitly selected reference product and retrieves the requested native raster window. It follows Phase 11.8 confidence evaluation. Retrieval is a mapping and data-access operation; it does not assess localization accuracy.

## Repository Infrastructure

The implementation reuses the frozen `ReferenceImageGeoreferencing` contract from Phase 11.7 and Rasterio, which is already used by M1 metadata inspection, QA, tiling, preprocessing, and image-pair handling. Rasterio supplies the authoritative dataset dimensions, CRS, affine transform, bounds, and window reads. No network retrieval or parallel raster system is introduced.

## Contracts

`ReferenceProduct` requires a product identifier, source type, matching Phase 11.7 georeferencing, provenance, and either a local path or external reference as appropriate. `ROIWindow` explicitly declares positive width, height, and either `pixels` or `coordinate` units. Pixel dimensions are integers. `ROIRetrievalRequest` carries the Phase 11.7 result, product, ROI, request ID, optional Phase 11.8 result, and caller provenance.

`ROIRetrievalResult` preserves status, requested center, resolved native window, returned data when pixels were really read, ROI and parent dimensions, ROI bounds and transform, coordinate semantics, product source/provenance, warnings, limitations, and reason. Its serialization explicitly reports whether pixels were retrieved.

## Mapping and Boundaries

The estimated coordinate is inverse-mapped through the product's full six-coefficient affine transform, including rotation terms. Pixel ROIs are centered on that resolved native pixel. Coordinate-sized ROIs inverse-map all four coordinate-space corners and read the enclosing native window. CRS, coordinate system, reference frame, units, axis order, product identity, raster dimensions, transform, and parsed CRS are checked before extraction.

Fully contained windows return `SUCCESS`. A boundary-intersecting request returns `OUT_OF_BOUNDS` unless `allow_partial=True`; then only the intersection is read and the result is `PARTIAL`. A completely disjoint request is `OUT_OF_BOUNDS`. The requested center is never moved and no coordinate is clamped into the raster. ROI sizes are never silently shrunk.

## Availability and Provenance

Only `LOCAL_AVAILABLE` products with an existing path are opened. External, local-missing, unavailable, and unknown sources return `REFERENCE_UNAVAILABLE`; they are never fabricated or downloaded. Product metadata and provenance are carried to the result, and synthetic products remain marked synthetic. Successful extraction from a synthetic fixture proves mechanics only.

## Statuses and Safeguards

`SUCCESS`, `PARTIAL`, `BLOCKED`, `INVALID_INPUT`, `REFERENCE_UNAVAILABLE`, `OUT_OF_BOUNDS`, and `FAILED` distinguish valid extraction, explicit clipping, absent upstream information, invalid contracts, unavailable references, spatial nonintersection, and unexpected runtime failures. Missing/nonfinite coordinates or incomplete semantics are rejected or blocked. An optional confidence result is identity-checked but never rescored.

## Non-goals and Limitations

This phase does not compare estimated coordinates with metadata coordinates, calculate error against ground truth, modify the Phase 11.8 score, validate lunar GPS, infer coordinates from names or paths, or establish geographic accuracy. Coordinate conversion between CRS/reference frames is intentionally unsupported; mismatches are rejected. The current implementation reads native windows and does not resample coordinate-sized requests.