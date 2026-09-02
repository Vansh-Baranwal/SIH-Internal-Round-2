import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CalendarRange, Database, Gauge, History } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { LoadingState } from '../components/LoadingState';
import { useDatasetSelection } from '../context/datasetSelectionContext';

export type TemporalWorkspaceStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'unavailable' | 'error';

export function TemporalChange() {
  const { selectedIds, datasets } = useDatasetSelection();
  const [status, setStatus] = useState<TemporalWorkspaceStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [beforeId, setBeforeId] = useState<string>('');
  const [afterId, setAfterId] = useState<string>('');

  useEffect(() => {
    let active = true;

    setStatus('loading');
    setError(null);

    // There is no genuine temporal-analysis API or observation pipeline in this build.
    // The workspace therefore exposes only the frontend capability seam and honest states.
    const available = selectedIds.filter((id) => Boolean(datasets[id]));

    if (!active) return;

    if (available.length < 2) {
      setStatus('empty');
      setBeforeId('');
      setAfterId('');
      setError('Select two datasets to prepare a temporal comparison pair.');
      return;
    }

    setBeforeId(available[0]);
    setAfterId(available[1]);
    setStatus('ready');

    return () => {
      active = false;
    };
  }, [datasets, selectedIds]);

  const orderedOptions = useMemo(
    () => selectedIds.filter((id) => Boolean(datasets[id])).map((id) => ({ id, label: datasets[id]?.displayLabel ?? id })),
    [datasets, selectedIds],
  );

  const beforeDataset = beforeId ? datasets[beforeId as keyof typeof datasets] : undefined;
  const afterDataset = afterId ? datasets[afterId as keyof typeof datasets] : undefined;

  return (
    <AppShell
      title="Temporal Change Analysis"
      subtitle="Observation-to-observation comparison workspace"
    >
      <div className="mx-auto w-full max-w-7xl px-8 pb-16 pt-8 space-y-8">
        <div className="rounded-2xl border border-violet-500/30 bg-violet-500/5 px-5 py-4">
          <div className="flex items-start gap-3 text-violet-200 text-sm font-medium leading-relaxed">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              This workspace is a frontend capability seam only. No genuine temporal change pipeline,
              change score, or difference map is available in this build.
            </span>
          </div>
        </div>

        <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">
                  Temporal Viewer
                </p>
                <p className="mt-2 text-sm text-zinc-300">Observation comparison area</p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                {status}
              </span>
            </div>

            {status === 'loading' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-dashed border-white/10 p-4">
                <LoadingState title="Loading" message="Preparing temporal comparison state…" className="min-w-[18rem] justify-center" />
              </div>
            )}

            {status === 'empty' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.015] px-8 text-center">
                <div className="text-sm font-medium leading-relaxed text-zinc-400">
                  {error ?? 'Select two temporal observations to enable the comparison workspace.'}
                </div>
              </div>
            )}

            {status === 'ready' && beforeDataset && afterDataset && (
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-[#0d0d10] p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                      <History className="h-3.5 w-3.5" />
                      Comparison pair
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Before</div>
                      <div className="mt-2 text-base font-medium text-violet-200">{beforeDataset.displayLabel}</div>
                      <div className="mt-1 text-xs text-zinc-400">{beforeDataset.id}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">After</div>
                      <div className="mt-2 text-base font-medium text-violet-200">{afterDataset.displayLabel}</div>
                      <div className="mt-1 text-xs text-zinc-400">{afterDataset.id}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                    <Gauge className="h-3.5 w-3.5" />
                    Comparison workspace
                  </div>
                  <div className="rounded-lg border border-dashed border-white/10 bg-black/10 p-5 text-sm leading-relaxed text-zinc-300">
                    Genuine temporal analysis results will appear here once a real backend contract is connected.
                    This area intentionally shows no fabricated change map, score, or scientific conclusion.
                  </div>
                </div>
              </div>
            )}

            {status === 'unavailable' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/5 px-8 text-center">
                <div className="text-sm font-medium leading-relaxed text-amber-200">
                  {error ?? 'Temporal data is unavailable in this build.'}
                </div>
              </div>
            )}

            {status === 'error' && (
              <div className="flex min-h-[18rem] items-center justify-center rounded-xl border border-red-500/30 bg-red-500/5 px-8 text-center">
                <div className="text-sm font-medium leading-relaxed text-red-300">
                  {error ?? 'Temporal metadata could not be loaded.'}
                </div>
              </div>
            )}
          </div>

          <aside className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                <Database className="h-3.5 w-3.5" />
                Observation selection
              </div>

              {orderedOptions.length === 0 ? (
                <div className="text-sm text-zinc-400">No observation datasets are currently selected.</div>
              ) : (
                <div className="space-y-3">
                  <label className="block text-xs uppercase tracking-[0.2em] text-zinc-500">Before</label>
                  <select
                    value={beforeId}
                    onChange={(event) => setBeforeId(event.target.value)}
                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-zinc-200"
                  >
                    {orderedOptions.map((option) => (
                      <option key={option.id} value={option.id}>{option.label}</option>
                    ))}
                  </select>

                  <label className="block text-xs uppercase tracking-[0.2em] text-zinc-500">After</label>
                  <select
                    value={afterId}
                    onChange={(event) => setAfterId(event.target.value)}
                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-zinc-200"
                  >
                    {orderedOptions.map((option) => (
                      <option key={option.id} value={option.id}>{option.label}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">
                <CalendarRange className="h-3.5 w-3.5" />
                Timeline controls
              </div>

              <div className="rounded-lg border border-dashed border-white/10 bg-black/10 px-3 py-4 text-sm text-zinc-400">
                Timestamp/date controls are not supported by the current temporal frontend contract.
                No real observation chronology is available in this build.
              </div>
            </div>
          </aside>
        </section>
      </div>
    </AppShell>
  );
}
