import { AlertTriangle, MapPinned } from 'lucide-react';
import { LoadingState } from './LoadingState';

export type MatchPointCoordinate = {
  x: number;
  y: number;
};

export type MatchPointPair = {
  id?: string;
  source: MatchPointCoordinate;
  reference: MatchPointCoordinate;
};

export type MatchPointVisualizationStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'unavailable'
  | 'error';

export interface MatchPointVisualizationProps {
  /** Match data to render. Coordinates are expected to be normalized in the 0..1 range. */
  pairs?: MatchPointPair[];
  /** Current state of the correspondence result. */
  status?: MatchPointVisualizationStatus;
  sourceLabel?: string;
  referenceLabel?: string;
  showConnections?: boolean;
  loadingMessage?: string;
  emptyMessage?: string;
  unavailableMessage?: string;
  errorMessage?: string;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function normalizePoint(point: MatchPointCoordinate): MatchPointCoordinate {
  return {
    x: clamp01(point.x),
    y: clamp01(point.y),
  };
}

function Pane({
  label,
  points,
  accent,
}: {
  label: string;
  points: MatchPointCoordinate[];
  accent: 'source' | 'reference';
}) {
  const accentStyle =
    accent === 'source'
      ? 'border-cyan-500/30 bg-cyan-500/5 text-cyan-200'
      : 'border-violet-500/30 bg-violet-500/5 text-violet-200';

  return (
    <div className="relative min-h-[16rem] overflow-hidden rounded-xl border border-white/10 bg-[#0d0d10]">
      <div className={`absolute inset-x-3 top-3 flex items-center justify-between rounded-lg border px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.25em] ${accentStyle}`}>
        <span>{label}</span>
        <span>{points.length}</span>
      </div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_55%)]" />
      <div className="absolute inset-0">
        {points.map((point, index) => (
          <span
            key={`${label}-${index}`}
            className={`absolute block rounded-full border shadow-[0_0_18px_rgba(255,255,255,0.2)] ${
              accent === 'source' ? 'border-cyan-200 bg-cyan-400' : 'border-violet-200 bg-violet-400'
            }`}
            style={{
              width: '10px',
              height: '10px',
              left: `${point.x * 100}%`,
              top: `${point.y * 100}%`,
              transform: 'translate(-50%, -50%)',
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function MatchPointVisualization({
  pairs = [],
  status = 'idle',
  sourceLabel = 'Source',
  referenceLabel = 'Reference',
  showConnections = true,
  loadingMessage = 'Loading match points…',
  emptyMessage = 'No correspondence match data is available for this registration pair.',
  unavailableMessage = 'Correspondence match data is unavailable in this build.',
  errorMessage = 'Match-point data could not be loaded.',
}: MatchPointVisualizationProps) {
  const normalizedPairs = pairs.map((pair, index) => ({
    id: pair.id ?? `${index}`,
    source: normalizePoint(pair.source),
    reference: normalizePoint(pair.reference),
  }));

  const hasPairs = normalizedPairs.length > 0;

  if (status === 'loading') {
    return <LoadingState title="Loading" message={loadingMessage} compact className="justify-start" />;
  }

  if (status === 'unavailable') {
    return (
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-4 py-5">
        <div className="flex items-start gap-3 text-amber-200 text-sm font-medium leading-relaxed">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{unavailableMessage}</span>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 px-4 py-5">
        <div className="flex items-start gap-3 text-red-300 text-sm font-medium leading-relaxed">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      </div>
    );
  }

  if (!hasPairs || status === 'empty' || status === 'idle') {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.015] px-4 py-5">
        <div className="flex items-start gap-3 text-zinc-400 text-sm font-medium leading-relaxed">
          <MapPinned className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{emptyMessage}</span>
        </div>
      </div>
    );
  }

  const sourcePoints = normalizedPairs.map((pair) => pair.source);
  const referencePoints = normalizedPairs.map((pair) => pair.reference);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#09090b] p-3">
      <div className="grid grid-cols-2 gap-3 relative z-10">
        <Pane label={sourceLabel} points={sourcePoints} accent="source" />
        <Pane label={referenceLabel} points={referencePoints} accent="reference" />
      </div>
      {showConnections && (
        <svg
          className="pointer-events-none absolute inset-0 z-20 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {normalizedPairs.map((pair) => {
            const sourceX = 8 + pair.source.x * 36;
            const sourceY = 14 + pair.source.y * 72;
            const referenceX = 56 + pair.reference.x * 36;
            const referenceY = 14 + pair.reference.y * 72;

            return (
              <line
                key={pair.id}
                x1={sourceX}
                y1={sourceY}
                x2={referenceX}
                y2={referenceY}
                stroke="rgba(255,255,255,0.7)"
                strokeWidth="0.5"
                strokeDasharray="1 2"
              />
            );
          })}
        </svg>
      )}
    </div>
  );
}
