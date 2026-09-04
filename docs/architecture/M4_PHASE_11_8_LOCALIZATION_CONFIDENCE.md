# M4 Phase 11.8: Localization Confidence

## Purpose and Pipeline Position

Phase 11.8 follows Phase 11.7 coordinate estimation and precedes Phase 11.9
ROI retrieval. It evaluates how strong and internally consistent the upstream
localization evidence is. It does not measure coordinate accuracy.

## Inputs and Output

`evaluate_localization_confidence` consumes the frozen
`GeometricVerificationResult` from Phase 11.6 and
`CoordinateEstimationResult` from Phase 11.7. The output is
`LocalizationConfidenceResult`, containing identifiers, upstream provenance,
raw evidence, normalized components, an explanation, limitations, warnings,
and an explicit status.

## Score Semantics

The bounded `evidence_score` is deterministic and uncalibrated. A value from
0 to 1 is an engineering quality score, not a probability of correctness and
not a claim of positional accuracy, ground-truth agreement, or metadata
agreement. No validated probabilistic model exists in the repository.

The score is the transparent weighted sum:

* `0.25 * min(inlier_count / 12, 1)`
* `0.20 * inlier_ratio`
* `0.30 * max(1 - mean_reprojection_error_px / 5, 0)`
* `0.25 * spatial_coverage`

Weights are engineering choices, not statistical independence assumptions.
The residual remains in upstream pixel units. Missing, nonfinite, out-of-range,
or contradictory evidence is rejected rather than favorably imputed.

## States and Thresholds

* `NOT_COMPUTABLE`: an upstream result is absent.
* `BLOCKED`: coordinate estimation did not complete because its chain was
  blocked, georeferencing/CRS was unavailable, or the result was out of extent.
* `INVALID_INPUT`: malformed results, invalid geometry, contradictory claims,
  unsupported model, or invalid evidence.
* `LOW`: score `< 0.40`.
* `MODERATE`: `0.40 <= score < 0.75`.
* `HIGH`: score `>= 0.75`.

Blocked and not-computable states have no score. They are not low confidence.

## Provenance and Scientific Boundaries

Input provenance is copied without upgrading it. Synthetic evidence remains
synthetic. The implementation does not use metadata coordinates, filenames,
paths, IDs, ground truth, or ROI data. It does not average independent
coordinate estimates, convert pixels to physical units, or infer a datum/CRS.

## Limitations and Non-goals

This phase does not validate accuracy (Phase 11.11), compare estimated and
metadata coordinates (Phase 11.10), retrieve an ROI (Phase 11.9), or perform
final lunar GPS validation (Phase 11.12). Inlier count and ratio are related
signals and are intentionally described as engineering evidence rather than
independent statistical factors. The score is not calibrated for any mission
or sensor.