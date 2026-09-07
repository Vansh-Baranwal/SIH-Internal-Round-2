import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchOhrcCamera, type OhrcCameraPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface OhrcCameraViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid';
  label?: string;
  message?: string;
}

function isRenderableCamera(camera: unknown): camera is OhrcCameraPayload {
  if (typeof camera !== 'object' || camera === null) return false;
  const candidate = camera as Partial<OhrcCameraPayload>;
  if (typeof candidate.display_label !== 'string' || typeof candidate.position_m !== 'object' || candidate.position_m === null || typeof candidate.target_m !== 'object' || candidate.target_m === null) return false;
  if (typeof candidate.vertical_fov_degrees !== 'number' || typeof candidate.aspect_ratio !== 'number' || typeof candidate.near_m !== 'number' || typeof candidate.far_m !== 'number') return false;
  const position = candidate.position_m;
  const target = candidate.target_m;
  if (typeof position.x !== 'number' || typeof position.y !== 'number' || typeof position.z !== 'number' || typeof target.x !== 'number' || typeof target.y !== 'number' || typeof target.z !== 'number') return false;
  const validated = candidate as OhrcCameraPayload;
  const values = [validated.position_m.x, validated.position_m.y, validated.position_m.z, validated.target_m.x, validated.target_m.y, validated.target_m.z, validated.vertical_fov_degrees, validated.aspect_ratio, validated.near_m, validated.far_m];
  return values.every(Number.isFinite)
    && validated.vertical_fov_degrees > 0 && validated.vertical_fov_degrees < 180
    && validated.aspect_ratio > 0 && validated.near_m > 0 && validated.far_m > validated.near_m;
}

/** A provider-backed OHRC frustum visualization, not an observation footprint. */
export function OhrcCameraFrustum({ onStateChange }: { onStateChange?: (state: OhrcCameraViewState) => void }) {
  const [cameraData, setCameraData] = useState<OhrcCameraPayload | null>(null);
  const [state, setState] = useState<OhrcCameraViewState>({ kind: 'loading', message: 'Loading OHRC camera geometry...' });

  useEffect(() => {
    let active = true;
    fetchOhrcCamera().then((camera: unknown) => {
      if (!active) return;
      if (!isRenderableCamera(camera)) setState({ kind: 'invalid', message: 'OHRC camera metadata is malformed.' });
      else setCameraData(camera);
    }).catch((error: unknown) => {
      if (!active) return;
      setState({ kind: 'unavailable', message: error instanceof Error ? error.message : 'OHRC camera metadata is unavailable.' });
    });
    return () => { active = false; };
  }, []);

  const helper = useMemo(() => {
    if (!cameraData) return null;
    const camera = new THREE.PerspectiveCamera(cameraData.vertical_fov_degrees, cameraData.aspect_ratio, cameraData.near_m, cameraData.far_m);
    camera.position.copy(toThreeVector(cameraData.position_m));
    camera.lookAt(toThreeVector(cameraData.target_m));
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    const nextHelper = new THREE.CameraHelper(camera);
    nextHelper.name = 'ohrc-camera-frustum';
    return nextHelper;
  }, [cameraData]);

  useEffect(() => {
    if (cameraData && helper) setState({ kind: 'ready', label: cameraData.display_label, message: 'Frustum is a development visualization, not observation coverage.' });
  }, [cameraData, helper]);
  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);
  useEffect(() => () => { helper?.dispose(); }, [helper]);

  return (
    <>
      {helper && <primitive object={helper} />}
      {cameraData && helper && (
        <mesh position={toThreeVector(cameraData.position_m).toArray()} name="ohrc-camera-marker">
          <sphereGeometry args={[14, 16, 16]} />
          <meshBasicMaterial color="#ff9900" />
        </mesh>
      )}
    </>
  );
}
