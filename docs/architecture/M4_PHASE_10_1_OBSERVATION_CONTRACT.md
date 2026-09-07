# M4 Phase 10.1: Multi-date Observation Contract

`LunarObservation` records one image observation and the metadata genuinely
available for it. Required identity fields are `observation_id`, `source`,
`image_reference`, and `provenance_source`. Acquisition time, dimensions, CRS,
footprint, GSD, view geometry, and illumination fields are optional on an
individual record and remain `null` when unavailable. `validation_status` has
the default value `unvalidated`; supplied `metadata_quality` and
`validation_status` values must be non-empty strings.

`ObservationPair` is the input boundary for later temporal stages. It requires
two distinct, real observations with parseable and different acquisition
timestamps. Both records must explicitly set `is_real_data=true` and
`provenance="real"`; synthetic, illustrative, estimated, or unavailable data
cannot be used as a temporal pair. The contract never derives dates from file
names or creates placeholder timestamps.

Basic structural checks are applied when spatial metadata is supplied. `crs`
must be a non-empty string. `geospatial_reference`, `footprint`, and
`view_geometry` must be dictionaries. Footprints must contain either M1-style
`bounds` (`west`, `south`, `east`, `north`) with finite positive extents or a
non-empty coordinate container with finite numeric values. Known camera
geometry fields `position_m` and `target_m` use the existing M4 three-coordinate
shape and are checked for finite values. These checks do not parse CRS values,
perform GIS transformations, calculate overlap, or model spacecraft geometry.

Malformed dictionary payloads are reported as `ObservationContractError`,
including missing nested observation fields, rather than leaking raw mapping
or constructor exceptions. Phase 10.2 onward should consume the pair and its
metadata, then pass the image references to correspondence and registration.
Pair selection belongs to Phase 10.3. This contract does not perform CRS
parsing, footprint intersection, pair selection, registration, differencing,
illumination filtering, noise suppression, change detection, or change
classification.