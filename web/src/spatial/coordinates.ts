/** Shared Phase 12 local rendering frame.
 *
 * Viewer positions are always Three.js [East, Up, North] in metres. The DEM
 * grid is the one deliberate boundary exception: its arrays are [East,
 * North, Up] because they mirror the terrain foundation's ENU grid contract.
 */
import * as THREE from 'three';

export const VIEW_COORDINATE_CONVENTION = {
  x: 'local_east_meters',
  y: 'local_up_meters',
  z: 'local_north_meters',
} as const;

export type ViewerPosition = { x: number; y: number; z: number };

export function toThreeVector(position: ViewerPosition, yOffset = 0): THREE.Vector3 {
  return new THREE.Vector3(position.x, position.y + yOffset, position.z);
}

export function terrainGridToThreeVector(east: number, north: number, up: number): THREE.Vector3 {
  return new THREE.Vector3(east, up, north);
}
