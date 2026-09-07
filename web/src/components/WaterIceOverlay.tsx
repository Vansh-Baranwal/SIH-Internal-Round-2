import { memo, useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchWaterIceOverlay, type WaterIceItemPayload, type WaterIceOverlayPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface WaterIceViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
  itemCount?: number;
}

function isRenderable(value: unknown): value is WaterIceOverlayPayload {
  if (typeof value !== 'object' || value === null) return false;
  const data = value as Partial<WaterIceOverlayPayload>;
  return typeof data.display_label === 'string' && Array.isArray(data.items)
    && data.items.every((item: WaterIceItemPayload) => typeof item.water_ice_id === 'string'
      && typeof item.position_m?.x === 'number' && typeof item.position_m?.y === 'number'
      && typeof item.position_m?.z === 'number'
      && (item.boundary_vertices_m === null || Array.isArray(item.boundary_vertices_m)));
}

const WaterIceItemElement = memo(function WaterIceItemElement({ item }: { item: WaterIceItemPayload }) {
  const { position_m: pos, boundary_vertices_m: poly } = item;
  const radius = 55;
  const boundary = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    const points = poly.map(v => toThreeVector(v, 0.7));
    points.push(points[0].clone());
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [poly]);
  const fill = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    // Triangulate the polygon in the viewer's East/Up/North frame so each
    // supplied elevation is retained instead of flattening to an average Y.
    const positions: number[] = [];
    for (let i = 1; i < poly.length - 1; i++) {
      for (const vertex of [poly[0], poly[i], poly[i + 1]]) {
        positions.push(vertex.x, vertex.y + 0.45, vertex.z);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    return { geometry };
  }, [poly]);
  useEffect(() => () => { boundary?.dispose(); fill?.geometry.dispose(); }, [boundary, fill]);
  const line = useMemo(() => boundary ? new THREE.Line(boundary, new THREE.LineBasicMaterial({ color: '#bae6fd' })) : null, [boundary]);
  useEffect(() => () => { line?.material.dispose(); }, [line]);
  return <group name={`water-ice-${item.water_ice_id}`}>
    {fill && <mesh geometry={fill.geometry} name="water-ice-region-fill">
      <meshBasicMaterial color="#38bdf8" transparent opacity={0.42} side={THREE.DoubleSide} />
    </mesh>}
    {line && <primitive object={line} name="water-ice-boundary-outline" />}
    <group position={toThreeVector(pos).toArray()} name="water-ice-marker">
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.5, 0]}><ringGeometry args={[radius - 5, radius, 32]} /><meshBasicMaterial color="#22d3ee" transparent opacity={0.8} /></mesh>
      <mesh position={[0, 22, 0]}><cylinderGeometry args={[1.1, 1.1, 44, 12]} /><meshBasicMaterial color="#67e8f9" /></mesh>
      <mesh position={[0, 48, 0]}><octahedronGeometry args={[7, 0]} /><meshBasicMaterial color="#e0f2fe" /></mesh>
    </group>
  </group>;
});

/** Provider-backed water-ice visualization, independent of spectral/IIRS/Sun/hazard data. */
export const WaterIceOverlay = memo(function WaterIceOverlay({ onStateChange }: { onStateChange?: (state: WaterIceViewState) => void }) {
  const [data, setData] = useState<WaterIceOverlayPayload | null>(null);
  const [state, setState] = useState<WaterIceViewState>({ kind: 'loading', message: 'Loading water-ice overlay...' });
  useEffect(() => {
    let active = true;
    fetchWaterIceOverlay().then((response: unknown) => {
      if (!active) return;
      if (!isRenderable(response)) setState({ kind: 'invalid', message: 'Water-ice metadata is malformed.' });
      else if (response.items.length === 0) { setData(response); setState({ kind: 'empty', label: response.display_label, message: 'No water-ice regions available.' }); }
      else setData(response);
    }).catch(error => { if (active) setState({ kind: 'unavailable', message: error instanceof Error ? error.message : 'Water-ice data is unavailable.' }); });
    return () => { active = false; };
  }, []);
  useEffect(() => { if (data && data.items.length > 0) setState({ kind: 'ready', label: data.display_label, message: `${data.items.length} spatial development regions rendered on DEM surface.`, itemCount: data.items.length }); }, [data]);
  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);
  return <>{data?.items.map(item => <WaterIceItemElement key={item.water_ice_id} item={item} />)}</>;
});
