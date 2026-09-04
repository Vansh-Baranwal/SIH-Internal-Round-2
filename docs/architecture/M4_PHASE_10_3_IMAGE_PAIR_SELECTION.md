# M4 Phase 10.3: Image-Pair Selection

Phase 10.3 evaluates genuine `LunarObservation` records and returns eligible
candidate pairs for downstream temporal analysis. It does not claim that a
pair is scientifically suitable for change detection and does not claim that
physical lunar change occurred.

`evaluate_pair(a, b)` returns a `PairSelectionResult` with observation
identities, `eligible`/`rejected` status, machine-readable hard rejection
reasons, separate warnings, temporal metadata, spatial signals, sensor
compatibility, image-reference status, provenance status, and an optional
candidate-selection score. The score is a deterministic metadata-ranking
signal, not scientific confidence. When eligible, it is the mean of six
transparent normalized signals: average temporal quality, CRS status,
footprint status, known-sensor status, the two image-reference statuses, and
average metadata completeness. It is reported on a 0-100 scale only for
candidate ranking.

Hard requirements are genuine `DataProvenance.REAL` observations with
`is_real_data=True`, distinct identities and acquisition instants, valid
temporal metadata, and non-empty valid image references. Missing optional
metadata is a warning. Synthetic, illustrative, estimated, unavailable, or
contradictory provenance is rejected.

Temporal assessment is delegated to Phase 10.2. Date-only metadata can be
eligible when ordered, but does not create exact elapsed seconds. Timezone-
naive metadata receives a warning and does not create absolute separation.

Spatial checks use the Phase 10.1/M1 `bounds` convention when both footprints
and equal CRS values are available. Clear non-overlap is rejected. Missing or
different CRS, coordinate-only footprints, and unavailable spatial evidence
produce unknown/warning signals; no CRS transformation or GIS overlap engine
is implemented. Different GSD or dimensions do not automatically reject a
candidate.

Known TMC, OHRC, IIRS, LRO NAC/NAC, and SELENE source labels are supported,
including cross-sensor combinations. Unknown labels remain explicitly
unknown rather than being rejected solely for being multimodal.

`select_candidate_pairs(observations)` de-duplicates exact identity/reference
records, enumerates combinations in deterministic identity order, avoids A/B
and B/A duplicates, and returns only eligible candidate results. It performs
no pair-selection threshold based on scientific change confidence.

Image references are classified as locally available, external references,
explicitly unavailable local references, or unknown. External, unavailable,
and unknown references are warnings because this repository does not require
every product to be locally present; blank/invalid references are hard
failures. No files are fabricated. Different GSD and dimensions are surfaced
as compatibility warnings and do not reject multi-resolution candidates.

**Phase 10.3 selects candidate pairs. It does not register images or determine
whether physical lunar change actually occurred.** Correspondence,
registration, differencing, filtering, and later validation remain deferred.