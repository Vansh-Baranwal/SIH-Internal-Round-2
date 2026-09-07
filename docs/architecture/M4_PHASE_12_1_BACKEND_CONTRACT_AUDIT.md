# M4 Phase 12.1: Phase 11 Backend Contract Audit

## Audit conclusion

Phase 11.1-11.12 is **IMPLEMENTED** as frozen Python dataclass/function contracts and is **EXECUTABLE** through direct imports/tests. It is **NOT EXPOSED** through the production FastAPI application. Consequently it is not **FRONTEND-CONSUMABLE** and not **INTEGRATED**.

A separate correspondence-engine router declares M2 routes, but the production app does not register that router. Those routes are not the Phase 11 lunar-GPS API.

No Phase 10 or Phase 11 implementation was modified.

## Scope and evidence

Inspected the production app and startup script, correspondence router/pipeline/metrics, all Phase 11.1-11.12 implementation modules, their architecture documents and reports, focused Phase 11 tests, and:

- `web/src/api/registration.ts`
- `web/src/api/client.ts`
- `web/src/pages/RegistrationCockpit.tsx`
- `web/src/components/MatchPointVisualization.tsx`
- `web/src/components/RegistrationMetricsPanel.tsx`

Focused validation passed: **190 Phase 11 tests passed**, with 24 known Rasterio pending-deprecation warnings. The production app and Phase 11 modules imported successfully.

## Actual HTTP exposure

### Production app

`src/lunar_hazard_mapper/api/main.py` is the app started by `scripts/start_api.py` using `lunar_hazard_mapper.api.main:app`.

It registers mission, terrain, camera, landmark, hazard, spectral, water-ice, upload, pipeline, and asset routes. It does not register a Phase 11 route and contains no `app.include_router(...)` for the correspondence router or a Phase 11 router.

**Actual Phase 11 endpoint: NONE / NOT FOUND.**

### Separate correspondence router

`src/lunar_hazard_mapper/correspondence_engine/api_router.py` declares, but does not register:

| Method | Declared path | Contract identity | Production exposure |
|---|---|---|---|
| POST | `/api/v1/correspondence/register` | M2 correspondence engine | NOT EXPOSED |
| GET | `/api/v1/correspondence/metrics/{job_id}` | M2 correspondence metrics | NOT EXPOSED |

The register route accepts `multipart/form-data`:

- required `source: UploadFile`
- required `reference: UploadFile`
- optional `matcher: str = "sift"`; accepted keys are `sift`, `akaze`, `superpoint_lightglue`, `loftr`
- optional `geo_model: str = "affine"`; no formal router enum validation

Its success response contains `job_id`, `metrics`, `warped_path`, `visualization_path`, `matches_csv_path`, and `matches_json_path`. `metrics` contains `rmse`, `inlier_count`, `total_matches`, `inlier_ratio`, `spatial_coverage`, and `meets_subpixel_target`. Errors are JSON `error` responses with 400, 422, or 500 status as applicable.

The metrics route accepts `job_id: str` and returns the saved M2 metrics object, or 404 `{ "error": "job not found" }`. Neither route accepts or returns Phase 11 `UnknownImage` or Phase 11 final-validation objects.

## Frozen internal Phase 11 contracts

These are internal Python contracts, not HTTP schemas. They are not Pydantic models and no JSON request/response envelope is registered.

### Request-side contracts

- `UnknownImage`: required non-empty `image_id`, `image_reference`, `provenance_source`; provenance and `is_real_data` must agree; `validation_status` defaults to `unvalidated`. Optional source/product identity, dimensions, GSD, CRS, footprint, acquisition, sensor, illumination, view geometry, metadata coordinates, quality, warnings, and notes are validated.
- `LandmarkRetrievalRequest`: `UnknownImage` plus optional landmark source, metadata quality, query context, quality/candidate limits, and context requirement.
- `LandmarkCorrespondenceRequest`: `UnknownImage`, retrieval result, optional reference features, matcher (`sift` default), ratio threshold (`0.75` default), minimum matches (`2` default), and `allow_partial` (`True` default).
- `GeometricVerificationRequest`: anchor selection result, point-pair mapping, optional config. Defaults are affine, minimum 3 inliers, minimum ratio 0.25, maximum reprojection error 5 px, and RANSAC threshold 3 px. Supported models are affine and homography.
- `CoordinateEstimationRequest`: unknown ID, two-dimensional target pixel, geometric result, optional reference georeferencing, reference ID, optional anchor ID, and provenance.
- `LocalizationConfidenceRequest`: optional geometric and coordinate results plus provenance.
- `ROIRetrievalRequest`: optional coordinate result, required reference product and ROI window, request ID, optional confidence and provenance. ROI units are `pixels` or `coordinate`.
- `EstimatedMetadataSeparationRequest`: request ID, optional unknown image, metadata quality, coordinate result, and provenance.
- `LocalizationAccuracyTestCase`: test ID, optional estimate and explicit truth reference, optional evaluation config, and provenance. No truth is defaulted.
- `LunarGPSFinalValidationRequest`: validation ID plus the Phase 11.1-11.11 result objects and provenance. The validator checks required chain artifacts for 11.1-11.7 and 11.11; confidence, ROI, and metadata separation are supporting optional evidence.

Validation rules, enums, defaults, and semantic boundaries are implemented in the owning modules. None is accepted over HTTP in the current application.

### Response-side contracts

The owning result objects serialize through `to_dict()` only:

- 11.1 `UnknownImage`: image identity/reference, provenance, source/product metadata, dimensions/geospatial metadata, acquisition/sensor metadata, metadata coordinates, validation status, warnings, notes.
- 11.2 `MetadataQualityResult`: image ID, assessment/completeness statuses and score, field assessments, warnings, limitations, provenance, source contract/version.
- 11.3 `LandmarkRetrievalResult`: status, query, candidates, warnings, limitations, synthetic flag, claim flags. Candidates include landmark/source/reference identities, optional coordinates and CRS, score/rank, provenance, and synthetic state.
- 11.4 `LandmarkCorrespondenceResult`: status, unknown ID, candidate IDs, records, warnings, limitations, provenance, and claim flags. Records include feature counts, tentative/surviving matches, descriptor distances, similarity scores, matched keypoints, method, and provenance.
- 11.5 `AnchorSelectionResult`: selected/rejected/ambiguous IDs, ranking, warnings, limitations, provenance, and claim flags.
- 11.6 `GeometricVerificationResult`: status, model, verified/selected anchors, inlier/outlier counts, inlier ratio, mean/median/max reprojection errors, spatial coverage, transform matrix, residuals, warnings, limitations, provenance, and claim flags.
- 11.7 `CoordinateEstimationResult`: status, image/reference/anchor IDs, target/reference pixels, estimated coordinate, coordinate system, reference frame, units, axis order, method, transformation model/parameters, warnings, limitations, provenance. CRS is not top-level here; reference CRS can be nested in provenance.
- 11.8 `LocalizationConfidenceResult`: status, image/reference/anchor IDs, uncalibrated evidence score, calibration flag, category, raw evidence, normalized components, factors, warnings, limitations, blocked reason, provenance.
- 11.9 `ROIRetrievalResult`: request/status, localization and product IDs, center, ROI request, raster window, ROI/parent dimensions, bounds, transform, coordinate semantics, source type, warnings, limitations, reason, provenance, and `pixels_retrieved`. ROI pixel data is omitted by `to_dict()`; no path field exists.
- 11.10 `EstimatedMetadataSeparationResult`: status, estimated and metadata coordinates, quality status, coordinate semantics, differences, separation, reason, interpretation, warnings, limitations, provenance. It explicitly is not localization accuracy or ground-truth error.
- 11.11 accuracy result/evaluation: explicit truth ID, axis/coordinate-space errors, tolerance state, coordinate semantics, statuses, aggregate, reason, and provenance. No authoritative real lunar truth dataset was found.
- 11.12 `LunarGPSFinalValidationResult`: validation ID, final status, level 0-4, estimated coordinate, upstream status map, evidence matrix, consistency checks, blocking reasons, warnings, limitations, decision evidence, interpretation, and provenance.

These fields are **PRESENT internally** but **NOT EXPOSED over HTTP**.

## Data-flow audit

```text
Frontend RegistrationCockpit
  -> submitRegistration returns unavailable immediately; no network request

Declared M2 correspondence router (not registered)
  -> multipart source/reference + matcher/geo_model
  -> M2 correspondence pipeline
  -> M2 metrics and output file paths

Frozen Phase 11 internal chain
  -> 11.1 UnknownImage
  -> 11.2 metadata quality
  -> 11.3 landmark retrieval
  -> 11.4 correspondence
  -> 11.5 anchor selection
  -> 11.6 geometric verification
  -> 11.7 coordinate estimation
  -> 11.8 localization confidence
  -> 11.9 ROI retrieval
  -> 11.10 estimated/metadata separation
  -> 11.11 localization accuracy
  -> 11.12 final validation
  -> no HTTP response
```

The Phase 11 stages are connected by internal request/result objects and direct tests. None is connected to `api/main.py`. The M2 route is a separate path and does not consume the Phase 11 chain. No fields are transported between a Phase 11 API request and response because that boundary does not exist.

## Registered-output audit

A compatible Phase 11 registered-output/handoff API object is **NOT FOUND**.

Existing internal pieces include a geometric transform matrix, coordinate-estimation transformation parameters, reference-product/ROI metadata, and M2 file paths for warped and match outputs. Missing as one compatible public handoff are registration ID, source/reference IDs, stable dimensions/grid and coordinate convention, provenance, registered raster identifier/API URL, and a status contract. M2 `job_id` is not a Phase 11 registration ID; a filesystem path is not a frontend-safe output contract.

## Frontend state

`web/src/api/registration.ts` is an explicit capability seam. `REGISTRATION_ENGINE_AVAILABLE` is `false`; `submitRegistration` ignores its source/reference sensor request and returns `status: 'unavailable'`. It does not fetch, construct multipart data, parse a backend response, or map errors.

Its hypothetical success type expects `registrationId`, arbitrary `metrics`, and optional source/reference point pairs. These are frontend expectations, not actual Phase 11 backend types.

`RegistrationCockpit.tsx` selects sensor IDs, calls only the unavailable seam, initializes match/metric views as unavailable, and clears data on unavailable/error. It does not show Phase 11 coordinates, CRS, ROI, accuracy, final validation, or provenance.

`MatchPointVisualization` can render normalized 0..1 source/reference pairs, but no genuine backend adapter supplies them. `RegistrationMetricsPanel` can render `rmsePx`, `inlierCount`, `inlierRatio`, `spatialCoverage`, quality, status, and message. The separate M2 route uses `rmse`, `inlier_count`, `inlier_ratio`, `spatial_coverage`, and `meets_subpixel_target`; direct use would require an explicit future mapping. No registration UI currently consumes real backend data.

The current UI uses explicit unavailable/synthetic-development messaging. It does not use fabricated registration results.

## Compatibility matrix

| Capability | Frozen Phase 11 contract | Actual backend exposure | Current frontend | Status |
|---|---|---|---|---|
| Source/reference IDs | Optional image/source/product IDs and reference IDs | NOT EXPOSED | Sensor IDs only | NOT COMPATIBLE |
| UnknownImage request | Rich frozen dataclass | NOT EXPOSED | No type/adapter | BLOCKED |
| Match points | `matched_keypoints` in internal records | NOT EXPOSED; M2 files only on unregistered router | Pair renderer shape exists | READY STRUCTURE ONLY |
| Inlier/outlier metrics | Geometric result fields | NOT EXPOSED; M2 has separate metrics | Panel supports subset | NOT INTEGRATED |
| RMSE | Reprojection fields; M2 calls it `rmse` | NOT EXPOSED for Phase 11 | Expects `rmsePx` | FIELD/CONTRACT MISMATCH |
| Transform/model | Matrix and model | NOT EXPOSED | No support | NOT COMPATIBLE |
| Coordinate/CRS | Estimate plus coordinate semantics | NOT EXPOSED | No support | BLOCKED |
| Confidence | Uncalibrated evidence score/category | NOT EXPOSED | No support | NOT COMPATIBLE |
| ROI | Status, identity, dimensions, bounds, retrieval flag | NOT EXPOSED | No support | NOT COMPATIBLE |
| Metadata quality/separation | Internal quality and explicit comparison result | NOT EXPOSED | No support | NOT COMPATIBLE |
| Accuracy/truth | Explicit truth reference/evaluation | NOT EXPOSED; truth dataset NOT FOUND | No support | BLOCKED |
| Final validation | Status, level, evidence, limitations | NOT EXPOSED | No support | NOT COMPATIBLE |
| Provenance/synthetic state | Internal provenance and claim safeguards | NOT EXPOSED by Phase 11 API | General utilities only | NOT INTEGRATED |
| Errors/blocking | Internal statuses, reasons, warnings | NOT EXPOSED | Generic unavailable/error state | UI STATE ONLY |
| Registered output | No unified Phase 11 object | NOT FOUND | No support | BLOCKED |

## Availability and tests

- Startup script exists and targets the production mission/M4 app.
- Production app import: PASS.
- Phase 11 module imports: PASS.
- Phase 11 focused regression: 190 passed, 24 known Rasterio warnings.
- M2 correspondence tests exist and use controlled synthetic image pairs; they do not prove production route registration or Phase 11 integration.
- No API test proves a Phase 11 route exists.
- No test proves the correspondence router is included in the production app; route inspection proves it is not.
- No frontend test proves real registration integration.
- Mission/API execution also depends on local mission export files; Phase 11/ROI execution depends on local image/raster inputs. No authentication contract was found.

The API is executable as a mission/M4 app, not as a Phase 11 API. The unregistered correspondence router cannot be demonstrated through the started production app without external wiring.

## Scientific-integrity audit

No active violation was found in the current registration UI or Phase 11 contracts:

- match points, metrics, coordinates, and confidence are not fabricated;
- metadata coordinates remain metadata and are not promoted to truth;
- synthetic evidence remains distinguishable and cannot validate real lunar localization;
- the confidence score is explicitly uncalibrated;
- RMSE is not converted into unsupported accuracy;
- CRS/datums and GPS/GNSS semantics are not invented;
- scientific registration and temporal calculations are not performed in React.

A future integration risk exists because the hypothetical frontend success branch uses `Record<string, unknown>` and generic names. Phase 12.2 must use explicit validated mappings and preserve provenance and status semantics.

## Missing contract pieces

- Phase 11 HTTP route and registered router: **NOT FOUND**.
- HTTP request/response schemas: **NOT FOUND**.
- Unified response envelope and error mapping: **NOT FOUND**.
- Registered-output handoff object: **NOT FOUND**.
- ROI data/path HTTP contract: **NOT EXPOSED**.
- Authoritative real lunar truth dataset and acceptance criterion: **NOT FOUND**.
- Frontend Phase 11 adapter and real integration test: **NOT FOUND**.

## Requirements before Phase 12.2

The owning backend work must first define and register an exact HTTP contract, including method, path, content type, validated request/response schemas, frozen-object mappings, identity fields, coordinate semantics, CRS/axis/units, provenance, synthetic/real state, status/error behavior, registered-output exposure, and authoritative validation evidence. API route tests must prove registration and response shape. Only then should frontend API/types/UI integration begin.

Phase 12.2 must not fabricate missing values, promote metadata to truth, reinterpret RMSE as accuracy, invent CRS/datums, or move scientific registration/temporal calculations into React.

## Frozen-state and artifact record

- Phase 10 behavior: NOT MODIFIED.
- Phase 11 behavior: NOT MODIFIED.
- Frontend files: NOT MODIFIED.
- Files created by Phase 12.1:
  - `M4_PHASE_12_1_IMPLEMENTATION_REPORT.txt`
  - `docs/architecture/M4_PHASE_12_1_BACKEND_CONTRACT_AUDIT.md`
- Phase 12.2/frontend integration: NOT STARTED.

## Final status

**PHASE 12.1 IMPLEMENTATION STATUS: READY**

**PHASE 12.1 FRONTEND INTEGRATION STATUS: NOT STARTED**
