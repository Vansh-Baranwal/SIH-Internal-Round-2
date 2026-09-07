# M4 Phase 11.11: Localization Accuracy Testing

## Purpose and Boundary

Phase 11.11 evaluates an already-produced Phase 11.7 estimate against an explicitly supplied authoritative test reference. It is downstream of ROI retrieval and the Phase 11.10 estimated-versus-metadata separation. It does not alter localization, confidence, reprojection, or ROI behavior, and it does not implement Phase 11.12 final Lunar GPS validation.

The three coordinate records remain distinct:

* **Estimated coordinate:** the `CoordinateEstimationResult` emitted by Phase 11.7.
* **Source metadata coordinate:** the Phase 11.10 record; it is never accepted here as truth.
* **Authoritative test reference:** a `LocalizationTruthReference` supplied explicitly for this test case.

## Truth Reference Contract

`LocalizationTruthReference` requires a reference ID, coordinate, coordinate system, CRS, reference frame, units, axis order, source, dataset/version, provenance, authority status, and validation state. Authority status must explicitly be `authoritative` or `ground_truth`, validation state must be `validated` or `verified`, and provenance must identify both source and dataset version. A coordinate-looking field, filename, landmark ID, metadata field, confidence score, or ROI is not promoted to truth.

The current repository contains controlled synthetic truth fixtures for earlier detector tests, but no dataset inspected for Phase 11.11 establishes authoritative real lunar localization reference coordinates. Therefore real lunar accuracy is currently `NO_GROUND_TRUTH`; synthetic fixtures validate only metric mechanics.

## Comparability and Metrics

Before calculation, dimensionality, coordinate system, CRS, reference frame, units, and axis order must match exactly. No CRS conversion, axis swap, longitude wrapping, angular-to-metre conversion, or datum assumption is performed.

For estimate $e$ and reference $t$, signed axis error is $e_i - t_i$ and absolute axis error is $|e_i - t_i|$. Coordinate-space error is reported only for explicitly `projected` or `cartesian` coordinates with non-angular declared units:

$$d_c = \sqrt{\sum_i(e_i-t_i)^2}$$

It retains the declared coordinate-space units. No physical positional distance or geodesic metric is implemented because no authoritative lunar distance model is available in this phase. Geographic/angular inputs still receive per-axis coordinate differences, but no Euclidean distance or metre value.

Collections evaluate each case independently. Compatible computed cases may aggregate mean absolute axis error and coordinate-space RMSE, with exact coordinate semantics required across the aggregate. No scientific threshold is hard-coded. An optional tolerance must explicitly declare compatible units and coordinate space; it is evaluation configuration, not certification.

## Status and Integrity Rules

Individual results distinguish `ACCURACY_COMPUTED`, `NO_GROUND_TRUTH`, `BLOCKED`, `NOT_COMPARABLE`, `INVALID_ESTIMATE`, `INVALID_TRUTH`, `INVALID_INPUT`, and `INSUFFICIENT_DATA`. Truth is consumed only after the estimate object exists and is never passed into any localization phase. Truth source, reference ID, dataset version, authority, validation, and coordinate semantics are retained in result provenance. Synthetic provenance remains synthetic.

Phase 11.8 confidence is not an accuracy metric. Phase 11.6 reprojection residual is not localization error against a truth reference. Phase 11.10 metadata separation is not truth error. Successful ROI retrieval is not evidence of correctness.

## Implementation and Deferred Work

The implementation is `src/lunar_hazard_mapper/m4_terrain/localization_accuracy.py`, exported through the M4 terrain package. Focused tests are in `tests/test_m4_11_11_localization_accuracy.py`. Phase 11.12 remains responsible for any final Lunar GPS validation, certification, acceptance decision, or benchmark claim.