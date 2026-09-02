import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { LoadingState } from '../LoadingState';
import { getWorkspaceByPath } from '../../workspaces/registry';

interface AppShellProps {
  /** Workspace page title. */
  title: string;
  /** Optional supporting line under the title. */
  subtitle?: string;
  /** Show a centred loading state instead of the content. */
  loading?: boolean;
  /** Show an error banner when set. */
  error?: string | null;
  /** Render the "scheduled / not yet implemented" marker. */
  planned?: boolean;
  children?: ReactNode;
}

/**
 * Phase 13.1 — shared workspace page frame.
 *
 * Renders the consistent workspace header (icon + workspace label + title +
 * subtitle), the shared loading / error slots and the workspace content. This
 * is the common scaffold for workspace pages so workspace-specific components
 * stay modular and the loading/error handling stays consistent.
 */
export function AppShell({
  title,
  subtitle,
  loading = false,
  error = null,
  planned = false,
  children,
}: AppShellProps) {
  const { pathname } = useLocation();
  const workspace = getWorkspaceByPath(pathname);
  const Icon = workspace?.icon;

  return (
    <div className="flex-grow flex flex-col font-sans">
      {/* Workspace header */}
      <div className="border-b border-white/5 bg-[#0a0a0a]/60 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto w-full px-8 pt-32 pb-6">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            {Icon && (
              <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-white/10 bg-white/[0.03]">
                <Icon className="w-4 h-4 text-zinc-300" />
              </span>
            )}
            <span className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">
              {workspace?.shortLabel ?? 'Workspace'}
            </span>
            {planned && (
              <span className="text-[9px] uppercase tracking-[0.2em] text-amber-300/90 border border-amber-300/30 bg-amber-300/5 px-2 py-0.5 rounded font-bold">
                Scheduled
              </span>
            )}
          </div>
          <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-2">
            {title}
          </h1>
          {subtitle && (
            <p className="text-zinc-500 font-medium tracking-wide text-sm">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Shared error / loading states */}
      {error && (
        <div className="mx-auto w-full max-w-7xl border-b border-red-500/30 bg-red-500/5 px-8 py-3">
          <div className="flex items-center gap-2 text-red-300 text-sm font-medium">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

      <div className="flex-grow flex flex-col">
        {loading ? (
          <div className="flex-grow flex items-center justify-center py-20 px-8">
            <LoadingState
              title="Loading"
              message="Loading workspace data…"
              className="min-w-[18rem] justify-center"
            />
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
