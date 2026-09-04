# M4 Phase 10.7: Noise Suppression

Phase 10.7 consumes only the successful Phase 10.6 illumination-filtered
signed and absolute difference artifacts. It applies a conservative,
mask-aware median operation to reduce isolated high-frequency noise. It does
not detect, classify, or interpret physical lunar change.

The default method is `masked_median` with a 3x3 kernel and a minimum of three
valid neighbors. These are explicit engineering parameters, not scientifically
calibrated lunar thresholds. A `none` method is also available for controlled
pass-through testing. The default filter is intentionally small because
stronger smoothing could erase small spatial signals or blur boundaries.

The Phase 10.6 illumination compatibility mask is authoritative. Invalid
pixels remain invalid and are stored as NaN in suppressed numerical products.
A valid pixel is influenced only by finite valid neighbors; when its valid
neighborhood is too small, its original valid center value is retained rather
than fabricated. The propagated boolean mask is saved separately. No invalid
region is filled with zero and no interpolation crosses invalid regions.

Signed differences retain the Phase 10.5/10.6 orientation `registered_A -
reference_B` and remain floating point. Absolute differences are filtered
separately and remain non-negative. The raw Phase 10.6 artifacts are never
overwritten.

Outputs are written as source-of-truth `.npy` arrays:

- `noise_suppressed_signed_difference.npy`
- `noise_suppressed_absolute_difference.npy`
- `propagated_valid_mask.npy`
- `noise_suppression_summary.json`

The result reports before/after valid and finite counts, signed mean,
absolute mean/median/standard deviation, and a high-frequency residual
standard deviation. That residual is an engineering diagnostic, not a noise
percentage, confidence value, or physical-change probability.

Phase 10.7 rejects unsuccessful or insufficient Phase 10.6 results, missing
filtered artifacts, invalid arrays, shape/mask mismatches, non-finite valid
pixels, and negative absolute differences. Zero valid input produces
`NO_VALID_DATA` without output fabrication.

Provenance links both observation IDs, Phase 10.6 status and artifacts, the
selected method and parameters, the mask policy, and the explicit limitation
that no physical lunar change was determined.

**Noise suppression does not establish that a temporal difference is a real
lunar surface change.** Change candidates, classification, crater/ejecta
analysis, and validation remain deferred to later phases.