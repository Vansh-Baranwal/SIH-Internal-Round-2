import type { Trajectory, TrajectoryPoint } from '../types/api';

export type DigitalTwinTrajectoryPoint = TrajectoryPoint & {
  pitch?: number;
  yaw?: number;
  roll?: number;
};

export interface DigitalTwinTrajectory {
  source: 'm6' | 'legacy-simulation';
  points: DigitalTwinTrajectoryPoint[];
}

export function isM6Trajectory(value: unknown): value is Trajectory {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<Trajectory>;
  if (!Array.isArray(candidate.points) || candidate.points.length === 0) return false;
  return candidate.points.every(isM6TrajectoryPoint);
}

function isM6TrajectoryPoint(value: unknown): value is TrajectoryPoint {
  if (!value || typeof value !== 'object') return false;
  const point = value as Partial<TrajectoryPoint>;
  return ['t', 'x', 'y', 'z', 'vx', 'vy', 'vz'].every((field) => Number.isFinite(point[field as keyof TrajectoryPoint]));
}

export function adaptM6TrajectoryForDigitalTwin(trajectory: Trajectory): DigitalTwinTrajectory {
  return { source: 'm6', points: trajectory.points };
}

/** M6 is East/North/Up; the viewer is East/Up/North. */
export function m6PointToDigitalTwinPosition(point: TrajectoryPoint): [number, number, number] {
  return [point.x, point.z, point.y];
}
