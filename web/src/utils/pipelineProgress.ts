import type { RegistrationSession } from '../types/registration';

export interface PipelineStage {
  id: 'registration' | 'imagery' | 'hazards' | 'landingSites' | 'trajectory' | 'simulation';
  label: string;
  path: string;
  /** True once this stage's actual data exists — not just once `result` is non-null. */
  complete: boolean;
}

/**
 * Single source of truth for "is stage X actually done", derived from the
 * same fields Imagery.tsx / HazardMap.tsx / LandingSites.tsx / Trajectory.tsx
 * each check locally (`original_url`/`sr_url`, `slope_url`/`risk_url`,
 * `sites_url_A`/`sites_url_B`, `m6.trajectory`). Kept here instead of
 * duplicated a fifth time in the navbar so the two can't disagree about
 * what "done" means — e.g. the stepper marking Hazards complete while
 * HazardMap.tsx itself still shows the "pending" panel.
 */
export function getPipelineStages(result: any, session: RegistrationSession): PipelineStage[] {
  const p = result?.pipeline;

  const originalUrl = result?.original_url || p?.original_url;
  const srUrl = result?.sr_url || p?.sr_url;

  const slopeUrl = result?.slope_url || p?.slope_url;
  const riskUrl = result?.risk_url || p?.risk_url;

  const m5A = result?.m5?.lander_A || p?.m5?.lander_A;
  const m5B = result?.m5?.lander_B || p?.m5?.lander_B;
  const sitesUrl = result?.sites_url || p?.sites_url || p?.m5?.sites_url;
  const sitesUrlA = result?.sites_url_A || sitesUrl;
  const sitesUrlB = result?.sites_url_B || sitesUrl;

  const m6 = result?.m6 || p?.m6;

  return [
    {
      id: 'imagery',
      label: 'Imagery',
      path: '/imagery',
      complete: !!(originalUrl && srUrl),
    },
    {
      id: 'hazards',
      label: 'Hazards',
      path: '/hazard-map',
      complete: !!(slopeUrl && riskUrl),
    },
    {
      id: 'landingSites',
      label: 'Sites',
      path: '/landing-sites',
      complete: !!(sitesUrlA || sitesUrlB || m5A || m5B),
    },
    {
      id: 'trajectory',
      label: 'Trajectory',
      path: '/trajectory',
      complete: !!m6?.trajectory,
    },
    {
      // Terminal stage — nothing downstream depends on it, so it has no
      // "complete" condition of its own; it just reflects reaching it.
      id: 'simulation',
      label: 'Simulation',
      path: '/simulation',
      complete: false,
    },
  ];
}