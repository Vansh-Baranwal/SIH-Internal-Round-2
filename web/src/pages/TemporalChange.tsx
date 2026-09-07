import { useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, Database, Loader2, ShieldCheck } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { ApiError } from '../api/client';
import { submitPhase10PairSelection, type Phase10ObservationRequest, type Phase10PairSelectionResponse } from '../api/temporal';

type WorkspaceState = 'idle' | 'loading' | 'success' | 'error';
type Provenance = NonNullable<Phase10ObservationRequest['provenance']>;
interface ObservationForm { observation_id: string; source: string; image_reference: string; acquisition_timestamp: string; provenance_source: string; provenance: Provenance; is_real_data: boolean; crs: string; }

const emptyObservation = (): ObservationForm => ({ observation_id: '', source: '', image_reference: '', acquisition_timestamp: '', provenance_source: '', provenance: 'unavailable', is_real_data: false, crs: '' });
function toRequest(value: ObservationForm): Phase10ObservationRequest { return { observation_id: value.observation_id.trim(), source: value.source.trim(), image_reference: value.image_reference.trim(), acquisition_timestamp: value.acquisition_timestamp.trim() || null, provenance_source: value.provenance_source.trim(), provenance: value.provenance, is_real_data: value.is_real_data, crs: value.crs.trim() || null }; }
function validate(value: ObservationForm, label: string): string | null {
  if (!value.observation_id.trim()) return `${label}: observation ID is required.`;
  if (!value.source.trim()) return `${label}: source is required.`;
  if (!value.image_reference.trim()) return `${label}: image reference is required.`;
  if (!value.provenance_source.trim()) return `${label}: provenance source is required.`;
  if (value.acquisition_timestamp && Number.isNaN(Date.parse(value.acquisition_timestamp))) return `${label}: acquisition timestamp must be ISO-8601.`;
  if (!value.is_real_data || value.provenance !== 'real') return `${label}: explicitly mark the observation as real with real provenance.`;
  return null;
}
function display(value: string | number | null | undefined): string { return value === null || value === undefined || value === '' ? 'Unavailable' : String(value); }
function canAnalyze(value: ObservationForm): boolean { return Boolean(value.observation_id.trim() && value.source.trim() && value.image_reference.trim() && value.provenance_source.trim() && value.is_real_data && value.provenance === 'real'); }

export function TemporalChange() {
  const [observationA, setObservationA] = useState(emptyObservation);
  const [observationB, setObservationB] = useState(emptyObservation);
  const [state, setState] = useState<WorkspaceState>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [response, setResponse] = useState<Phase10PairSelectionResponse | null>(null);
  const readyToAnalyze = canAnalyze(observationA) && canAnalyze(observationB);

  async function analyze() {
    const validationError = validate(observationA, 'Observation A') ?? validate(observationB, 'Observation B');
    if (validationError) { setState('error'); setMessage(validationError); setResponse(null); return; }
    setState('loading'); setMessage(null); setResponse(null);
    try {
      const result = await submitPhase10PairSelection({ observation_a: toRequest(observationA), observation_b: toRequest(observationB) });
      setResponse(result); setState('success');
    } catch (error: unknown) {
      setState('error'); setResponse(null);
      if (error instanceof ApiError) {
        if (error.kind === 'network') setMessage('Network error: the Phase 10 backend could not be reached.');
        else if (error.kind === 'response') setMessage('Response error: Phase 10 returned malformed data.');
        else if (error.status === 422) setMessage('Validation error: Phase 10 rejected the request (422).');
        else if (error.status === 500) setMessage('Backend error: Phase 10 failed to process the pair (500).');
        else setMessage(error.message);
      } else setMessage('The Phase 10 request could not be completed.');
    }
  }

  return <AppShell title="Temporal Workspace" subtitle="Client-ordered Phase 10 observation pair selection"><div className="mx-auto w-full max-w-7xl space-y-8 px-8 pb-16 pt-8">
    <Notice title="Phase 10 boundary" icon={<AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />} tone="amber">This workspace submits observation metadata to Phase 10. It does not calculate temporal change, generate maps, or infer scientific values in the browser.</Notice>
    <section><div className="mb-4 flex items-end justify-between gap-4"><div><h2 className="text-xs font-bold uppercase tracking-[0.3em] text-zinc-500">Observation pair</h2><p className="mt-2 text-sm text-zinc-400">Enter genuine Phase 10 metadata. The order below is sent unchanged.</p></div><span className="hidden items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500 sm:flex"><Database className="h-3.5 w-3.5" /> No synthetic records</span></div><div className="grid gap-4 lg:grid-cols-2"><ObservationCard label="Observation A" role="First member of client-supplied pair" value={observationA} onChange={setObservationA} /><ObservationCard label="Observation B" role="Second member of client-supplied pair" value={observationB} onChange={setObservationB} /></div></section>
    <section className="rounded-2xl border border-white/10 bg-white/[0.015] p-5"><div className="mb-4 flex items-center gap-2"><Clock3 className="h-4 w-4 text-zinc-300" /><h2 className="text-xs font-bold uppercase tracking-[0.3em] text-zinc-400">Temporal relationship</h2></div><div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:text-left"><span className="rounded-lg border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200">A: {observationA.acquisition_timestamp || 'Timestamp unavailable'}</span><ArrowRight className="h-4 w-4 text-zinc-600" /><span className="rounded-lg border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200">B: {observationB.acquisition_timestamp || 'Timestamp unavailable'}</span></div><p className="mt-3 text-xs text-zinc-500">Phase 10 determines the temporal view from supplied timestamps. The client does not sort or reinterpret the pair.</p></section>
    <section className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.015] p-5 sm:flex-row sm:items-center"><div><h2 className="text-xs font-bold uppercase tracking-[0.3em] text-zinc-400">Analysis controls</h2><p className="mt-2 text-sm text-zinc-500">Both observations must be explicitly marked real before the request can run.</p></div><button type="button" onClick={analyze} disabled={state === 'loading' || !readyToAnalyze} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-black disabled:cursor-not-allowed disabled:opacity-50">{state === 'loading' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{state === 'loading' ? 'Running pair selection' : 'Analyze temporal pair'}</button></section>
    {state === 'loading' && <Notice title="Running temporal pair analysis..." icon={<Loader2 className="h-4 w-4 animate-spin" />} tone="neutral">Waiting for the Phase 10 response. No progress estimate is shown.</Notice>}
    {state === 'error' && <Notice title="Analysis unavailable" icon={<AlertTriangle className="h-4 w-4" />} tone="red">{message ?? 'The request failed.'}</Notice>}
    {state === 'success' && response && <ResultPanel response={response} />}
    <section className="grid gap-4 lg:grid-cols-2"><InfoPanel title="Provenance">Input provenance fields are forwarded unchanged. Phase 10 rejection reasons, warnings, and provenance status remain visible in the response.</InfoPanel><InfoPanel title="Spatial limitations">CRS text is displayed only as supplied. This workspace performs no coordinate conversion, map rendering, or pixel-to-metre interpretation.</InfoPanel></section>
  </div></AppShell>;
}

function ObservationCard({ label, role, value, onChange }: { label: string; role: string; value: ObservationForm; onChange: (value: ObservationForm) => void }) {
  const update = (field: keyof ObservationForm, next: string | boolean) => onChange({ ...value, [field]: next });
  return <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-5"><div className="mb-4 border-b border-white/10 pb-3"><h3 className="text-sm font-bold text-white">{label}</h3><p className="mt-1 text-xs text-zinc-500">{role}</p></div><div className="grid gap-3 sm:grid-cols-2"><Field label="Observation ID" value={value.observation_id} onChange={(v) => update('observation_id', v)} required /><Field label="Source" value={value.source} onChange={(v) => update('source', v)} required /><Field label="Image reference" value={value.image_reference} onChange={(v) => update('image_reference', v)} required /><Field label="Acquisition timestamp" value={value.acquisition_timestamp} onChange={(v) => update('acquisition_timestamp', v)} type="datetime-local" /><Field label="Provenance source" value={value.provenance_source} onChange={(v) => update('provenance_source', v)} required /><label className="text-xs text-zinc-400">Provenance<select value={value.provenance} onChange={(e) => update('provenance', e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-zinc-200">{['unavailable', 'real', 'synthetic', 'estimated', 'illustrative', 'deferred'].map((option) => <option key={option}>{option}</option>)}</select></label><Field label="CRS (optional)" value={value.crs} onChange={(v) => update('crs', v)} /></div><label className="mt-4 flex items-start gap-2 text-xs font-medium text-zinc-300"><input type="checkbox" checked={value.is_real_data} onChange={(e) => update('is_real_data', e.target.checked)} className="mt-0.5" />I confirm this record is genuine real observation data.</label></div>;
}
function Field({ label, value, onChange, required = false, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; type?: string }) { return <label className="text-xs text-zinc-400">{label}{required && <span className="text-amber-300"> *</span>}<input type={type} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-white/30" /></label>; }
function Notice({ title, icon, tone, children }: { title: string; icon: React.ReactNode; tone: 'amber' | 'neutral' | 'red'; children: React.ReactNode }) { const classes = tone === 'red' ? 'border-red-500/30 bg-red-500/5 text-red-200' : tone === 'amber' ? 'border-amber-500/30 bg-amber-500/5 text-amber-200' : 'border-white/10 bg-white/[0.015] text-zinc-300'; return <div role="status" className={`flex items-start gap-3 rounded-2xl border px-5 py-4 ${classes}`}>{icon}<div><p className="text-sm font-bold">{title}</p><p className="mt-2 text-sm leading-relaxed opacity-80">{children}</p></div></div>; }
function InfoPanel({ title, children }: { title: string; children: React.ReactNode }) { return <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-5"><h2 className="mb-3 text-xs font-bold uppercase tracking-[0.3em] text-zinc-400">{title}</h2><p className="text-sm leading-relaxed text-zinc-400">{children}</p></div>; }
function ResultPanel({ response }: { response: Phase10PairSelectionResponse }) { const metadata = response.temporal_metadata; return <section aria-live="polite" className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5"><div className="mb-5 flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-300" /><h2 className="text-xs font-bold uppercase tracking-[0.3em] text-emerald-200">Phase 10 response</h2></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Result label="Eligibility" value={response.eligibility} /><Result label="Pair A" value={display(response.observation_a_id)} /><Result label="Pair B" value={display(response.observation_b_id)} /><Result label="Provenance status" value={response.provenance_status} /><Result label="Temporal notes" value={display(metadata?.notes)} /><Result label="Temporal source field" value={display(metadata?.source_field)} /><Result label="Candidate selection score" value={display(response.candidate_selection_score)} /><Result label="Metadata completeness" value={display(response.metadata_completeness)} /><Result label="CRS compatibility" value={response.crs_compatibility} /><Result label="Footprint compatibility" value={response.footprint_compatibility} /><Result label="Sensor compatibility" value={response.sensor_compatibility} /><Result label="Image reference A" value={response.image_reference_a} /><Result label="Image reference B" value={response.image_reference_b} /></div><ResponseList label="Hard rejection reasons" values={response.hard_rejection_reasons} /><ResponseList label="Warnings" values={response.warnings} />{metadata && <div className="mt-4 border-t border-white/10 pt-4"><p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Temporal metadata</p><div className="grid gap-2 sm:grid-cols-2"><Result label="Original timestamp" value={display(metadata.original_timestamp)} /><Result label="Normalized timestamp" value={display(metadata.normalized_timestamp)} /><Result label="Acquisition date" value={display(metadata.acquisition_date)} /><Result label="Precision" value={metadata.precision} /><Result label="Timezone aware" value={String(metadata.timezone_aware)} /><Result label="Authoritative" value={String(metadata.authoritative)} /></div></div>}</section>; }
function Result({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-white/10 bg-black/20 p-3"><p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</p><p className="mt-1 break-words text-sm text-zinc-200">{value}</p></div>; }
function ResponseList({ label, values }: { label: string; values: string[] }) { return <div className="mt-4 border-t border-white/10 pt-4"><p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</p><p className="mt-2 text-sm text-zinc-300">{values.length ? values.join(' · ') : 'None reported'}</p></div>; }
