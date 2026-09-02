import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchLandmarks, type LandmarksPayload, type LandmarkItemPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface LandmarkViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
  landmarkCount?: number;
}

function isRenderableLandmarks(data: unknown): data is LandmarksPayload {
  if (typeof data !== 'object' || data === null) return false;
  const candidate = data as Partial<LandmarksPayload>;
  if (typeof candidate.display_label !== 'string' || !Array.isArray(candidate.landmarks)) return false;
  return candidate.landmarks.every(lm => (
    typeof lm === 'object' && lm !== null
    && typeof lm.landmark_id === 'string'
    && typeof lm.estimated_position_m === 'object' && lm.estimated_position_m !== null
    && typeof lm.estimated_position_m.x === 'number'
    && typeof lm.estimated_position_m.y === 'number'
    && typeof lm.estimated_position_m.z === 'number'
  ));
}

interface LandmarkMarkerGroupProps {
  item: LandmarkItemPayload;
}

function SingleLandmarkMarker({ item }: LandmarkMarkerGroupProps) {
  const { estimated_position_m: est, reference_position_m: ref, diameter_m: diam } = item;
  const radius = Math.max(15, Math.min(diam / 2.0, 100));

  // Line geometry connecting estimated and reference positions (if distinct)
  const offsetLineGeom = useMemo(() => {
    if (!ref) return null;
    const dx = ref.x - est.x;
    const dy = ref.y - est.y;
    const dz = ref.z - est.z;
    if (Math.hypot(dx, dy, dz) < 0.1) return null;

    const points = [
      toThreeVector(est, 2),
      toThreeVector(ref, 2),
    ];
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [est, ref]);

  useEffect(() => () => { offsetLineGeom?.dispose(); }, [offsetLineGeom]);

  return (
    <group name={`landmark-${item.landmark_id}`}>
      {/* Estimated Coordinate Marker (Cyan / Sky Blue) */}
      <group position={toThreeVector(est).toArray()} name="landmark-estimated-coordinate">
        {/* Ring on terrain */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.5, 0]}>
          <ringGeometry args={[radius * 0.8, radius, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.8} />
        </mesh>
        {/* Center pin */}
        <mesh position={[0, 25, 0]}>
          <cylinderGeometry args={[2, 2, 50, 16]} />
          <meshBasicMaterial color="#38bdf8" />
        </mesh>
        {/* Top diamond */}
        <mesh position={[0, 55, 0]}>
          <octahedronGeometry args={[10, 0]} />
          <meshBasicMaterial color="#00f0ff" />
        </mesh>
      </group>

      {/* Reference Coordinate Marker (Amber / Yellow) when distinct */}
      {ref && (
        <group position={toThreeVector(ref).toArray()} name="landmark-reference-coordinate">
          {/* Reference ring */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.5, 0]}>
            <ringGeometry args={[radius * 0.7, radius * 0.9, 32]} />
            <meshBasicMaterial color="#fbbf24" side={THREE.DoubleSide} transparent opacity={0.6} />
          </mesh>
          {/* Reference pin */}
          <mesh position={[0, 20, 0]}>
            <cylinderGeometry args={[1.5, 1.5, 40, 16]} />
            <meshBasicMaterial color="#fbbf24" />
          </mesh>
        </group>
      )}

      {/* Offset Line connecting Estimated and Reference positions */}
      {offsetLineGeom && (
        <primitive
          object={new THREE.Line(
            offsetLineGeom,
            new THREE.LineBasicMaterial({ color: '#f59e0b', linewidth: 2 })
          )}
          name="landmark-offset-line"
        />
      )}
    </group>
  );
}

/** Provider-backed landmark visualization displaying estimated vs reference coordinates. */
export function LandmarkMarkers({ onStateChange }: { onStateChange?: (state: LandmarkViewState) => void }) {
  const [data, setData] = useState<LandmarksPayload | null>(null);
  const [state, setState] = useState<LandmarkViewState>({ kind: 'loading', message: 'Loading landmarks...' });

  useEffect(() => {
    let active = true;
    fetchLandmarks()
      .then((res: unknown) => {
        if (!active) return;
        if (!isRenderableLandmarks(res)) {
          setState({ kind: 'invalid', message: 'Landmark metadata is malformed.' });
        } else if (res.landmarks.length === 0) {
          setState({ kind: 'empty', label: res.display_label, message: 'No landmarks available.' });
          setData(res);
        } else {
          setData(res);
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({
          kind: 'unavailable',
          message: error instanceof Error ? error.message : 'Landmark data is unavailable.',
        });
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (data && data.landmarks.length > 0) {
      setState({
        kind: 'ready',
        label: data.display_label,
        message: `${data.landmarks.length} landmarks rendered (estimated vs reference coords separated).`,
        landmarkCount: data.landmarks.length,
      });
    }
  }, [data]);

  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);

  return (
    <>
      {data && data.landmarks.map(item => (
        <SingleLandmarkMarker key={item.landmark_id} item={item} />
      ))}
    </>
  );
}
