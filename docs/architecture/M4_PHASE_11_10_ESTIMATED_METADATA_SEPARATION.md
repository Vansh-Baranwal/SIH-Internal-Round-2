# M4 Phase 11.10: Estimated-vs-Metadata Coordinate Separation

## Purpose and Pipeline Position

Phase 11.10 follows ROI Retrieval and reports two independent coordinate records: the Phase 11.7 estimated coordinate and the source coordinate supplied by `UnknownImage.metadata_coordinates`. It describes whether the records are comparable and, only then, their coordinate-space difference. It does not determine accuracy or truth.

## Upstream Contracts

The implementation consumes the frozen `CoordinateEstimationResult`, `UnknownImage`, and `MetadataQualityResult` contracts. The estimated CRS is read only from the existing Phase 11.7 `reference_georeferencing` provenance record because the frozen estimate result does not expose a separate CRS field. Metadata values and provenance remain distinct. No Phase 11.8 confidence or Phase 11.9 ROI computation is called or changed.

## Metadata Quality and Coordinate Semantics

Missing metadata returns `METADATA_MISSING`. A malformed or nonfinite metadata record, or a frozen quality field marked invalid, returns `METADATA_INVALID`. A metadata record may be compared only when it explicitly declares coordinate system, CRS, reference frame, units, axis order, and two finite values. `lon`/`lat` keys alone do not establish geographic semantics. Partial metadata quality permits a comparison with an explicit limitation; insufficient, unknown, or invalid quality does not.

## Comparability and Difference

Before comparison, coordinate dimensionality and coordinate system, CRS, reference frame, units, and axis order must match exactly. No CRS conversion, datum assumption, axis swap, or longitude wrapping is performed. A comparable result reports signed per-axis difference, absolute per-axis difference, and Euclidean coordinate-space separation. That separation is labeled as a coordinate-space difference, never as positional error, accuracy, or ground-truth deviation.

## Results and Provenance

`EstimatedMetadataSeparationResult` preserves separate estimated and metadata records, quality status, semantic details, differences, limitations, interpretation, and independent provenance. Synthetic inputs remain synthetic. The result contains no validated/best coordinate and no confidence, ROI, accuracy, or ground-truth field.

## Statuses and Non-goals

`COMPARABLE`, `NOT_COMPARABLE`, `METADATA_MISSING`, `METADATA_INVALID`, `ESTIMATE_MISSING`, `ESTIMATE_INVALID`, `BLOCKED`, and `INVALID_INPUT` distinguish the comparison outcomes. This phase does not modify the estimate, compare against ground truth, recalculate confidence, alter ROI retrieval, perform localization accuracy testing, or perform final lunar GPS validation. CRS/reference-frame conversion remains an explicit limitation until an authoritative project convention exists.