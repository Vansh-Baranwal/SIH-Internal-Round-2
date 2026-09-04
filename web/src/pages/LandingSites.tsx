import { API_ROOT } from '../api/client';
import { useMission } from '../context/useMission';
import { useNavigate } from 'react-router-dom';

export function LandingSites() {
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
  const m5A = result.m5?.lander_A || p?.m5?.lander_A;
  const m5B = result.m5?.lander_B || p?.m5?.lander_B;
  const sitesUrl = result.sites_url || p?.sites_url || p?.m5?.sites_url;
  const sitesUrlA = result.sites_url_A || sitesUrl;
  const sitesUrlB = result.sites_url_B || sitesUrl;

  // Same gap as HazardMap.tsx: `result` can exist (e.g. right after
  // Registration.tsx's sendToMissionPipeline) with no M5 site-evaluation
  // data computed yet. Without this guard, sitesUrlA/B are undefined and
  // the <img> tags below would silently request
  // `${API_ROOT}undefined`.
  const hasSiteData = !!(sitesUrlA || sitesUrlB || m5A || m5B);

  if (!hasSiteData) {
    return (
      <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
        <div className="flex justify-between items-end mb-16 border-b border-white/5 pb-6">
          <div>
            <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Site Evaluation</h1>
            <p className="text-zinc-500 font-medium tracking-wide">Phase V: Dual Lander Feasibility Analysis</p>
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
            {result.from_registration ? 'Registered Image Ready — Site Evaluation Pending' : 'No Site Data Yet'}
          </p>
          <p className="text-zinc-500 text-sm max-w-lg leading-relaxed">
            {result.from_registration
              ? 'This image came from the Multi-Sensor Registration Cockpit. Dual-lander site feasibility (M5) still needs to run against the computed hazard layers before this view can render.'
              : 'Process a dataset through the hazard pipeline first — site evaluation depends on its slope and risk outputs.'}
          </p>
          <button
            onClick={() => navigate(result.from_registration ? '/hazard-map' : '/imagery')}
            className="mt-2 bg-zinc-200 hover:bg-white text-black font-bold tracking-widest text-xs uppercase py-3 px-6 transition-colors"
          >
            {result.from_registration ? '← Back to Hazard Analysis' : '← Go to Imagery'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
      <div className="flex justify-between items-end mb-16 border-b border-white/5 pb-6">
        <div>
          <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Site Evaluation</h1>
          <p className="text-zinc-500 font-medium tracking-wide">
            Phase V: Dual Lander Feasibility Analysis
            {result.from_registration && <span className="text-zinc-600"> · Source: Registration Cockpit</span>}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 mb-20">
        {/* Lander A Stats */}
        <div className="border-l border-white/5 pl-8">
            <h2 className="text-xl text-white font-bold tracking-wide mb-8 uppercase">{m5A?.name || 'LANDER A'}</h2>
            <div className="flex items-center space-x-4 mb-8">
                <span className="text-zinc-500 text-[10px] font-bold tracking-widest uppercase">Status</span>
                <span className={`text-xs font-bold tracking-widest uppercase ${m5A?.feasible_sites > 0 ? "text-green-500" : "text-zinc-400"}`}>
                    {m5A?.feasible_sites > 0 ? 'Feasible' : 'No Feasible Site'}
                </span>
            </div>
            <div className="flex flex-col gap-4 font-mono text-sm">
                {m5A?.best_site && (
                    <div>
                        <div className="text-[10px] font-sans font-bold tracking-widest text-zinc-600 uppercase mb-2">Prime Target</div>
                        <div className="text-zinc-300">
                          <span className="text-zinc-600">X:</span> {m5A.best_site.x_m}m <br/>
                          <span className="text-zinc-600">Y:</span> {m5A.best_site.y_m}m
                        </div>
                    </div>
                )}
            </div>
        </div>

        {/* Lander B Stats */}
        <div className="border-l border-white/5 pl-8">
            <h2 className="text-xl text-white font-bold tracking-wide mb-8 uppercase">{m5B?.name || 'APOLLO LEM (LEGACY)'}</h2>
            <div className="flex items-center space-x-4 mb-8">
                <span className="text-zinc-500 text-[10px] font-bold tracking-widest uppercase">Status</span>
                <span className={`text-xs font-bold tracking-widest uppercase ${m5B?.feasible_sites > 0 ? "text-green-500" : "text-zinc-400"}`}>
                    {m5B?.feasible_sites > 0 ? 'Feasible' : 'No Feasible Site'}
                </span>
            </div>
            <div className="flex flex-col gap-4 font-mono text-sm">
                {m5B?.best_site && (
                    <div>
                        <div className="text-[10px] font-sans font-bold tracking-widest text-zinc-600 uppercase mb-2">Prime Target</div>
                        <div className="text-zinc-300">
                          <span className="text-zinc-600">X:</span> {m5B.best_site.x_m}m <br/>
                          <span className="text-zinc-600">Y:</span> {m5B.best_site.y_m}m
                        </div>
                    </div>
                )}
                {!m5B?.best_site && (
                    <div>
                        <div className="text-[10px] font-sans font-bold tracking-widest text-zinc-600 uppercase mb-2">Analysis</div>
                        <div className="text-zinc-400 text-xs font-sans mt-1">Vehicle constraints exceed terrain safety margins.</div>
                    </div>
                )}
            </div>
        </div>
      </div>

      <div className="w-full mb-12">
        <div className="flex justify-between items-end mb-8 border-b border-white/5 pb-6">
            <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase">Safe Landing Zones Map</h3>
            <button 
                onClick={() => navigate('/trajectory')}
                className="bg-zinc-200 hover:bg-white text-black font-bold tracking-widest text-xs uppercase py-3 px-6 transition-colors"
            >
                Compute Trajectory →
            </button>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="border-l border-green-500/30 pl-8">
                <h4 className="text-green-400 font-bold tracking-widest text-xs uppercase mb-6">{m5A?.name || 'VIKRAM'} Feasible Zones</h4>
                <div className="w-full bg-[#030303] flex justify-center items-center py-8 min-h-[200px]">
                    {sitesUrlA ? (
                      <img
                        src={`${API_ROOT}${sitesUrlA}`}
                        alt="Safe Sites Map A"
                        className="max-h-[500px] object-contain"
                      />
                    ) : (
                      <span className="text-zinc-600 text-xs font-bold tracking-widest uppercase">No feasibility map computed</span>
                    )}
                </div>
            </div>

            <div className="border-l border-white/20 pl-8">
                <h4 className="text-zinc-300 font-bold tracking-widest text-xs uppercase mb-6">{m5B?.name || 'APOLLO LEM'} Feasible Zones</h4>
                <div className="w-full bg-[#030303] flex justify-center items-center py-8 min-h-[200px]">
                    {sitesUrlB ? (
                      <img
                        src={`${API_ROOT}${sitesUrlB}`}
                        alt="Safe Sites Map B"
                        className="max-h-[500px] object-contain"
                      />
                    ) : (
                      <span className="text-zinc-600 text-xs font-bold tracking-widest uppercase">No feasibility map computed</span>
                    )}
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}