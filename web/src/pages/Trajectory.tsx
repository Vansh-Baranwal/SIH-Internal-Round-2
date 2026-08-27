import { useMission } from '../context/MissionContext';
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
  const m6 = result.m6 || p.m6;
  const m5A = result.m5?.lander_A || p.m5?.lander_A;

  return (
    <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
      <div className="flex justify-between items-end mb-16 border-b border-white/5 pb-6">
        <div>
          <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Trajectory Analysis</h1>
          <p className="text-zinc-500 font-medium tracking-wide">Phase VI: Reachability & Descent Validation</p>
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

