# M4 Phase 10.4: Multi-date Registration

Phase 10.4 is an M4 orchestration layer around the existing M2 correspondence
engine. It accepts an eligible Phase 10.3 `ObservationPair`, resolves local
image inputs, invokes M2, and adapts the returned metrics and output artifacts
for later temporal processing. A successful result means **registered
observation pair**; it does not prove physical lunar change.

`RegistrationConfig` carries the M2 path-based options: output directory,
matcher, geometric model, GSD hints, scale matching, uniform filtering, and
illumination-invariant preprocessing. `TemporalRegistrationRequest` binds an
eligible Phase 10.3 selection to the exact pair and configuration. The M4
adapter does not duplicate observation metadata or registration algorithms.

M2 is invoked as `run_pipeline(source_path, reference_path, output_dir, ...)`.
Observation A is passed as M2's source image and Observation B as its
reference image. Existing local files are passed only when they exist and are
files. HTTP/S3/GS references are reported as unsupported by this path-based
M2 interface; unresolved local paths are reported as missing inputs. No
downloads or placeholder files are created.

The integrated M2 pipeline actually performs its existing preprocessing,
matching, geometric verification, sub-pixel phase-correlation refinement,
warping, and metric/export stages. M2 returns `RegistrationMetrics` containing
RMSE, total matches, inliers, inlier ratio, spatial coverage, and its
sub-pixel-target flag. These values are copied without redefinition.

The result preserves the requested M2 geometric model. M2's current public
function does not return its transform matrix or actual matcher backend, so
`transformation_parameters` and `backend_used` remain `null`, with explicit
warnings. The adapter reports sub-pixel refinement as executed only after M2
returns successfully because the current M2 pipeline calls that refinement.

`warped_source.png` is required for a successful result. `matches.json` is
returned when present. Missing metrics remain `null` when M2 omits optional
values; NaN, infinity, inconsistent counts, invalid ratios, and invalid
coverage are rejected. No dummy artifacts are generated.

Machine-readable failures include `ineligible_pair`, `missing_image_input`,
`invalid_image_reference`, `external_image_reference_unsupported_by_m2`,
`unsupported_registration_backend`, `registration_execution_failed`,
`insufficient_matches`, `invalid_registration_metrics`, and
`missing_registered_output`.

Phase 10.4 does not implement another registration engine, pair selection,
correspondence alternatives, image differencing, illumination filtering,
noise suppression, change detection, or final validation. It only establishes
spatial alignment through M2 for a genuine eligible observation pair.