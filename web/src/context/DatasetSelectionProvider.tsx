import { useCallback, useState } from 'react';
import type { ReactNode } from 'react';
import { DatasetSelectionContext, type SelectedDataset, type SensorId } from './datasetSelectionContext';

/**
 * Phase 13.3 — shared multi-sensor selection state.
 *
 * Stores which imaging datasets are selected plus their latest metadata so
 * downstream Phase 13 workspaces can consume a single, consistent selection.
 */
export function DatasetSelectionProvider({ children }: { children: ReactNode }) {
  const [selectedIds, setSelectedIds] = useState<SensorId[]>([]);
  const [datasets, setDatasets] = useState<Partial<Record<SensorId, SelectedDataset>>>({});

  const isSelected = useCallback((id: SensorId) => selectedIds.includes(id), [selectedIds]);

  const toggle = useCallback((id: SensorId) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const registerDataset = useCallback((dataset: SelectedDataset) => {
    setDatasets((prev) => ({ ...prev, [dataset.id]: dataset }));
  }, []);

  return (
    <DatasetSelectionContext.Provider
      value={{ selectedIds, datasets, toggle, isSelected, registerDataset }}
    >
      {children}
    </DatasetSelectionContext.Provider>
  );
}
