import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchSpectralOverlay, type SpectralOverlayPayload, type SpectralRegionPayload, type SpectralBandPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface SpectralViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
  regionCount?: number;
  activeBand?: string;
}

function isRenderableSpectral(data: unknown): data is SpectralOverlayPayload {
  if (typeof data !== 'object' || data === null) return false;
  const candidate = data as Partial<SpectralOverlayPayload>;
  if (typeof candidate.display_label !== 'string' || !Array.isArray(candidate.regions)) return false;
  return candidate.regions.every(r => (
    typeof r === 'object' && r !== null
    && typeof r.region_id === 'string'
    && typeof r.center_m === 'object' && r.center_m !== null
    && typeof r.center_m.x === 'number'
    && typeof r.center_m.y === 'number'
    && typeof r.center_m.z === 'number'
    && Array.isArray(r.boundary_vertices_m)
  ));
}

/** Deterministic colormap mapping normalized value [0, 1] to RGB hex string */
function getSpectralColormap(value: number): string {
  const clamped = Math.max(0, Math.min(1, value));
  if (clamped < 0.25) return '#6366f1'; // Indigo
  if (clamped < 0.50) return '#06b6d4'; // Cyan
  if (clamped < 0.75) return '#10b981'; // Emerald
  return '#f59e0b'; // Amber
}

interface SingleSpectralRegionProps {
  item: SpectralRegionPayload;
  activeBandId: string;
}

function SingleSpectralRegion({ item, activeBandId }: SingleSpectralRegionProps) {
  const { center_m: c, boundary_vertices_m: poly, band_values } = item;
  const rawValue = band_values[activeBandId] ?? item.scalar_index;
  // Normalize assuming typical reflectance 0.0 to 0.35
  const normValue = Math.max(0, Math.min(1, rawValue / 0.35));
  const hexColor = getSpectralColormap(normValue);

  // Boundary outline geometry
  const boundaryLineGeom = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    const points = poly.map(v => toThreeVector(v, 0.2));
    points.push(new THREE.Vector3(poly[0].x, poly[0].y + 0.2, poly[0].z));
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [poly]);

  // Polygon fill shape
  const polygonFillMesh = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    const shape = new THREE.Shape();
    shape.moveTo(poly[0].x, -poly[0].z);
    for (let i = 1; i < poly.length; i++) {
      shape.lineTo(poly[i].x, -poly[i].z);
    }
    shape.closePath();

    const geom = new THREE.ShapeGeometry(shape);
    const avgY = poly.reduce((acc, v) => acc + v.y, 0) / poly.length + 0.1;
    return { geom, avgY };
  }, [poly]);

  useEffect(() => () => {
    boundaryLineGeom?.dispose();
    polygonFillMesh?.geom.dispose();
  }, [boundaryLineGeom, polygonFillMesh]);

  return (
    <group name={`spectral-region-${item.region_id}`}>
      {/* Translucent Spectral Draped Region Fill */}
      {polygonFillMesh && (
        <mesh
          geometry={polygonFillMesh.geom}
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, polygonFillMesh.avgY, 0]}
          name="spectral-region-fill"
        >
          <meshBasicMaterial color={hexColor} transparent opacity={0.38} side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Spectral Perimeter Outline (Indigo/Violet) */}
      {boundaryLineGeom && (
        <primitive
          object={new THREE.Line(
            boundaryLineGeom,
            new THREE.LineBasicMaterial({ color: '#818cf8', linewidth: 2 })
          )}
          name="spectral-boundary-outline"
        />
      )}

      {/* Center Spectral Tag Pin */}
      <group position={toThreeVector(c).toArray()} name="spectral-center-tag">
        <mesh position={[0, 10, 0]}>
          <cylinderGeometry args={[0.8, 0.8, 20, 8]} />
          <meshBasicMaterial color="#818cf8" />
        </mesh>
        <mesh position={[0, 22, 0]}>
          <boxGeometry args={[6, 6, 6]} />
          <meshBasicMaterial color={hexColor} />
        </mesh>
      </group>
    </group>
  );
}

/** Provider-backed 3D spectral overlay layer spatially draped on DEM terrain. */
export function SpectralOverlay({ onStateChange }: { onStateChange?: (state: SpectralViewState) => void }) {
  const [data, setData] = useState<SpectralOverlayPayload | null>(null);
  const [activeBandId, setActiveBandId] = useState<string>('BAND_950NM');
  const [state, setState] = useState<SpectralViewState>({ kind: 'loading', message: 'Loading spectral overlays...' });

  useEffect(() => {
    let active = true;
    fetchSpectralOverlay()
      .then((res: unknown) => {
        if (!active) return;
        if (!isRenderableSpectral(res)) {
          setState({ kind: 'invalid', message: 'Spectral metadata is malformed.' });
        } else if (res.regions.length === 0) {
          setState({ kind: 'empty', label: res.display_label, message: 'No spectral regions available.' });
          setData(res);
        } else {
          setData(res);
          if (res.available_bands.length > 0) {
            setActiveBandId(res.available_bands[0].band_id);
          }
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({
          kind: 'unavailable',
          message: error instanceof Error ? error.message : 'Spectral overlay data is unavailable.',
        });
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (data && data.regions.length > 0) {
      const activeBandObj = data.available_bands.find(b => b.band_id === activeBandId);
      const bandLabel = activeBandObj ? `${activeBandObj.name}` : activeBandId;
      setState({
        kind: 'ready',
        label: data.display_label,
        message: `${data.regions.length} spectral units draped on DEM (${bandLabel}).`,
        regionCount: data.regions.length,
        activeBand: activeBandId,
      });
    }
  }, [data, activeBandId]);

  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);

  return (
    <>
      {data && data.regions.map(item => (
        <SingleSpectralRegion key={item.region_id} item={item} activeBandId={activeBandId} />
      ))}
    </>
  );
}
