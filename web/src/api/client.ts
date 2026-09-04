import type { MissionData } from '../types/api';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export class ApiError extends Error {
  status?: number;
  kind: 'http' | 'network' | 'response';

  constructor(message: string, status?: number, kind: 'http' | 'network' | 'response' = 'http') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

async function fetchJson<T>(url: string, label: string): Promise<T> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const detail = response.statusText ? ` (${response.statusText})` : '';
      throw new ApiError(`${label} request failed (${response.status}${detail})`, response.status);
    }

    const payload = await response.json().catch(() => {
      throw new ApiError(`${label} returned invalid JSON.`, response.status, 'response');
    });

    if (!isRecord(payload)) {
      throw new ApiError(`${label} returned a malformed response.`, response.status, 'response');
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof TypeError) {
      throw new ApiError(`${label} failed because the request could not be completed.`, undefined, 'network');
    }

    throw new ApiError(`${label} request could not be processed.`);
  }
}

export async function postJson<T>(url: string, label: string, body: unknown): Promise<T> {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const detail = response.statusText ? ` (${response.statusText})` : '';
      throw new ApiError(`${label} request failed (${response.status}${detail})`, response.status);
    }

    const payload = await response.json().catch(() => {
      throw new ApiError(`${label} returned invalid JSON.`, response.status, 'response');
    });

    if (!isRecord(payload)) {
      throw new ApiError(`${label} returned a malformed response.`, response.status, 'response');
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof TypeError) {
      throw new ApiError(`${label} failed because the request could not be completed.`, undefined, 'network');
    }

    throw new ApiError(`${label} request could not be processed.`);
  }
}

export async function fetchMissionData(): Promise<MissionData> {
  return fetchJson<MissionData>(`${API_BASE}/mission`, 'Mission data');
}

export function getAssetUrl(assetPath: string): string {
  return `${API_BASE}/assets/${assetPath}`;
}

export interface MissionStatusPayload {
  status: string;
  has_primary: boolean;
  has_replan: boolean;
  has_replanned_trajectory: boolean;
}

export async function fetchMissionStatus(): Promise<MissionStatusPayload> {
  return fetchJson<MissionStatusPayload>(`${API_BASE}/mission/status`, 'Mission status');
}

export interface DemTerrainPayload {
  metadata: {
    display_label: string;
    data_status: string;
    source_type: string;
    vertical_units: string;
    coordinate_convention: Record<string, string>;
    provenance: Record<string, unknown>;
  };
  grid: {
    width: number;
    height: number;
    pixel_size_m: number;
    x: number[][];
    y: number[][];
    z: number[][];
    valid_mask: boolean[][];
    coordinate_convention: Record<string, string>;
  };
}

export async function fetchDemTerrain(): Promise<DemTerrainPayload> {
  return fetchJson<DemTerrainPayload>(`${API_BASE}/terrain/dem`, 'Terrain');
}

export interface TmcCameraPayload {
  display_label: string;
  data_status: 'synthetic' | 'real' | 'unknown';
  position_m: { x: number; y: number; z: number };
  target_m: { x: number; y: number; z: number };
  vertical_fov_degrees: number;
  aspect_ratio: number;
  near_m: number;
  far_m: number;
  coordinate_convention: Record<string, string>;
  provenance: Record<string, unknown>;
}

export async function fetchTmcCamera(): Promise<TmcCameraPayload> {
  return fetchJson<TmcCameraPayload>(`${API_BASE}/cameras/tmc`, 'TMC camera');
}

export interface OhrcCameraPayload {
  display_label: string;
  data_status: 'synthetic' | 'real' | 'unknown';
  position_m: { x: number; y: number; z: number };
  target_m: { x: number; y: number; z: number };
  vertical_fov_degrees: number;
  aspect_ratio: number;
  near_m: number;
  far_m: number;
  coordinate_convention: Record<string, string>;
  provenance: Record<string, unknown>;
}

export async function fetchOhrcCamera(): Promise<OhrcCameraPayload> {
  return fetchJson<OhrcCameraPayload>(`${API_BASE}/cameras/ohrc`, 'OHRC camera');
}

export interface IirsFootprintPayload {
  display_label: string;
  data_status: 'synthetic' | 'real' | 'unknown';
  sensor_type: string;
  camera: {
    display_label: string;
    data_status: string;
    position_m: { x: number; y: number; z: number };
    target_m: { x: number; y: number; z: number };
    fov_across_track_degrees: number;
    fov_along_track_degrees: number;
    near_m: number;
    far_m: number;
  };
  footprint: {
    boundary_vertices: Array<{ x: number; y: number; z: number }>;
    vertex_count: number;
    surface_area_m2: number;
    is_within_dem_bounds: boolean;
    has_nodata_intersection: boolean;
  };
  coordinate_convention: Record<string, string>;
  provenance: Record<string, unknown>;
}

export async function fetchIirsFootprint(): Promise<IirsFootprintPayload> {
  return fetchJson<IirsFootprintPayload>(`${API_BASE}/cameras/iirs`, 'IIRS footprint');
}

export const fetchIirsCamera = fetchIirsFootprint;

export interface LandmarkItemPayload {
  landmark_id: string;
  display_label: string;
  estimated_position_m: { x: number; y: number; z: number };
  reference_position_m: { x: number; y: number; z: number } | null;
  diameter_m: number;
  depth_m: number | null;
  confidence: number | null;
  quality_score: number | null;
  localization_status: string;
  data_status: string;
  provenance: Record<string, unknown>;
}

export interface LandmarksPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  landmark_count: number;
  coordinate_convention: Record<string, string>;
  landmarks: LandmarkItemPayload[];
  provenance: Record<string, unknown>;
}

export async function fetchLandmarks(): Promise<LandmarksPayload> {
  return fetchJson<LandmarksPayload>(`${API_BASE}/landmarks`, 'Landmarks');
}

export interface HazardItemPayload {
  hazard_id: string;
  hazard_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  risk_score: number;
  confidence: number | null;
  description: string;
  position_m: { x: number; y: number; z: number };
  radius_m: number | null;
  boundary_vertices_m: Array<{ x: number; y: number; z: number }> | null;
  data_status: string;
  provenance: Record<string, unknown>;
}

export interface HazardsPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  hazard_count: number;
  coordinate_convention: Record<string, string>;
  hazards: HazardItemPayload[];
  provenance: Record<string, unknown>;
}

export async function fetchHazards(): Promise<HazardsPayload> {
  return fetchJson<HazardsPayload>(`${API_BASE}/hazards`, 'Hazards');
}

export interface SpectralBandPayload {
  band_id: string;
  name: string;
  wavelength_um: number | null;
  unit: string;
}

export interface SpectralRegionPayload {
  region_id: string;
  display_label: string;
  center_m: { x: number; y: number; z: number };
  boundary_vertices_m: Array<{ x: number; y: number; z: number }>;
  band_values: Record<string, number>;
  scalar_index: number;
  data_status: string;
  provenance: Record<string, unknown>;
}

export interface SpectralClassificationSummaryPayload {
  class_name: string;
  pixel_count: number;
  valid_pixel_count: number;
  valid_pixel_percentage: number;
}

export interface SpectralClassificationPayload {
  status: 'illustrative' | string;
  source_type: 'synthetic' | string;
  classes: string[];
  class_map: string[][];
  score_map: Array<Array<number | null>>;
  score_semantics: string;
  valid_mask: boolean[][];
  shape: { height: number; width: number };
  summary: SpectralClassificationSummaryPayload[];
  provenance: Record<string, unknown>;
}

export interface SpectralOverlayPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  region_count: number;
  colormap_name: string;
  min_value: number;
  max_value: number;
  coordinate_convention: Record<string, string>;
  available_bands: SpectralBandPayload[];
  regions: SpectralRegionPayload[];
  classification?: SpectralClassificationPayload;
  provenance: Record<string, unknown>;
}

export async function fetchSpectralOverlay(): Promise<SpectralOverlayPayload> {
  return fetchJson<SpectralOverlayPayload>(`${API_BASE}/spectral`, 'Spectral overlay');
}

export interface WaterIceItemPayload {
  water_ice_id: string;
  display_label: string;
  position_m: { x: number; y: number; z: number };
  boundary_vertices_m: Array<{ x: number; y: number; z: number }> | null;
  data_status: string;
  provenance: Record<string, unknown>;
}

export interface WaterIceOverlayPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  item_count: number;
  region_count: number;
  coordinate_convention: Record<string, string>;
  items: WaterIceItemPayload[];
  provenance: Record<string, unknown>;
}

export async function fetchWaterIceOverlay(): Promise<WaterIceOverlayPayload> {
  return fetchJson<WaterIceOverlayPayload>(`${API_BASE}/water-ice`, 'Water-ice overlay');
}
