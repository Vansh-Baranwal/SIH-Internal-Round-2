import { AlertTriangle, RefreshCcw } from 'lucide-react';

export interface ErrorStateProps {
  title?: string;
  message: string;
  detail?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({
  title = 'Unable to load data',
  message,
  detail,
  onRetry,
  retryLabel = 'Retry',
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-red-500/30 bg-red-500/5 px-4 py-5 text-red-200"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-bold uppercase tracking-[0.28em] text-red-300/90">
            {title}
          </div>
          <p className="mt-2 text-sm font-medium leading-relaxed">{message}</p>
          {detail && <p className="mt-2 text-xs text-red-100/75 leading-relaxed">{detail}</p>}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-red-100 transition hover:bg-red-500/15"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              {retryLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
