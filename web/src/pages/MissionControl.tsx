import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Server,
  Database,
  CheckCircle2,
  type LucideIcon,
} from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { ErrorState } from '../components/ErrorState';
import { GuidedDemo } from '../components/GuidedDemo';
import { LoadingState } from '../components/LoadingState';
import { WORKSPACES } from '../workspaces/registry';
import { useMission } from '../context/MissionContext';
import { ApiError, fetchMissionStatus, type MissionStatusPayload } from '../api/client';

type StatusTone = 'ok' | 'warn' | 'muted';
type ExportStateTone = 'available' | 'synthetic' | 'warning' | 'deferred';

interface SystemStatusState {
  loading: boolean;
  error: string | null;
  data: MissionStatusPayload | null;
}

function StatusCard({
  icon: Icon,
  label,
  value,
  tone,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: StatusTone;
  detail: string;
}) {
  const valueTone =
    tone === 'ok' ? 'text-green-400' : tone === 'warn' ? 'text-amber-300' : 'text-zinc-300';
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-6">
      <div className="flex items-center gap-2 text-zinc-500 text-[10px] font-bold uppercase tracking-[0.25em] mb-3">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <div className={`text-xl font-bold tracking-tight ${valueTone}`}>{value}</div>
      <p className="mt-1 text-zinc-600 text-xs font-medium leading-relaxed">{detail}</p>
    </div>
  );
}

function ExportPill({ label, present }: { label: string; present: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold ${
        present
          ? 'border-green-500/30 bg-green-500/5 text-green-300'
          : 'border-white/10 bg-white/[0.02] text-zinc-500'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${present ? 'bg-green-400' : 'bg-zinc-600'}`} />
      {label}
    </span>
  );
}

function OutputReadinessCard({
  label,
  state,
  detail,
}: {
  label: string;
  state: ExportStateTone;
  detail: string;
}) {
  const palette = {
    available: 'border-green-500/30 bg-green-500/5 text-green-200',
    synthetic: 'border-amber-500/30 bg-amber-500/5 text-amber-200',
    warning: 'border-red-500/30 bg-red-500/5 text-red-200',
    deferred: 'border-violet-500/30 bg-violet-500/5 text-violet-200',
  };

  const statusLabel = {
    available: 'Available',
    synthetic: 'Synthetic',
    warning: 'Unavailable',
    deferred: 'Deferred',
  }[state];

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-5">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-bold text-white tracking-tight">{label}</h3>
        <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.2em] ${palette[state]}`}>
          {statusLabel}
        </span>
      </div>
      <p className="text-zinc-500 text-xs font-medium leading-relaxed">{detail}</p>
    </div>
  );
}

export function MissionControl() {
  const { hasData, datasetLabel } = useMission();
  const [system, setSystem] = useState<SystemStatusState>({ loading: true, error: null, data: null });

  const loadMissionStatus = () => {
    let cancelled = false;
    setSystem({ loading: true, error: null, data: null });
    fetchMissionStatus()
      .then((data) => {
        if (!cancelled) setSystem({ loading: false, error: null, data });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const isUnavailable = err instanceof ApiError && err.status === 404;
          setSystem({
            loading: false,
            error: err instanceof Error ? err.message : 'System status unavailable',
            data: null,
          });
          if (isUnavailable) {
            setSystem((prev) => ({ ...prev, error: 'Mission status endpoint is unavailable in this build.' }));
          }
        }
      });
    return () => {
      cancelled = true;
    };
  };

  useEffect(() => {
    return loadMissionStatus();
  }, []);

  return (
    <AppShell title="Mission Control" subtitle="Operational overview of the application">
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-10">
        <GuidedDemo />

        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Output / Export Readiness
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <OutputReadinessCard
              label="Mission overview"
              state={system.data ? 'available' : 'warning'}
              detail={system.data ? 'Mission status is available and can be reviewed in the dashboard.' : 'Mission status is not yet available; retry the backend check to refresh the panel.'}
            />
            <OutputReadinessCard
              label="Dataset provenance"
              state="synthetic"
              detail="Current dataset labels are intentionally synthetic or development-only and are clearly marked as such."
            />
            <OutputReadinessCard
              label="Registration outputs"
              state="warning"
              detail="No correspondence engine or exported registration metrics are available in this build; match points and RMSE remain intentionally unavailable."
            />
            <OutputReadinessCard
              label="Water-Ice outputs"
              state="deferred"
              detail="Water-Ice overlays remain deferred and are not presented as genuine scientific detections or exports."
            />
            <OutputReadinessCard
              label="Temporal outputs"
              state="deferred"
              detail="Temporal change detection remains intentionally deferred and is not presented as actual multi-date analysis."
            />
            <OutputReadinessCard
              label="3D Digital Twin"
              state="available"
              detail="The Phase 12 Digital Twin remains presentation-ready and is preserved as a live inspection workflow without new scientific claims."
            />
          </div>
        </section>

        {/* System / module status */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            System Status
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatusCard
              icon={Server}
              label="Backend"
              value={system.data ? 'Online' : system.loading ? 'Checking…' : 'Offline'}
              tone={system.data ? 'ok' : system.error ? 'warn' : 'muted'}
              detail={system.data ? 'Mission API responding' : system.error ?? 'No backend response'}
            />
            <StatusCard
              icon={Database}
              label="Dataset"
              value={hasData ? 'Loaded' : 'Awaiting'}
              tone={hasData ? 'ok' : 'muted'}
              detail={hasData ? datasetLabel : 'Process a dataset in Imagery to load it'}
            />
            <StatusCard
              icon={CheckCircle2}
              label="Data Provenance"
              value="Synthetic / Development"
              tone="muted"
              detail="Phase 12 data is explicitly development-only; no real observations are claimed."
            />
          </div>
        </section>
        {/* Mission exports availability */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-3">
            Mission Exports
          </h2>
          {system.loading ? (
            <LoadingState title="Loading" message="Checking backend status…" compact />
          ) : system.error ? (
            <ErrorState
              title="Unable to load mission status"
              message={system.error}
              onRetry={loadMissionStatus}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              <ExportPill label="Primary Trajectory" present={system.data?.has_primary ?? false} />
              <ExportPill label="Replan Event" present={system.data?.has_replan ?? false} />
              <ExportPill label="Replanned Trajectory" present={system.data?.has_replanned_trajectory ?? false} />
            </div>
          )}
        </section>

        {/* Workspace entry points */}
        <section>
          <h2 className="text-xs uppercase tracking-[0.3em] text-zinc-500 font-bold mb-4">
            Workspaces
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {WORKSPACES.map((workspace) => {
              const Icon = workspace.icon;
              const isFullyPlanned = workspace.routes.every((route) => route.planned);
              return (
                <div
                  key={workspace.id}
                  className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-6"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-white/10 bg-white/[0.03]">
                      <Icon className="w-4 h-4 text-zinc-300" />
                    </span>
                    <h3 className="text-sm font-bold text-white tracking-tight">{workspace.label}</h3>
                  </div>
                  <p className="text-zinc-500 text-xs font-medium leading-relaxed mb-4 min-h-[2.5rem]">
                    {workspace.description}
                  </p>
                  {isFullyPlanned ? (
                    <Link
                      to={workspace.routes[0].path}
                      className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-amber-300/90 hover:text-amber-200"
                    >
                      Scheduled <ArrowRight className="w-3 h-3" />
                    </Link>
                  ) : (
                    <div className="space-y-2">
                      {workspace.routes.map((route) => (
                        <Link
                          key={route.path}
                          to={route.path}
                          className="group flex items-center justify-between text-[12px] font-semibold text-zinc-300 hover:text-white transition-colors"
                        >
                          <span className="flex items-center gap-2">
                            {route.label}
                            {route.planned && (
                              <span className="text-[8px] uppercase tracking-widest text-amber-300/80">
                                Scheduled
                              </span>
                            )}
                          </span>
                          <ArrowRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100" />
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
