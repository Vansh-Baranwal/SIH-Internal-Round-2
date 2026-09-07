# M4 Phase 10.10: New-Crater / Ejecta Candidates

## 1. Purpose

Phase 10.10 screens existing Phase 10.9 temporal candidates for observable image-space characteristics that may justify later specialized validation. It is candidate screening, not a detector that assumes a crater exists.

## 2. Pipeline position

The stage follows 10.9 Change Classification and precedes 10.11 false-positive validation and 10.12 final temporal-change validation. It does not implement either later phase.

## 3. Scientific-integrity boundary

Outputs are `NEW_CRATER_CANDIDATE`, `EJECTA_CANDIDATE`, `CRATER_AND_EJECTA_CANDIDATE`, `NON_SPECIALIZED_CANDIDATE`, or `UNDETERMINED`. These are algorithmically screened candidates based on observable temporal-difference morphology. They are not confirmed craters, ejecta deposits, impacts, or physical lunar changes. No physical cause, confidence, probability, material change, or geological process is inferred.

## 4. Input contract

`CraterEjectaCandidateRequest` requires a successful or empty `ChangeClassificationResult`, matching `ChangeCandidateResult`, matching successful `NoiseSuppressionResult`, and configuration. The authoritative 10.8 mask and labels must agree with 10.9 records and with the signed difference, absolute difference, and boolean valid mask. Observation IDs must match. No upstream stage is rerun and no new temporal candidate is created.

## 5. Crater-like indicators

The screen measures component area, inclusive bounding box, aspect ratio, extent, perimeter, compactness, equivalent diameter in pixels, radial coverage, and boundary contact. A non-boundary candidate is crater-like only when at least three independent indicators are present: compact circular-like geometry, bounded aspect ratio, sufficient image-space area, and measurable radial extent. This is a multi-indicator engineering screen, not a crater claim.

## 6. Ejecta-like indicators

An ejecta-like screen requires both broad diffuse extent and measurable radial absolute-difference decline. Diffuse morphology alone is insufficient. No isolated diffuse candidate is labeled ejecta solely because it is diffuse. There is no implicit central/surrounding association between separate components in this implementation.

## 7. Radial analysis

For each existing component, radial distances are measured from its image-space centroid. Absolute-difference values are grouped into four deterministic radial bins spanning the component's observed radius. The output reports bin means, counts, coverage, maximum radius, and decline from the first to last available mean. Empty bins are JSON `null`, not zero or NaN. Radial analysis is limited to the existing component; it does not create a surrounding temporal region. At least three populated bins are required for radial availability.

## 8. Central/surrounding analysis

No separate-component association or inferred surrounding region is implemented. The screen deliberately analyzes only each authoritative 10.8/10.9 component and its internal radial profile.

## 9. Geometry methodology

Perimeter is the count of component pixels removed by 3x3 binary erosion. Compactness is `4*pi*area/perimeter^2`; extent is area divided by bounding-box area; aspect ratio is the larger bounding-box dimension divided by the smaller; equivalent diameter is `sqrt(4*area/pi)`. All dimensions are pixels. No geographic coordinates, lunar metres, GSD conversion, or physical area is fabricated.

## 10. Sign-response methodology

The screen reports positive and negative signed-pixel counts plus signed mean and median. Signed polarity remains an observed temporal response. It is never called deposition, excavation, erosion, material gain/loss, or impact.

## 11. Mask/NaN behavior

The Phase 10.7 valid mask is authoritative. Candidate pixels must be valid and finite in both difference products. Negative absolute values, invalid mask states, label inconsistencies, NaNs in candidates, and shape mismatches are rejected. Invalid values are never replaced with zero and cannot influence geometry or radial measurements.

## 12. Thresholds/configuration

Defaults are `minimum_morphology_pixels=9`, `crater_compactness_threshold=0.65`, `crater_max_aspect_ratio=1.75`, `crater_min_radial_bins=3`, `crater_min_radial_coverage=0.60`, `ejecta_min_area_pixels=15`, `ejecta_max_extent=0.55`, `ejecta_min_radial_bins=3`, `ejecta_min_radial_decline=0.10`, `radial_bin_count=4`, and `analysis_window_margin=2`. They are explicit engineering screening criteria, not scientific calibration. Boundary contact suppresses crater/ejecta specialization because morphology is incomplete.

## 13. Screening scores

No numerical screening score is emitted. The output contains only measured descriptors and indicator lists.

## 14. Candidate taxonomy

The exact candidate types are `NEW_CRATER_CANDIDATE`, `EJECTA_CANDIDATE`, `CRATER_AND_EJECTA_CANDIDATE`, `NON_SPECIALIZED_CANDIDATE`, and `UNDETERMINED`.

## 15. Unknown/undetermined handling

Candidates below `minimum_morphology_pixels` are `UNDETERMINED`. Valid candidates with no specialized indicators are `NON_SPECIALIZED_CANDIDATE`. A valid empty upstream set returns `NO_CANDIDATES`; a valid batch with no specialized results returns `NO_SPECIALIZED_CANDIDATES`.

## 16. Boundary handling

Image-boundary candidates retain geometry and boundary status but lose compact/radial crater indicators and receive `boundary_truncation_limits_morphology`. Missing surroundings are not treated as evidence against or for ejecta.

## 17. Output artifacts

The configured output directory receives `crater_ejecta_candidates.json` and `crater_ejecta_candidate_summary.json`. Phase 10.7, 10.8, and 10.9 artifacts are not overwritten.

## 18. Provenance

The summary preserves both observation IDs, Phase 10.9 and 10.8 statuses, Phase 10.7 provenance, all input artifact references, method, exact thresholds, warnings, and limitations. It explicitly says that outputs are not confirmed craters, ejecta deposits, impacts, or physical lunar changes.

## 19. Status handling

Implemented statuses are `SUCCESS`, `NO_CANDIDATES`, `NO_SPECIALIZED_CANDIDATES`, `UNDETERMINED`, `INVALID_CLASSIFICATION_INPUT`, `MISSING_CANDIDATE_ARTIFACT`, `INVALID_CANDIDATE_ARTIFACT`, `SHAPE_MISMATCH`, `INVALID_PIXEL_DATA`, `INSUFFICIENT_MORPHOLOGY`, and `SCREENING_FAILED`. Individual generic or insufficient candidates do not fail a valid batch.

## 20. Test coverage

Focused tests cover compact multi-indicator screening, elongated rejection, diffuse-only rejection, radial decline, mixed signed response preservation, boundaries, invalid masks, NaN-safe upstream behavior, insufficient morphology, multiple candidates, no specialized candidates, missing artifacts, shape mismatch, reproducibility, provenance, guardrails, and raw artifact preservation.

## 21. Scientific limitations

Candidate screening is based on small image-space temporal components and cannot establish physical causation. It may reflect residual noise, illumination, registration, or other artifacts. It does not confirm a crater, ejecta, impact, or physical lunar change. 10.11 and 10.12 validation remain required.

## 22. Explicit non-goals

No crater/ejecta confirmation, physical dimensions, impact energy, geological process, material deposition/removal claim, confidence/probability, external model, network call, candidate recreation, or Phase 10.11/10.12 implementation is included.
