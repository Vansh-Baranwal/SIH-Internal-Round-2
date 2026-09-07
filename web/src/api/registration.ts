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
import type {
  DatasetInput,
  MatchPoint,
  RegistrationMetrics,
  RegistrationStatus,
  Transformation,
} from '../types/registration';
import { deriveQuality } from '../types/registration';
import { joinApiUrl } from './client';

export interface RegisterRequestPayload {
  sourceFile: File;
  referenceFile: File;
  sunSimulation?: { azimuthDeg: number; elevationDeg: number; illuminationVariant: boolean };
}

export interface RegisterJobHandle {
  jobId: string;
  result: RegistrationJobResult;
}

export interface RegistrationJobResult {
  status: RegistrationStatus;
  matchPoints: MatchPoint[];
  transformation: Transformation | null;
  metrics: RegistrationMetrics | null;
  overlayImageUrl: string | null;
  error?: string;
}

/** Keep a local image available for preview and later multipart submission. */
export async function ingestDataset(file: File, sensor: DatasetInput['sensor']): Promise<DatasetInput> {
  return {
    id: crypto.randomUUID(),
    sensor,
    name: file.name,
    previewUrl: URL.createObjectURL(file),
    file,
  };
}

/** Submit both local images to the real correspondence engine. */
export async function startRegistration(payload: RegisterRequestPayload): Promise<RegisterJobHandle> {
  const formData = new FormData();
  formData.append('source', payload.sourceFile);
  formData.append('reference', payload.referenceFile);
  const res = await fetch(joinApiUrl('api/v1/correspondence/register'), {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Registration request failed: ${res.status}`);
  const data = await res.json();
  const metrics = data.metrics
    ? {
        // The engine reports pixel RMSE; no physical scale is available here.
        rmseMeters: undefined,
        rmsePixels: data.metrics.rmse,
        inlierCount: data.metrics.inlier_count,
        totalMatches: data.metrics.total_matches,
        inlierRatio: data.metrics.inlier_ratio,
        spatialCoverage: data.metrics.spatial_coverage,
        quality: deriveQuality(data.metrics.inlier_ratio, data.metrics.rmse),
      }
    : null;
  const matchPoints: MatchPoint[] = (data.matches ?? []).map((match: any, index: number) => ({
    id: `${data.job_id}-${index}`,
    sourceX: match.src[0],
    sourceY: match.src[1],
    referenceX: match.ref[0],
    referenceY: match.ref[1],
    confidence: match.confidence,
    isInlier: true,
  }));

  return {
    jobId: data.job_id,
    result: {
      status: 'succeeded',
      matchPoints,
      transformation: null,
      metrics,
      overlayImageUrl: data.warped_url ? joinApiUrl(data.warped_url) : null,
    },
  };
}

// ---- spectral / water-ice intelligence ----

export interface SpectralRequestPayload {
  datasetId: string;
  kind: 'mineral-classification' | 'water-ice-confidence';
}

export interface SpectralLayerResult {
  kind: SpectralRequestPayload['kind'];
  label: string;
  overlayUrl: string;
}

/** Requests a spectral/water-ice overlay for an already-registered dataset. */
export async function requestSpectralLayer(payload: SpectralRequestPayload): Promise<SpectralLayerResult> {
  const endpoint =
    payload.kind === 'mineral-classification' ? '/api/v1/spectral/classify' : '/api/v1/ice/confidence';

  const res = await fetch(joinApiUrl(endpoint), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: payload.datasetId }),
  });
  if (!res.ok) throw new Error(`Spectral request failed: ${res.status}`);
  const data = await res.json();

  return {
    kind: payload.kind,
    label: payload.kind === 'mineral-classification' ? 'Mineral Classification' : 'Water-Ice Confidence',
    overlayUrl: data.overlay_url,
  };
}
