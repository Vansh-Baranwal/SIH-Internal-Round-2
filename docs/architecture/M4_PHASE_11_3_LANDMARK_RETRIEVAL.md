# M4 Phase 11.3: Landmark Retrieval for Unknown Images

## Purpose

Phase 11.3 is the retrieval-only stage in the Phase 11 Lunar Image GPS pipeline:

Unknown Image → Feature Extraction → Landmark Database Query → Correspondence Engine → Geometric Verification → Coordinate Estimation → ROI Retrieval

This phase does not localize the image, does not match landmarks to the unknown image, and does not estimate coordinates. It only retrieves candidate landmark records from the project’s existing landmark source and packages them as deterministic, provenance-aware retrieval results.

## Boundary and Scope

Phase 11.3 consumes:

- the frozen `UnknownImage` contract from Phase 11.1
- metadata-quality status from Phase 11.2 where appropriate
- the project’s existing landmark records or landmark database source

Phase 11.3 does not perform:

- feature extraction
- correspondence matching
- geometric verification
- coordinate estimation
- localization claims
- ROI retrieval

The phase must explicitly preserve the fact that the unknown image has not yet been localized.

## Retrieval Contract

The new retrieval API centers on:

- `LandmarkRetrievalRequest`: the input request combining the unknown image, optional landmark source, metadata quality, and retrieval constraints
- `LandmarkQuery`: a deterministic normalized query built from the unknown image metadata
- `LandmarkCandidate`: a retrieved candidate landmark record with provenance, score, rank, and warnings
- `LandmarkRetrievalResult`: the retrieval outcome including status, candidates, warnings, and limitations
- `RetrievalStatus`: the explicit result-state enum for retrieval-only behavior

### Retrieval status values

- `SUCCESS`: retrieval succeeded with one or more candidate records
- `EMPTY_RESULT`: retrieval executed but no candidate records satisfied the query
- `NO_RETRIEVAL_CONTEXT`: retrieval context is insufficient when `require_context=True`
- `LANDMARK_SOURCE_UNAVAILABLE`: no authoritative landmark source is configured
- `INVALID_INPUT`: the unknown image is invalid or malformed
- `INVALID_LANDMARK_SOURCE`: the supplied source is not a recognized project source
- `RETRIEVAL_FAILED`: the retrieval operation failed unexpectedly

## Source handling

The implementation checks the project’s existing landmark infrastructure and supports the reusable scientific sources already in the repository:

- `CraterLandmarkDatabase`
- `CraterLandmarkNetwork`
- list/tuple sequences of `CraterLandmark` objects, converted into an in-memory network automatically

If no authoritative source is available, the request returns `LANDMARK_SOURCE_UNAVAILABLE` rather than fabricating landmarks.

## Query construction

The retrieval query is normalized from available `UnknownImage` fields, including:

- `image_id`
- `image_reference`
- sensor and GSD if present
- CRS if present
- metadata coordinates when they are supplied as metadata-only data
- provenance and metadata-quality status

The query is deterministic and intentionally does not infer hidden coordinates or file path semantics. Filenames are preserved exactly as provided; no directory-based localization guesswork is introduced.

## Candidate semantics

Candidates are returned as retrieval-only references. They are not matches.

Each candidate carries:

- stable landmark identifier
- source database information
- provenance metadata
- optional score
- retrieval rank
- warnings and limitations

Important guardrails:

- `claims_correspondence` remains `False`
- `claims_localization` remains `False`
- no estimated coordinate field is introduced into the retrieval result
- metadata coordinates remain metadata-only and are never treated as an estimated localization

## Provenance and safety

The retrieval layer enforces provenance awareness without turning retrieval into scientific interpretation.

- synthetic landmarks remain identifiable as synthetic
- real-data unknown images and synthetic landmark sources generate a provenance warning
- the system preserves the difference between actual landmark source provenance and the fact that the unknown image itself is still not localized

This prevents synthetic or illustrative data from being mistaken for scientifically validated match outcomes.

## Validation and tests

The Phase 11.3 suite validates the retrieval boundary using direct, contract-driven tests for:

- valid retrieval success
- deterministic ordering
- empty result handling
- unavailable and invalid sources
- retrieval context gating
- provenance mismatch warnings
- serialization round-trips
- no correspondence/localization claims

## Implementation status

This phase is intentionally limited to retrieval-only logic. Matching, geometric verification, coordinate estimation, and ROI retrieval remain out of scope and are explicitly deferred to later Phase 11 tasks.
