import { Link, useLocation } from 'react-router-dom';
import { WORKSPACES, getWorkspaceByPath, primaryPathOf } from '../../workspaces/registry';

/**
 * Phase 13.1 — workspace-level navigation.
 *
 * A compact, shared switcher that groups the application into the Phase 13
 * workspaces. It is additive: the existing module navbar (Imagery, Terrain,
 * Hazards, ...) is preserved unchanged.
 */
export function WorkspaceNav() {
  const { pathname } = useLocation();
  const active = getWorkspaceByPath(pathname);

  return (
    <nav
      aria-label="Workspaces"
      className="fixed top-[4.5rem] left-0 right-0 z-40 flex justify-center px-6 pointer-events-none"
    >
      <div className="pointer-events-auto w-full max-w-7xl">
        <div className="flex items-center gap-1.5 overflow-x-auto rounded-2xl border border-white/10 bg-[#0a0a0a]/85 backdrop-blur px-2 py-1.5">
          {WORKSPACES.map((workspace) => {
            const isActive = active?.id === workspace.id;
            const Icon = workspace.icon;
            return (
              <Link
                key={workspace.id}
                to={primaryPathOf(workspace)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-[11px] font-bold uppercase tracking-[0.15em] whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-white text-black'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-white/5'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {workspace.shortLabel}
              </Link>
            );
          })}
        </div>

        {active && (
          <div className="mt-2 flex items-center gap-2 overflow-x-auto px-4">
            {active.routes.map((route) => (
              <Link
                key={route.path}
                to={route.path}
                className={`flex items-center gap-1.5 text-[11px] font-semibold tracking-wide whitespace-nowrap transition-colors ${
                  pathname === route.path ? 'text-white' : 'text-zinc-500 hover:text-zinc-200'
                } ${route.planned ? 'opacity-70' : ''}`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                {route.label}
                {route.planned && (
                  <span className="text-[8px] uppercase tracking-widest text-amber-300/80">planned</span>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
