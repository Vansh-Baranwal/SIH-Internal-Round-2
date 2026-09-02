import { fetchTmcCamera, fetchOhrcCamera, fetchIirsFootprint } from '../api/client';
import type { SensorId, SelectedDataset } from '../context/datasetSelectionContext';

export interface SensorOption {
  id: SensorId;
  label: string;
  description: string;
}

export const SENSOR_OPTIONS: SensorOption[] = [
  { id: 'tmc', label: 'TMC', description: 'Terrain Mapping Camera — imaging sensor' },
  { id: 'ohrc', label: 'OHRC', description: 'Orbiter High Resolution Camera — imaging sensor' },
  { id: 'iirs', label: 'IIRS', description: 'Imaging Infrared Spectrometer — imaging sensor' },
];

async function loadTmc(): Promise<SelectedDataset> {
  const payload = await fetchTmcCamera();
  return {
    id: 'tmc',
    label: 'TMC',
    displayLabel: payload.display_label,
    dataStatus: payload.data_status,
    coordinateConvention: payload.coordinate_convention,
    metadata: {
      position_m: payload.position_m,
      target_m: payload.target_m,
      vertical_fov_degrees: payload.vertical_fov_degrees,
      aspect_ratio: payload.aspect_ratio,
      near_m: payload.near_m,
      far_m: payload.far_m,
    },
    provenance: payload.provenance,
  };
}

async function loadOhrc(): Promise<SelectedDataset> {
  const payload = await fetchOhrcCamera();
  return {
    id: 'ohrc',
    label: 'OHRC',
    displayLabel: payload.display_label,
    dataStatus: payload.data_status,
    coordinateConvention: payload.coordinate_convention,
    metadata: {
      position_m: payload.position_m,
      target_m: payload.target_m,
      vertical_fov_degrees: payload.vertical_fov_degrees,
      aspect_ratio: payload.aspect_ratio,
      near_m: payload.near_m,
      far_m: payload.far_m,
    },
    provenance: payload.provenance,
  };
}

async function loadIirs(): Promise<SelectedDataset> {
  const payload = await fetchIirsFootprint();
  return {
    id: 'iirs',
    label: 'IIRS',
    displayLabel: payload.display_label,
    dataStatus: payload.data_status,
    coordinateConvention: payload.coordinate_convention,
    metadata: {
      sensor_type: payload.sensor_type,
      camera: payload.camera,
      footprint: payload.footprint,
    },
    provenance: payload.provenance,
  };
}

/** Fetch the metadata for a given sensor and normalize it to a SelectedDataset. */
export function loadSensorDataset(id: SensorId): Promise<SelectedDataset> {
  if (id === 'tmc') return loadTmc();
  if (id === 'ohrc') return loadOhrc();
  return loadIirs();
}
