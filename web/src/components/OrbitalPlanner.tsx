import { useState, useMemo, useRef, useEffect, type ChangeEvent, type KeyboardEvent, type MouseEvent } from 'react';

interface OrbitalPlannerProps {
  onClose: () => void;
  onExecute: (x: number, z: number) => void;
}

const Spacecraft = ({ x, y, rot }: {x:number, y:number, rot:number}) => (
  <g transform={`translate(${x}, ${y}) rotate(${rot}) scale(0.8)`}>
    {/* Solar Panels */}
    <rect x="-24" y="-4" width="14" height="8" fill="#52525b" rx="1" />
    <rect x="10" y="-4" width="14" height="8" fill="#52525b" rx="1" />
    {/* Legs */}
    <line x1="-6" y1="8" x2="-12" y2="16" stroke="#94a3b8" strokeWidth="2" />
    <line x1="6" y1="8" x2="12" y2="16" stroke="#94a3b8" strokeWidth="2" />
    {/* Body */}
    <rect x="-8" y="-8" width="16" height="16" fill="#cbd5e1" rx="2" />
    <rect x="-6" y="-6" width="12" height="6" fill="#94a3b8" rx="1" />
  </g>
);

const LabelBox = ({ x, y, title, sub, width=110 }: {x:number, y:number, title:string, sub?:string, width?:number}) => (
  <g transform={`translate(${x}, ${y})`}>
    <rect x="0" y="0" width={width} height={sub ? "40" : "28"} fill="#09090b" stroke="#3f3f46" strokeWidth="1.5" rx="6" />
    <text x="10" y={sub ? "16" : "18"} fill="#f4f4f5" fontSize="11" fontWeight="bold" fontFamily="sans-serif">{title}</text>
    {sub && <text x="10" y="30" fill="#a1a1aa" fontSize="10" fontFamily="sans-serif">{sub}</text>}
  </g>
);

export function OrbitalPlanner({ onClose, onExecute }: OrbitalPlannerProps) {
  const [vx, setVx] = useState(0);
  const [vz, setVz] = useState(0);
  const [deorbitData, setDeorbitData] = useState<{x: number, y: number, orbit: number} | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const selectOrbit = (orbitIndex: number, x?: number, y?: number) => {
    setDeorbitData({ x: x ?? 380, y: y ?? 350, orbit: orbitIndex });
  };

  const handleOrbitClick = (e: MouseEvent<SVGElement>, orbitIndex: number) => {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const screenMatrix = svg.getScreenCTM();
    if (!screenMatrix) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const cursorPt = pt.matrixTransform(screenMatrix.inverse());
    selectOrbit(orbitIndex, cursorPt.x, cursorPt.y);
  };

  const handleOrbitKeyDown = (e: KeyboardEvent<SVGElement>, orbitIndex: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      selectOrbit(orbitIndex);
    }
  };

  const focusRing = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/80';
  const panelId = 'trajectory-override-panel';
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) onClose();
  };
  const handleXChange = (e: ChangeEvent<HTMLInputElement>) => setVx(parseFloat(e.target.value));
  const handleZChange = (e: ChangeEvent<HTMLInputElement>) => setVz(parseFloat(e.target.value));

  const DESCENT_TIME = 15; 
  const targetX = vx * DESCENT_TIME;
  const targetZ = vz * DESCENT_TIME;

  // Visual layout mapping
  const moonCx = 440;
  const moonCy = 350;
  const moonR = 120;

  // The landing blue zone center
  const lzCx = 345;
  const lzCy = 265;

  const visualTargetX = lzCx + (targetX * 0.15); 
  const visualTargetY = lzCy - (targetZ * 0.15); 

  // Generate some static stars for the background
  // Generate multi-stage spiral trajectory based on which orbit was clicked
  let trajectoryPath = "";
  if (deorbitData) {
    const { x: startX, y: startY, orbit } = deorbitData;
    
    // The injected velocity warps the orbital transfer centers! 
    // This makes the entire path morph from the departure point, rather than just shifting the final landing coordinate.
    const warpCenterX = 380 + (vx * 2);
    const warpCenterY = 350 + (vz * 2);
    
    const dx = startX - 380;
    const dy = startY - 350;

    if (orbit === 3) {
      // Direct descent: we manipulate the arc radii slightly based on velocity to warp the curve
      const rX = 130 + (vx * 1.5);
      const rY = 115 + (vz * 1.5);
      trajectoryPath = `M ${startX} ${startY} A ${Math.max(50, rX)} ${Math.max(50, rY)} -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 2) {
      // 1 transfer orbit -> Orbit 3 -> Surface
      const midX = warpCenterX - dx * 0.7;
      const midY = warpCenterY - dy * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 170 130 -10 0 1 ${midX} ${midY} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    } else if (orbit === 1) {
      // 2 transfer orbits -> Orbit 2 -> Orbit 3 -> Surface
      const mid1X = warpCenterX - dx * 0.74;
      const mid1Y = warpCenterY - dy * 0.74;
      const dx2 = mid1X - warpCenterX;
      const dy2 = mid1Y - warpCenterY;
      const mid2X = warpCenterX - dx2 * 0.7;
      const mid2Y = warpCenterY - dy2 * 0.7;
      trajectoryPath = `M ${startX} ${startY} A 230 160 -15 0 1 ${mid1X} ${mid1Y} A 170 130 -10 0 1 ${mid2X} ${mid2Y} A 130 115 -5 0 1 ${visualTargetX} ${visualTargetY}`;
    }
  }

  const stars = useMemo(() => Array.from({length: 80}).map(() => ({
    x: Math.random() * 600, 
    y: Math.random() * 600, 
    r: Math.random() * 1.2,
    o: 0.2 + Math.random() * 0.5
  })), []);

  return (
    <div
      className="absolute inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#050505]/80 backdrop-blur-xl p-3 sm:p-8 font-sans"
      role="dialog"
      aria-modal="true"
      aria-labelledby={panelId}
      onMouseDown={handleBackdropClick}
    >
      <div className="border border-white/10 bg-[#0a0a0a] w-full max-w-6xl min-h-[min(720px,calc(100vh-1.5rem))] max-h-[calc(100vh-1.5rem)] sm:h-full flex flex-col lg:flex-row shadow-2xl rounded-2xl overflow-hidden">
        
        {/* LEFT PANEL: 2D Interactive Orbital Map */}
        <div className="flex-grow relative border-r border-white/5 bg-[#09090b] overflow-hidden">
          <h2 id={panelId} className="absolute top-4 left-4 sm:top-6 sm:left-6 text-zinc-300 font-bold tracking-wide text-base sm:text-lg z-10 drop-shadow-md">Lunar Orbital Dynamics Planner</h2>
          
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox="0 0 600 600"
            className="absolute inset-0"
            aria-label="Interactive lunar orbit map"
            role="img"
          >
            <defs>
              <radialGradient id="moonGlow" cx="30%" cy="30%" r="70%">
                <stop offset="60%" stopColor="#000" stopOpacity="0" />
                <stop offset="100%" stopColor="#000" stopOpacity="0.8" />
              </radialGradient>
              <clipPath id="moonClip">
                <circle cx={moonCx} cy={moonCy} r={moonR} />
              </clipPath>
            </defs>

            {/* Stars */}
            {stars.map((s, i) => (
              <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#fff" opacity={s.o} />
            ))}

            {/* Orbit 1 (Outer) */}
            <ellipse cx="280" cy="350" rx="270" ry="180" transform="rotate(-15 280 350)" fill="none" stroke="#52525b" strokeWidth="3" />
            <ellipse cx="280" cy="350" rx="270" ry="180" transform="rotate(-15 280 350)" fill="none" stroke="transparent" strokeWidth="20" className={`cursor-crosshair hover:stroke-white/10 transition-colors ${focusRing}`} role="button" tabIndex={0} aria-label="Select lunar orbit 1" onClick={(e) => handleOrbitClick(e, 1)} onKeyDown={(e) => handleOrbitKeyDown(e, 1)} />
            
            {/* Orbit 2 (Middle) */}
            <ellipse cx="340" cy="350" rx="200" ry="150" transform="rotate(-10 340 350)" fill="none" stroke="#52525b" strokeWidth="3" />
            <ellipse cx="340" cy="350" rx="200" ry="150" transform="rotate(-10 340 350)" fill="none" stroke="transparent" strokeWidth="20" className={`cursor-crosshair hover:stroke-white/10 transition-colors ${focusRing}`} role="button" tabIndex={0} aria-label="Select lunar orbit 2" onClick={(e) => handleOrbitClick(e, 2)} onKeyDown={(e) => handleOrbitKeyDown(e, 2)} />
            
            {/* Orbit 3 (Inner) */}
            <ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="#52525b" strokeWidth="3" />
            {/* Invisible thicker overlay for easier clicking */}
            <ellipse cx="400" cy="350" rx="140" ry="125" transform="rotate(-5 400 350)" fill="none" stroke="transparent" strokeWidth="20" className={`cursor-crosshair hover:stroke-white/10 transition-colors ${focusRing}`} role="button" tabIndex={0} aria-label="Select lunar orbit 3" onClick={(e) => handleOrbitClick(e, 3)} onKeyDown={(e) => handleOrbitKeyDown(e, 3)} />

            {/* Spacecrafts on orbits */}
            <Spacecraft x={220} y={190} rot={30} /> {/* Orbit 1 */}
            <Spacecraft x={300} y={210} rot={15} /> {/* Orbit 2 */}

            {/* Moon Rendering */}
            <g clipPath="url(#moonClip)">
              {/* Fallback gray base */}
              <circle cx={moonCx} cy={moonCy} r={moonR} fill="#cbd5e1" />
              {/* Realistic moon texture */}
              <image href="/moon_map.png" x={moonCx - moonR} y={moonCy - moonR} width={moonR*2} height={moonR*2} preserveAspectRatio="xMidYMid slice" opacity="0.8" />
              {/* 3D shadow gradient */}
              <circle cx={moonCx} cy={moonCy} r={moonR} fill="url(#moonGlow)" />
            </g>

            {/* Landing Area Highlight (Blue ellipse on surface) */}
            <ellipse cx={lzCx} cy={lzCy} rx="45" ry="20" transform={`rotate(-25 ${lzCx} ${lzCy})`} fill="#3f3f46" opacity="0.6" />

            {deorbitData && (
              <g>
                {/* Deorbit Burn Point */}
                <g transform={`translate(${deorbitData.x}, ${deorbitData.y})`}>
                  <circle cx="0" cy="0" r="4" fill="#e4e4e7" />
                  <circle cx="0" cy="0" r="8" fill="none" stroke="#e4e4e7" strokeWidth="1.5" opacity="0.6" />
                  {/* Delta-V Burn Vector Indicator */}
                  {(vx !== 0 || vz !== 0) && (
                    <g>
                      <line x1="0" y1="0" x2={vx * 2.5} y2={vz * 2.5} stroke="#a1a1aa" strokeWidth="2" />
                      <circle cx={vx * 2.5} cy={vz * 2.5} r="1.5" fill="#a1a1aa" />
                    </g>
                  )}
                  <text x="-45" y="-12" fill="#e4e4e7" fontSize="9" fontWeight="bold" opacity="0.8">DEORBIT</text>
                  {(vx !== 0 || vz !== 0) && <text x="-45" y="20" fill="#a1a1aa" fontSize="8" fontWeight="bold" opacity="0.8">?v BURN</text>}
                </g>
                {/* Final Descent Trajectory (dynamic multi-stage spiral) */}
                <path 
                  d={trajectoryPath} 
                  fill="none" 
                  stroke="#e4e4e7" 
                  strokeWidth="3" 
                  strokeDasharray="4 4"
                />
              </g>
            )}

            {/* Landing Target Reticle */}
            <g transform={`translate(${visualTargetX}, ${visualTargetY})`}>
              <circle cx="0" cy="0" r="5" fill="#e4e4e7" />
              <circle cx="0" cy="0" r="12" fill="none" stroke="#e4e4e7" strokeWidth="1.5" />
              <line x1="-16" y1="0" x2="16" y2="0" stroke="#e4e4e7" strokeWidth="1.5" />
              <line x1="0" y1="-16" x2="0" y2="16" stroke="#e4e4e7" strokeWidth="1.5" />
            </g>

            {/* Data Labels */}
            <LabelBox x={20} y={140} title="Lunar Orbit 1" width={95} />
            <LabelBox x={120} y={320} title="Lunar Orbit 2" width={95} />
            <LabelBox x={290} y={470} title="Lunar Orbit 3" width={95} />

            <LabelBox x={460} y={220} title="Landing Phase" sub="Target Active" width={110} />
          </svg>
        </div>

        {/* RIGHT PANEL: Controls */}
        <div className="w-full lg:w-[400px] max-h-full overflow-y-auto p-5 sm:p-8 flex flex-col justify-between gap-8 bg-zinc-950/80 z-10 shadow-2xl border-t lg:border-t-0 lg:border-l border-white/5">
          <div>
            <div className="flex justify-between items-center mb-8 pb-4 border-b border-white/5">
              <h3 className="text-zinc-300 font-semibold tracking-wide text-lg">Trajectory Override</h3>
              <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="Close trajectory override" className={`text-zinc-500 hover:text-white ${focusRing} transition-colors bg-white/5 hover:bg-white/10 w-8 h-8 rounded-full flex items-center justify-center`}>×</button>
            </div>

            <p className="text-sm text-zinc-500 mb-10 leading-relaxed font-medium">
              Use the orbital diversion parameters below to dynamically alter the descent trajectory. 
              The physics engine will recalculate the parabolic entry curve based on injected velocity.
            </p>

            <div className="mb-8">
              <label className="flex justify-between text-zinc-400 text-xs mb-3 font-semibold tracking-wide uppercase">
                <span>Cross-Track Vel (Vx)</span>
                <span className="font-mono text-zinc-300">{vx.toFixed(1)} m/s</span>
              </label>
              <input
                type="range"
                aria-label="Cross-track velocity"
                min="-15"
                max="15"
                step="0.5"
                value={vx}
                onChange={handleXChange}
                className={`w-full accent-zinc-300 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer ${focusRing}`}
              />
              <div className="text-[10px] text-zinc-600 font-mono mt-1 text-right">Offset: {targetX.toFixed(0)}m</div>
            </div>

            <div className="mb-10">
              <label className="flex justify-between text-zinc-400 text-xs mb-3 font-semibold tracking-wide uppercase">
                <span>Downrange Vel (Vz)</span>
                <span className="font-mono text-zinc-300">{vz.toFixed(1)} m/s</span>
              </label>
              <input
                type="range"
                aria-label="Downrange velocity"
                min="-15"
                max="15"
                step="0.5"
                value={vz}
                onChange={handleZChange}
                className={`w-full accent-zinc-300 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer ${focusRing}`}
              />
              <div className="text-[10px] text-zinc-600 font-mono mt-1 text-right">Offset: {targetZ.toFixed(0)}m</div>
            </div>

            <div className="p-5 border border-amber-500/20 bg-amber-500/5 rounded-xl">
              <h4 className="text-[11px] text-amber-500 font-bold tracking-widest uppercase mb-2">Awaiting Verification</h4>
              <p className="text-xs text-zinc-400 leading-relaxed font-medium">
                The 3D Raycaster will verify landing zone slope and altitude upon execution. 
                If the terrain exceeds 10° slope, the lander will crash.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => deorbitData && onExecute(targetX, targetZ)}
            disabled={!deorbitData}
            className={`w-full py-4 rounded-xl font-semibold tracking-wide text-sm transition-all shadow-lg ${focusRing} ${deorbitData ? 'bg-zinc-200 hover:bg-white text-black' : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'}`}
          >
            {deorbitData ? 'Execute Divert Maneuver' : 'Select Deorbit Point First'}
          </button>
        </div>

      </div>
    </div>
  );
}
