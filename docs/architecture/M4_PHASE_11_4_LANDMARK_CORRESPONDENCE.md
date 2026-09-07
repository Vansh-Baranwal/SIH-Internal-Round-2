# M4 Phase 11.4: Landmark Correspondence for Unknown Images

## Purpose

Phase 11.4 is the retrieval-to-correspondence boundary in the Phase 11 Lunar Image GPS pipeline:

Unknown Image → Feature Extraction → Landmark Database Query → Landmark Correspondence → Anchor Selection → Geometric Verification → Coordinate Estimation → ROI Retrieval

This phase does not localize the image, select an anchor, estimate coordinates, or perform geometric verification. It only asks a narrow scientific question: do the observable features in the unknown image correspond to reference feature evidence associated with one or more retrieved landmark candidates?

> Correspondence is not geometric verification and is not localization.

## Scope and boundary

The implementation consumes:

- the frozen `UnknownImage` contract from Phase 11.1
- the metadata-quality assessment from Phase 11.2 when present
- the candidate landmark retrieval result from Phase 11.3
- configurable feature reference data for each retrieved candidate

The implementation does not perform:

- anchor selection or ranking
- RANSAC, MAGSAC++, homography fitting, TPS fitting, or other geometric verification
- coordinate estimation or localization confidence scoring
- physical lunar interpretation, crater confirmation, or hazard claims
- ROI retrieval

## Input contract

The main Phase 11.4 input is `LandmarkCorrespondenceRequest` in `src/lunar_hazard_mapper/m4_terrain/landmark_correspondence.py`.

It contains:

- `image`: a validated `UnknownImage`
- `retrieval_result`: the Phase 11.3 `LandmarkRetrievalResult`
- `reference_features`: a mapping from candidate ID to a feature payload
- `matcher`: descriptor matching method name
- `ratio_threshold`: descriptor ratio-test threshold
- `min_matches`: minimum required surviving matches
- `allow_partial`: controls whether partial results are allowed

The request is intentionally narrow and deterministic. It does not fabricate missing data or infer spatial truth from filenames or directories.

## Output contract

The output is `LandmarkCorrespondenceResult`, which includes:

- `status`
- `unknown_image_id`
- `candidate_ids`
- `records`
- `warnings`
- `limitations`
- `provenance`
- explicit `claims_localization=False`
- explicit `claims_geometric_verification=False`
- explicit `claims_correspondence` semantics only when supported by actual evidence

Per-candidate `LandmarkCorrespondenceRecord` values include:

- candidate ID
- status
- feature counts
- tentative match count
- surviving match count
- descriptor distances
- similarity scores
- matched keypoint pairs
- warnings and limitations
- provenance of source and candidate
- `geometric_verification_performed=False`

## Feature representation

The project already provides OpenCV-based feature extraction for image feature matching through the existing M2 correspondence stack. Phase 11.4 reuses the repository’s practical descriptor-matching approach without introducing a separate ML or geometric framework.

The implementation uses a simple deterministic feature representation:

- keypoints as `(x, y)` pixel coordinates
- descriptor vectors as numeric rows
- deterministic `feature_count`
- descriptor dimensionality tracking
- optional feature type metadata such as `sift`

Reference landmark feature sets are accepted as explicit payloads when supplied. Missing or malformed feature payloads remain intentionally unavailable or invalid rather than being invented.

## Matching and filtering method

The implementation uses a ratio-test descriptor matcher based on OpenCV brute-force matching.

The algorithm is intentionally limited to:

1. extract unknown-image SIFT features when a local readable image exists
2. validate reference feature payload structure
3. compare descriptor dimensionality compatibility
4. compute tentative descriptor matches with a ratio test
5. report counts of tentative and surviving matches
6. return the result without geometric verification

This is correspondence evidence only. It is not geometric inlier filtering or transformation fitting.

## Thresholds and configuration

The phase exposes configuration on the request:

- `ratio_threshold` default `0.75`
- `min_matches` default `2`
- `matcher` default `sift`
- `allow_partial` default `True`

The thresholds are explicit and deterministic. They are not described as scientifically calibrated unless the repository later provides calibration evidence.

## Status taxonomy

The implementation uses explicit statuses such as:

- `SUCCESS`
- `NO_CANDIDATES`
- `NO_FEATURES`
- `REFERENCE_FEATURES_UNAVAILABLE`
- `IMAGE_UNAVAILABLE`
- `INVALID_INPUT`
- `INCOMPATIBLE_FEATURES`
- `NO_CORRESPONDENCES`
- `PARTIAL_CORRESPONDENCE`
- `CORRESPONDENCE_FAILED`
- `BLOCKED_BY_PROVENANCE`

These states distinguish retrieval from actual feature evidence and avoid collapsing all failures into one generic result.

## Provenance and scientific integrity

The implementation preserves the project’s provenance architecture:

- `UnknownImage.provenance`
- candidate provenance from `LandmarkCandidate`
- use of `DataProvenance` enum values
- propagation of synthetic/real/unavailable states without upgrades
- explicit warnings for provenance mismatch

The phase does not convert synthetic or unavailable evidence into real correspondence. It also does not fabricate pixels, keypoints, descriptors, or landmark observations.

## Artifacts

The phase may emit deterministic JSON-like results and match summaries in the result object itself. It does not generate fake visualization images or localization artifacts. Any artifact is an audit record of correspondence evidence only, not a localization product.

## Determinism and order

The result ordering is deterministic for the same image input, landmark candidate set, and configuration.

- candidate IDs are preserved in retrieval ordering
- correspondence records are emitted in retrieval order
- match descriptors and metrics are reported in deterministic order when available

## Known limitations

This phase is intentionally limited and deliberately conservative:

- descriptor matching is only as good as the supplied feature payloads
- missing local imagery blocks feature extraction
- missing reference features remain unavailable
- descriptor compatibility mismatches remain incompatible
- no geometric verification means the result remains tentative evidence only
- no localization or coordinate estimate is permitted

## Boundary with 11.5 and 11.6

Phase 11.4 ends before:

- anchor selection (Phase 11.5)
- geometric verification and transformation fitting (Phase 11.6)
- coordinate estimation (Phase 11.7)
- confidence evaluation and ROI retrieval (later phases)

A successful correspondence result is therefore evidence of tentative feature-level agreement only, not a localized landmark or verified geometric alignment.

## Implementation and validation status

The implementation and validation in the repository enforce the contract and guardrails described above. The focused Phase 11.4 tests and the adjacent Phase 11.1–11.3 regression suites pass in the project environment.
