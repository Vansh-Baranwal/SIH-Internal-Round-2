# M4 Phase 11 HTTP API Contract

## 1. Purpose

This document describes the minimal HTTP boundary around the existing frozen Phase 11 implementation. The adapter validates an explicit `UnknownImage` request, runs the existing Phase 11.2 metadata assessment and Phase 11.3 retrieval boundary, and returns an explicit blocked response when the repository does not provide the required landmark source.

It does not reimplement Phase 11, expose the M2 correspondence route as Phase 11, integrate the frontend, or fabricate downstream evidence.

## 2. Exact endpoint

- Method: `POST`
- Path: `/api/phase11/lunar-gps`
- Request content type: `application/json`
- Response content type: `application/json`
- Router: `src/lunar_hazard_mapper/api/phase11_router.py`
- Registration: `src/lunar_hazard_mapper/api/main.py`, included in the production `app`

This route is distinct from `/api/v1/correspondence/register`, which remains the separate unregistered M2 correspondence router.

## 3. Request schema

The top-level request is `Phase11Request`:

| Field | Type | Required/default | Meaning |
|---|---|---|---|
| `validation_request_id` | non-empty string | required | Caller correlation ID; passed to the API envelope, not renamed into a registration ID |
| `image` | `UnknownImageHttpRequest` | required | Explicit JSON projection used to construct frozen `UnknownImage` |

`UnknownImageHttpRequest` supports only fields that construct the existing Phase 11.1 object:

- Required: `image_id`, `image_reference`, `provenance_source`.
- Defaulted: `image_reference_type: unknown`, `provenance: unavailable`, `is_real_data: false`, `validation_status: unvalidated`, `warnings: []`.
- Optional: `source_id`, `product_id`, `local_path`, `external_reference`, positive `width`, `height`, `channels`, `bit_depth`, `image_format`, `dtype`, positive `gsd_m`, `crs`, `geospatial_reference`, `footprint`, `acquisition_timestamp`, `acquisition_date`, `sensor`, `source_name`, `illumination`, `view_geometry`, `metadata_coordinates`, `metadata_quality`, and `notes`.

`image_reference_type` accepts the frozen values `local_available`, `external_reference`, `local_missing`, `unavailable`, `unknown`, and `invalid`; the frozen object rejects invalid references. `provenance` accepts the existing `DataProvenance` values. Unknown fields are rejected.

The API does not accept image bytes, a landmark database, reference feature maps, point pairs, reference georeferencing, ROI requests, or truth references. Those inputs are not safely available as a single supported production HTTP contract in the current repository. External references are recorded only; the adapter does not download them.

The frozen `UnknownImage` validation remains authoritative after Pydantic validation. Contradictory real/synthetic state, malformed dates/footprints/metadata, and unsupported reference combinations return structured HTTP 422 responses.

## 4. Response schema

The response is `Phase11ApiResponse`:

| Field | Type | Meaning |
|---|---|---|
| `validation_request_id` | string | Echoed caller correlation ID |
| `status` | string | API operation state; currently `blocked` when the real prerequisite boundary is unavailable |
| `source_image_id` | string | Actual `UnknownImage.image_id` |
| `metadata_quality` | `Phase11StageResponse` | Actual 11.2 result status and exact `MetadataQualityResult.to_dict()` payload |
| `landmark_retrieval` | `Phase11StageResponse` | Actual 11.3 result status and exact `LandmarkRetrievalResult.to_dict()` payload |
| `downstream_statuses` | mapping of stage to optional status | Explicit `not_executed` markers for 11.4-11.12 |
| `final_validation` | object or null | Null because 11.12 is not safely executable without required upstream artifacts |
| `warnings` | list of strings | Combined actual 11.2/11.3 warnings |
| `limitations` | list of strings | Actual retrieval limitations plus explicit API blocking reason |
| `provenance` | object | Boundary provenance and actual input classification |

`Phase11StageResponse.result` preserves the owning frozen `to_dict()` shape. No estimated coordinate, confidence score, RMSE, transform, CRS, accuracy, truth reference, ROI, or registration ID is added when its owning phase has not produced one.

The response is currently `200` with `status: blocked` for an accepted request whose next prerequisite is unavailable. This is an expected scientific state, not an internal server error.

## 5. Status semantics

The adapter preserves the frozen status values where a stage has run:

- `metadata_quality.status`: actual `MetadataAssessmentStatus` value.
- `landmark_retrieval.status`: actual `RetrievalStatus` value, currently `landmark_source_unavailable` when no source is supplied.
- Top-level `status: blocked`: the API cannot continue without the actual landmark source and does not manufacture downstream results.
- Downstream `not_executed`: an explicit transport state, not a scientific Phase 11 result status.

The API does not claim `validated`, `technically_valid`, or `inconclusive` for a final result because 11.12 is not called without its required chain artifacts. It does not upgrade a blocked state.

## 6. Error semantics

- HTTP 422: Pydantic request validation failure or frozen `UnknownImage` construction failure. The response detail contains `status: invalid_input` and a reason for adapter construction failures; standard FastAPI validation details are used for schema failures.
- HTTP 200 with top-level `blocked`: expected missing prerequisite, such as no serializable project landmark source. The response preserves stage payloads and limitations.
- HTTP 500: unexpected adapter/execution failure. The response exposes only `{ "status": "internal_error", "reason": "Phase 11 execution failed." }`; no stack trace is returned.

Expected scientific blocking is not converted into HTTP 500.

## 7. Provenance and synthetic/real semantics

The adapter passes request values into frozen `UnknownImage` unchanged. It returns:

- `provenance.image_provenance`: the actual input provenance value;
- `provenance.provenance_source`: the caller-supplied provenance record;
- `provenance.synthetic`: true only when the input provenance is the frozen `synthetic` value;
- the exact metadata/retrieval provenance nested in each frozen result payload.

There is no server-side `real=true` default. `REAL` provenance still requires `is_real_data=true`, and synthetic/unavailable values remain classified as supplied. Metadata is not promoted to truth. No authoritative truth reference is created.

## 8. Internal Phase 11 mapping

```text
Phase11Request.image
  -> UnknownImageHttpRequest.to_unknown_image()
  -> frozen UnknownImage
  -> assess_metadata_quality(image)
  -> frozen MetadataQualityResult
  -> LandmarkRetrievalRequest(image=image, metadata_quality=metadata)
  -> retrieve_landmarks(request)
  -> frozen LandmarkRetrievalResult
  -> Phase11ApiResponse
```

The adapter stops at 11.3 because no supported HTTP input supplies a project landmark source. Consequently 11.4 correspondence, 11.5 anchors, 11.6 geometry, 11.7 coordinate estimation, 11.8 confidence, 11.9 ROI, 11.10 separation, 11.11 accuracy, and 11.12 final validation are explicitly not executed. No algorithm is duplicated in the API layer.

## 9. Registered-output availability

A unified Phase 11 registered-output handoff remains **NOT FOUND**. This API does not invent a registration ID, rename `validation_request_id`, reuse M2 `job_id`, expose filesystem paths as URLs, or claim a registered raster exists.

## 10. Known limitations

- The API is a legitimate validation and early-chain boundary, but full Phase 11 execution is blocked by absent serializable landmark-source/reference-feature/georeferencing/truth inputs.
- No image upload path is provided because the frozen Phase 11.1 contract describes references and the current chain does not define an upload-to-local-reference adapter.
- The current response does not expose downstream Phase 11 result fields because those phases did not execute.
- The production app's unrelated mission/M4 routes retain their existing behavior.
- The FastAPI TestClient emits a known Starlette/httpx deprecation warning in this environment.

## 11. Example request

This is an unavailable external reference classification, not a real lunar result:

```json
{
  "validation_request_id": "example-validation-001",
  "image": {
    "image_id": "example-unknown-image",
    "image_reference": "example-external-reference",
    "image_reference_type": "external_reference",
    "provenance": "unavailable",
    "provenance_source": "documented-example-only",
    "is_real_data": false,
    "validation_status": "unvalidated",
    "external_reference": "https://example.invalid/image.tif"
  }
}
```

## 12. Example response

Illustrative shape only. Values are explicitly unavailable/example values and must never be treated as real lunar output:

```json
{
  "validation_request_id": "example-validation-001",
  "status": "blocked",
  "source_image_id": "example-unknown-image",
  "metadata_quality": {
    "status": "metadata_unknown",
    "result": {
      "image_id": "example-unknown-image",
      "assessment_status": "metadata_unknown",
      "provenance": "unavailable"
    }
  },
  "landmark_retrieval": {
    "status": "landmark_source_unavailable",
    "result": {
      "status": "landmark_source_unavailable",
      "candidates": [],
      "claims_correspondence": false,
      "claims_localization": false
    }
  },
  "downstream_statuses": {
    "11.4_landmark_correspondence": "not_executed",
    "11.7_coordinate_estimation": "not_executed",
    "11.12_final_validation": "not_executed"
  },
  "final_validation": null,
  "warnings": [],
  "limitations": [
    "No serializable project landmark source is supplied by this API.",
    "No downstream result is fabricated."
  ],
  "provenance": {
    "image_provenance": "unavailable",
    "synthetic": false
  }
}
```

## 13. Future frontend integration notes

Phase 12.2 must consume this endpoint only through an explicit client/schema mapping. It must preserve `blocked`, `not_executed`, warnings, limitations, and provenance. It must not treat the M2 correspondence route as Phase 11, invent match points/metrics/coordinates/confidence, promote metadata to truth, or infer CRS/datums.

A later backend contract is required before displaying downstream Phase 11 results: it must provide legitimate landmark/reference prerequisites, explicit georeferencing and ROI inputs, and authoritative truth inputs before 11.11/11.12 claims can be exposed.

## 14. Frozen implementation confirmation

Phase 11.1-11.12 algorithms, formulas, thresholds, provenance semantics, and status semantics were not modified. Phase 10 was not modified. The frontend was not modified. M2 correspondence semantics were not repurposed. No scientific results or authoritative lunar truth were fabricated.
