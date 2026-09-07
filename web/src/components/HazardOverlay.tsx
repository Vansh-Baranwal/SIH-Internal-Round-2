import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchHazards, type HazardsPayload, type HazardItemPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface HazardViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
  hazardCount?: number;
}

function isRenderableHazards(data: unknown): data is HazardsPayload {
  if (typeof data !== 'object' || data === null) return false;
  const candidate = data as Partial<HazardsPayload>;
  if (typeof candidate.display_label !== 'string' || !Array.isArray(candidate.hazards)) return false;
  return candidate.hazards.every(h => (
    typeof h === 'object' && h !== null
    && typeof h.hazard_id === 'string'
    && typeof h.position_m === 'object' && h.position_m !== null
    && typeof h.position_m.x === 'number'
    && typeof h.position_m.y === 'number'
    && typeof h.position_m.z === 'number'
  ));
}

function getHazardColor(severity: string): { primary: string; glow: string; fill: string } {
  switch (severity) {
    case 'CRITICAL':
      return { primary: '#ef4444', glow: '#f87171', fill: '#ef4444' };
    case 'HIGH':
      return { primary: '#f97316', glow: '#fb923c', fill: '#f97316' };
    case 'MODERATE':
      return { primary: '#eab308', glow: '#fde047', fill: '#eab308' };
    case 'LOW':
    default:
      return { primary: '#84cc16', glow: '#a3e635', fill: '#84cc16' };
  }
}

interface SingleHazardProps {
  item: HazardItemPayload;
}

function SingleHazardElement({ item }: SingleHazardProps) {
  const { position_m: pos, radius_m, boundary_vertices_m: poly, severity } = item;
  const colors = getHazardColor(severity);
  const radius = radius_m ?? 50.0;

  // Boundary line geometry for polygon hazard regions
  const boundaryLineGeom = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    const points = poly.map(v => toThreeVector(v, 0.3));
    // Close the loop
    points.push(new THREE.Vector3(poly[0].x, poly[0].y + 0.3, poly[0].z));
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [poly]);

  // Polygon fill shape if vertices exist
  const polygonFillMesh = useMemo(() => {
    if (!poly || poly.length < 3) return null;
    // Project vertices onto a flat triangulated geometry
    const shape = new THREE.Shape();
    shape.moveTo(poly[0].x, -poly[0].z);
    for (let i = 1; i < poly.length; i++) {
      shape.lineTo(poly[i].x, -poly[i].z);
    }
    shape.closePath();

    const geom = new THREE.ShapeGeometry(shape);
    // Average Y altitude
    const avgY = poly.reduce((acc, v) => acc + v.y, 0) / poly.length + 0.15;

    return { geom, avgY };
  }, [poly]);

  useEffect(() => () => {
    boundaryLineGeom?.dispose();
    polygonFillMesh?.geom.dispose();
  }, [boundaryLineGeom, polygonFillMesh]);

  return (
    <group name={`hazard-${item.hazard_id}`}>
      {/* Center Zone Marker & Pin */}
        <group position={toThreeVector(pos).toArray()} name="hazard-center-marker">
        {/* Ground Hazard Ring */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.2, 0]}>
          <ringGeometry args={[radius * 0.85, radius, 32]} />
          <meshBasicMaterial color={colors.primary} side={THREE.DoubleSide} transparent opacity={0.65} />
        </mesh>

        {/* Hazard Zone Transparent Floor Fill */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0]}>
          <circleGeometry args={[radius * 0.85, 32]} />
          <meshBasicMaterial color={colors.fill} side={THREE.DoubleSide} transparent opacity={0.18} />
        </mesh>

        {/* Warning Marker Pole */}
        <mesh position={[0, 18, 0]}>
          <cylinderGeometry args={[1.2, 1.2, 36, 12]} />
          <meshBasicMaterial color={colors.primary} />
        </mesh>

        {/* Warning Indicator Diamond at Top */}
        <mesh position={[0, 42, 0]}>
          <octahedronGeometry args={[8, 0]} />
          <meshBasicMaterial color={colors.glow} />
        </mesh>
      </group>

      {/* Polygon Boundary Outline if region vertices provided */}
      {boundaryLineGeom && (
        <primitive
          object={new THREE.Line(
            boundaryLineGeom,
            new THREE.LineBasicMaterial({ color: colors.primary, linewidth: 3 })
          )}
          name="hazard-boundary-outline"
        />
      )}

      {/* Polygon Region Fill if available */}
      {polygonFillMesh && (
        <mesh
          geometry={polygonFillMesh.geom}
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, polygonFillMesh.avgY, 0]}
          name="hazard-region-fill"
        >
          <meshBasicMaterial color={colors.fill} transparent opacity={0.2} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  );
}

/** Provider-backed 3D hazard overlay layer spatially associated with DEM terrain. */
export function HazardOverlay({ onStateChange }: { onStateChange?: (state: HazardViewState) => void }) {
  const [data, setData] = useState<HazardsPayload | null>(null);
  const [state, setState] = useState<HazardViewState>({ kind: 'loading', message: 'Loading hazard overlays...' });

  useEffect(() => {
    let active = true;
    fetchHazards()
      .then((res: unknown) => {
        if (!active) return;
        if (!isRenderableHazards(res)) {
          setState({ kind: 'invalid', message: 'Hazard metadata is malformed.' });
        } else if (res.hazards.length === 0) {
          setState({ kind: 'empty', label: res.display_label, message: 'No hazard overlays active.' });
          setData(res);
        } else {
          setData(res);
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({
          kind: 'unavailable',
          message: error instanceof Error ? error.message : 'Hazard overlay data is unavailable.',
        });
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (data && data.hazards.length > 0) {
      setState({
        kind: 'ready',
        label: data.display_label,
        message: `${data.hazards.length} hazard zones rendered on DEM surface.`,
        hazardCount: data.hazards.length,
      });
    }
  }, [data]);

  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);

  return (
    <>
      {data && data.hazards.map(item => (
        <SingleHazardElement key={item.hazard_id} item={item} />
      ))}
    </>
  );
}
