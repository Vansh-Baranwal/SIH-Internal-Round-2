import { ApiError, API_BASE, postJson } from './client';

export type Phase10DataProvenance =
  | 'real'
  | 'synthetic'
  | 'estimated'
  | 'illustrative'
  | 'deferred'
  | 'unavailable';

export interface Phase10ObservationRequest {
  observation_id: string;
  source: string;
  image_reference: string;
  acquisition_timestamp?: string | null;
  product_id?: string | null;
  crs?: string | null;
  geospatial_reference?: Record<string, unknown> | null;
  dimensions?: [number, number] | null;
  gsd_m?: number | null;
  footprint?: Record<string, unknown> | null;
  view_geometry?: Record<string, unknown> | null;
  sun_azimuth_deg?: number | null;
  sun_elevation_deg?: number | null;
  phase_angle_deg?: number | null;
  incidence_angle_deg?: number | null;
  emission_angle_deg?: number | null;
  metadata_quality?: string | null;
  provenance_source: string;
  provenance?: Phase10DataProvenance;
  is_real_data?: boolean;
  validation_status?: string;
  notes?: string | null;
}

export interface Phase10PairSelectionRequest {
  observation_a: Phase10ObservationRequest;
  observation_b: Phase10ObservationRequest;
}

export interface Phase10TemporalMetadata {
  original_timestamp: string | null;
  normalized_timestamp: string | null;
  acquisition_date: string | null;
  precision: string;
  timezone_aware: boolean;
  source_field: string | null;
  metadata_quality: string;
  authoritative: boolean;
  start_timestamp: string | null;
  end_timestamp: string | null;
  notes: string;
}

export interface Phase10PairSelectionResponse {
  observation_a_id: string | null;
  observation_b_id: string | null;
  eligibility: string;
  hard_rejection_reasons: string[];
  warnings: string[];
  candidate_selection_score: number | null;
  temporal_metadata: Phase10TemporalMetadata | null;
  crs_compatibility: string;
  footprint_compatibility: string;
  sensor_compatibility: string;
  image_reference_a: string;
  image_reference_b: string;
  metadata_completeness: number;
  provenance_status: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isTemporalMetadata(value: unknown): value is Phase10TemporalMetadata {
  if (!isRecord(value)) return false;
  return (
    isNullableString(value.original_timestamp) &&
    isNullableString(value.normalized_timestamp) &&
    isNullableString(value.acquisition_date) &&
    typeof value.precision === 'string' &&
    typeof value.timezone_aware === 'boolean' &&
    isNullableString(value.source_field) &&
    typeof value.metadata_quality === 'string' &&
    typeof value.authoritative === 'boolean' &&
    isNullableString(value.start_timestamp) &&
    isNullableString(value.end_timestamp) &&
    typeof value.notes === 'string'
  );
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function isPhase10PairSelectionResponse(value: unknown): value is Phase10PairSelectionResponse {
  if (!isRecord(value)) return false;
  return (
    isNullableString(value.observation_a_id) &&
    isNullableString(value.observation_b_id) &&
    typeof value.eligibility === 'string' &&
    isStringArray(value.hard_rejection_reasons) &&
    isStringArray(value.warnings) &&
    (value.candidate_selection_score === null || typeof value.candidate_selection_score === 'number') &&
    (value.temporal_metadata === null || isTemporalMetadata(value.temporal_metadata)) &&
    typeof value.crs_compatibility === 'string' &&
    typeof value.footprint_compatibility === 'string' &&
    typeof value.sensor_compatibility === 'string' &&
    typeof value.image_reference_a === 'string' &&
    typeof value.image_reference_b === 'string' &&
    typeof value.metadata_completeness === 'number' &&
    typeof value.provenance_status === 'string'
  );
}

export async function submitPhase10PairSelection(
  request: Phase10PairSelectionRequest,
): Promise<Phase10PairSelectionResponse> {
  const response = await postJson<unknown>(
    `${API_BASE}/phase10/pair-selection`,
    'Phase 10 pair selection',
    request,
  );

  if (!isPhase10PairSelectionResponse(response)) {
    throw new ApiError('Phase 10 pair selection returned an invalid response contract.', undefined, 'response');
  }

  return response;
}
