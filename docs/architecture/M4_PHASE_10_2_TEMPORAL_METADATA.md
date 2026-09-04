# M4 Phase 10.2: Temporal Metadata Handling

Phase 10.2 assesses temporal metadata associated with a
`LunarObservation`. `TemporalMetadata.from_observation()` uses the explicit
Phase 10.1 `observation.acquisition_timestamp` as its primary source. A
caller may also provide a metadata mapping containing the explicit keys
`acquisition_timestamp` or `acquisition_date`; this adapter does not inspect
filenames or treat M1 manifest `created_at` values as acquisition times.

When both sources exist, the Phase 10.1 observation field takes precedence. If
the explicit values disagree, the result is `conflicting` and retains a note;
it is never silently resolved. Missing values are `missing`, blank or invalid
values are `invalid`, and all original text is retained for provenance.

Valid values are normalized with Python ISO-8601 parsing. Explicit offsets and
`Z` are converted to UTC while timezone-naive values remain timezone-naive and
are marked `timezone_naive`. Date-only, hour-only, and minute-only values
retain their declared `date`/`hour`/`minute` precision and receive
`limited_precision`; date-only values do not receive a fabricated midnight
timestamp. Limited-precision pair views may expose calendar ordering, but do
not expose exact second separation.

`TemporalPairView`, available as `ObservationPair.temporal_metadata`, exposes
the two temporal records, chronological order, timestamp availability,
metadata quality, and separation in seconds. Absolute separation is withheld
for timezone-naive values, mixed timezone awareness, or invalid/conflicting
metadata; same-clock naive values may still provide source-clock ordering.
The pair view does not decide whether a pair is scientifically suitable.

Temporal provenance is independent from scientific authenticity: test or
synthetic observations retain their Phase 10.1 `DataProvenance` and
`is_real_data` values. Phase 10.2 never upgrades them to genuine data.

Phase 10.2 handles temporal metadata. It does not select image pairs. Pair
selection is Phase 10.3. Registration, differencing, illumination filtering,
noise suppression, change detection, and validation remain later work.