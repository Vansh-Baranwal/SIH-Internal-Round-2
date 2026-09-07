import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { fetchIirsFootprint, type IirsFootprintPayload } from '../api/client';
import { toThreeVector } from '../spatial/coordinates';

export interface IirsFootprintViewState {
  kind: 'loading' | 'ready' | 'unavailable' | 'invalid' | 'empty';
  label?: string;
  message?: string;
}

function isRenderableFootprint(data: unknown): data is IirsFootprintPayload {
  if (typeof data !== 'object' || data === null) return false;
  const candidate = data as Partial<IirsFootprintPayload>;
  if (typeof candidate.display_label !== 'string' || typeof candidate.footprint !== 'object' || candidate.footprint === null) return false;
  const fp = candidate.footprint;
  if (!Array.isArray(fp.boundary_vertices) || fp.boundary_vertices.length < 3) return false;
  return fp.boundary_vertices.every(
    v => typeof v === 'object' && v !== null && typeof v.x === 'number' && typeof v.y === 'number' && typeof v.z === 'number'
      && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z)
  );
}

/** A provider-backed IIRS terrain footprint visualization, not a historical observation footprint. */
export function IirsFootprint({ onStateChange }: { onStateChange?: (state: IirsFootprintViewState) => void }) {
  const [footprintData, setFootprintData] = useState<IirsFootprintPayload | null>(null);
  const [state, setState] = useState<IirsFootprintViewState>({ kind: 'loading', message: 'Loading IIRS footprint...' });

  useEffect(() => {
    let active = true;
    fetchIirsFootprint()
      .then((data: unknown) => {
        if (!active) return;
        if (!isRenderableFootprint(data)) {
          setState({ kind: 'invalid', message: 'IIRS footprint metadata is malformed.' });
        } else {
          setFootprintData(data);
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({
          kind: 'unavailable',
          message: error instanceof Error ? error.message : 'IIRS footprint is unavailable.',
        });
      });
    return () => { active = false; };
  }, []);

  const { lineGeometry, fillGeometry } = useMemo(() => {
    if (!footprintData) return { lineGeometry: null, fillGeometry: null };
    const vertices = footprintData.footprint.boundary_vertices;
    if (vertices.length < 3) return { lineGeometry: null, fillGeometry: null };

    // Line loop geometry along terrain surface (offset slightly +0.8m in Y to prevent z-fighting)
    const linePoints: THREE.Vector3[] = [];
    vertices.forEach(v => {
      linePoints.push(toThreeVector(v, 0.8));
    });
    // Close line loop
    linePoints.push(toThreeVector(vertices[0], 0.8));

    const lineGeom = new THREE.BufferGeometry().setFromPoints(linePoints);

    // Triangulated fill fan/strip for semi-transparent surface overlay
    const positions: number[] = [];
    const indices: number[] = [];

    // Calculate center point for triangle fan
    let cx = 0, cy = 0, cz = 0;
    vertices.forEach(v => {
      cx += v.x;
      cy += v.y + 0.5;
      cz += v.z;
    });
    cx /= vertices.length;
    cy /= vertices.length;
    cz /= vertices.length;

    const centerIdx = 0;
    positions.push(cx, cy, cz);

    vertices.forEach(v => {
      positions.push(v.x, v.y + 0.5, v.z);
    });

    for (let i = 1; i <= vertices.length; i += 1) {
      const next = (i % vertices.length) + 1;
      indices.push(centerIdx, i, next);
    }

    const fillGeom = new THREE.BufferGeometry();
    fillGeom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    fillGeom.setIndex(indices);
    fillGeom.computeVertexNormals();

    return { lineGeometry: lineGeom, fillGeometry: fillGeom };
  }, [footprintData]);

  useEffect(() => {
    if (footprintData && lineGeometry) {
      setState({
        kind: 'ready',
        label: footprintData.display_label,
        message: 'Footprint is a development viewing area, not historical observation coverage.',
      });
    }
  }, [footprintData, lineGeometry]);

  useEffect(() => { onStateChange?.(state); }, [onStateChange, state]);

  useEffect(() => () => {
    lineGeometry?.dispose();
    fillGeometry?.dispose();
  }, [lineGeometry, fillGeometry]);

  return (
    <>
      {lineGeometry && (
        <primitive
          object={new THREE.Line(
            lineGeometry,
            new THREE.LineBasicMaterial({ color: '#22c55e', linewidth: 2 })
          )}
          name="iirs-footprint-boundary"
        />
      )}
      {fillGeometry && (
        <mesh geometry={fillGeometry} name="iirs-footprint-surface">
          <meshBasicMaterial
            color="#22c55e"
            transparent
            opacity={0.25}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      )}
    </>
  );
}
