/**
 * Phase 15.10 — Synthetic-vs-Real Separation Validation (Frontend)
 *
 * Centralized data provenance classification system mirroring the backend registry.
 * Ensures consistent classification and auditable separation of synthetic vs real data.
 */

export enum DataProvenance {
  REAL = 'real',
  SYNTHETIC = 'synthetic',
  ESTIMATED = 'estimated',
  ILLUSTRATIVE = 'illustrative',
  DEFERRED = 'deferred',
  UNAVAILABLE = 'unavailable',
}

export interface ProvenanceMetadata {
  classification: DataProvenance;
  sourceModule: string;
  dataType: string;
  createdAt?: string;
  description: string;
  notes: string;
  isCached?: boolean;
  requiresBackendApi?: boolean;
}

export class M4DataProvenanceRegistry {
  private registry: Map<string, ProvenanceMetadata> = new Map();

  constructor() {
    this.initializeRegistry();
  }

  private initializeRegistry(): void {
    // Terrain (Phase 12.1)
    this.register({
      key: 'terrain_dem',
      classification: DataProvenance.SYNTHETIC,
      sourceModule: 'm4_12_1_terrain_foundation',
      dataType: 'DEM (Digital Elevation Model)',
      description: '3D terrain foundation for the Digital Twin viewer',
      notes: 'Current implementation uses synthetic terrain generator. Not real lunar observations.',
      requiresBackendApi: true,
    });

    // Cameras (Phase 12.3, 12.4, 12.5)
    const cameras = [
      { key: 'camera_tmc', name: 'TMC', module: 'm4_12_3_tmc_camera' },
      { key: 'camera_ohrc', name: 'OHRC', module: 'm4_12_4_ohrc_camera' },
      { key: 'camera_iirs', name: 'IIRS', module: 'm4_12_5_iirs_footprint' },
    ];

    cameras.forEach(({ key, name, module }) => {
      this.register({
        key,
        classification: DataProvenance.SYNTHETIC,
        sourceModule: module,
        dataType: `${name} Camera Metadata`,
        description: `${name} camera pose and frustum for visualization`,
        notes: `Synthetic development configuration. Not real ${name} metadata or observation.`,
        requiresBackendApi: true,
      });
    });

    // Landmarks (Phase 12.6)
    this.register({
      key: 'landmarks',
      classification: DataProvenance.SYNTHETIC,
      sourceModule: 'm4_12_6_landmark_visualization',
      dataType: 'Landmark Visualization',
      description: 'Crater landmarks for 3D Digital Twin inspection',
      notes: 'Synthetic development markers. Not real landmark detections or localizations.',
      requiresBackendApi: true,
    });

    // Hazards (Phase 12.9)
    this.register({
      key: 'hazards',
      classification: DataProvenance.SYNTHETIC,
      sourceModule: 'm4_12_9_hazard_overlay',
      dataType: 'Hazard Overlay',
      description: 'Hazard visualization overlays on 3D terrain',
      notes: 'Synthetic development hazard regions. Not real hazard detections or scientific classifications.',
      requiresBackendApi: true,
    });

    // Spectral Intelligence (Phase 12.10)
    this.register({
      key: 'spectral_overlay',
      classification: DataProvenance.SYNTHETIC,
      sourceModule: 'm4_12_10_spectral_overlay',
      dataType: 'Spectral Overlay',
      description: 'Spectral band visualization for IIRS imagery',
      notes: 'Synthetic development spectral regions. No mineral classification or spectral inference performed.',
      requiresBackendApi: true,
    });

    // Water-Ice Intelligence (Phase 12.11)
    this.register({
      key: 'water_ice_overlay',
      classification: DataProvenance.SYNTHETIC,
      sourceModule: 'm4_12_11_water_ice_overlay',
      dataType: 'Water-Ice Overlay',
      description: 'Water-ice marker visualization',
      notes: 'Synthetic development display markers. Not real water-ice detections or scientific observations.',
      requiresBackendApi: true,
    });

    // Sun Simulation (Phase 12.7, 12.8)
    [
      { key: 'sun_control', desc: 'Sun position and illumination control' },
      { key: 'counterfactual_sun', desc: 'What-if sun angle simulation' },
    ].forEach(({ key, desc }) => {
      this.register({
        key,
        classification: DataProvenance.ILLUSTRATIVE,
        sourceModule: 'm4_12_7_sun_control',
        dataType: 'Sun Simulation',
        description: desc,
        notes: 'Illustrative rendering. Not real ephemeris or observation predictions.',
      });
    });

    // Registration (Phase 13.11)
    this.register({
      key: 'registration_engine',
      classification: DataProvenance.UNAVAILABLE,
      sourceModule: 'm4_13_11_registration_cockpit',
      dataType: 'Image Registration',
      description: 'Multi-sensor image correspondence and alignment',
      notes: 'Registration engine not available in this build. No match points or RMSE values are produced.',
    });

    // Temporal Change (Phase 13)
    this.register({
      key: 'temporal_change',
      classification: DataProvenance.DEFERRED,
      sourceModule: 'm4_13_temporal_change',
      dataType: 'Temporal Change Detection',
      description: 'Multi-date temporal analysis and change maps',
      notes: 'Temporal science pipeline is deferred and not implemented. No change values are real.',
    });

    // Mission Status (Phase 13.2)
    this.register({
      key: 'mission_status',
      classification: DataProvenance.UNAVAILABLE,
      sourceModule: 'm4_13_mission_control',
      dataType: 'Mission Status',
      description: 'System status and operational overview',
      notes: 'Mission export status depends on external pipeline execution.',
      requiresBackendApi: true,
    });
  }

  private register(opts: {
    key: string;
    classification: DataProvenance;
    sourceModule: string;
    dataType: string;
    description: string;
    notes: string;
    requiresBackendApi?: boolean;
  }): void {
    this.registry.set(opts.key, {
      classification: opts.classification,
      sourceModule: opts.sourceModule,
      dataType: opts.dataType,
      description: opts.description,
      notes: opts.notes,
      requiresBackendApi: opts.requiresBackendApi ?? false,
    });
  }

  get(key: string): ProvenanceMetadata | undefined {
    return this.registry.get(key);
  }

  isSynthetic(key: string): boolean {
    const meta = this.get(key);
    return meta?.classification === DataProvenance.SYNTHETIC;
  }

  isReal(key: string): boolean {
    const meta = this.get(key);
    return meta?.classification === DataProvenance.REAL;
  }

  isAvailable(key: string): boolean {
    const meta = this.get(key);
    return (
      meta &&
      ![DataProvenance.UNAVAILABLE, DataProvenance.DEFERRED].includes(meta.classification)
    );
  }

  getAllSynthetic(): Record<string, ProvenanceMetadata> {
    const result: Record<string, ProvenanceMetadata> = {};
    this.registry.forEach((meta, key) => {
      if (meta.classification === DataProvenance.SYNTHETIC) {
        result[key] = meta;
      }
    });
    return result;
  }

  getAllReal(): Record<string, ProvenanceMetadata> {
    const result: Record<string, ProvenanceMetadata> = {};
    this.registry.forEach((meta, key) => {
      if (meta.classification === DataProvenance.REAL) {
        result[key] = meta;
      }
    });
    return result;
  }

  getAllUnavailable(): Record<string, ProvenanceMetadata> {
    const result: Record<string, ProvenanceMetadata> = {};
    this.registry.forEach((meta, key) => {
      if (meta.classification === DataProvenance.UNAVAILABLE) {
        result[key] = meta;
      }
    });
    return result;
  }

  getAllDeferred(): Record<string, ProvenanceMetadata> {
    const result: Record<string, ProvenanceMetadata> = {};
    this.registry.forEach((meta, key) => {
      if (meta.classification === DataProvenance.DEFERRED) {
        result[key] = meta;
      }
    });
    return result;
  }

  getUiLabel(classification: DataProvenance): string {
    const labels: Record<DataProvenance, string> = {
      [DataProvenance.REAL]: 'Real Authoritative Data',
      [DataProvenance.SYNTHETIC]: 'Synthetic Development Data',
      [DataProvenance.ESTIMATED]: 'Model Estimated Data',
      [DataProvenance.ILLUSTRATIVE]: 'Illustrative Example',
      [DataProvenance.DEFERRED]: 'Deferred / Unimplemented',
      [DataProvenance.UNAVAILABLE]: 'Unavailable / Missing',
    };
    return labels[classification] ?? 'Unknown';
  }

  auditReport(): string {
    const synthetic = this.getAllSynthetic();
    const real = this.getAllReal();
    const unavailable = this.getAllUnavailable();
    const deferred = this.getAllDeferred();

    const lines = [
      'M4 Data Provenance Audit Report',
      '='.repeat(60),
      '',
      'REGISTRY SUMMARY',
      `Total entries: ${this.registry.size}`,
      `Synthetic: ${Object.keys(synthetic).length}`,
      `Real: ${Object.keys(real).length}`,
      `Unavailable: ${Object.keys(unavailable).length}`,
      `Deferred: ${Object.keys(deferred).length}`,
      '',
      'SYNTHETIC OUTPUTS (May NOT be presented as real)',
      '-'.repeat(60),
    ];

    Object.entries(synthetic).forEach(([key, meta]) => {
      lines.push(`  ${key}: ${meta.dataType} (${meta.sourceModule})`);
      lines.push(`    Note: ${meta.notes}`);
    });

    lines.push('');
    lines.push('REAL OUTPUTS (May be presented as authoritative)');
    lines.push('-'.repeat(60));

    if (Object.keys(real).length > 0) {
      Object.entries(real).forEach(([key, meta]) => {
        lines.push(`  ${key}: ${meta.dataType} (${meta.sourceModule})`);
      });
    } else {
      lines.push('  (None currently available)');
    }

    lines.push('');
    lines.push('UNAVAILABLE OUTPUTS (Will not be presented)');
    lines.push('-'.repeat(60));

    Object.entries(unavailable).forEach(([key, meta]) => {
      lines.push(`  ${key}: ${meta.dataType}`);
      lines.push(`    ${meta.notes}`);
    });

    lines.push('');
    lines.push('DEFERRED OUTPUTS (Will not be presented as real)');
    lines.push('-'.repeat(60));

    Object.entries(deferred).forEach(([key, meta]) => {
      lines.push(`  ${key}: ${meta.dataType}`);
      lines.push(`    ${meta.notes}`);
    });

    lines.push('');

    return lines.join('\n');
  }
}

// Global registry instance
let globalRegistry: M4DataProvenanceRegistry | null = null;

export function getProvenanceRegistry(): M4DataProvenanceRegistry {
  if (!globalRegistry) {
    globalRegistry = new M4DataProvenanceRegistry();
  }
  return globalRegistry;
}

/**
 * Utility to validate that a data status string from the API matches
 * the registered classification for that output.
 *
 * This acts as a guard to catch accidental mislabeling.
 */
export function validateDataStatus(
  registryKey: string,
  apiStatus: string | undefined
): boolean {
  const registry = getProvenanceRegistry();
  const meta = registry.get(registryKey);
  if (!meta) return true; // Unknown keys pass through

  // Map API data_status values to provenance classifications
  const statusToProvenance: Record<string, DataProvenance> = {
    synthetic: DataProvenance.SYNTHETIC,
    real: DataProvenance.REAL,
    estimated: DataProvenance.ESTIMATED,
    unknown: DataProvenance.DEFERRED,
  };

  const mappedStatus = statusToProvenance[apiStatus?.toLowerCase() ?? ''];
  if (!mappedStatus) return false;

  return mappedStatus === meta.classification;
}
