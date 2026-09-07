# M4 Phase 10.8: Change Candidate Detection

Phase 10.8 consumes only successful Phase 10.7 noise-suppressed signed and
absolute difference products plus the propagated valid mask. It identifies
algorithmic candidate regions that satisfy an explicit magnitude threshold and
spatial-coherence requirements. A detected candidate is not a confirmed lunar
surface change.

`ChangeCandidateConfig` requires a finite positive
`absolute_difference_threshold` and exposes `minimum_component_size`,
`minimum_valid_neighbors`, and 4- or 8-connected component connectivity. The
threshold is an engineering detection criterion supplied by the caller. It is
not derived from fabricated data and is not calibrated against confirmed lunar
events.

Detection uses the Phase 10.7 absolute difference for magnitude and retains
the signed difference for candidate statistics. A pixel must be valid in the
authoritative Phase 10.7 mask, finite in both products, and meet the inclusive
threshold. It must also have the configured number of valid neighbors and
belong to a connected component meeting the minimum size. No dilation,
threshold fallback, resizing, or gap bridging is performed.

Candidate masks use explicit labels:

- `0`: invalid input pixel
- `1`: valid non-candidate pixel
- `2`: candidate pixel

`candidate_labels.npy` stores deterministic connected-component IDs. Candidate
records use image-space row/column bounding boxes and centroids, pixel counts,
threshold, absolute extrema/statistics, signed statistics, and a positive,
negative, or mixed sign characterization. No geographic coordinates, crater
dimensions, ejecta properties, geological interpretation, or confidence score
is generated.

Outputs are:

- `change_candidate_mask.npy`
- `candidate_labels.npy`
- `change_candidates.json`
- `change_candidate_summary.json`

The Phase 10.7 input artifacts are never modified. Missing, invalid,
incompatible, non-finite, or zero-valid input produces explicit statuses.
Valid input with no qualifying components returns `NO_CANDIDATES` and is not an
error. All candidate IDs and component traversal are deterministic.

**Candidate detected by algorithm** does not mean **confirmed lunar surface
change**. Phase 10.9 classification and later validation remain deferred.