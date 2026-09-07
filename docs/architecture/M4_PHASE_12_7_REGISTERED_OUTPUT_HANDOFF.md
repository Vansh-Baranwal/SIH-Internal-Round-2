# M4 Phase 12.7 Registered-Output Handoff

## Decision

Outcome B applies to the current repository. Phase 11 does not currently
produce a genuine registered image, registration transform, or localized
output through its supported HTTP boundary, and no existing M4, M5, or M6
consumer requires one.

Phase 12.7 did not fabricate or infer a registered output. The handoff remains
future-ready but inactive until Phase 11 produces a supported registered/
localized result.

## Inspected contracts

- Phase 11 source: `src/lunar_hazard_mapper/api/phase11_router.py`, the frozen
  Phase 11 terrain contracts, and `web/src/api/registration.ts`.
- Phase 11 UI: `web/src/pages/RegistrationCockpit.tsx`. It displays the
  nullable result slots and does not create registration or localization data.
- M4: `src/lunar_hazard_mapper/m4_hazards/handoff.py` accepts computed DEM,
  raster hazard layers, craters, and boulders. It has no Phase 11 result input.
- M5: `src/lunar_hazard_mapper/m5_lander/site_generator.py` and
  `src/lunar_hazard_mapper/m5_lander/evaluator.py` consume the M4 terrain and
  hazard payload to generate and score candidate sites.
- M6: `src/lunar_hazard_mapper/m6_planner/adapters/m5_adapter.py` consumes M5
  site evaluations as `SiteResult` values. Its trajectory target is an M5 site,
  not a Phase 11 localization result.

The M4 ROI field `localization_result_id` is not a registered-output handoff:
it identifies the Phase 11 unknown image in an ROI request and is not exposed
by the Phase 11 HTTP response. The M2 correspondence endpoint remains a
separate subsystem.

## Current Phase 11 behavior

The supported API runs the real metadata and landmark-retrieval prefix, then
returns `status: blocked` because no serializable project landmark source is
provided. It explicitly returns:

```json
{
  "match_points": null,
  "registration_metrics": null,
  "localization": null,
  "final_validation": null
}
```

`validation_request_id` remains a caller correlation ID. It is never renamed
to `registration_id`, `registered_image_id`, or `output_id`.

## Handoff boundary

The minimal future-ready boundary is
`src/lunar_hazard_mapper/api/phase12_7_handoff.py`. Its
`adapt_phase11_result()` function returns either a typed `Phase11ResultHandoff`
or `None`. It accepts only the existing `Phase11ApiResponse`, preserves the
current result dictionaries and provenance by identity, and does not expose a
new registration-image, transform, CRS, or coordinate field.

Blocked responses and responses whose four result slots are all null return
`None`. A future non-blocked response with an existing supported result slot
can pass through this boundary without rewriting Phase 11 or downstream
science. Coordinate semantics, when present inside the existing result, are
carried unchanged; no conversion or validation is performed here.

Until then:

- M4 continues to build its existing M4-to-M5 terrain/hazard payload.
- M5 continues to generate and score sites from that payload.
- M6 continues to consume M5 `SiteResult` values.
- Null and blocked Phase 11 results do not create downstream scientific output.
- Existing synthetic, legacy, Digital Twin, and M2 workflows remain separate.

## Validation

Focused coverage is in `tests/test_m4_phase_12_7_registered_output_handoff.py`.
It verifies blocked and synthetic Phase 11 requests preserve null result
semantics, provenance, and correlation-ID meaning, and that the M2 route is
not used as a shortcut. No scientific algorithm or downstream contract was
changed.

Phase 12.8 remains the separate Phase 10 backend contract audit and is outside
this change.