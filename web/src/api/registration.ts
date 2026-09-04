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
