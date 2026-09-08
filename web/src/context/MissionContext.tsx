import { useState, useCallback, type ReactNode } from 'react';
import type { RegistrationSession, DatasetInput } from '../types/registration';
import { createEmptySession } from '../types/registration';
import { MissionContext } from './MissionContextValue';

export type DatasetLoadStatus = 'idle' | 'ready' | 'error';

/**
 * Phase 13.1 — shared dataset / metadata / layer state.
 *
 * Wraps the raw mission pipeline payload (kept as-is for Phase 12 compatibility)
 * plus a small set of derived, typed fields describing the dataset the app is
 * currently working with. Existing consumers that destructure `result` /
 * `setResult` are unaffected.
 */
type MissionContextType = {
  /** Raw mission / pipeline payload (Phase 12 compatibility). */
  result: any;
  setResult: (data: any) => void;
  /** Derived helper: a dataset has been loaded. */
  hasData: boolean;
  /** Derived load state. */
  dataStatus: DatasetLoadStatus;
  /** Human-readable label for the currently loaded dataset. */
  datasetLabel: string;
};
export type { MissionContextType } from './MissionContextValue';

// NOTE ON MIGRATION
// -----------------
// `result` is the original, untyped blob produced by the legacy M2-M6
// pipeline (used by Imagery.tsx, HazardMap.tsx, LandingSites.tsx,
// Trajectory.tsx, Simulation.tsx, Terrain.tsx). We keep it as-is so none of
// those pages need to change in this pass.
//
// `session` is the new typed state for the Multi-Modal Correspondence
// Engine workflow (Registration.tsx and anything downstream of it).
// The two are intentionally decoupled: the correspondence engine's
// `overlayImageUrl` is handed to the legacy imagery workflow only when the
// user explicitly continues from Registration (see `sendToMissionPipeline`).
// rather than baked into a single shared blob.


export function MissionProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<any>(null);
  const [session, setSession] = useState<RegistrationSession>(createEmptySession());

  const resetSession = useCallback(() => setSession(createEmptySession()), []);

  const sendToMissionPipeline = useCallback((overlayImageUrl: string) => {
    // Bridges the new correspondence output into the legacy `result` shape
    // that Imagery.tsx and the downstream views already read
    // from (`result.slope_url`, `result.risk_url`, `result.pipeline`, etc).
    // This keeps those pages untouched while letting registered imagery
    // become their input, as called for in the target architecture doc.
    //
    // `from_registration: true` is what lets those pages tell "no data at
    // all" apart from "registered image present, downstream M3/M4/M5/M6
    // hasn't processed it yet" and show the right message instead of a
    // silently broken image request.
    setResult((prev: any) => ({
      ...(prev ?? {}),
      source_image_url: overlayImageUrl,
      from_registration: true,
      pipeline: prev?.pipeline ?? {},
    }));
  }, []);

  const startCounterfactualSession = useCallback(
    (capture: { dataUrl: string; azimuthDeg: number; elevationDeg: number }) => {
      const dataset: DatasetInput = {
        id: crypto.randomUUID(),
        sensor: 'OHRC',
        name: `Counterfactual (az ${capture.azimuthDeg.toFixed(0)}°, el ${capture.elevationDeg.toFixed(0)}°)`,
        previewUrl: capture.dataUrl,
        datasetId: `counterfactual-${Date.now()}`,
        synthetic: true,
      };
      setSession({
        ...createEmptySession(),
        datasetSource: dataset,
        sunSimulation: {
          azimuthDeg: capture.azimuthDeg,
          elevationDeg: capture.elevationDeg,
          illuminationVariant: true,
        },
      });
    },
    [setSession],
  );

  const hasData = result !== null;
  const dataStatus: DatasetLoadStatus = hasData ? 'ready' : 'idle';
  const datasetLabel = hasData ? 'Mission Dataset' : 'No Dataset Loaded';

  return (
    
    <MissionContext.Provider
      value={{ result, setResult, session, setSession, resetSession, sendToMissionPipeline, startCounterfactualSession, hasData, dataStatus, datasetLabel }}
    >
      {children}
    </MissionContext.Provider>
  );
}
