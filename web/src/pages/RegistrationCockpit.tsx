import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Loader2, MapPinned, ScanLine } from 'lucide-react';
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
  submitPhase11Localization,
  type Phase11ApiResponse,
  type Phase11DataProvenance,
  type Phase11ImageReferenceType,
} from '../api/registration';
import { ApiError } from '../api/client';

type RegistrationState = 'idle' | 'submitting' | 'response' | 'error';

function datasetLabel(dataset: SelectedDataset): string {
  return `${dataset.label} — ${dataset.displayLabel}`;
}

export function RegistrationCockpit() {
  const { selectedIds, datasets } = useDatasetSelection();
  const capability = getRegistrationCapability();

  const [source, setSource] = useState<SensorId | null>(null);
  const [reference, setReference] = useState<SensorId | null>(null);
  const [validationRequestId, setValidationRequestId] = useState('');
  const [imageReference, setImageReference] = useState('');
  const [provenanceSource, setProvenanceSource] = useState('');
  const [imageReferenceType, setImageReferenceType] = useState<Phase11ImageReferenceType>('unknown');
  const [provenance, setProvenance] = useState<Phase11DataProvenance>('unavailable');
  const [isRealData, setIsRealData] = useState(false);
  const [validationStatus, setValidationStatus] = useState('unvalidated');
  const [state, setState] = useState<RegistrationState>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [response, setResponse] = useState<Phase11ApiResponse | null>(null);
  const [matchPairs, setMatchPairs] = useState<MatchPointPair[]>([]);
  const [metrics, setMetrics] = useState<RegistrationMetricsData | null>(null);

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

  const sourceDataset = source ? datasets[source] : undefined;
  const referenceDataset = reference ? datasets[reference] : undefined;
  const canSubmitPhase11 = Boolean(sourceDataset && validationRequestId.trim() && imageReference.trim() && provenanceSource.trim());
  const matchStatus: MatchPointVisualizationStatus =
    state === 'submitting' ? 'loading' : state === 'error' ? 'error' : 'unavailable';
  const metricsStatus: RegistrationMetricsStatus =
    state === 'submitting' ? 'loading' : state === 'error' ? 'error' : 'unavailable';
  const metricsUnavailableMessage =
    response?.status.toUpperCase() === 'BLOCKED'
      ? 'Registration metrics unavailable — Phase 11 is currently BLOCKED.'
      : 'Registration metrics unavailable from the current Phase 11 response.';

  async function onRegister() {
    if (!canSubmitPhase11 || !sourceDataset) return;
    setState('submitting');
    setMessage(null);
    setResponse(null);
    setMatchPairs([]);
    setMetrics(null);
    try {
      const phase11Response = await submitPhase11Localization({
        validation_request_id: validationRequestId.trim(),
        image: {
          image_id: sourceDataset.id,
          image_reference: imageReference.trim(),
          provenance_source: provenanceSource.trim(),
          image_reference_type: imageReferenceType,
          provenance,
          is_real_data: isRealData,
          validation_status: validationStatus,
        },
      });
      setResponse(phase11Response);
      setState('response');
      setMessage(null);
    } catch (error: unknown) {
      setState('error');
      setMetrics(null);
      setMatchPairs([]);
      if (error instanceof ApiError) {
        setMessage(
          error.kind === 'network'
            ? 'Unable to reach the Phase 11 backend.'
            : error.kind === 'response'
              ? 'Phase 11 returned an invalid response.'
              : 'The Phase 11 request failed.',
        );
      } else {
        setMessage('The Phase 11 request failed.');
      }
    }
  }

  useEffect(() => {
    if (!capability.available) {
      setMatchPairs([]);
      setMetrics(null);
      return;
    }

    const hasSelection = sourceDataset && referenceDataset && source !== reference;
    if (!hasSelection) {
      setMatchPairs([]);
      setMetrics(null);
      return;
    }

    setMatchPairs([]);
    setMetrics(null);
  }, [capability.available, sourceDataset, referenceDataset, source, reference]);

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

        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Phase 11 Request
          </h2>
          <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <TextField label="Validation Request ID" value={validationRequestId} onChange={setValidationRequestId} placeholder="validation-request-001" />
              <TextField label="Image Reference" value={imageReference} onChange={setImageReference} placeholder="Path or external reference" />
              <TextField label="Provenance Source" value={provenanceSource} onChange={setProvenanceSource} placeholder="Dataset or mission source" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <SelectField label="Image Reference Type" value={imageReferenceType} onChange={(value) => setImageReferenceType(value as Phase11ImageReferenceType)} options={['local_available', 'external_reference', 'local_missing', 'unavailable', 'unknown', 'invalid']} />
              <SelectField label="Provenance" value={provenance} onChange={(value) => setProvenance(value as Phase11DataProvenance)} options={['real', 'synthetic', 'estimated', 'illustrative', 'deferred', 'unavailable']} />
              <SelectField label="Validation Status" value={validationStatus} onChange={setValidationStatus} options={['unvalidated', 'pending', 'validated', 'rejected']} />
            </div>
            <label className="inline-flex items-center gap-2 text-xs text-zinc-300 font-medium">
              <input type="checkbox" checked={isRealData} onChange={(event) => setIsRealData(event.target.checked)} />
              Mark image as real data
            </label>
            <p className="text-xs text-zinc-500">
              Image ID sent to Phase 11: {sourceDataset?.id ?? 'Select a source dataset'}
            </p>
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
          <RegistrationMetricsPanel
            metrics={metrics}
            status={metricsStatus}
            unavailableMessage={metricsUnavailableMessage}
          />
        </section>

        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Localization
          </h2>
          <Phase11LocalizationPanel state={state} response={response} />
        </section>

        {/* Registration action */}
        <section className="space-y-3">
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold">Registration</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={onRegister}
              disabled={!canSubmitPhase11 || state === 'submitting'}
              className={`rounded-lg px-5 py-3 text-[12px] font-bold uppercase tracking-widest transition-colors ${
                canSubmitPhase11
                  ? 'bg-white text-black hover:bg-zinc-200'
                  : 'bg-white/5 text-zinc-500 cursor-not-allowed'
              }`}
            >
              {state === 'submitting' ? 'Submitting...' : 'Submit Phase 11'}
            </button>
            {state === 'submitting' && <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />}
          </div>
          {message && (
            <div
              className={`rounded-xl border px-4 py-3 text-sm font-medium leading-relaxed ${
                state === 'error'
                    ? 'border-red-500/30 bg-red-500/5 text-red-300'
                    : 'border-amber-500/30 bg-amber-500/5 text-amber-200'
              }`}
            >
              {message}
            </div>
          )}
          {state === 'submitting' && (
            <p className="text-zinc-400 text-xs font-medium">Submitting Phase 11 localization request...</p>
          )}
          {!canSubmitPhase11 && (
            <p className="text-zinc-500 text-xs font-medium">
              Submit is disabled until a source dataset and all required Phase 11 request fields are provided.
            </p>
          )}
        </section>

        {response && <Phase11ResponsePanel response={response} />}
      </div>
    </AppShell>
  );
}

function formatResponseValue(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value === null || value === undefined) return 'null';
  try {
    return JSON.stringify(value);
  } catch {
    return '[unrenderable value]';
  }
}

function StageSummary({ label, stage }: { label: string; stage: { status: string; result: Record<string, unknown> } }) {
  const resultEntries = Object.entries(stage.result);
  return (
    <div className="rounded-xl border border-white/10 bg-[#0d0d10] p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold">{label}</p>
        <span className="text-xs text-zinc-200 font-semibold">{stage.status}</span>
      </div>
      {resultEntries.length > 0 ? (
        <div className="space-y-1.5">
          {resultEntries.map(([key, value]) => (
            <div key={key} className="grid grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] gap-3 text-xs">
              <span className="text-zinc-500 break-words">{key}</span>
              <span className="text-zinc-300 break-words">{formatResponseValue(value)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-zinc-500">No stage result fields returned.</p>
      )}
    </div>
  );
}

function ResponseList({ title, items, tone }: { title: string; items: string[]; tone: 'warning' | 'limitation' }) {
  const color = tone === 'warning' ? 'text-amber-200 border-amber-500/30 bg-amber-500/5' : 'text-orange-200 border-orange-500/30 bg-orange-500/5';
  return (
    <div className={`rounded-xl border p-4 ${color}`}>
      <p className="text-[10px] uppercase tracking-[0.25em] font-bold mb-2">{title}</p>
      {items.length > 0 ? <ul className="space-y-1 text-xs leading-relaxed">{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul> : <p className="text-xs opacity-80">None returned.</p>}
    </div>
  );
}

function Phase11LocalizationPanel({
  state,
  response,
}: {
  state: RegistrationState;
  response: Phase11ApiResponse | null;
}) {
  if (state === 'submitting') {
    return (
      <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/5 px-4 py-5">
        <div className="flex items-start gap-3 text-cyan-200 text-sm font-medium leading-relaxed">
          <Loader2 className="w-4 h-4 shrink-0 mt-0.5 animate-spin" />
          <span>Waiting for the Phase 11 localization result...</span>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 px-4 py-5">
        <div className="flex items-start gap-3 text-red-300 text-sm font-medium leading-relaxed">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>Localization unavailable because the Phase 11 request failed.</span>
        </div>
      </div>
    );
  }

  if (!response || response.localization === null) {
    const message = response?.status.toUpperCase() === 'BLOCKED'
      ? 'Localization unavailable — Phase 11 is currently BLOCKED.'
      : 'Localization result is not currently available from Phase 11.';
    return (
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-4 py-5">
        <div className="flex items-start gap-3 text-amber-200 text-sm font-medium leading-relaxed">
          <MapPinned className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{message}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
      <div className="flex items-center gap-2 text-zinc-300 mb-3">
        <MapPinned className="w-4 h-4 text-cyan-300" />
        <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-500">
          Backend Localization Result
        </span>
      </div>
      <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words">
        {formatResponseValue(response.localization)}
      </pre>
    </div>
  );
}

function Phase11ResponsePanel({ response }: { response: Phase11ApiResponse }) {
  const isBlocked = response.status.toUpperCase() === 'BLOCKED';
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold">Phase 11 Response</h2>
        <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-widest font-bold ${isBlocked ? 'border-amber-500/40 text-amber-200 bg-amber-500/10' : 'border-cyan-500/30 text-cyan-200 bg-cyan-500/10'}`}>
          {response.status}
        </span>
      </div>
      <div className={`rounded-xl border px-4 py-3 text-sm font-medium ${isBlocked ? 'border-amber-500/30 bg-amber-500/5 text-amber-200' : 'border-cyan-500/30 bg-cyan-500/5 text-cyan-200'}`}>
        {isBlocked ? 'The Phase 11 request completed, but the scientific pipeline is blocked.' : `Phase 11 returned backend status: ${response.status}`}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-white/[0.015] p-4 text-xs space-y-2">
          <p><span className="text-zinc-500">validation_request_id:</span> <span className="text-zinc-200">{response.validation_request_id}</span></p>
          <p><span className="text-zinc-500">source_image_id:</span> <span className="text-zinc-200">{response.source_image_id}</span></p>
          <p className="text-zinc-500">This identifier is not a registration ID.</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.015] p-4">
          <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-2">Provenance</p>
          <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{formatResponseValue(response.provenance)}</pre>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StageSummary label="Metadata Quality" stage={response.metadata_quality} />
        <StageSummary label="Landmark Retrieval" stage={response.landmark_retrieval} />
      </div>
      <div className="rounded-xl border border-white/10 bg-white/[0.015] p-4">
        <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-3">Downstream Statuses</p>
        <div className="space-y-2 text-xs">
          {Object.entries(response.downstream_statuses).map(([stage, status]) => (
            <div key={stage} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3"><span className="text-zinc-500 break-words">{stage}</span><span className="text-zinc-300 break-words">{status ?? 'null'}</span></div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ResponseList title="Warnings" items={response.warnings} tone="warning" />
        <ResponseList title="Limitations" items={response.limitations} tone="limitation" />
      </div>
      <div className="rounded-xl border border-white/10 bg-white/[0.015] p-4">
        <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-2">Final Validation</p>
        <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{response.final_validation === null ? 'Not available from this Phase 11 response.' : formatResponseValue(response.final_validation)}</pre>
      </div>
      <p className="text-xs text-zinc-500">Localization is rendered only from the Phase 11 localization response field. Metadata coordinates, landmarks, match points, and registration metrics are not used as localization.</p>
    </section>
  );
}

function TextField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="space-y-2 block">
      <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full bg-transparent border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-white/30" />
    </label>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <label className="space-y-2 block">
      <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full bg-transparent border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-white/30">
        {options.map((option) => <option key={option} value={option} className="bg-zinc-900">{option}</option>)}
      </select>
    </label>
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
          unavailableMessage="Match-point data is not available from the current Phase 11 response."
        />
      )}
      {!shouldShowMatches && status === 'unavailable' && (
        <MatchPointVisualization
          pairs={[]}
          status="unavailable"
          sourceLabel={sourceLabel}
          referenceLabel={referenceLabel}
          unavailableMessage="Match-point data is not available from the current Phase 11 response."
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
