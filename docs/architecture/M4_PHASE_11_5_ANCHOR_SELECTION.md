# M4 Phase 11.5: Anchor Selection for Correspondence Candidates

## Purpose

Phase 11.5 is the explicit preparation step between Phase 11.4 landmark correspondence and the later geometric verification stage.

Unknown Image → Feature Extraction → Landmark Database Query → Landmark Correspondence → Anchor Selection → Geometric Verification → Coordinate Estimation → ROI Retrieval

Its purpose is to take the upstream Phase 11.4 correspondence evidence and identify which candidate(s) are suitable to pass forward as candidate anchors for downstream verification.

> Anchor selection does not constitute geometric verification or localization.

## Definition of an anchor

In this phase, an anchor is a retrieved landmark candidate with enough correspondence evidence to justify downstream geometric verification.

An anchor is not:

- a verified map alignment
- a localised coordinate estimate
- a confirmed candidate match in a geographic sense
- a confidence-certified result
- a geometric inlier set

It is simply a deterministic selection of correspondence evidence that is suitable for the next stage.

## Input contract

The authoritative input is the frozen Phase 11.4 `LandmarkCorrespondenceResult` object from `src/lunar_hazard_mapper/m4_terrain/landmark_correspondence.py`.

The Phase 11.5 request consumes:

- the upstream `LandmarkCorrespondenceResult`
- optional `AnchorSelectionConfig`
- deterministic selection logic based only on available 11.4 metrics

The implementation does not rerun feature extraction or landmark retrieval.

## Output contract

The output is `AnchorSelectionResult`, which includes:

- `status`
- `selected_anchor_ids`
- `rejected_anchor_ids`
- `ambiguous_anchor_ids`
- `ranking`
- `warnings`
- `limitations`
- `provenance`
- explicit `claims_localization=False`
- explicit `claims_geometric_verification=False`
- explicit `claims_localization_confidence=False`

## Selection methodology

The implementation ranks only candidates that already have explicit correspondence evidence from Phase 11.4.

Selection criteria are deliberately limited to evidence actually produced by 11.4:

- surviving match count
- tentative match count
- match survival ratio
- descriptor-distance statistics
- similarity-score statistics
- feature coverage derived from surviving matches relative to feature counts

The result is computed deterministically using:

1. higher surviving-match evidence first
2. higher survival ratio
3. better similarity score summary
4. lower descriptor-distance summary
5. stable candidate-id tie-break

This is an engineering ranking score, not a scientific probability or localization confidence metric.

## Configuration parameters

The module exposes `AnchorSelectionConfig` with:

- `min_surviving_matches` default 1
- `min_tentative_matches` default 1
- `min_survival_ratio` default 0.0
- `max_anchors` default 1

Every threshold is explicit, deterministic, and purely operational.

## Ambiguity handling

When multiple candidates are eligible, the implementation preserves ambiguity explicitly.

Possible behaviors include:

- `SINGLE_ANCHOR_SELECTED`
- `MULTIPLE_ANCHORS_SELECTED`
- `NO_ELIGIBLE_ANCHORS`
- `NO_CORRESPONDENCE`
- `AMBIGUOUS_ANCHORS`
- `INVALID_INPUT`

This prevents collapse of ambiguity into a false scientific certainty.

## Provenance rules

The Phase 11.5 output preserves upstream provenance and selection metadata:

- unknown-image provenance
- candidate provenance
- selection configuration
- selection methodology
- warnings and limitations

Synthetic fixtures remain as synthetic. Unavailable or external evidence stays unavailable and is never upgraded into a real anchor.

## Scientific guardrails

This phase explicitly avoids:

- coordinate estimation
- RANSAC or MAGSAC++
- affine/homography/TPS fitting
- localization confidence
- geographic ranking based on guessed coordinates
- crater or geological interpretation
- hazard conclusions

The selection score is limited to correspondence evidence and not a scientific certainty measure.

## Artifacts

The result object itself acts as the audit artifact. It records ranking evidence, selected IDs, rejected candidates, and configuration without inventing visual or localization artifacts.

## Testing and validation

The project includes focused tests in `tests/test_m4_11_5_anchor_selection.py` for:

- valid single anchor selection
- multiple eligible anchors
- no eligible anchors
- deterministic ordering
- provenance preservation
- absence of coordinate estimation and geometric verification claims
- invalid-input handling

## Limitations

Phase 11.5 is intentionally conservative. It only operates on evidence already produced by Phase 11.4. If the correspondence data is missing, malformed, or insufficient, the result remains inconclusive rather than fabricating an anchor.

## Boundary with 11.4 and 11.6

Phase 11.5 ends before:

- geometric verification (Phase 11.6)
- coordinate estimation (Phase 11.7)
- localization confidence (Phase 11.8)
- ROI retrieval (Phase 11.9)

The selected anchors are only candidates prepared for the next phase, not verified spatial solutions.
