import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Database,
  Menu,
  X,
  Check,
  Home,
  ClipboardList,
  Image as ImageIcon,
  AlertTriangle,
  Activity,
  Droplets,
  Clock,
  PlayCircle
} from 'lucide-react';
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
    { name: 'Home', path: '/', icon: Home },
    { name: 'Registration', path: '/registration', icon: ClipboardList },
    { name: 'Imagery', path: '/imagery', icon: ImageIcon },
    { name: 'Hazards', path: '/hazard-map', icon: AlertTriangle },
    { name: 'Spectral', path: '/spectral', icon: Activity },
    { name: 'Water Ice', path: '/water-ice', icon: Droplets },
    { name: 'Temporal', path: '/temporal', icon: Clock },
    { name: 'Simulation', path: '/simulation', icon: PlayCircle },
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
    <header className="fixed top-4 z-50 flex w-full flex-col items-center px-3 sm:px-6 pointer-events-none">
      <div className="bg-[#0a0a0a]/90 backdrop-blur-2xl p-1 sm:p-1.5 rounded-full shadow-[0_0_30px_-5px_rgba(255,255,255,0.15),_0_20px_40px_rgba(0,0,0,0.5)] hover:shadow-[0_0_40px_-5px_rgba(255,255,255,0.25),_0_20px_40px_rgba(0,0,0,0.5)] transition-shadow duration-500 pointer-events-auto border border-white/20">
        <div className="bg-[#27272a]/80 backdrop-blur-md rounded-full shadow-[inset_0_2px_10px_rgba(0,0,0,0.6)] p-1 flex items-center">
          
          {/* Desktop Navigation */}
          <nav aria-label="Primary navigation" className="hidden lg:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.path;
              const Icon = link.icon;
              return (
                <Link
                  key={link.name}
                  to={link.path}
                  className={`flex flex-col items-center justify-center px-2 py-1 min-w-[64px] h-[46px] rounded-full transition-all duration-300 transform active:scale-95 ${
                    isActive 
                      ? 'bg-zinc-100 text-black shadow-[0_4px_12px_rgba(255,255,255,0.3)]' 
                      : 'text-zinc-400 hover:text-white hover:bg-white/10 hover:shadow-lg'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 mb-0.5" strokeWidth={isActive ? 2 : 1.5} />
                  <span className="text-[9px] tracking-wide font-medium">{link.name}</span>
                </Link>
              );
            })}

            <div className="flex flex-col items-center justify-center px-3 py-1 h-[46px] ml-1 border-l border-zinc-700/50">
               <Database className={`w-3.5 h-3.5 mb-0.5 ${hasRegistration ? 'text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'text-zinc-500'}`} strokeWidth={1.5} />
               <span className="text-[9px] tracking-wide font-medium text-zinc-400 whitespace-nowrap">
                 {hasRegistration ? 'Registered' : hasData ? 'Data Loaded' : 'Awaiting Data'}
               </span>
            </div>
          </nav>

          {/* Mobile Navigation Bar */}
          <nav aria-label="Mobile top bar" className="flex lg:hidden items-center justify-between w-full min-w-[240px] px-1">
            <Link
              to="/"
              className={`flex flex-col items-center justify-center px-2 py-1 w-[56px] h-[46px] rounded-full transition-all duration-300 transform active:scale-95 ${location.pathname === '/' ? 'bg-zinc-100 text-black shadow-[0_4px_12px_rgba(255,255,255,0.3)]' : 'text-zinc-400 hover:text-white hover:bg-white/10'}`}
            >
              <Home className="w-3.5 h-3.5 mb-0.5" strokeWidth={location.pathname === '/' ? 2 : 1.5} />
              <span className="text-[9px] tracking-wide font-medium">Home</span>
            </Link>

            <div className="flex flex-col items-center justify-center px-2 h-[46px]">
               <Database className={`w-3.5 h-3.5 mb-0.5 ${hasRegistration ? 'text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'text-zinc-500'}`} strokeWidth={1.5} />
               <span className="text-[9px] tracking-wide font-medium text-zinc-400 whitespace-nowrap">
                 {hasRegistration ? 'Registered' : hasData ? 'Data Loaded' : 'Awaiting Data'}
               </span>
            </div>

            <button
              type="button"
              className="flex flex-col items-center justify-center px-2 py-1 w-[56px] h-[46px] rounded-full transition-all duration-300 transform active:scale-95 text-zinc-400 hover:text-white hover:bg-white/10 focus:outline-none"
              onClick={() => setMobileOpen((open) => !open)}
            >
              {mobileOpen ? <X className="w-3.5 h-3.5 mb-0.5" strokeWidth={1.5} /> : <Menu className="w-3.5 h-3.5 mb-0.5" strokeWidth={1.5} />}
              <span className="text-[9px] tracking-wide font-medium">Menu</span>
            </button>
          </nav>
        </div>
      </div>

      <PipelineStepper result={result} session={session} />

      {mobileOpen && (
        <div ref={mobileMenuRef} id={mobileMenuId} className="lg:hidden fixed inset-x-3 top-[6rem] z-40 pointer-events-auto sm:inset-x-6">
          <div className="relative bg-[#0a0a0a]/95 backdrop-blur-2xl border border-white/10 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] p-4 sm:p-6 max-h-[calc(100vh-8rem)] overflow-y-auto">
            <nav aria-label="Mobile navigation" className="flex flex-col space-y-2">
              {navLinks.map((link) => {
                const isActive = location.pathname === link.path;
                const Icon = link.icon;
                return (
                  <Link
                    key={link.name}
                    to={link.path}
                    onClick={() => setMobileOpen(false)}
                    aria-current={isActive ? 'page' : undefined}
                    className={`flex items-center gap-4 px-5 py-4 rounded-[1.5rem] transition-all duration-300 ${isActive ? 'bg-zinc-100 text-black shadow-md' : 'text-zinc-400 hover:text-white hover:bg-white/5'}`}
                  >
                    <Icon className="w-5 h-5" strokeWidth={isActive ? 2 : 1.5} />
                    <span className="text-sm font-semibold tracking-wide">{link.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      )}
    </header>
  );
}


