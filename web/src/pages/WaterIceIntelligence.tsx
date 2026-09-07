import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Database, Droplets, Layers3, MapPinned } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { ApiError, fetchWaterIceOverlay, type WaterIceItemPayload, type WaterIceOverlayPayload } from '../api/client';
import { useDatasetSelection } from '../context/datasetSelectionContext';

export type WaterIceWorkspaceStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'unavailable' | 'error';

function formatConvention(convention: Record<string, string>): string {
  return Object.entries(convention)
    .map(([key, value]) => `${key}=${value}`)
    .join(' · ');
}

function provenanceNote(provenance: Record<string, unknown>): string {
  const note = provenance.note;
  return typeof note === 'string' ? note : '';
}

function statusLabel(value: string): string {
  switch (value) {
    case 'synthetic':
      return 'Synthetic / development overlay';
    case 'estimated':
      return 'Estimated';
    case 'real':
      return 'Real observation';
    case 'unknown':
    default:
      return 'Unknown status';
  }
}

function itemSummary(item: WaterIceItemPayload): string {
  const parts = [item.display_label, item.data_status];
  if (item.provenance && typeof item.provenance === 'object') {
    const note = provenanceNote(item.provenance as Record<string, unknown>);
    if (note) parts.push(note);
  }
  return parts.filter(Boolean).join(' · ');
}

export function WaterIceIntelligence() {
  const { datasets } = useDatasetSelection();
  const [status, setStatus] = useState<WaterIceWorkspaceStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<WaterIceOverlayPayload | null>(null);

  const loadWaterIceData = () => {
    let active = true;

    setStatus('loading');
    setError(null);

    fetchWaterIceOverlay()
      .then((payload: WaterIceOverlayPayload) => {
        if (!active) return;

        if (!payload || !Array.isArray(payload.items)) {
          setStatus('error');
          setError('Water-ice metadata is malformed.');
          return;
        }

        setData(payload);
        setStatus(payload.items.length === 0 ? 'empty' : 'ready');
      })
      .catch((reason: unknown) => {
        if (!active) return;
        const errorMessage = reason instanceof Error ? reason.message : 'Water-ice data is unavailable.';
        const isUnavailable = reason instanceof ApiError && reason.status === 404;
        setStatus(isUnavailable ? 'unavailable' : 'error');
        setError(errorMessage);
      });

    return () => {
      active = false;
    };
  };

  useEffect(() => {
    return loadWaterIceData();
  }, []);

  const selectedDatasetLabels = useMemo(() => {
    const values = Object.values(datasets).filter(Boolean);
    return values.length > 0 ? values.map((dataset) => dataset.displayLabel) : ['No dataset selected'];
  }, [datasets]);

  const summaryText = useMemo(() => {
    if (!data) return 'Waiting for water-ice overlay metadata.';
    return `${data.item_count} item${data.item_count === 1 ? '' : 's'} · ${data.region_count} region${data.region_count === 1 ? '' : 's'}`;
  }, [data]);

  return (
    <AppShell
      title="Water-Ice Intelligence"
      subtitle="Water-ice overlay inspection and provenance workspace"
    >
      <div className="mx-auto w-full max-w-7xl px-8 pb-16 pt-8 space-y-8">
        <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/5 px-5 py-4">
          <div className="flex items-start gap-3 text-cyan-200 text-sm font-medium leading-relaxed">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              This workspace uses only the existing frontend Water-Ice contract. No scientific confidence,
              concentration, or detection values are invented here.
            </span>
          </div>
        </div>

        <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">
                  Water-Ice Viewer
                </p>
                <p className="mt-2 text-sm text-zinc-300">
                  {data ? data.display_label : 'Waiting for Water-Ice data'}
                </p>
              </div>
              {data && (
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                  {data.data_status}
                </span>
              )}
            </div>

            {status === 'loading' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-dashed border-white/10 p-4">
                <LoadingState title="Loading" message="Loading water-ice overlay…" className="min-w-[17rem] justify-center" />
              </div>
            )}

            {status === 'unavailable' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                <ErrorState
                  title="Water-ice endpoint unavailable"
                  message={error ?? 'Water-ice data is unavailable in this build.'}
                  onRetry={loadWaterIceData}
                />
              </div>
            )}

            {status === 'error' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-red-500/30 bg-red-500/5 p-4">
                <ErrorState
                  title="Unable to load water-ice data"
                  message={error ?? 'Water-ice metadata could not be loaded.'}
                  detail="Retry to fetch the latest overlay response."
                  onRetry={loadWaterIceData}
                />
              </div>
            )}

            {status === 'empty' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.015] px-8 text-center">
                <div className="text-sm font-medium leading-relaxed text-zinc-400">
                  No water-ice regions are currently available for the selected dataset context.
                </div>
              </div>
            )}

            {status === 'ready' && data && (
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-[#0d0d10] p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                      <MapPinned className="h-3.5 w-3.5" />
                      Spatial summary
                    </div>
                    <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                      {statusLabel(data.data_status)}
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Items</div>
                      <div className="mt-2 text-xl font-semibold text-cyan-200">{data.item_count}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Regions</div>
                      <div className="mt-2 text-xl font-semibold text-cyan-200">{data.region_count}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Convention</div>
                      <div className="mt-2 text-xs text-zinc-300">{formatConvention(data.coordinate_convention)}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                    <Layers3 className="h-3.5 w-3.5" />
                    Overlay items
                  </div>
                  <div className="space-y-2">
                    {data.items.map((item) => (
                      <div key={item.water_ice_id} className="rounded-lg border border-white/10 bg-black/10 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-cyan-100">{item.display_label}</div>
                            <div className="mt-1 text-[11px] text-zinc-400">{item.water_ice_id}</div>
                          </div>
                          <span className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-cyan-200">
                            {item.data_status}
                          </span>
                        </div>
                        <div className="mt-3 text-xs text-zinc-300 leading-relaxed">
                          {itemSummary(item)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <aside className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                <Database className="h-3.5 w-3.5" />
                Selection context
              </div>

              <div className="space-y-2 text-sm text-zinc-300">
                {selectedDatasetLabels.map((label) => (
                  <div key={label} className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
                    {label}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                <Droplets className="h-3.5 w-3.5" />
                Legend & status
              </div>

              <div className="space-y-3 text-sm text-zinc-300">
                <div className="rounded-lg border border-cyan-400/20 bg-cyan-500/5 px-3 py-2">
                  <div className="font-medium text-cyan-200">Data status</div>
                  <div className="mt-1 text-xs text-zinc-300">
                    {data ? statusLabel(data.data_status) : 'Waiting for payload'}
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
                  <div className="font-medium text-zinc-200">Summary</div>
                  <div className="mt-1 text-xs text-zinc-300">{summaryText}</div>
                </div>
                {data && (
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
                    <div className="font-medium text-zinc-200">Provenance</div>
                    <div className="mt-1 text-xs text-zinc-300 leading-relaxed">
                      {provenanceNote(data.provenance) || 'No provenance note supplied by the current contract.'}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </aside>
        </section>
      </div>
    </AppShell>
  );
}
