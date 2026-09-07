import { postJson, ApiError } from './client';

/**
 * Phase 13.4 — registration contract & capability seam.
 *
 * The real correspondence engine / registration endpoint is NOT implemented in
 * the backend for this build. This module is the single seam where the real
 * engine will be wired later, so the Registration Cockpit does not need to be
 * redesigned. No registration results, match points, RMSE or inlier metrics
 * are fabricated anywhere here.
 */

export type RegistrationSensor = 'tmc' | 'ohrc' | 'iirs';

export interface RegistrationPoint {
  x: number;
  y: number;
}

export interface RegistrationMatchPair {
  id?: string;
  source: RegistrationPoint;
  reference: RegistrationPoint;
}

export interface RegistrationMatchData {
  pairs: RegistrationMatchPair[];
  sourceLabel?: string;
  referenceLabel?: string;
}

export interface RegistrationRequest {
  sourceSensor: RegistrationSensor;
  referenceSensor: RegistrationSensor;
}

export type RegistrationOutcome =
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string }
  | {
      status: 'success';
      registrationId: string;
      metrics: Record<string, unknown>;
      matches?: RegistrationMatchData | null;
    };

export interface RegistrationCapability {
  available: boolean;
  reason: string;
}

/**
 * The correspondence engine/model is not available in this build. Flip this to
 * `true` (and implement `submitRegistration`) when the real engine is wired.
 */
export const REGISTRATION_ENGINE_AVAILABLE = false;

export type Phase11ImageReferenceType =
  | 'local_available'
  | 'external_reference'
  | 'local_missing'
  | 'unavailable'
  | 'unknown'
  | 'invalid';

export type Phase11DataProvenance =
  | 'real'
  | 'synthetic'
  | 'estimated'
  | 'illustrative'
  | 'deferred'
  | 'unavailable';

export interface Phase11UnknownImageRequest {
  image_id: string;
  image_reference: string;
  provenance_source: string;
  image_reference_type?: Phase11ImageReferenceType;
  provenance?: Phase11DataProvenance;
  is_real_data?: boolean;
  validation_status?: string;
  source_id?: string | null;
  product_id?: string | null;
  local_path?: string | null;
  external_reference?: string | null;
  width?: number | null;
  height?: number | null;
  channels?: number | null;
  image_format?: string | null;
  dtype?: string | null;
  bit_depth?: number | null;
  gsd_m?: number | null;
  crs?: string | null;
  geospatial_reference?: Record<string, unknown> | null;
  footprint?: Record<string, unknown> | null;
  acquisition_timestamp?: string | null;
  acquisition_date?: string | null;
  sensor?: string | null;
  source_name?: string | null;
  illumination?: Record<string, unknown> | null;
  view_geometry?: Record<string, unknown> | null;
  metadata_coordinates?: Record<string, unknown> | null;
  metadata_quality?: string | null;
  warnings?: string[];
  notes?: string | null;
}

export interface Phase11Request {
  validation_request_id: string;
  image: Phase11UnknownImageRequest;
}

export interface Phase11StageResponse {
  status: string;
  result: Record<string, unknown>;
}

export type Phase11DownstreamStatuses = Record<string, string | null>;

export interface Phase11ApiResponse {
  validation_request_id: string;
  status: string;
  source_image_id: string;
  metadata_quality: Phase11StageResponse;
  landmark_retrieval: Phase11StageResponse;
  downstream_statuses: Phase11DownstreamStatuses;
  match_points: Record<string, unknown> | null;
  registration_metrics: Record<string, unknown> | null;
  localization: Record<string, unknown> | null;
  final_validation: Record<string, unknown> | null;
  warnings: string[];
  limitations: string[];
  provenance: Record<string, unknown>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isStageResponse(value: unknown): value is Phase11StageResponse {
  if (!isRecord(value) || typeof value.status !== 'string') return false;
  return isRecord(value.result);
}

function isPhase11ApiResponse(value: unknown): value is Phase11ApiResponse {
  if (!isRecord(value)) return false;
  if (typeof value.validation_request_id !== 'string') return false;
  if (typeof value.status !== 'string' || typeof value.source_image_id !== 'string') return false;
  if (!isStageResponse(value.metadata_quality) || !isStageResponse(value.landmark_retrieval)) return false;
  if (!isRecord(value.downstream_statuses)) return false;
  if (!Object.values(value.downstream_statuses).every((status) => status === null || typeof status === 'string')) return false;
  if (value.match_points !== null && !isRecord(value.match_points)) return false;
  if (value.registration_metrics !== null && !isRecord(value.registration_metrics)) return false;
  if (value.localization !== null && !isRecord(value.localization)) return false;
  if (value.final_validation !== null && !isRecord(value.final_validation)) return false;
  if (!Array.isArray(value.warnings) || !value.warnings.every((warning) => typeof warning === 'string')) return false;
  if (!Array.isArray(value.limitations) || !value.limitations.every((limitation) => typeof limitation === 'string')) return false;
  return isRecord(value.provenance);
}

export async function submitPhase11Localization(request: Phase11Request): Promise<Phase11ApiResponse> {
  const response = await postJson<unknown>(
    `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'}/phase11/lunar-gps`,
    'Phase 11 lunar-GPS',
    request,
  );

  if (!isPhase11ApiResponse(response)) {
    throw new ApiError('Phase 11 lunar-GPS returned an invalid response contract.', undefined, 'response');
  }

  return response;
}

export function getRegistrationCapability(): RegistrationCapability {
  return {
    available: REGISTRATION_ENGINE_AVAILABLE,
    reason:
      'The correspondence engine/model is not available in this build. Registration cannot be executed and no result is produced.',
  };
}

/**
 * Initiate registration through the backend contract.
 *
 * With the engine unavailable this returns an explicit `unavailable` outcome
 * rather than a fabricated success, so the UI never claims a result that does
 * not exist. When the real endpoint is connected, replace the body with a POST
 * to the registration endpoint and surface the genuine response.
 */
export async function submitRegistration(
  request: RegistrationRequest,
): Promise<RegistrationOutcome> {
  void request;
  return {
    status: 'unavailable',
    message:
      'Registration is not available: the correspondence engine/model is not implemented in this build. No result, match points or metrics were produced.',
  };
}
