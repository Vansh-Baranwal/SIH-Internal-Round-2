# M4 Phase 11.7 Coordinate Estimation

## Purpose

Phase 11.7 estimates a coordinate only through a verified Phase 11.6 image-geometry result and an explicit reference-raster pixel-to-coordinate mapping. Coordinate estimation produces an estimated lunar coordinate through the available verified geometric and reference-coordinate chain. It does not by itself establish localization confidence or accuracy.

## Input Contract

`CoordinateEstimationRequest` requires the unknown image ID, an explicit target pixel `(column, row)`, the frozen `GeometricVerificationResult`, the reference image ID, and `ReferenceImageGeoreferencing`. The anchor ID, when supplied, must match the verified 11.6 anchor. No image center or filename-derived point is selected.

`ReferenceImageGeoreferencing` requires raster width/height, six affine coefficients `(a, b, c, d, e, f)`, CRS, coordinate-system name, reference frame, units, axis order, source, and provenance. The affine map is `X = a*column + b*row + c`, `Y = d*column + e*row + f`. Rotation terms are preserved.

## Coordinate Chain

`unknown pixel -> verified 11.6 source-to-reference transform -> reference pixel -> authoritative raster affine transform -> coordinate tuple`.

11.6 uses source-to-reference direction, as established by its OpenCV reprojection calculation. Affine and homography models are supported. Homography points are dehomogenized only when the homogeneous denominator is finite and nonzero.

## Semantics and CRS

Coordinates are returned as an explicit tuple with coordinate system, reference frame, units, and axis order. No Earth WGS84, EPSG:4326, longitude wrapping, or silent reprojection is introduced. The M4 crater landmark record contains optional latitude/longitude, but it does not contain a reference-image geotransform; those point coordinates are therefore not substituted for arbitrary pixel localization.

## Validation and Boundaries

Only `SUCCESS` or `VERIFIED` 11.6 results are accepted. Missing or mismatched image mapping, malformed or singular transforms, non-finite values, unknown CRS, unsupported pixel/image-relative systems, and points outside `[0,width] x [0,height]` are blocked. Boundary points are accepted. No clamping is performed.

Multiple requests are estimated independently and returned without averaging or confidence weighting. Conflicting estimates remain separate observations. The result contains provenance for the unknown image, 11.6 verification, reference metadata, transformation parameters, method, and output classification `estimated`.

## Output and Deferred Scope

`CoordinateEstimationResult` contains status, identities, target/reference pixels, estimated coordinate, coordinate metadata, transformation details, warnings, limitations, and provenance. It contains no confidence, accuracy metric, metadata comparison, ROI, or retrieval output. Phase 11.8 confidence, 11.9 ROI retrieval, 11.10 metadata separation/comparison, 11.11 accuracy testing, and 11.12 final validation remain out of scope.

## Testing and Limitation

Focused tests use explicitly synthetic provenance and controlled affine/homography fixtures. Existing M1 metadata conventions are reused: raster dimensions, six-term transform, and explicit CRS. The repository does not currently establish a default landmark-reference-image georeferencing association; callers must provide authoritative `ReferenceImageGeoreferencing` or receive a blocked result.
