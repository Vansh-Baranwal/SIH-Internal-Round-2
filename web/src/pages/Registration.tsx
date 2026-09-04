import { useCallback, useEffect, useRef, useState } from 'react';
import {
  UploadCloud,
  Play,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  Sun,
  Layers,
} from 'lucide-react';
import { useMission } from '../context/useMission';
import {
  ingestDataset,
  startRegistration,
} from '../api/registration';
import type { DatasetInput, SensorType, SpectralLayer } from '../types/registration';
import { useNavigate } from 'react-router-dom';
import { ProgressBar, StatusPanel } from '../components/ui/StatusPanel';

const SENSORS: SensorType[] = ['TMC', 'OHRC', 'IIRS', 'NAC', 'DEM'];

function DatasetSlot({
  label,
  dataset,
  onSelect,
  onRemove,
  disabled,
}: {
  label: string;
  dataset: DatasetInput | null;
  onSelect: (file: File, sensor: SensorType) => void;
  onRemove: () => void;
  disabled: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [sensor, setSensor] = useState<SensorType>(label === 'Source' ? 'OHRC' : 'TMC');

  return (
    <div className="border-l border-white/5 pl-8 flex-1 min-w-0">
      <div className="flex items-center justify-between mb-6 gap-4">
        <div>
          <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase">{label} Image</h3>
          <p className="text-[10px] text-zinc-600 tracking-wide mt-2">{label === 'Source' ? 'Required: image to transform' : 'Required: geometry reference'}</p>
        </div>
        <label className="sr-only" htmlFor={`${label.toLowerCase()}-sensor`}>{label} sensor</label>
        <select
          id={`${label.toLowerCase()}-sensor`}
          value={sensor}
          onChange={(e) => setSensor(e.target.value as SensorType)}
          disabled={disabled}
          className="bg-transparent border border-white/10 text-zinc-400 text-[11px] font-bold tracking-widest uppercase px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 focus:border-white/30"
        >
          {SENSORS.map((s) => (
            <option key={s} value={s} className="bg-[#0a0a0a]">
              {s}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        aria-label={dataset ? `Replace ${label.toLowerCase()} image` : `Select ${label.toLowerCase()} image`}
        className="w-full bg-[#030303] flex flex-col items-center justify-center min-h-[320px] border border-dashed border-white/10 hover:border-white/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 transition-colors disabled:cursor-not-allowed disabled:opacity-60 overflow-hidden"
      >
        {dataset ? (
          <img src={dataset.previewUrl} alt={`${label} preview: ${dataset.name}`} className="max-h-[320px] object-contain" />
        ) : (
          <div className="flex flex-col items-center gap-3 text-zinc-600">
            <UploadCloud className="w-6 h-6" />
            <span className="text-xs font-bold tracking-widest uppercase">Select {label} File</span>
          </div>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,.tif,.tiff"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onSelect(file, sensor);
          e.target.value = '';
        }}
      />

      {dataset ? (
        <div className="mt-4 pt-3 border-t border-white/5 flex items-start justify-between gap-4">
          <div className="min-w-0 text-[11px] font-bold tracking-widest uppercase">
            <p className="text-zinc-500 truncate" title={dataset.name}>{dataset.name}</p>
            <p className="text-zinc-600 mt-2 normal-case tracking-normal font-medium">
              {dataset.width && dataset.height ? `${dataset.width} × ${dataset.height} · ` : ''}
              {dataset.synthetic ? 'Synthetic capture' : `${(dataset.previewUrl ? 'Local' : 'Remote')} dataset`}
            </p>
          </div>
          <button
            type="button"
            onClick={onRemove}
            className="shrink-0 text-[10px] font-bold tracking-widest uppercase text-zinc-600 hover:text-rose-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 disabled:opacity-40"
          >
            Remove
          </button>
        </div>
      ) : (
        <p className="mt-4 text-[10px] text-zinc-600 tracking-wide">Accepted: PNG, JPEG, TIFF · Choose the sensor that captured this frame.</p>
      )}
    </div>
  );
}

function QualityBadge({ quality }: { quality: 'good' | 'weak' | 'failed' }) {
  const config = {
    good: { text: 'Registration Stable', color: 'text-emerald-500', Icon: CheckCircle2 },
    weak: { text: 'Weak Correspondence', color: 'text-amber-500', Icon: AlertTriangle },
    failed: { text: 'Registration Failed', color: 'text-red-500', Icon: AlertTriangle },
  }[quality];

  return (
    <div className={`flex items-center gap-2 ${config.color}`}>
      <config.Icon className="w-3.5 h-3.5" />
      <span className="text-[11px] font-bold tracking-widest uppercase">{config.text}</span>
    </div>
  );
}

function SunAnglePanel({
  azimuthDeg,
  elevationDeg,
  illuminationVariant,
  onChange,
  disabled,
}: {
  azimuthDeg: number;
  elevationDeg: number;
  illuminationVariant: boolean;
  onChange: (next: { azimuthDeg: number; elevationDeg: number; illuminationVariant: boolean }) => void;
  disabled: boolean;
}) {
  return (
    <div className="border-l border-white/5 pl-8">
      <div className="flex items-center gap-2 mb-8">
        <Sun className="w-3.5 h-3.5 text-zinc-500" />
        <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase">Sun-Angle Simulator</h3>
      </div>

      <div className="space-y-6">
        <div>
          <div className="flex justify-between text-[11px] font-bold tracking-widest uppercase text-zinc-500 mb-2">
            <span>Azimuth</span>
            <span className="text-zinc-300">{azimuthDeg.toFixed(0)}°</span>
          </div>
          <input
            type="range"
            min={0}
            max={360}
            value={azimuthDeg}
            disabled={disabled}
            onChange={(e) => onChange({ azimuthDeg: Number(e.target.value), elevationDeg, illuminationVariant })}
            className="w-full accent-sky-400"
          />
        </div>

        <div>
          <div className="flex justify-between text-[11px] font-bold tracking-widest uppercase text-zinc-500 mb-2">
            <span>Elevation</span>
            <span className={elevationDeg < 20 ? 'text-amber-500' : 'text-zinc-300'}>{elevationDeg.toFixed(0)}°</span>
          </div>
          <input
            type="range"
            min={2}
            max={90}
            value={elevationDeg}
            disabled={disabled}
            onChange={(e) => onChange({ azimuthDeg, elevationDeg: Number(e.target.value), illuminationVariant })}
            className="w-full accent-sky-400"
          />
          {elevationDeg < 20 && (
            <p className="text-[10px] text-amber-500 tracking-wide mt-2">
              Low sun angle — grazing shadows will stress the correspondence engine.
            </p>
          )}
        </div>

        <label className="flex items-center gap-3 pt-2 cursor-pointer">
          <input
            type="checkbox"
            checked={illuminationVariant}
            disabled={disabled}
            onChange={(e) => onChange({ azimuthDeg, elevationDeg, illuminationVariant: e.target.checked })}
            className="accent-sky-400"
          />
          <span className="text-[11px] font-bold tracking-widest uppercase text-zinc-400">
            Illumination-Variant Pass
          </span>
        </label>
      </div>
    </div>
  );
}

function SpectralPanel({
  layers,
  loadingKind,
  onRequest,
  onToggle,
  onOpacityChange,
  errors,
}: {
  layers: SpectralLayer[];
  loadingKind: SpectralLayer['kind'] | null;
  onRequest: (kind: SpectralLayer['kind']) => void;
  onToggle: (id: string) => void;
  onOpacityChange: (id: string, opacity: number) => void;
  errors: Partial<Record<SpectralLayer['kind'], string>>;
}) {
  const kinds: { kind: SpectralLayer['kind']; label: string }[] = [
    { kind: 'mineral-classification', label: 'Mineral Classification' },
    { kind: 'water-ice-confidence', label: 'Water-Ice Confidence' },
  ];

  return (
    <div className="border-l border-white/5 pl-8">
      <div className="flex items-center gap-2 mb-8">
        <Layers className="w-3.5 h-3.5 text-zinc-500" />
        <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase">Spectral &amp; Ice Intelligence</h3>
      </div>

      <div className="space-y-5">
        {kinds.map(({ kind, label }) => {
          const layer = layers.find((l) => l.kind === kind);
          const isLoading = loadingKind === kind;

          if (!layer) {
            return (
              <div key={kind}>
                <button
                  type="button"
                  onClick={() => onRequest(kind)}
                  disabled
                  className="w-full flex items-center justify-between border border-white/10 hover:border-white/25 px-4 py-3 text-[11px] font-bold tracking-widest uppercase text-zinc-400 transition-colors disabled:opacity-50"
                >
                  {label}
                  {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <span>Unavailable</span>}
                </button>
                {errors[kind] && <p role="alert" className="mt-2 text-[10px] text-rose-300">{errors[kind]}</p>}
              </div>
            );
          }

          return (
            <div key={layer.id} className="border border-white/10 px-4 py-3">
              <label className="flex items-center justify-between cursor-pointer mb-3">
                <span className="text-[11px] font-bold tracking-widest uppercase text-zinc-300">{layer.label}</span>
                <input
                  type="checkbox"
                  checked={layer.visible}
                  onChange={() => onToggle(layer.id)}
                  className="accent-sky-400"
                />
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={layer.opacity}
                disabled={!layer.visible}
                onChange={(e) => onOpacityChange(layer.id, Number(e.target.value))}
                className="w-full accent-sky-400"
              />
              <button
                type="button"
                onClick={() => onRequest(kind)}
                disabled
                className="mt-3 flex items-center gap-1.5 text-[10px] font-bold tracking-widest uppercase text-zinc-600 hover:text-zinc-400 disabled:opacity-50 transition-colors"
              >
                {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                {isLoading ? 'Generating…' : 'Unavailable'}
              </button>
              {errors[kind] && <p role="alert" className="mt-2 text-[10px] text-rose-300">{errors[kind]}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Registration() {
  const { session, setSession, setResult, resetSession, sendToMissionPipeline } = useMission();
  const navigate = useNavigate();
  const isRunning = session.status === 'queued' || session.status === 'running' || session.status === 'uploading';

  const [sunParams, setSunParams] = useState({ azimuthDeg: 135, elevationDeg: 45, illuminationVariant: false });
  const loadingSpectralKind: SpectralLayer['kind'] | null = null;
  const [spectralErrors, setSpectralErrors] = useState<Partial<Record<SpectralLayer['kind'], string>>>({});
  const [previousQuality, setPreviousQuality] = useState<'good' | 'weak' | 'failed' | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runGenerationRef = useRef(0);

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => clearPollTimer, [clearPollTimer]);

  const handleSelect = useCallback(
    async (slot: 'source' | 'reference', file: File, sensor: SensorType) => {
      const generation = ++runGenerationRef.current;
      clearPollTimer();
      setSession((prev) => ({ ...prev, status: 'uploading', error: undefined, updatedAt: new Date().toISOString() }));
      try {
        const dataset = await ingestDataset(file, sensor);
        if (generation !== runGenerationRef.current) return;
        setSession((prev) => ({
          ...prev,
          status: 'idle',
          [slot === 'source' ? 'datasetSource' : 'datasetReference']: dataset,
          updatedAt: new Date().toISOString(),
        }));
      } catch (err) {
        if (generation !== runGenerationRef.current) return;
        setSession((prev) => ({
          ...prev,
          status: 'failed',
          error: err instanceof Error ? err.message : 'Dataset ingestion failed',
          updatedAt: new Date().toISOString(),
        }));
      }
    },
    [clearPollTimer, setSession],
  );

  const handleRemove = useCallback(
    (slot: 'source' | 'reference') => {
      ++runGenerationRef.current;
      clearPollTimer();
      setSession((prev) => ({
        ...prev,
        status: 'idle',
        error: undefined,
        [slot === 'source' ? 'datasetSource' : 'datasetReference']: null,
        matchPoints: [],
        transformation: null,
        metrics: null,
        overlayImageUrl: null,
        updatedAt: new Date().toISOString(),
      }));
    },
    [clearPollTimer, setSession],
  );

  const handleRun = useCallback(async () => {
    if (!session.datasetSource?.file || !session.datasetReference?.file || isRunning) return;

    clearPollTimer();
    const generation = ++runGenerationRef.current;
    setPreviousQuality(session.metrics?.quality ?? null);
    setResult(null);
    setSession((prev) => ({
      ...prev,
      status: 'running',
      error: undefined,
      matchPoints: [],
      transformation: null,
      metrics: null,
      overlayImageUrl: null,
      sunSimulation: sunParams,
      updatedAt: new Date().toISOString(),
    }));
    try {
      const { result } = await startRegistration({
        sourceFile: session.datasetSource.file,
        referenceFile: session.datasetReference.file,
        sunSimulation: sunParams,
      });
      if (generation !== runGenerationRef.current) return;
      setSession((prev) => ({
        ...prev,
        status: result.status,
        matchPoints: result.matchPoints,
        transformation: result.transformation,
        metrics: result.metrics,
        overlayImageUrl: result.overlayImageUrl,
        error: result.error,
        updatedAt: new Date().toISOString(),
      }));
    } catch (err) {
      if (generation !== runGenerationRef.current) return;
      setSession((prev) => ({
        ...prev,
        status: 'failed',
        matchPoints: [],
        transformation: null,
        metrics: null,
        overlayImageUrl: null,
        error: err instanceof Error ? err.message : 'Registration request failed',
        updatedAt: new Date().toISOString(),
      }));
    }
  }, [clearPollTimer, isRunning, session.datasetReference, session.datasetSource, session.metrics, setResult, setSession, sunParams]);

  const handleCancel = useCallback(() => {
    ++runGenerationRef.current;
    clearPollTimer();
    setSession((prev) => ({ ...prev, status: 'idle', error: 'Registration cancelled.', updatedAt: new Date().toISOString() }));
  }, [clearPollTimer, setSession]);

  const handleRetry = useCallback(() => {
    void handleRun();
  }, [handleRun]);

  const handleRequestSpectralLayer = useCallback(
    (kind: SpectralLayer['kind']) => {
      setSpectralErrors((prev) => ({
        ...prev,
        [kind]: 'Spectral analysis is not connected for local uploads yet.',
      }));
    },
    [],
  );

  const toggleSpectralLayer = useCallback(
    (id: string) => {
      setSession((prev) => ({
        ...prev,
        spectralLayers: prev.spectralLayers.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
      }));
    },
    [setSession],
  );

  const setSpectralOpacity = useCallback(
    (id: string, opacity: number) => {
      setSession((prev) => ({
        ...prev,
        spectralLayers: prev.spectralLayers.map((l) => (l.id === id ? { ...l, opacity } : l)),
      }));
    },
    [setSession],
  );

  const canRun = !!session.datasetSource?.file && !!session.datasetReference?.file && !isRunning;
  const showResults = session.status === 'succeeded' && session.metrics;
  const statusCopy = session.status === 'idle' ? null : {
    uploading: { tone: 'info' as const, title: 'Preparing images', message: 'Reading the selected local frames before submission.' },
    queued: { tone: 'info' as const, title: 'Preparing registration', message: 'The selected images are being prepared for the correspondence engine.' },
    running: { tone: 'info' as const, title: 'Registration in progress', message: 'The backend is matching features, estimating geometry, and verifying inliers.' },
    succeeded: { tone: 'success' as const, title: 'Registration complete', message: 'The registered output is ready for review.' },
    failed: { tone: 'error' as const, title: 'Registration needs attention', message: session.error ?? 'The engine could not complete this run.' },
  }[session.status];

  const handleReset = useCallback(() => {
    clearPollTimer();
    ++runGenerationRef.current;
    setSpectralErrors({});
    setPreviousQuality(null);
    resetSession();
  }, [clearPollTimer, resetSession]);

  const handleDatasetRemove = useCallback((slot: 'source' | 'reference') => {
    handleRemove(slot);
    setSpectralErrors({});
  }, [handleRemove]);

  return (
    <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
      <div className="mb-10 flex flex-col gap-6 border-b border-white/5 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">
            Multi-Sensor Registration
          </h2>
          <p className="text-zinc-500 font-medium tracking-wide">
            Correspondence Engine · Feature Matching &amp; Geometric Verification
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 text-xs font-bold tracking-widest uppercase transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
          {isRunning ? (
            <button
              type="button"
              onClick={handleCancel}
              className="flex items-center gap-2 border border-white/10 px-4 py-3 text-xs font-bold tracking-widest uppercase text-zinc-400 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70"
            >
              Cancel
            </button>
          ) : (
            <button
              type="button"
              onClick={session.status === 'failed' ? handleRetry : handleRun}
              disabled={!canRun}
              className="flex items-center gap-2 bg-zinc-200 hover:bg-white disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-black font-bold tracking-widest text-xs uppercase py-3 px-6 transition-colors"
            >
              {session.status === 'failed' ? <RotateCcw className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {session.status === 'failed' ? 'Retry Registration' : 'Run Registration'}
            </button>
          )}
        </div>
      </div>

      {statusCopy && (
        <div className="mb-10 space-y-4">
          <StatusPanel
            tone={statusCopy.tone}
            title={statusCopy.title}
            message={statusCopy.message}
            action={session.status === 'failed' && canRun ? <button type="button" onClick={handleRetry} className="text-xs font-bold uppercase tracking-widest underline underline-offset-4">Retry</button> : undefined}
          />
          {isRunning && <ProgressBar label={session.status === 'uploading' ? 'Preparing frames' : 'Matching and verifying'} />}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 mb-16">
        <DatasetSlot
          label="Source"
          dataset={session.datasetSource}
          disabled={isRunning}
          onSelect={(file, sensor) => handleSelect('source', file, sensor)}
          onRemove={() => handleDatasetRemove('source')}
        />
        <DatasetSlot
          label="Reference"
          dataset={session.datasetReference}
          disabled={isRunning}
          onSelect={(file, sensor) => handleSelect('reference', file, sensor)}
          onRemove={() => handleDatasetRemove('reference')}
        />
      </div>

      <div className="mb-16">
        <SunAnglePanel
          azimuthDeg={sunParams.azimuthDeg}
          elevationDeg={sunParams.elevationDeg}
          illuminationVariant={sunParams.illuminationVariant}
          onChange={setSunParams}
          disabled={isRunning}
        />
      </div>


      {session.matchPoints.length > 0 && (
        <div className="mb-16">
          <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase mb-8 border-b border-white/5 pb-4">
            Feature Correspondence
          </h3>
          <div className="relative w-full bg-[#030303] min-h-[420px] flex items-center justify-center overflow-hidden">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full opacity-80">
              {(() => {
                const sourceWidth = Math.max(...session.matchPoints.map((m) => m.sourceX), 1);
                const sourceHeight = Math.max(...session.matchPoints.map((m) => m.sourceY), 1);
                const referenceWidth = Math.max(...session.matchPoints.map((m) => m.referenceX), 1);
                const referenceHeight = Math.max(...session.matchPoints.map((m) => m.referenceY), 1);
                return session.matchPoints.map((m) => (
                  <line
                    key={m.id}
                    x1={(m.sourceX / sourceWidth) * 45}
                    y1={(m.sourceY / sourceHeight) * 100}
                    x2={55 + (m.referenceX / referenceWidth) * 45}
                    y2={(m.referenceY / referenceHeight) * 100}
                    stroke={m.isInlier ? '#38bdf8' : '#52525b'}
                    strokeWidth={m.isInlier ? 0.15 : 0.08}
                    opacity={m.isInlier ? 0.7 : 0.25}
                  />
                ));
              })()}
            </svg>
            <div className="relative z-10 flex w-full justify-between px-8 py-8 pointer-events-none">
              <span className="text-[11px] font-bold tracking-widest uppercase text-zinc-600">Source</span>
              <span className="text-[11px] font-bold tracking-widest uppercase text-zinc-600">Reference</span>
            </div>
          </div>
        </div>
      )}

      {showResults && session.metrics && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8 mb-8">
          <div className="border-l border-white/20 pl-6 xl:col-span-1">
            <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase mb-6">Registration Quality</h3>
            <QualityBadge quality={session.metrics.quality} />
          </div>
          <Metric label="RMSE" value={`${session.metrics.rmsePixels.toFixed(2)} px`} sub="backend-reported pixel error" />
          <Metric
            label="Inlier Ratio"
            value={`${(session.metrics.inlierRatio * 100).toFixed(0)}%`}
            sub={`${session.metrics.inlierCount} / ${session.metrics.totalMatches} matches`}
          />
          <Metric label="Spatial Coverage" value={`${(session.metrics.spatialCoverage * 100).toFixed(0)}%`} sub="of reference frame" />
        </div>
      )}

      {showResults && previousQuality && (
        <div className="mb-16 text-[11px] font-bold tracking-widest uppercase text-zinc-500">
          {previousQuality === session.metrics?.quality
            ? `Quality unchanged (${previousQuality}) under this sun-angle pass — engine appears illumination-invariant.`
            : `Quality shifted from ${previousQuality} to ${session.metrics?.quality} under this sun-angle pass.`}
        </div>
      )}

      {showResults && (
        <div className="mb-16">
          <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase mb-8 border-b border-white/5 pb-4">
            Registered Output
          </h3>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-16">
            <div className="xl:col-span-2 relative w-full bg-[#030303] min-h-[420px] flex items-center justify-center overflow-hidden">
              {session.overlayImageUrl && (
                <img src={session.overlayImageUrl} alt="Registered output" className="max-h-[420px] object-contain" />
              )}
              {session.spectralLayers
                .filter((l) => l.visible)
                .map((l) => (
                  <div
                    key={l.id}
                    className="absolute inset-0 pointer-events-none mix-blend-screen"
                    style={{
                      opacity: l.opacity,
                      background:
                        l.kind === 'mineral-classification'
                          ? 'radial-gradient(circle at 40% 40%, rgba(245,158,11,0.9), transparent 60%)'
                          : 'radial-gradient(circle at 60% 55%, rgba(56,189,248,0.9), transparent 60%)',
                    }}
                  />
                ))}
            </div>
            <SpectralPanel
              layers={session.spectralLayers}
              loadingKind={loadingSpectralKind}
              onRequest={handleRequestSpectralLayer}
              onToggle={toggleSpectralLayer}
              onOpacityChange={setSpectralOpacity}
              errors={spectralErrors}
            />
          </div>
        </div>
      )}

      {showResults && (
        <div className="flex justify-end gap-4 border-t border-white/5 pt-8">
          <button
            onClick={() => {
              if (session.overlayImageUrl) {
                sendToMissionPipeline(session.overlayImageUrl);
                // Lands on Imagery (M2) rather than Hazard Map (M4) —
                // matches the legacy pipeline order (M1 → M2 → M3/M4 →
                // M5/M6): a registered image should go through
                // super-resolution before hazard analysis, not skip it.
                navigate('/imagery');
              }
            }}
            className="flex items-center gap-2 bg-zinc-200 hover:bg-white text-black font-bold tracking-widest text-xs uppercase py-3 px-6 transition-colors"
          >
            Send to Mission Pipeline
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="border-l border-white/5 pl-6">
      <h4 className="text-zinc-500 font-bold tracking-widest text-[11px] uppercase mb-3">{label}</h4>
      <div className="text-2xl font-medium text-white mb-1">{value}</div>
      <div className="text-zinc-600 text-xs tracking-wide">{sub}</div>
    </div>
  );
}