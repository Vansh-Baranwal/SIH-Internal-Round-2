import type { ReactNode } from 'react';

export type StatusTone = 'info' | 'success' | 'warning' | 'error';

const toneClasses: Record<StatusTone, string> = {
  info: 'border-sky-400/20 bg-sky-400/5 text-sky-200',
  success: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-200',
  warning: 'border-amber-400/20 bg-amber-400/5 text-amber-200',
  error: 'border-rose-400/20 bg-rose-400/5 text-rose-200',
};

export function StatusPanel({
  tone = 'info',
  title,
  message,
  action,
  className = '',
}: {
  tone?: StatusTone;
  title: string;
  message?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`border px-5 py-4 ${toneClasses[tone]} ${className}`} role={tone === 'error' ? 'alert' : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase">{title}</p>
          {message && <p className="mt-2 text-sm leading-relaxed text-zinc-400">{message}</p>}
        </div>
        {action}
      </div>
    </div>
  );
}

export function ProgressBar({ value, label }: { value?: number; label: string }) {
  const determinate = typeof value === 'number';
  return (
    <div className="space-y-2" aria-label={label} role="status">
      <div className="flex items-center justify-between gap-4 text-[10px] font-bold tracking-[0.16em] uppercase text-zinc-500">
        <span>{label}</span>
        {determinate && <span>{Math.round(value)}%</span>}
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full bg-sky-400 transition-[width] duration-300 ${determinate ? '' : 'w-1/3 animate-[progress_1.2s_ease-in-out_infinite]'}`}
          style={determinate ? { width: `${Math.max(0, Math.min(100, value))}%` } : undefined}
        />
      </div>
    </div>
  );
}
