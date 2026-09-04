// Typed data model for the Multi-Modal Correspondence Engine workflow.
// Mirrors the implemented correspondence API contract:
// POST /api/v1/correspondence/register and its synchronous result.

export type SensorType = 'TMC' | 'OHRC' | 'IIRS' | 'NAC' | 'DEM';

export type RegistrationStatus =
  | 'idle'
  | 'uploading'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed';

/** A single selectable/uploaded dataset (source or reference image). */
export interface DatasetInput {
  id: string;
  sensor: SensorType;
  /** Display name, e.g. filename or catalog id. */
  name: string;
  /** URL the frontend can render as a preview (may be a blob: URL pre-upload). */
  previewUrl: string;
  /** Original browser file retained until both datasets are submitted. */
  file?: File;
  /** Reserved for a future catalog-backed dataset workflow. */
  datasetId?: string;
  width?: number;
  height?: number;
  /**
   * True when this dataset came from the Counterfactual Sun Simulator
   * rather than a real sensor capture. Per
   * 01_EXISTING_PROJECT_AND_TARGET_ARCHITECTURE.md §5 ("Isolated Synthetic
   * Generation"), synthetic imagery must stay isolated from real registered
   * output — this flag is what lets the UI (and eventually the backend)
   * enforce that instead of silently mixing the two.
   */
  synthetic?: boolean;
}

/** A single matched keypoint pair between source and reference images. */
export interface MatchPoint {
  id: string;
  sourceX: number;
  sourceY: number;
  referenceX: number;
  referenceY: number;
  /** Match confidence in [0, 1], used to color/filter overlay lines. */
  confidence: number;
  /** Whether RANSAC kept this match as a geometric inlier. */
  isInlier: boolean;
}

/** Estimated geometric transform between source and reference. */
export interface Transformation {
  model: 'affine' | 'homography' | 'similarity' | 'polynomial';
  /** Row-major transform matrix, shape depends on `model`. */
  matrix: number[][];
}

/** Quantitative registration quality metrics for the analytics panel. */
export interface RegistrationMetrics {
  rmseMeters?: number;
  rmsePixels: number;
  inlierCount: number;
  totalMatches: number;
  inlierRatio: number;
  /** Fraction of the reference frame covered by matched points, 0-1. */
  spatialCoverage: number;
  /** Coarse pass/fail read derived from thresholds, for the status badge. */
  quality: 'good' | 'weak' | 'failed';
}

export interface SunSimulationParams {
  azimuthDeg: number;
  elevationDeg: number;
  illuminationVariant: boolean;
}

export interface SpectralLayer {
  id: string;
  label: string;
  /** e.g. 'mineral-classification' | 'water-ice-confidence' */
  kind: 'mineral-classification' | 'water-ice-confidence';
  overlayUrl: string;
  visible: boolean;
  opacity: number;
}

/** Full state of one registration job/session — the thing that used to be `result`. */
export interface RegistrationSession {
  id: string;
  status: RegistrationStatus;
  error?: string;

  datasetSource: DatasetInput | null;
  datasetReference: DatasetInput | null;

  matchPoints: MatchPoint[];
  transformation: Transformation | null;
  metrics: RegistrationMetrics | null;

  /** URL of the source image warped into the reference frame. */
  overlayImageUrl: string | null;

  sunSimulation: SunSimulationParams | null;
  spectralLayers: SpectralLayer[];

  createdAt: string;
  updatedAt: string;
}

export function createEmptySession(): RegistrationSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    status: 'idle',
    datasetSource: null,
    datasetReference: null,
    matchPoints: [],
    transformation: null,
    metrics: null,
    overlayImageUrl: null,
    sunSimulation: null,
    spectralLayers: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function deriveQuality(
  inlierRatio: number,
  rmsePixels: number,
): RegistrationMetrics['quality'] {
  if (inlierRatio >= 0.6 && rmsePixels <= 1.5) return 'good';
  if (inlierRatio >= 0.3 && rmsePixels <= 4) return 'weak';
  return 'failed';
}