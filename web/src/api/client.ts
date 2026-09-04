import type { MissionData } from '../types/api';

const configuredApiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
const normalizedApiUrl = configuredApiUrl.replace(/\/+$/, '');

// The legacy endpoints live below `/api`, while versioned registration
// endpoints are built from the host root. Accept either a host URL or an
// already versioned `/api` URL from VITE_API_URL without double segments.
export const API_BASE = normalizedApiUrl.endsWith('/api')
  ? normalizedApiUrl
  : `${normalizedApiUrl}/api`;
export const API_ROOT = API_BASE.replace(/\/api$/, '');

export function joinApiUrl(...segments: string[]): string {
  return [API_ROOT, ...segments]
    .map((segment, index) => index === 0 ? segment.replace(/\/+$/, '') : segment.replace(/^\/+|\/+$/g, ''))
    .filter(Boolean)
    .join('/');
}

export async function fetchMissionData(): Promise<MissionData> {
  const response = await fetch(`${API_BASE}/mission`);
  if (!response.ok) {
    throw new Error('Failed to fetch mission data');
  }
  return response.json();
}

export function getAssetUrl(assetPath: string): string {
  return `${API_BASE}/assets/${assetPath}`;
}