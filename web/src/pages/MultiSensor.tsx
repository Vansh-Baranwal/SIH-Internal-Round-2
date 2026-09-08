import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, AlertTriangle, ScanLine } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { SENSOR_OPTIONS, loadSensorDataset } from '../sensors/sensors';
import { useDatasetSelection, type SelectedDataset, type SensorId } from '../context/datasetSelectionContext';
import { useMission } from '../context/useMission';

interface LoadState {
  loading: boolean;
  error: string | null;
}

function formatConvention(convention: Record<string, string>): string {
  return Object.entries(convention)
    .map(([key, value]) => `${key}=${value}`)
    .join(' · ');
}

function formatPosition(position: unknown): string {
  if (typeof position !== 'object' || position === null) return '—';
  const p = position as { x?: number; y?: number; z?: number };
  return `x ${p.x ?? 0}, y ${p.y ?? 0}, z ${p.z ?? 0}`;
}

function provenanceNote(provenance: Record<string, unknown>): string {
  const note = provenance.note;
  return typeof note === 'string' ? note : '';
}

export function MultiSensor() {
  const { datasets, toggle, isSelected, registerDataset } = useDatasetSelection();
  const { hasData, datasetLabel } = useMission();
  const [loadState, setLoadState] = useState<Partial<Record<SensorId, LoadState>>>({});

  useEffect(() => {
    let cancelled = false;
    for (const sensor of SENSOR_OPTIONS) {
      setLoadState((prev) => ({ ...prev, [sensor.id]: { loading: true, error: null } }));
      loadSensorDataset(sensor.id)
        .then((dataset) => {
          if (!cancelled) {
            registerDataset(dataset);
            setLoadState((prev) => ({ ...prev, [sensor.id]: { loading: false, error: null } }));
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setLoadState((prev) => ({
              ...prev,
              [sensor.id]: {
                loading: false,
                error: err instanceof Error ? err.message : 'Unavailable',
              },
            }));
          }
        });
    }
    return () => {
      cancelled = true;
    };
  }, [registerDataset]);

  return (
    <AppShell title="Multi-Sensor Data Selection" subtitle="Choose datasets for downstream multi-sensor workspaces">
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-8">
        <div className="flex items-center gap-2 text-[11px] font-semibold text-zinc-500">
          <span className="uppercase tracking-widest">Mission Dataset:</span>
          <span className="text-zinc-300">{hasData ? datasetLabel : 'No dataset processed'}</span>
        </div>

        <p className="text-zinc-500 text-sm font-medium max-w-3xl">
          Select one or more imaging sensors to define the active dataset set. Selections are
          shared so later registration, spectral and Water-Ice workspaces can consume them.
        </p>


        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {SENSOR_OPTIONS.map((sensor) => {
            const dataset = datasets[sensor.id];
            const state = loadState[sensor.id];
            const selected = isSelected(sensor.id);
            const unavailable = state?.error != null && !state?.loading;

            return (
              <div
                key={sensor.id}
                className={`rounded-2xl border p-6 bg-white/[0.015] backdrop-blur transition-colors ${
                  selected ? 'border-white/30 ring-1 ring-white/10' : 'border-white/10'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-white/10 bg-white/[0.03]">
                      <ScanLine className="w-4 h-4 text-zinc-300" />
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-tight">{sensor.label}</h3>
                      <p className="text-zinc-500 text-[11px] font-medium">{sensor.description}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => toggle(sensor.id)}
                    disabled={unavailable}
                    className={`shrink-0 rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors ${
                      selected
                        ? 'bg-white text-black'
                        : 'bg-white/5 text-zinc-300 hover:bg-white/10'
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {selected ? 'Selected' : 'Select'}
                  </button>
                </div>

                <div className="mb-3 space-y-1.5 text-[11px] font-semibold">
                  <div className="flex items-center gap-2">
                    {state?.loading ? (
                      <span className="flex items-center gap-1.5 text-zinc-400">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
                      </span>
                    ) : unavailable ? (
                      <span className="flex items-center gap-1.5 text-red-300">
                        <AlertTriangle className="w-3.5 h-3.5" /> Unavailable
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-green-400">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Available
                      </span>
                    )}
                  </div>
                  {selected && state?.error && <p className="text-red-300/80">{state.error}</p>}
                </div>

                {selected && dataset && <SensorMetadata dataset={dataset} />}
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}

function SensorMetadata({ dataset }: { dataset: SelectedDataset }) {
  const metadata = dataset.metadata;
  const convention = formatConvention(dataset.coordinateConvention);
  const note = provenanceNote(dataset.provenance);
  const isSynthetic = dataset.dataStatus === 'synthetic';
  const camera = (metadata.camera ?? {}) as { position_m?: unknown; target_m?: unknown };
  const position = metadata.position_m ?? camera.position_m;
  const target = metadata.target_m ?? camera.target_m;

  return (
    <div className="border-t border-white/5 pt-3 space-y-2 text-xs">
      <Row label="Label" value={dataset.displayLabel} />
      {isSynthetic && <Row label="Provenance" value="Synthetic / Development" />}
      <Row label="Convention" value={convention} />
      <Row label="Position" value={formatPosition(position)} />
      <Row label="Target" value={formatPosition(target)} />
      <Row
        label="Sensor Type"
        value={typeof metadata.sensor_type === 'string' ? metadata.sensor_type : '—'}
      />
      {note && <p className="text-zinc-600 leading-relaxed">{note}</p>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-zinc-500 font-bold uppercase tracking-widest text-[9px]">{label}</span>
      <span className="text-zinc-300 font-medium text-right">{value}</span>
    </div>
  );
}


