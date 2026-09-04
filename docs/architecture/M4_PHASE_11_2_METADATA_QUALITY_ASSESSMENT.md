# M4 Phase 11.2: Metadata Quality Assessment

## Phase
Phase 11.2 - Metadata Quality Assessment

## Status
READY

## Objective
Assess the quality and completeness of metadata attached to an `UnknownImage` record without performing localization, coordinate estimation, or any later-stage scientific inference. This stage is intentionally limited to evaluating the metadata as supplied by the Phase 11.1 contract.

## Scope boundary
This module intentionally does not:
- estimate image ground location
- fabricate coordinates or georeferencing data
- infer hidden spatial truth from weak metadata
- localize the image or compute unresolved geometry
- perform Phase 11.3+ scientific interpretation or mapping

The assessment is strictly metadata-only and deterministic.

## Input contract
The input is the frozen Phase 11.1 `UnknownImage` object from `src/lunar_hazard_mapper/m4_terrain/unknown_image.py`.

Required semantics:
- `image_id` and `image_reference` must be present and non-empty
- `provenance` must be a valid `DataProvenance` enum value
- `image_reference_type` must be recognized, with explicit handling for local/external/unavailable states
- `warnings` remains informational metadata and is preserved in the assessment result
- metadata fields may be missing, present-valid, limited, unknown, or invalid
- no coordinate values are estimated or synthesized

## Output contract
The module returns `MetadataQualityResult` with:
- `image_id`
- `assessment_status`
- `completeness_status`
- `completeness_score`
- `field_assessments` keyed by field name
- `warnings`
- `limitations`
- `provenance`
- `source_contract` and `source_contract_version`

Each `FieldAssessment` contains:
- `field_name`
- `status` from `FieldAssessmentStatus`
- `message`
- `value_summary`

## Assessment logic
The implementation evaluates fields in categories:

1. Reference and provenance
   - checks for non-empty `image_reference`
   - validates `image_reference_type`
   - classifies local/external/unavailable metadata states
   - flags contradictory provenance and `is_real_data`

2. Generic metadata fields
   - validates dimensional and type constraints
   - marks missing values as `MISSING`
   - marks invalid or non-positive numeric fields as `INVALID`
   - keeps metadata-only values distinct from geolocation estimates

3. Temporal metadata
   - parses ISO-8601 acquisition timestamps and dates
   - flags timezone-naive timestamps as `LIMITED`
   - detects date/timestamp disagreement

4. Geometric metadata
   - validates `illumination` and `view_geometry` map structure
   - ensures footprint bounds and coordinate containers are well-formed
   - preserves metadata-only semantics even when coordinates are present

5. Overall quality scoring
   - `PRESENT_VALID` = 1.0
   - `LIMITED` = 0.5
   - missing/unknown/invalid = 0.0
   - overall status is selected deterministically from the aggregate score and invalid flags

## Scientific guardrails
The module intentionally does not:
- convert metadata quality into certainty about hazard presence
- imply localization from weak metadata
- create fallback coordinate estimates
- assert an image is georeferenced when only metadata exists

The quality result is a statement about metadata sufficiency, not about the actual lunar ground truth.

## Files
- `src/lunar_hazard_mapper/m4_terrain/metadata_quality.py`
- `tests/test_m4_11_2_metadata_quality.py`
- `src/lunar_hazard_mapper/m4_terrain/__init__.py`

## Validation
Focused validation command executed:
- `.venv\Scripts\python.exe -m pytest tests/test_m4_11_2_metadata_quality.py -q`

Result:
- 32 passed, 0 failed
