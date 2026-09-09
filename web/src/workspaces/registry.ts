import { Gauge, ScanLine, Waves, History, Boxes, type LucideIcon } from 'lucide-react';

/**
 * Phase 13.1 — workspace registry.
 *
 * Single source of truth for the application architecture. Each entry describes
 * one Phase 13 workspace bucket and the routes that belong to it. Existing Phase
 * 12 routes are mapped into their home workspace; workspaces that are not yet
 * implemented are flagged with `planned` so the architecture reserves a home for
 * them without fabricating functionality.
 *
 * This is scaffolding only: it declares the structure, not the implementation of
 * any Phase 13 workspace.
 */

export type WorkspaceId =
  | 'mission-control'
  | 'multi-sensor-registration'
  | 'spectral-water-ice'
  | 'temporal-analysis';

export interface WorkspaceRoute {
  label: string;
  path: string;
  /** True when the target is a Phase 13 workspace milestone not implemented yet. */
  planned?: boolean;
}

export interface WorkspaceDefinition {
  id: WorkspaceId;
  /** Human-facing workspace label. */
  label: string;
  /** Compact label used in navigation. */
  shortLabel: string;
  description: string;
  icon: LucideIcon;
  routes: WorkspaceRoute[];
}

export const WORKSPACES: WorkspaceDefinition[] = [
  {
    id: 'mission-control',
    label: 'Mission Control',
    shortLabel: 'Mission Control',
    description: 'Mission overview, hazard maps, site assessment and trajectory operations.',
    icon: Gauge,
    routes: [
      { label: 'Hazards', path: '/hazard-map' },
      { label: 'Landing Sites', path: '/landing-sites' },
      { label: 'Trajectory', path: '/trajectory' },
    ],
  },
  {
    id: 'multi-sensor-registration',
    label: 'Multi-sensor & Registration',
    shortLabel: 'Sensors',
    description: 'Multi-sensor imagery and sensor-to-sensor registration.',
    icon: ScanLine,
    routes: [
      { label: 'Imagery', path: '/imagery' },
      { label: 'Sensor Data', path: '/sensors' },
      { label: 'Registration', path: '/registration' },
    ],
  },
  {
    id: 'spectral-water-ice',
    label: 'Spectral & Water-Ice',
    shortLabel: 'Spectral',
    description: 'Spectral and Water-Ice intelligence workspaces using the current frontend data contracts and honest unavailable states.',
    icon: Waves,
    routes: [
      { label: 'Spectral', path: '/scientific' },
      { label: 'Water-Ice', path: '/water-ice' },
    ],
  },
  {
    id: 'temporal-analysis',
    label: 'Temporal Analysis',
    shortLabel: 'Temporal',
    description: 'Frontend temporal comparison workspace for genuine observation pairs and future change-analysis integration.',
    icon: History,
    routes: [{ label: 'Temporal Analysis', path: '/temporal' }],
  },
];

/** Return the workspace that owns the given route path, if any. */
export function getWorkspaceByPath(path: string): WorkspaceDefinition | undefined {
  return WORKSPACES.find((workspace) =>
    workspace.routes.some((route) => route.path === path),
  );
}

/** Return the first non-planned route of a workspace (its primary entry point). */
export function primaryPathOf(workspace: WorkspaceDefinition): string {
  const primary = workspace.routes.find((route) => !route.planned) ?? workspace.routes[0];
  return primary ? primary.path : '/';
}
