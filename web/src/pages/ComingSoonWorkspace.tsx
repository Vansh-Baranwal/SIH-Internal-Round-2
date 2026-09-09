import { WORKSPACES, type WorkspaceId } from '../workspaces/registry';
import { AppShell } from '../components/layout/AppShell';

/**
 * Phase 13.1 — shared placeholder for a workspace that is reserved in the
 * architecture but not implemented yet.
 *
 * This is scaffolding only: it does not implement any Phase 13 milestone and it
 * never fabricates synthetic or real scientific results.
 */
export function ComingSoonWorkspace({ workspaceId }: { workspaceId: WorkspaceId }) {
  const workspace = WORKSPACES.find((entry) => entry.id === workspaceId);

  return (
    <AppShell planned title={workspace?.label ?? 'Workspace'} subtitle={workspace?.description}>
      <div className="max-w-7xl mx-auto w-full px-8 pt-10 pb-16">
        <div className="rounded-2xl border border-white/10 bg-white/[0.015] backdrop-blur p-10 max-w-3xl">
          <p className="text-zinc-400 font-medium leading-relaxed">
            This workspace is a reserved slot in the Phase 13 application architecture. Its
            functionality is scheduled for a later Phase 13 milestone and is not implemented here.
            No synthetic or real scientific results are produced or fabricated in this placeholder.
          </p>
          <p className="mt-4 text-zinc-600 text-sm font-medium tracking-wide">
            Existing Phase 12 components remain available in the "Simulation" workspace, and
            all currently working modules keep their existing routes.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
