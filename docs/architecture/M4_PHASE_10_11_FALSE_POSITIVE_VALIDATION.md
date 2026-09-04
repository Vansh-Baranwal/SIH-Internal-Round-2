# M4 Phase 10.11: False-Positive Validation

## 1. Purpose

Phase 10.11 evaluates whether a previously screened temporal candidate contains measurable false-positive evidence. It does not confirm a physical lunar change, candidate cause, or crater/ejecta interpretation. It only checks whether the authoritative 10.7-10.10 chain contains evidence that an observed signal may be explained by a registration, boundary, mask, illumination, noise, or support artifact.

## 2. Pipeline position

This stage follows 10.10 crater/ejecta candidate screening and precedes any later final temporal-change validation. It does not implement or duplicate earlier stages. It consumes authoritative upstream artifacts and reports only validation evidence, not physical truth.

## 3. Scientific-integrity boundary

The stage may emit categories such as `REGISTRATION_ARTIFACT`, `BOUNDARY_ARTIFACT`, `MASK_ARTIFACT`, `ILLUMINATION_ARTIFACT`, `NOISE_ARTIFACT`, `INSUFFICIENT_SUPPORT`, or `METADATA_LIMITATION`. It may also report `NO_FALSE_POSITIVE_EVIDENCE` when no measurable artifact explanation is present. It never claims that a candidate is confirmed as a crater, impact, ejecta deposit, or physical lunar change.

The implementation explicitly avoids:
- false-positive probability claims
- confidence scores
- crater/ejecta confirmation
- material gain/loss interpretation
- impact or geological causation claims
- replacement of 10.12 final validation

## 4. Input contract

`FalsePositiveValidationRequest` requires:
- a valid `CraterEjectaCandidateResult` from Phase 10.10
- a valid `ChangeClassificationResult` from Phase 10.9
- a valid `ChangeCandidateResult` from Phase 10.8
- a valid `NoiseSuppressionResult` from Phase 10.7
- a `FalsePositiveValidationConfig`

Optional inputs are:
- `TemporalRegistrationResult` from Phase 10.4
- `IlluminationFilterResult` from Phase 10.6

Observation IDs must match across the authoritative chain. No upstream stage is rerun, and no new change candidate is created.

## 5. Evidence checks

The validator performs conservative checks on the authoritative candidate:

- registration quality: inlier ratio, RMSE, and spatial coverage
- illumination metadata: missing or incomplete geometry metadata
- boundary truncation: contact with image bounds or truncated morphology
- valid-mask support: candidate pixels dominated by invalid or masked support
- support size: whether the candidate remains large enough to discriminate from isolated noise
- residual-noise level: whether local residual variability is suspiciously high

Each check is recorded in `ValidationCheck` entries with a status and evidence. Candidate-level output retains the relevant categories, warnings, limitations, and provenance without making a physical claim.

## 6. Output semantics

The result is a `FalsePositiveValidationResult` whose top-level status is one of:
- `NO_CANDIDATES`
- `NO_FALSE_POSITIVE_EVIDENCE`
- `LIKELY_FALSE_POSITIVE`
- `FALSE_POSITIVE`
- `INCONCLUSIVE`
- `VALIDATION_BLOCKED`
- `INVALID_INPUT`

A result with no detected false-positive category is not treated as confirmation of physical change. It is only a negative result for measurable artifact evidence in the supplied chain.

## 7. Provenance and artifacts

The summary artifact preserves:
- observation IDs
- upstream phase metadata
- input artifact references for candidate mask, candidate labels, signed difference, absolute difference, and valid mask
- thresholds
- warnings and limitations
- scientific interpretation stating this is false-positive validation only

The validator writes `false_positive_validation_summary.json` under the configured output directory while leaving upstream artifacts unchanged.

## 8. Guardrails and non-goals

The implementation deliberately does not:
- recreate candidate masks/labels
- infer physical processes from sign response
- establish confidence or probability
- convert image-space evidence into crater, ejecta, or impact confirmation
- claim final validation

## 9. Test coverage

The focused suite exercises clean candidates, poor registration, boundary truncation, invalid mask support, illumination metadata limitation, insufficient support, multiple candidates, no candidates, threshold boundaries, reproducibility, provenance guardrails, and raw artifact preservation.

## 10. Final status

This stage is a conservative evidence-only validation layer for false-positive explanations. It is not a physical-change detector and must remain separate from later final validation.
