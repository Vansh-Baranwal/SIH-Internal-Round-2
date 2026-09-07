# M4 Phase 11.6: Geometric Verification

## Purpose

Phase 11.6 consumes the frozen Phase 11.5 anchor-selection result and determines whether the supplied correspondence evidence is geometrically consistent with a valid image-to-reference transformation.

This is a verification step only. It does not estimate lunar coordinates, produce a localization confidence score, retrieve an ROI, or validate physical crater truth.

> Geometric verification is not coordinate estimation and does not by itself constitute lunar localization.

## Input contract

The authoritative input is a `GeometricVerificationRequest` built from:

- `AnchorSelectionResult` from Phase 11.5
- `point_pairs` keyed by candidate/anchor ID
- each point-pair payload containing actual `source` and `reference` arrays of shape `(N, 2)`
- optional `GeometricVerificationConfig`

The implementation does not rerun feature extraction, landmark retrieval, or anchor selection. It consumes only the already-produced point-pair evidence.

## Output contract

The output is `GeometricVerificationResult` with:

- `status`
- `model`
- `verified_anchor_id`
- `selected_anchor_ids`
- `inlier_count`
- `inlier_ratio`
- `mean_reprojection_error_px`
- `median_reprojection_error_px`
- `max_reprojection_error_px`
- `outlier_count`
- `spatial_coverage`
- `transform_matrix`
- `residuals_px`
- `warnings`
- `limitations`
- `provenance`
- explicit `claims_geometric_verification=True`
- explicit `claims_localization=False`
- explicit `claims_coordinate_estimation=False`

## Geometric model

This phase uses the project’s existing OpenCV-based robust estimation layer and intentionally supports only:

- `affine` for planar, near-nadir transfer between source and reference points
- `homography` where a projective transform is scientifically appropriate

The TPS model is intentionally excluded from this phase because the project does not establish it as the correct geometric verification model for this boundary, and the earlier 11.4/11.5 contracts define a conservative verification-only stage rather than a full non-rigid registration model.

## Estimator

The implementation reuses the repository’s authoritative `correspondence_engine.geometry.ransac.geometric_verification()` adapter and calls it with the selected model and `ransac_thresh` configured through `GeometricVerificationConfig`.

The estimator is deterministic for a fixed input set and configuration. The robust fitting is applied only to the supplied point pairs and is reported as a transformation artifact for verification, not localization.

## Minimum correspondence requirements

For this Phase 11.6 contract, the minimum point requirement is the real model requirement:

- affine: minimum 3 correspondences
- homography: minimum 4 correspondences

The configured `min_inliers` must be checked against the actual model. Insufficient numeric evidence is rejected with explicit status values rather than silently repaired.

## Degeneracy handling

The implementation rejects point sets that are invalid for transformation fitting:

- non-finite coordinates (NaN/Inf)
- mismatched source/reference lengths
- duplicate source points
- duplicate destination points
- near-collinear or degenerate configurations when insufficient rank exists for the model
- malformed or missing payloads

These conditions are reported as explicit statuses including `INVALID_INPUT`, `NONFINITE_COORDINATES`, and `DEGENERATE_CONFIGURATION`.

## Inlier/outlier semantics

The Phase 11.4 output is descriptor evidence; Phase 11.5 selects candidate anchors; Phase 11.6 determines which correspondences are geometrically consistent with the fitted model.

This means:

- tentative correspondences are the upstream descriptor matches
- selected anchors are the Phase 11.5 candidate IDs
- geometric inliers are those accepted by the robust transform fit
- geometric outliers are those rejected by the fit

A geometric inlier is not automatically a confirmed crater, a validated landmark, or a localized lunar coordinate.

## Residual and reprojection metrics

Residuals are calculated in pixels using the fitted transform and the known source/reference point pairs.

Reported metrics include:

- per-point reprojection residuals
- mean residual
- median residual
- max residual
- inlier count
- outlier count
- inlier ratio

All residuals are explicitly labeled as pixel-space metrics and are not interpreted as physical localization error.

## Spatial coverage

If the point-pair evidence is valid, the implementation reports a simple image-space coverage metric based on the source-point span. This prevents a transform from appearing strong when all points are clustered into a tiny region.

Coverage is reported separately from residual error and does not become a localization confidence measure.

## Verification thresholds

The config exposes explicit thresholds:

- `min_inliers`
- `min_inlier_ratio`
- `max_reprojection_error_px`
- `ransac_thresh_px`

Each threshold is deterministic, configurable, and documented. It does not represent scientific calibration or geographic confidence.

## Determinism

For the same input evidence and configuration, the output is reproducible. The implementation preserves candidate ordering from the upstream selection result and reports deterministic statuses, warnings, and provenance metadata.

## Provenance and synthetic data

Phase 11.6 preserves provenance from the upstream phases and never upgrades the provenance classification. Synthetic fixtures remain synthetic; unavailable evidence stays unavailable.

## Artifacts

The `GeometricVerificationResult` object itself is the primary artifact. It stores:

- candidate/anchor identity
- transformation matrix (when available)
- estimator configuration
- inlier/outlier counts
- residual statistics
- coverage
- provenance
- warnings
- limitations

No geographic maps or coordinate outputs are fabricated in this phase.

## Testing

The focused tests cover:

- valid affine verification
- invalid inputs
- insufficient correspondences
- degeneracy checks
- duplicate source points
- NaN/Inf rejection
- inlier ratio and residual reporting
- deterministic behavior
- provenance preservation
- no coordinate estimation output

## Limitations

This phase is intentionally bounded:

- it does not estimate latitude/longitude
- it does not localize the image
- it does not produce ROI retrieval
- it does not generate model-based confidence for lunar localization
- it does not use TPS in this phase

## Boundary with 11.5 and 11.7

Phase 11.5 prepares candidate anchors from descriptor evidence. Phase 11.6 validates whether that evidence is geometrically coherent. Phase 11.7 and later are explicitly deferred and must not be inferred here.
