# M4 Phase 10.6: Illumination-Aware Filtering

Phase 10.6 assesses illumination differences between the genuine observations
behind a Phase 10.5 image difference. The repository contains no validated
observation-specific lunar photometric/BRDF model and no authoritative DEM
illumination model for these observations. Its existing M2 illumination
utility is a feature-map transform for matching, and its M4 shadow simulator
is explicitly synthetic. Neither is used to claim a physical correction.

The implementation therefore uses a conservative, explicit `metadata_gate`:
it compares the Phase 10.1 illumination fields and creates a binary
illumination-compatibility mask only when the required fields are present and
within configured engineering tolerances. This mask is not a probability and
does not identify which remaining pixels are physical change.

The five compared fields are `sun_azimuth_deg`, `sun_elevation_deg`,
`phase_angle_deg`, `incidence_angle_deg`, and `emission_angle_deg`. Azimuth
uses the shortest circular difference, so 359 degrees and 1 degree differ by
2 degrees. The other fields use absolute differences. Missing values remain
missing and are never treated as zero. View geometry is reported as available
or unavailable but is not modeled.

`IlluminationFilterConfig` exposes non-negative tolerances for each field and
the `filter_different_geometry` policy. Defaults are zero tolerance and a
conservative global gate for explicitly different geometry. These are
engineering controls, not scientifically calibrated lunar thresholds.

`IlluminationFilterRequest` references a successful Phase 10.5
`ImageDifferenceResult`, its Phase 10.1 `ObservationPair`, and the config.
Failed or mismatched difference results cannot be filtered. The raw signed
difference, raw absolute difference, and raw valid mask are never overwritten.

For `COMPARABLE` geometry, the filter retains the Phase 10.5 valid mask. For
explicitly `DIFFERENT` geometry, the default global gate excludes all raw-valid
pixels because no pixel-level model can distinguish illumination effects; the
filtered arrays contain NaN rather than zero. For `UNKNOWN` or
`INSUFFICIENT_METADATA`, no filtered pixels are fabricated and the status is
`INSUFFICIENT_ILLUMINATION_MODEL` while raw artifacts remain available.

Filtered artifacts are separate `.npy` files:

- `illumination_filtered_signed_difference.npy`
- `illumination_filtered_absolute_difference.npy`
- `illumination_compatibility_mask.npy`
- `illumination_filter_summary.json`

Before/after statistics report valid counts and mean, median, and standard
deviation of absolute differences. They describe filtering only and are not
change confidence. Provenance records the Phase 10.6 method, raw-preservation
policy, and difference orientation.

Statuses include `SUCCESS`, `INSUFFICIENT_ILLUMINATION_MODEL`,
`INVALID_DIFFERENCE_INPUT`, `MISSING_DIFFERENCE_ARTIFACT`,
`INVALID_DIFFERENCE_ARTIFACT`, `SHAPE_MISMATCH`, and `FILTERING_FAILED`.

**Phase 10.6 reduces or flags differences that may be explained by
illumination/viewing geometry. It does not establish that remaining
differences represent genuine physical lunar change.** Noise suppression,
change candidates, classification, and final validation are deferred to later
phases.