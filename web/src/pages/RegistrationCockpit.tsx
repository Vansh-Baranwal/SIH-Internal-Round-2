import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Loader2, ScanLine, CheckCircle2 } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import {
  MatchPointVisualization,
  type MatchPointVisualizationStatus,
  type MatchPointPair,
} from '../components/MatchPointVisualization';
import {
  RegistrationMetricsPanel,
  type RegistrationMetricsData,
  type RegistrationMetricsStatus,
} from '../components/RegistrationMetricsPanel';
import { useDatasetSelection, type SensorId, type SelectedDataset } from '../context/datasetSelectionContext';
import {
  getRegistrationCapability,
  submitRegistration,
  type RegistrationMatchData,
} from '../api/registration';

type RegistrationState = 'idle' | 'submitting' | 'success' | 'unavailable' | 'error';

function datasetLabel(dataset: SelectedDataset): string {
  return `${dataset.label} — ${dataset.displayLabel}`;
}

export function RegistrationCockpit() {
  const { selectedIds, datasets } = useDatasetSelection();
  const capability = getRegistrationCapability();

  const [source, setSource] = useState<SensorId | null>(null);
  const [reference, setReference] = useState<SensorId | null>(null);
  const [state, setState] = useState<RegistrationState>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [matchPairs, setMatchPairs] = useState<MatchPointPair[]>([]);
  const [matchStatus, setMatchStatus] = useState<MatchPointVisualizationStatus>(
    capability.available ? 'empty' : 'unavailable',
  );
  const [metrics, setMetrics] = useState<RegistrationMetricsData | null>(null);
  const [metricsStatus, setMetricsStatus] = useState<RegistrationMetricsStatus>(
    capability.available ? 'empty' : 'unavailable',
  );

  const available = useMemo(
    () =>
      selectedIds
        .map((id) => datasets[id])
        .filter((dataset): dataset is SelectedDataset => dataset != null),
    [selectedIds, datasets],
  );

  useEffect(() => {
    if (source === null && available.length > 0) setSource(available[0].id);
  }, [available, source]);

  useEffect(() => {
    if (reference === null && available.length > 1) {
      const candidate = available.find((dataset) => dataset.id !== source);
      if (candidate) setReference(candidate.id);
    }
  }, [available, source, reference]);

  const canRegister = source !== null && reference !== null && source !== reference;

  async function onRegister() {
    if (!canRegister || !source || !reference) return;
    setState('submitting');
    setMessage(null);
    const outcome = await submitRegistration({ sourceSensor: source, referenceSensor: reference });
    if (outcome.status === 'success') {
      setState('success');
      setMessage('Registration completed.');
      applyMatchData(outcome.matches ?? null);
      setMetrics(outcome.metrics as RegistrationMetricsData | null);
      setMetricsStatus('ready');
    } else if (outcome.status === 'error') {
      setState('error');
      setMessage(outcome.message);
      setMatchStatus('error');
      setMatchPairs([]);
      setMetricsStatus('error');
      setMetrics(null);
    } else {
      setState('unavailable');
      setMessage(outcome.message);
      setMatchStatus('unavailable');
      setMatchPairs([]);
      setMetricsStatus('unavailable');
      setMetrics(null);
    }
  }

  const sourceDataset = source ? datasets[source] : undefined;
  const referenceDataset = reference ? datasets[reference] : undefined;

  useEffect(() => {
    if (!capability.available) {
      setMatchPairs([]);
      setMatchStatus('unavailable');
      setMetrics(null);
      setMetricsStatus('unavailable');
      return;
    }

    const hasSelection = sourceDataset && referenceDataset && source !== reference;
    if (!hasSelection) {
      setMatchPairs([]);
      setMatchStatus('empty');
      setMetrics(null);
      setMetricsStatus('empty');
      return;
    }

    setMatchPairs([]);
    setMatchStatus('empty');
    setMetrics(null);
    setMetricsStatus('empty');
  }, [capability.available, sourceDataset, referenceDataset, source, reference]);

  function applyMatchData(matchData: RegistrationMatchData | null | undefined) {
    if (!matchData || matchData.pairs.length === 0) {
      setMatchPairs([]);
      setMatchStatus('empty');
      return;
    }

    setMatchPairs(matchData.pairs as MatchPointPair[]);
    setMatchStatus('ready');
  }

  return (
    <AppShell title="Registration Cockpit" subtitle="Set up and initiate multi-sensor image registration">
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-8">
        {/* Engine capability */}
        <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 px-5 py-4">
          <AlertTriangle className="w-5 h-5 text-amber-300 shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-200 font-bold uppercase tracking-widest text-[10px] mb-1">
              Correspondence engine unavailable
            </p>
            <p className="text-zinc-300 text-sm font-medium leading-relaxed">{capability.reason}</p>
          </div>
        </div>

        {/* Source / Reference dataset selection */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Dataset Selection
          </h2>
          {available.length < 2 ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-6">
              <p className="text-zinc-400 text-sm font-medium leading-relaxed mb-3">
                Select at least two datasets in the Multi-Sensor workspace to define the source and
                reference inputs for registration.
              </p>
              <Link
                to="/sensors"
                className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-black bg-white hover:bg-zinc-200 px-3 py-1.5 rounded-lg"
              >
                Open Sensor Data <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <DatasetPicker
                label="Source"
                value={source}
                datasets={available}
                onChange={setSource}
              />
              <DatasetPicker
                label="Reference"
                value={reference}
                datasets={available}
                onChange={setReference}
              />
            </div>
          )}
          {source !== null && source === reference && (
            <p className="mt-2 text-red-300 text-xs font-medium">Source and Reference must differ.</p>
          )}
        </section>

        {/* Selected source/reference summary */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Selected Datasets
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-5">
              <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-2">Source</p>
              {sourceDataset ? (
                <DatasetSummary dataset={sourceDataset} />
              ) : (
                <p className="text-zinc-500 text-sm">None selected</p>
              )}
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-5">
              <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-2">Reference</p>
              {referenceDataset ? (
                <DatasetSummary dataset={referenceDataset} />
              ) : (
                <p className="text-zinc-500 text-sm">None selected</p>
              )}
            </div>
          </div>
        </section>

        {/* Two-image / viewer workspace placeholder */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Registration Workspace
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ViewerPane
              label="Source"
              dataset={sourceDataset}
              status={matchStatus}
              matchPairs={matchPairs}
              sourceLabel="Source"
              referenceLabel="Reference"
            />
            <ViewerPane
              label="Reference"
              dataset={referenceDataset}
              status={matchStatus}
              matchPairs={matchPairs}
              sourceLabel="Source"
              referenceLabel="Reference"
            />
          </div>
          <p className="mt-3 text-zinc-600 text-xs font-medium">
            This workspace is prepared for a side-by-side image viewer. Genuine correspondence data
            and registration metrics are not available in this build until the engine is connected.
          </p>
        </section>

        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Registration Metrics
          </h2>
          <RegistrationMetricsPanel metrics={metrics} status={metricsStatus} />
        </section>

        {/* Registration action */}
        <section className="space-y-3">
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold">Registration</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={onRegister}
              disabled={!canRegister || state === 'submitting'}
              className={`rounded-lg px-5 py-3 text-[12px] font-bold uppercase tracking-widest transition-colors ${
                canRegister
                  ? 'bg-white text-black hover:bg-zinc-200'
                  : 'bg-white/5 text-zinc-500 cursor-not-allowed'
              }`}
            >
              {state === 'submitting' ? 'Submitting…' : 'Register'}
            </button>
            {state === 'submitting' && <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />}
          </div>
          {message && (
            <div
              className={`rounded-xl border px-4 py-3 text-sm font-medium leading-relaxed ${
                state === 'success'
                  ? 'border-green-500/30 bg-green-500/5 text-green-300'
                  : state === 'error'
                    ? 'border-red-500/30 bg-red-500/5 text-red-300'
                    : 'border-amber-500/30 bg-amber-500/5 text-amber-200'
              }`}
            >
              {state === 'success' ? (
                <span className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" /> {message}
                </span>
              ) : (
                message
              )}
            </div>
          )}
          {!canRegister && (
            <p className="text-zinc-500 text-xs font-medium">
              Register is disabled until both a source and a different reference dataset are selected.
            </p>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function DatasetPicker({
  label,
  value,
  datasets,
  onChange,
}: {
  label: string;
  value: SensorId | null;
  datasets: SelectedDataset[];
  onChange: (id: SensorId) => void;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-5">
      <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-2">{label}</p>
      <select
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value as SensorId)}
        className="w-full bg-transparent border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-200 font-medium focus:outline-none focus:border-white/30"
      >
        <option value="" disabled className="bg-zinc-900">
          Select dataset
        </option>
        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id} className="bg-zinc-900">
            {datasetLabel(dataset)}
          </option>
        ))}
      </select>
    </div>
  );
}

function DatasetSummary({ dataset }: { dataset: SelectedDataset }) {
  const convention = Object.entries(dataset.coordinateConvention)
    .map(([key, value]) => `${key}=${value}`)
    .join(' · ');
  const isSynthetic = dataset.dataStatus === 'synthetic';

  return (
    <div className="space-y-1.5 text-xs">
      <p className="text-zinc-300 font-semibold">{dataset.displayLabel}</p>
      {isSynthetic && <p className="text-amber-300/90 font-semibold">Synthetic / Development</p>}
      <p className="text-zinc-500">{convention}</p>
    </div>
  );
}

function ViewerPane({
  label,
  dataset,
  status,
  matchPairs,
  sourceLabel,
  referenceLabel,
}: {
  label: string;
  dataset: SelectedDataset | undefined;
  status: MatchPointVisualizationStatus;
  matchPairs: MatchPointPair[];
  sourceLabel: string;
  referenceLabel: string;
}) {
  const shouldShowMatches = status !== 'unavailable' && status !== 'loading' && status !== 'error';

  return (
    <div className="space-y-3 rounded-2xl border border-dashed border-white/15 bg-white/[0.01] p-3">
      <div className="min-h-[16rem] flex items-center justify-center rounded-xl border border-white/10 bg-[#0a0a0a]">
        <div className="text-center px-6">
          <ScanLine className="w-6 h-6 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm font-bold uppercase tracking-widest">{label}</p>
          <p className="text-zinc-600 text-xs font-medium mt-1">
            {dataset ? dataset.displayLabel : 'No dataset selected'}
          </p>
        </div>
      </div>
      {shouldShowMatches && (
        <MatchPointVisualization
          pairs={matchPairs}
          status={status}
          sourceLabel={sourceLabel}
          referenceLabel={referenceLabel}
          emptyMessage={
            dataset
              ? `No match points are available for ${dataset.displayLabel} yet.`
              : 'No match points are available for the current selection.'
          }
          unavailableMessage="Correspondence match points are unavailable in this build."
        />
      )}
      {!shouldShowMatches && status === 'unavailable' && (
        <MatchPointVisualization
          pairs={[]}
          status="unavailable"
          sourceLabel={sourceLabel}
          referenceLabel={referenceLabel}
        />
      )}
      {!shouldShowMatches && status === 'error' && (
        <MatchPointVisualization
          pairs={[]}
          status="error"
          sourceLabel={sourceLabel}
          referenceLabel={referenceLabel}
        />
      )}
    </div>
  );
}
