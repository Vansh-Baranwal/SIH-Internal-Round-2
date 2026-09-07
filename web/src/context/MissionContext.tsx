import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

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

const MissionContext = createContext<MissionContextType | undefined>(undefined);

export function MissionProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<any>(null);

  const hasData = result !== null;
  const dataStatus: DatasetLoadStatus = hasData ? 'ready' : 'idle';
  const datasetLabel = hasData ? 'Mission Dataset' : 'No Dataset Loaded';

  return (
    <MissionContext.Provider value={{ result, setResult, hasData, dataStatus, datasetLabel }}>
      {children}
    </MissionContext.Provider>
  );
}

export function useMission() {
  const context = useContext(MissionContext);
  if (context === undefined) {
    throw new Error('useMission must be used within a MissionProvider');
  }
  return context;
}
