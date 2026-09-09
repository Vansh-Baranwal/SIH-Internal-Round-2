import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Database, Satellite, Menu, X, Check } from 'lucide-react';
import { useMission } from '../../context/useMission';
import { getPipelineStages } from '../../utils/pipelineProgress';
import type { RegistrationSession } from '../../types/registration';

const mobileMenuId = 'mobile-navigation-menu';
const focusRing = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70';

function PipelineStepper({ result, session }: { result: any; session: any }) {
  return null;
  const location = useLocation();
  const stages = getPipelineStages(result, session);
  const hasStarted = session.status !== 'idle' || result !== null;

  if (!hasStarted) return null;

  return (
    <nav
      aria-label="Mission pipeline progress"
      className="hidden lg:flex mt-2 items-center gap-0.5 bg-[#0a0a0a]/90 backdrop-blur-xl rounded-full border border-white/10 px-5 py-2.5 pointer-events-auto shadow-2xl"
    >
      {stages.map((stage, i) => {
        const isCurrent = location.pathname === stage.path;
        return (
          <div key={stage.id} className="flex items-center">
            <Link
              to={stage.path}
              aria-current={isCurrent ? 'step' : undefined}
              className={`${focusRing} flex items-center gap-1.5 rounded px-1 py-0.5 text-[10px] font-bold tracking-widest uppercase transition-colors ${
                isCurrent ? 'text-white' : stage.complete ? 'text-emerald-400 hover:text-emerald-300' : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex items-center justify-center w-4 h-4 rounded-full border text-[9px] leading-none ${
                  stage.complete
                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                    : isCurrent
                      ? 'border-sky-400 text-sky-400'
                      : 'border-zinc-700 text-zinc-600'
                }`}
              >
                {stage.complete ? <Check className="w-2.5 h-2.5" /> : i + 1}
              </span>
              {stage.label}
            </Link>
            {i < stages.length - 1 && (
              <div aria-hidden="true" className={`w-6 h-px mx-2 ${stage.complete ? 'bg-emerald-500/40' : 'bg-white/10'}`} />
            )}
          </div>
        );
      })}
    </nav>
  );
}

export function Navbar() {
  const location = useLocation();
  const { result, session } = useMission();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);

  const navLinks = [
    { name: 'Registration', path: '/registration' },
    { name: 'Imagery', path: '/imagery' },
    { name: 'Hazards', path: '/hazard-map' },
    { name: 'Spectral', path: '/spectral' },
    { name: 'Water Ice', path: '/water-ice' },
    { name: 'Temporal', path: '/temporal' },
    { name: 'Simulation', path: '/simulation' },
    { name: '3D Twin', path: '/digital-twin' },
  ];

  const hasRegistration = session.status === 'succeeded';
  const hasData = result !== null;

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!mobileMenuRef.current?.contains(target)) setMobileOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [mobileOpen]);

  return (
    <header className="fixed top-3 z-50 flex w-full flex-col items-center px-3 sm:top-6 sm:px-6 pointer-events-none">
      <div className="bg-[#0a0a0a]/90 backdrop-blur-xl rounded-2xl shadow-2xl flex items-center justify-between px-3 py-2 w-full max-w-fit gap-3 sm:gap-6 lg:gap-12 border border-white/10 pointer-events-auto">
        <div className="flex items-center space-x-4 sm:space-x-6">
          <Link to="/" aria-label="Luna Drishti home" className={`flex items-center justify-center bg-black w-8 h-8 rounded-lg shadow-inner border border-white/20 relative group overflow-hidden ${focusRing}`}>
            <div className="absolute top-0.5 left-0.5 w-1 h-1 border-t border-l border-white/20" />
            <div className="absolute top-0.5 right-0.5 w-1 h-1 border-t border-r border-white/20" />
            <div className="absolute bottom-0.5 left-0.5 w-1 h-1 border-b border-l border-white/20" />
            <div className="absolute bottom-0.5 right-0.5 w-1 h-1 border-b border-r border-white/20" />
            <Satellite className="w-4 h-4 text-white" aria-hidden="true" />
          </Link>

          <nav aria-label="Primary navigation" className="hidden lg:flex items-center gap-3 xl:gap-5">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                to={link.path}
                aria-current={location.pathname === link.path ? 'page' : undefined}
                className={`${focusRing} rounded px-1 py-1 text-[13px] whitespace-nowrap transition-colors ${location.pathname === link.path ? 'text-white font-bold' : 'text-zinc-400 font-medium hover:text-white'}`}
              >
                {link.name}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center space-x-3 sm:space-x-4">
          <div className="hidden sm:flex items-center space-x-2 border-l border-white/10 pl-4 text-[12px] font-semibold pr-1" aria-live="polite">
            <Database className="w-3.5 h-3.5 text-white" aria-hidden="true" />
            <span className="text-white">{hasRegistration ? 'Registered' : hasData ? 'Data Loaded' : 'Awaiting Data'}</span>
          </div>

          <button
            type="button"
            className={`lg:hidden flex items-center justify-center w-8 h-8 text-zinc-400 hover:text-white transition-colors ${focusRing}`}
            onClick={() => setMobileOpen((open) => !open)}
            aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={mobileOpen}
            aria-controls={mobileMenuId}
          >
            {mobileOpen ? <X className="w-5 h-5" aria-hidden="true" /> : <Menu className="w-5 h-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      <PipelineStepper result={result} session={session} />

      {mobileOpen && (
        <div ref={mobileMenuRef} id={mobileMenuId} className="lg:hidden fixed inset-x-3 top-[4.5rem] z-40 pointer-events-auto sm:inset-x-6 sm:top-[5.5rem]">
          <div className="relative bg-[#0a0a0a]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl p-4 sm:p-6 max-h-[calc(100vh-6rem)] overflow-y-auto">
            <nav aria-label="Mobile navigation" className="flex flex-col space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.path}
                  onClick={() => setMobileOpen(false)}
                  aria-current={location.pathname === link.path ? 'page' : undefined}
                  className={`${focusRing} px-4 py-3 rounded-lg text-sm transition-colors ${location.pathname === link.path ? 'text-white font-bold bg-white/5' : 'text-zinc-400 font-medium hover:text-white hover:bg-white/5'}`}
                >
                  {link.name}
                </Link>
              ))}
            </nav>

            <div className="sm:hidden flex items-center space-x-2 mt-6 pt-4 border-t border-white/10 px-4 text-[12px] font-semibold" aria-live="polite">
              <Database className="w-3.5 h-3.5 text-white" aria-hidden="true" />
              <span className="text-white">{hasRegistration ? 'Registered' : hasData ? 'Data Loaded' : 'Awaiting Data'}</span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}


