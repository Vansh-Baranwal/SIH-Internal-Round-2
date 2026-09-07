# M4 Phase 11.1: Unknown Image Input Contract

## Purpose

`UnknownImage` is the strict input contract for a lunar image whose geographic location is not assumed to be known. This is the entry boundary for the Phase 11 Lunar Image GPS pipeline:

Unknown Image → Feature Extraction → Landmark Database Query → Correspondence Engine → Geometric Verification → Coordinate Estimation → ROI Retrieval

Phase 11.1 does not localize the image. It does not estimate lunar coordinates. It only records the image and all metadata that is genuinely available, while leaving unknown information explicitly unknown.

## Relationship to Lunar Image GPS

This contract is the upstream boundary for Lunar Image GPS. It preserves:

- image identity and references
- provenance and data-source safety
- image properties and sensor metadata
- optional geospatial metadata when supplied
- metadata-only coordinate information that is separate from future estimated coordinates
- validation state, warnings, and notes

The contract is intentionally limited to description and validation. Future phases will consume this object for query, correspondence, verification, geographic estimation, localization scoring, and ROI retrieval.

## Relationship to the Phase 11 Pipeline

Phase 11.1 defines the input object only. It is not responsible for:

- feature extraction
- landmark retrieval
- matching or correspondence
- geometric verification
- coordinate estimation
- localization confidence
- ROI retrieval

Those functional stages belong to later Phase 11 tasks and should consume `UnknownImage` without changing its semantics.

## Contract Fields

### Required fields

- `image_id`: non-empty identifier for the image record
- `image_reference`: non-empty image reference string
- `provenance`: one of the repository-backed `DataProvenance` values
- `provenance_source`: provenance record identifying the upstream source
- `is_real_data`: boolean indicating whether the image is genuine real data
- `validation_status`: non-empty string such as `unvalidated` or `validated`

### Optional fields

- `source_id`, `product_id`
- `local_path`, `external_reference`
- `width`, `height`, `channels`
- `image_format`, `dtype`, `bit_depth`
- `gsd_m`
- `crs`
- `geospatial_reference`
- `footprint`
- `acquisition_timestamp`, `acquisition_date`
- `sensor`, `source_name`
- `illumination`
- `view_geometry`
- `metadata_coordinates`
- `metadata_quality`
- `warnings`, `notes`

## Image Reference Semantics

The contract supports several clearly distinguished statuses via `UnknownImageReferenceType`:

- `LOCAL_AVAILABLE`: local image exists and is available
- `EXTERNAL_REFERENCE`: non-local reference such as a URL or remote identifier
- `LOCAL_MISSING`: local path is declared but missing
- `UNAVAILABLE`: unavailable reference state
- `UNKNOWN`: reference exists but cannot be classified safely
- `INVALID`: malformed or empty reference

The contract does not attempt to download external images or infer locations from filenames or directories.

## Provenance Semantics

The contract reuses the repository’s `DataProvenance` enum. It keeps provenance explicit and conservative:

- `real`: genuine real-data input
- `synthetic`: test or synthetic fixture
- `unavailable`: provenance unknown or absent
- `estimated`, `illustrative`, `deferred`: retained for general compatibility but not assumed for this contract

Synthetic fixtures are allowed in tests and must remain identifiable as synthetic. The contract does not silently upgrade unknown provenance into real data.

## Unknown Metadata Handling

The contract allows partial or absent metadata without inventing defaults:

- coordinates may be unknown
- CRS may be missing
- footprint may be missing
- GSD may be missing
- acquisition timestamp may be missing
- sensor may be missing
- illumination may be missing
- view geometry may be missing

Fields remain `None` when unavailable. The contract never creates placeholder values such as `(0, 0)`, a default CRS, a guessed sensor, or a synthetic acquisition date.

## Coordinate Separation

The contract explicitly distinguishes metadata coordinates from estimated coordinates.

- `metadata_coordinates`: coordinates supplied by source metadata, preserved as metadata only
- estimated coordinates: not created in Phase 11.1 and not implied by the contract

This separation is required to support future Phase 11.10 logic where estimated-vs-metadata coordinate differences must be clearly evaluated.

## Validation Rules

Deterministic validation rejects malformed or contradictory values:

- empty `image_id`
- empty `image_reference`
- invalid `width`, `height`, `channels`
- zero or negative dimensions
- invalid numeric metadata
- malformed `crs`, `geospatial_reference`, or `footprint`
- invalid `image_reference_type`
- contradictory provenance state
- malformed timestamps
- blank `metadata_quality` or `validation_status`

Optional metadata is allowed to be absent, but when supplied it must be structurally valid.

## Serialization and Deserialization

`UnknownImage` is JSON-safe and round-trips via `to_dict()` and `from_dict()`.

Rules:

- enums serialize deterministically to their string values
- warnings serialize as a list
- `None` remains `None` for absent metadata
- malformed payloads raise `UnknownImageContractError`
- the object remains free of runtime-only Python object representations in JSON output

## Error Handling

Validation errors raise `UnknownImageContractError`, a dedicated ValueError subclass for the Phase 11.1 input contract. This keeps contract failures explicit and avoids leaking raw constructor exceptions.

## Synthetic Data Safeguards

The contract enforces synthetic-data safety:

- `is_real_data=True` requires `provenance == DataProvenance.REAL`
- `provenance == DataProvenance.SYNTHETIC` cannot silently become real data
- synthetic test fixtures remain traceable through provenance

## Limitations

This contract is intentionally narrow:

- it describes an unknown image but does not localize it
- it does not perform feature extraction or matching
- it does not query a landmark database
- it does not compute coordinates
- it does not infer a lunar position from metadata strings or filenames
- it does not perform any geometric verification or ROI retrieval

## Example

```python
image = UnknownImage(
    image_id="IMG-001",
    image_reference="images/IMG-001.tif",
    image_reference_type=UnknownImageReferenceType.LOCAL_AVAILABLE,
    local_path="images/IMG-001.tif",
    provenance=DataProvenance.UNAVAILABLE,
    provenance_source="user_upload",
    is_real_data=False,
    width=2048,
    height=1024,
    channels=3,
    image_format="TIFF",
    metadata_quality="partial",
    validation_status="unvalidated",
    warnings=("missing_crs", "missing_gsd"),
    notes="Image is pending localization.",
)
```

This object is valid because the metadata is incomplete, but the location is still unknown and no coordinate estimation is implied.
