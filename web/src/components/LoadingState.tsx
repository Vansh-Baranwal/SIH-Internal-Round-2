import { Loader2 } from 'lucide-react';

export interface LoadingStateProps {
  title?: string;
  message?: string;
  compact?: boolean;
  className?: string;
}

export function LoadingState({
  title = 'Loading',
  message,
  compact = false,
  className = '',
}: LoadingStateProps) {
  return (
    <div
      className={[
        'flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.015] px-4 py-3 text-zinc-300',
        compact ? 'text-sm' : 'text-base',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <Loader2 className={compact ? 'h-4 w-4 animate-spin text-zinc-400' : 'h-5 w-5 animate-spin text-zinc-400'} />
      <div className="flex flex-col">
        <span className="text-[10px] font-bold uppercase tracking-[0.28em] text-zinc-500">{title}</span>
        {message && <span className="text-xs font-medium text-zinc-400">{message}</span>}
      </div>
    </div>
  );
}
