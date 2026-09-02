import { AlertTriangle, BarChart3, TrendingUp } from 'lucide-react';
import { LoadingState } from './LoadingState';

export type RegistrationMetricsStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'unavailable'
  | 'error';

export interface RegistrationMetricsData {
  rmsePx?: number | null;
  inlierCount?: number | null;
  inlierRatio?: number | null;
  spatialCoverage?: number | null;
  quality?: string | null;
  status?: string | null;
  message?: string | null;
}

export interface RegistrationMetricsPanelProps {
  metrics?: RegistrationMetricsData | null;
  status?: RegistrationMetricsStatus;
  loadingMessage?: string;
  emptyMessage?: string;
  unavailableMessage?: string;
  errorMessage?: string;
}

function formatOptionalNumber(value: number | null | undefined, suffix?: string): string {
  if (value == null || Number.isNaN(value)) return '—';
  const formatted = suffix === '%' ? `${(value * 100).toFixed(1)}%` : value.toFixed(3);
  return suffix === '%' ? formatted : `${formatted}${suffix ?? ''}`;
}

function formatRatio(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (value <= 1) return `${(value * 100).toFixed(1)}%`;
  return `${value.toFixed(3)}`;
}

export function RegistrationMetricsPanel({
  metrics = null,
  status = 'idle',
  loadingMessage = 'Loading registration metrics…',
  emptyMessage = 'No registration metrics are available for this dataset pair yet.',
  unavailableMessage = 'Registration metrics are unavailable because the correspondence engine is not available in this build.',
  errorMessage = 'Registration metrics could not be loaded.',
}: RegistrationMetricsPanelProps) {
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

  if (!metrics || status === 'empty' || status === 'idle') {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.015] px-4 py-5">
        <div className="flex items-start gap-3 text-zinc-400 text-sm font-medium leading-relaxed">
          <BarChart3 className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{emptyMessage}</span>
        </div>
      </div>
    );
  }

  const rows = [
    { label: 'RMSE', value: formatOptionalNumber(metrics.rmsePx, ' px') },
    { label: 'Inlier Count', value: metrics.inlierCount == null ? '—' : metrics.inlierCount.toString() },
    { label: 'Inlier Ratio', value: formatRatio(metrics.inlierRatio) },
    { label: 'Spatial Coverage', value: formatRatio(metrics.spatialCoverage) },
    { label: 'Registration Status', value: metrics.status ?? '—' },
    { label: 'Quality', value: metrics.quality ?? '—' },
  ];

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-white/10 mb-4">
        <div className="flex items-center gap-2 text-zinc-300">
          <TrendingUp className="w-4 h-4 text-cyan-300" />
          <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-500">
            Registration Metrics
          </span>
        </div>
        {metrics.message && <span className="text-[10px] text-zinc-500">{metrics.message}</span>}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {rows.map((row) => (
          <div key={row.label} className="rounded-xl border border-white/10 bg-[#0d0d10] px-3 py-2.5">
            <p className="text-[9px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-1.5">
              {row.label}
            </p>
            <p className="text-sm font-medium text-zinc-200">{row.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
