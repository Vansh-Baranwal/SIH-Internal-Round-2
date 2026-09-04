import { useMission } from '../context/useMission';
import { useNavigate } from 'react-router-dom';

export function Trajectory() {
  const { result } = useMission();
  const navigate = useNavigate();

  if (!result) {
    return (
      <div className="flex-grow flex items-center justify-center">
        <div className="text-zinc-500 font-medium tracking-widest text-sm uppercase">
          Data Unavailable. Please process a dataset first.
        </div>
      </div>
    );
  }

  const p = result.pipeline;
  const m6 = result.m6 || p?.m6;
  const m5A = result.m5?.lander_A || p?.m5?.lander_A;

  // Same shape of gap as HazardMap.tsx / LandingSites.tsx: `result` can
  // exist with no M6 trajectory computed yet (e.g. straight off
  // Registration.tsx). Previously this silently rendered "0" / "0s" as if
  // those were real computed values instead of missing data.
  const hasTrajectoryData = !!m6?.trajectory;

  if (!hasTrajectoryData) {
    return (
      <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
        <div className="flex justify-between items-end mb-16 border-b border-white/5 pb-6">
          <div>
            <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Trajectory Analysis</h1>
            <p className="text-zinc-500 font-medium tracking-wide">Phase VI: Reachability &amp; Descent Validation</p>
          </div>
        </div>

        <div className="border border-amber-500/20 bg-amber-500/5 px-8 py-12 flex flex-col items-center text-center gap-5">
          {result.source_image_url && (
            <div className="w-full max-w-md h-56 bg-[#030303] border border-white/10 flex items-center justify-center overflow-hidden mb-2">
              <img
                src={result.source_image_url}
                alt="Registered source"
                className="max-h-full max-w-full object-contain opacity-80"
              />
            </div>
          )}
          <p className="text-amber-500 text-xs font-bold tracking-widest uppercase">
            {result.from_registration ? 'Registered Image Ready — Trajectory Not Yet Computed' : 'No Trajectory Data Yet'}
          </p>
          <p className="text-zinc-500 text-sm max-w-lg leading-relaxed">
            {result.from_registration
              ? 'This image came from the Multi-Sensor Registration Cockpit. Reachability and descent trajectory (M6) depend on a selected landing site from M5 — that step hasn\'t run yet.'
              : 'Select a feasible landing site first — trajectory analysis depends on its coordinates.'}
          </p>
          <button
            onClick={() => navigate(result.from_registration ? '/landing-sites' : '/imagery')}
            className="mt-2 bg-zinc-200 hover:bg-white text-black font-bold tracking-widest text-xs uppercase py-3 px-6 transition-colors"
          >
            {result.from_registration ? '← Back to Site Evaluation' : '← Go to Imagery'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
      <div className="flex justify-between items-end mb-16 border-b border-white/5 pb-6">
        <div>
          <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Trajectory Analysis</h1>
          <p className="text-zinc-500 font-medium tracking-wide">
            Phase VI: Reachability &amp; Descent Validation
            {result.from_registration && <span className="text-zinc-600"> · Source: Registration Cockpit</span>}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-16 mb-20">
        <div className="border-l border-white/5 pl-8">
            <h2 className="text-zinc-300 font-bold tracking-widest uppercase mb-10 text-xs">Mission Parameters</h2>
            <div className="space-y-8 text-sm font-medium">
                <div>
                    <p className="text-zinc-600 tracking-widest uppercase text-[10px] font-bold mb-2">Selected Lander</p>
                    <p className="text-white font-bold">{m5A?.name || 'N/A'}</p>
                </div>
                <div>
                    <p className="text-zinc-600 tracking-widest uppercase text-[10px] font-bold mb-2">Target Coordinates</p>
                    <p className="text-zinc-300 font-mono">
                      {m6?.trajectory?.selected_site?.x || 0}, {m6?.trajectory?.selected_site?.y || 0}
                    </p>
                </div>
                <div>
                    <p className="text-zinc-600 tracking-widest uppercase text-[10px] font-bold mb-2">Time of Flight</p>
                    <p className="text-zinc-300 font-mono">{m6?.trajectory?.time_of_flight || 0}s</p>
                </div>
            </div>
        </div>
        

      </div>

      <div className="flex border-t border-white/5 pt-12">
        <button 
          onClick={() => navigate('/simulation')}
          className="bg-zinc-200 hover:bg-white text-black font-bold tracking-widest uppercase text-sm py-4 px-12 transition-colors w-full md:w-auto"
        >
          Initialize 3D Physics Simulation →
        </button>
      </div>
    </div>
  );
}