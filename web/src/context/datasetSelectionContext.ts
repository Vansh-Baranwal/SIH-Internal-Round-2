import { createContext, useContext } from 'react';

/** The currently supported imaging sensors. */
export type SensorId = 'tmc' | 'ohrc' | 'iirs';

/**
 * A normalized, reusable description of one selected dataset/sensor. Later
 * Phase 13 workspaces (registration, spectral, Water-Ice) can consume the
 * selected datasets and their metadata from the shared selection state.
 */
export interface SelectedDataset {
  id: SensorId;
  label: string;
  displayLabel: string;
  dataStatus: string;
  coordinateConvention: Record<string, string>;
  metadata: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

export interface DatasetSelectionContextValue {
  /** Ordered ids of the currently selected datasets. */
  selectedIds: SensorId[];
  /** Latest loaded dataset payload per sensor id. */
  datasets: Partial<Record<SensorId, SelectedDataset>>;
  /** Toggle a sensor in/out of the active selection. */
  toggle: (id: SensorId) => void;
  /** Whether a sensor is currently selected. */
  isSelected: (id: SensorId) => boolean;
  /** Store the latest loaded metadata for a sensor (called after a fetch). */
  registerDataset: (dataset: SelectedDataset) => void;
}

export const DatasetSelectionContext = createContext<DatasetSelectionContextValue | undefined>(undefined);

export function useDatasetSelection() {
  const context = useContext(DatasetSelectionContext);
  if (context === undefined) {
    throw new Error('useDatasetSelection must be used within a DatasetSelectionProvider');
  }
  return context;
}
