import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchDemTerrain, type DemTerrainPayload } from '../api/client';
import { terrainGridToThreeVector } from '../spatial/coordinates';

interface TerrainProps {
  onClick?: (x: number, y: number, z: number, isSafe: boolean) => void;
  target?: { x: number, y: number, z: number } | null;
  onStateChange?: (state: TerrainViewState) => void;
}

export interface TerrainViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
}

interface MeshData {
  geometry: THREE.BufferGeometry;
}

export type DemGeometryResult =
  | { kind: 'geometry'; mesh: MeshData }
  | { kind: 'empty' }
  | { kind: 'invalid'; message: string };

function isDemTerrainPayload(value: unknown): value is DemTerrainPayload {
  if (typeof value !== 'object' || value === null) return false;
  const payload = value as { metadata?: unknown; grid?: unknown };
  if (typeof payload.metadata !== 'object' || payload.metadata === null || typeof payload.grid !== 'object' || payload.grid === null) return false;
  const metadata = payload.metadata as { display_label?: unknown };
  const grid = payload.grid as { width?: unknown; height?: unknown; x?: unknown; y?: unknown; z?: unknown; valid_mask?: unknown };
  return typeof metadata.display_label === 'string'
    && Number.isInteger(grid.width) && Number.isInteger(grid.height)
    && Array.isArray(grid.x) && Array.isArray(grid.y) && Array.isArray(grid.z) && Array.isArray(grid.valid_mask);
}

/**
 * Builds the mesh directly from the TerrainFoundation payload. The only
 * visualization transform is ENU -> Three axes: East -> X, North -> Z,
 * Up -> Y. All coordinate and elevation values remain metres.
 *
 * A DEM quad is emitted only when all four samples are valid and finite.
 * Consequently nodata/NaN cells remain holes rather than fabricated terrain.
 */
export function buildDemTerrainGeometry(payload: DemTerrainPayload): DemGeometryResult {
  const { width, height, x, y, z, valid_mask: validMask } = payload.grid;
  if (width < 2 || height < 2 || x.length !== height || y.length !== height || z.length !== height || validMask.length !== height) {
    return { kind: 'invalid', message: 'Terrain grid dimensions do not match its declared shape.' };
  }

  const positions: number[] = [];
  const indices: number[] = [];
  const vertexForCell = new Map<number, number>();
  const isValid = (row: number, column: number) => Boolean(validMask[row]?.[column])
    && Number.isFinite(x[row]?.[column])
    && Number.isFinite(y[row]?.[column])
    && Number.isFinite(z[row]?.[column]);
  for (let row = 0; row < height; row += 1) {
    if (x[row]?.length !== width || y[row]?.length !== width || z[row]?.length !== width || validMask[row]?.length !== width) {
      return { kind: 'invalid', message: 'Terrain grid row dimensions do not match its declared width.' };
    }
    for (let column = 0; column < width; column += 1) {
      if (validMask[row][column] && !isValid(row, column)) {
        return { kind: 'invalid', message: 'Terrain declares a valid cell with non-finite coordinates or elevation.' };
      }
    }
  }
  const addVertex = (row: number, column: number) => {
    const key = row * width + column;
    const current = vertexForCell.get(key);
    if (current !== undefined) return current;
    const index = positions.length / 3;
    // East/North/Up metadata coordinates are rendered as Three X/Z/Y.
    // Equivalent to the established mapping: positions.push(x[row][column], z[row][column], y[row][column]).
    const position = terrainGridToThreeVector(x[row][column], y[row][column], z[row][column]);
    positions.push(position.x, position.y, position.z);
    vertexForCell.set(key, index);
    return index;
  };

  for (let row = 0; row < height - 1; row += 1) {
    for (let column = 0; column < width - 1; column += 1) {
      if (![isValid(row, column), isValid(row, column + 1), isValid(row + 1, column), isValid(row + 1, column + 1)].every(Boolean)) continue;
      const topLeft = addVertex(row, column);
      const topRight = addVertex(row, column + 1);
      const bottomLeft = addVertex(row + 1, column);
      const bottomRight = addVertex(row + 1, column + 1);
      // Winding gives an upward (local-Up / Three +Y) face normal.
      indices.push(topLeft, topRight, bottomLeft, topRight, bottomRight, bottomLeft);
    }
  }
  if (indices.length === 0) return { kind: 'empty' };

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return { kind: 'geometry', mesh: { geometry } };
}

export function Terrain({ onClick, target, onStateChange }: TerrainProps) {
  const [terrain, setTerrain] = useState<DemTerrainPayload | null>(null);
  const [state, setState] = useState<TerrainViewState>({ kind: 'loading', message: 'Loading DEM terrain…' });

  useEffect(() => {
    let active = true;
    fetchDemTerrain()
      .then((payload: unknown) => {
        if (!active) return;
        if (!isDemTerrainPayload(payload)) setState({ kind: 'invalid', message: 'Terrain response does not satisfy the DEM terrain contract.' });
        else setTerrain(payload);
      })
      .catch((error: unknown) => {
        if (!active) return;
        const message = error instanceof Error ? error.message : 'Terrain data is unavailable.';
        setState({ kind: 'unavailable', message });
      });
    return () => { active = false; };
  }, []);

  const meshResult = useMemo(() => terrain ? buildDemTerrainGeometry(terrain) : null, [terrain]);
  useEffect(() => {
    if (!terrain) return;
    if (meshResult?.kind === 'invalid') setState({ kind: 'invalid', label: terrain.metadata.display_label, message: meshResult.message });
    else if (meshResult?.kind === 'empty') setState({ kind: 'empty', label: terrain.metadata.display_label, message: 'Terrain contains no renderable valid DEM cells.' });
    else setState({ kind: 'ready', label: terrain.metadata.display_label });
  }, [meshResult, terrain]);
  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);
  useEffect(() => () => { if (meshResult?.kind === 'geometry') meshResult.mesh.geometry.dispose(); }, [meshResult]);

  const handleClick = (event: { stopPropagation: () => void; point: THREE.Vector3; face: THREE.Face | null; object: THREE.Object3D }) => {
    event.stopPropagation();
    if (!onClick || !event.face) return;
    const normal = event.face.normal.clone();
    normal.applyMatrix3(new THREE.Matrix3().getNormalMatrix(event.object.matrixWorld)).normalize();
    const slope = Math.acos(Math.min(1, Math.abs(normal.y))) * (180 / Math.PI);
    // The callback stays in viewer axes: X=east, Y=up/elevation, Z=north.
    onClick(event.point.x, event.point.y, event.point.z, slope <= 10.0);
  };

  return (
    <group>
      {meshResult?.kind === 'geometry' && <mesh geometry={meshResult.mesh.geometry} onClick={handleClick} receiveShadow castShadow name="dem-terrain">
        <meshStandardMaterial color="#72706a" roughness={0.95} metalness={0} side={THREE.DoubleSide} />
      </mesh>}
      {target && <group position={[target.x, target.y + 0.5, target.z]} name="target-marker">
        <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[20, 30, 32]} /><meshBasicMaterial color="yellow" /></mesh>
        <mesh position={[0, 40, 0]}><cylinderGeometry args={[0, 10, 80, 16]} /><meshBasicMaterial color="red" /></mesh>
      </group>}
    </group>
  );
}

useGLTF.preload(getAssetUrl('moon_surface.glb?v=3'));
