import { useState, useEffect, Suspense, useCallback, type ChangeEvent } from 'react';
import { useMission } from '../context/useMission';
import { useNavigate } from 'react-router-dom';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Terrain } from '../components/Terrain';
import { Lander } from '../components/Lander';
import { HUD } from '../components/HUD';
import { OrbitalPlanner } from '../components/OrbitalPlanner';
import { Sun, Aperture, ArrowRight } from 'lucide-react';
import * as THREE from 'three';

interface TrajectoryPoint {
  t: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  pitch: number;
  yaw: number;
  roll: number;
}

// Converts azimuth/elevation into a directional-light position on a sphere
// around the terrain, so the sun-angle sliders drive real scene lighting
// instead of just being a number readout. Mirrors the SunSimulationParams
// shape used by the Registration cockpit so the two stay comparable.
function sunPositionFromAngles(azimuthDeg: number, elevationDeg: number, distance = 3000) {
  const az = THREE.MathUtils.degToRad(azimuthDeg);
  const el = THREE.MathUtils.degToRad(elevationDeg);
  const x = distance * Math.cos(el) * Math.sin(az);
  const y = distance * Math.sin(el);
  const z = distance * Math.cos(el) * Math.cos(az);
  return [x, y, z] as [number, number, number];
}

// A helper component inside the Canvas that can raycast the 3D terrain
function TerrainRaycaster({ command, onResult }: { command: {x: number, z: number, id: number} | null, onResult: (x: number, y: number, z: number, isSafe: boolean) => void }) {
  const { scene } = useThree();
  
  useEffect(() => {
    if (command) {
      const { x, z } = command;
      const raycaster = new THREE.Raycaster();
      // Cast a ray from high above the map directly downward
      raycaster.set(new THREE.Vector3(x, 5000, z), new THREE.Vector3(0, -1, 0));
      
      const intersects = raycaster.intersectObject(scene, true);
      
      let altitude = 0;
      let isSafe = true;

      if (intersects.length > 0) {
        // Find the first intersection that is the actual terrain (not a marker or lander)
        const hit = intersects.find(i => i.object.type === 'Mesh' && !i.object.name.includes('marker'));
        if (hit) {
            altitude = hit.point.y;
            if (hit.face) {
                const normal = hit.face.normal.clone();
                const normalMatrix = new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld);
                normal.applyMatrix3(normalMatrix).normalize();
                
                const slope = Math.acos(Math.abs(normal.y)) * (180 / Math.PI);
                isSafe = slope <= 10.0;
            }
        }
      }
      
      onResult(x, altitude, z, isSafe);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command?.id, scene]);
  
  return null;
}

// Illustrative placeholder for "where the sensor is looking" — there's no
// real OHRC/TMC pose data wired up yet, so this draws a fixed wireframe
// frustum above the map center rather than a geometrically accurate one.
// Swap the position/rotation for real sensor pose once M1 exposes it.
function SensorFrustum({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <group position={[0, 900, 0]} rotation={[Math.PI, 0, 0]}>
      <mesh>
        <coneGeometry args={[260, 900, 4, 1, true]} />
        <meshBasicMaterial color="#38bdf8" wireframe transparent opacity={0.5} />
      </mesh>
    </group>
  );
}

// Grabs a still frame of the live WebGL canvas on command, used to feed the
// Counterfactual Sun Simulator's output into the Registration cockpit as a
// synthetic dataset. Requires `gl={{ preserveDrawingBuffer: true }}` on the
// parent <Canvas>, otherwise toDataURL() can return a blank frame.
function CounterfactualCapture({ command, onCaptured }: { command: { id: number } | null; onCaptured: (dataUrl: string) => void }) {
  const { gl, scene, camera } = useThree();

  useEffect(() => {
    if (command) {
      gl.render(scene, camera);
      onCaptured(gl.domElement.toDataURL('image/png'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command?.id]);

  return null;
}

export function Simulation() {
  const { result, session, startCounterfactualSession } = useMission();
  const navigate = useNavigate();

  const [target, setTarget] = useState<{x: number, y: number, z: number} | null>(null);
  const [trajectory, setTrajectory] = useState<{ points: TrajectoryPoint[] } | null>(null);
  const [animationTime, setAnimationTime] = useState(0);
  const [status, setStatus] = useState('STANDBY');
  const [isCrashing, setIsCrashing] = useState(false);
  const [telemetry, setTelemetry] = useState<TrajectoryPoint | null>(null);
  const [isPlannerOpen, setIsPlannerOpen] = useState(false);

  // Digital-twin controls — independent of the legacy hazard/landing flow.
  const [sunAngle, setSunAngle] = useState({ azimuthDeg: 135, elevationDeg: 45 });
  const [showFrustum, setShowFrustum] = useState(false);
  const [captureCommand, setCaptureCommand] = useState<{ id: number } | null>(null);

  // State to trigger the 3D raycaster from the 2D planner
  const [divertCommand, setDivertCommand] = useState<{x: number, z: number, id: number} | null>(null);
  
  useEffect(() => {
    if (result?.pipeline?.binary_url) {
        setStatus('AWAITING TARGET');
    }
  }, [result]);

  const initiateDescent = (x: number, altitude: number, z: number, isSafe: boolean) => {
    setTarget({x, y: altitude, z});
    
    if (isSafe) {
        setStatus('DESCENDING (SAFE TRAJECTORY)');
        setIsCrashing(false);
    } else {
        setStatus('WARNING: STEEP SLOPE DETECTED - CRASH IMMINENT');
        setIsCrashing(true);
    }
    
    const points = [];
    const steps = 600; 
    
    const startAltitude = Math.max(altitude + 400, 400);
    const startX = x + 600;      
    const startY = -z + 400;     
    const initialVx = 1680.0; 
    
    for(let i=0; i<=steps; i++) {
        const t = (i / steps) * 10; 
        const progress = i / steps; 
        
        let ease = progress;
        let pitch = 0, yaw = 0, roll = 0;
        let currentAltitude = 0;
        let currentX = x;
        let currentY = -z;
        let vx = 0, vy = 0, vz = 0;

        if (isSafe) {
            ease = 1 - (1 - progress) * (1 - progress); 
            
            currentX = startX - (startX - x) * ease;
            currentY = startY - (startY - (-z)) * ease;
            currentAltitude = startAltitude - (startAltitude - altitude) * ease;
            
            pitch = (1 - ease) * (Math.PI / 3); 
            yaw = Math.atan2((startX - x), (startY - (-z))) * 0.5; 
            roll = Math.cos(progress * Math.PI * 2) * 0.02; 
            
            vx = initialVx * (1 - progress); 
            vy = (startAltitude - altitude) * -0.5 * (1 - progress); 
        } else {
            if (progress < 0.9) {
                const p = progress / 0.9;
                ease = p * p * p; 
                
                const horizEase = p * p; 
                
                currentX = startX - (startX - x) * horizEase;
                currentY = startY - (startY - (-z)) * horizEase;
                currentAltitude = startAltitude - (startAltitude - altitude) * ease;
                
                pitch = p * Math.PI * 6; 
                roll = p * Math.PI * 4;
                yaw = p * Math.PI * 2;
                
                vx = initialVx * (1 - p * 0.2); 
                vy = (startAltitude - altitude) * -2.0 * p; 
            } else {
                const p = (progress - 0.9) / 0.1;
                const bounce = Math.abs(Math.sin(p * Math.PI * 2)) * 30 * (1 - p);
                
                currentX = x - (startX - x) * 0.1 * p;
                currentY = -z - (startY - (-z)) * 0.1 * p;
                currentAltitude = altitude + bounce;
                
                pitch = (0.9 * Math.PI * 6) + (p * Math.PI / 2);
                roll = (0.9 * Math.PI * 4) + (p * Math.PI / 2);
                
                vx = initialVx * 0.2 * (1 - p); 
                vy = bounce > 0.1 ? 15 : 0;
            }
        }
        
        points.push({
            t: t,
            x: currentX, 
            y: currentY, 
            z: currentAltitude, 
            vx, vy, vz,
            pitch, yaw, roll
        });
    }
    
    setTrajectory({ points });
    setAnimationTime(0);
  };

  const handleTerrainClick = (x: number, altitude: number, z: number, isSafe: boolean) => {
    initiateDescent(x, altitude, z, isSafe);
  };

  const handlePlannerExecute = (x: number, z: number) => {
    // Instead of immediately executing, we send a command to the 3D Raycaster inside the Canvas.
    // The Raycaster will find the exact 3D altitude and slope, and then call initiateDescent!
    setDivertCommand({ x, z, id: Date.now() });
    setIsPlannerOpen(false);
  };

  const syncSunFromRegistration = useCallback(() => {
    if (session.sunSimulation) {
      setSunAngle({
        azimuthDeg: session.sunSimulation.azimuthDeg,
        elevationDeg: session.sunSimulation.elevationDeg,
      });
    }
  }, [session.sunSimulation]);

  const handleGenerateCounterfactual = useCallback(() => {
    setCaptureCommand({ id: Date.now() });
  }, []);

  const handleCaptured = useCallback(
    (dataUrl: string) => {
      startCounterfactualSession({ dataUrl, azimuthDeg: sunAngle.azimuthDeg, elevationDeg: sunAngle.elevationDeg });
      navigate('/registration');
    },
    [startCounterfactualSession, sunAngle, navigate],
  );

  const TimeUpdater = () => {
    useFrame((_state, delta) => {
        if (status.includes('DESCENDING') || status.includes('CRASH IMMINENT')) {
            setAnimationTime(prev => {
                const speed = 1.5; 
                const next = prev + delta * speed; 
                if (next > 10) {
                    if (isCrashing) {
                        setStatus('CATASTROPHIC FAILURE (CRASH)');
                    } else {
                        setStatus('TOUCHDOWN - NOMINAL');
                    }
                    return 10;
                }
                return next;
            });
        }
    });
    return null;
  };

  if (!result) {
    // Loosened per 01_EXISTING_PROJECT_AND_TARGET_ARCHITECTURE.md §3: the 3D
    // system evolves into a standalone digital-twin viewer, so it shouldn't
    // require the legacy hazard/landing pipeline to have already run.
    // Trajectory/HUD/Orbital Planner still need a `result`-derived target,
    // so those stay gated below — only this branch renders without one.
    return (
      <div className="w-full relative bg-black flex flex-col pt-24" style={{ height: '100vh', overflow: 'hidden' }}>
        <div className="absolute inset-0 pt-24 w-full h-full z-0">
          <Canvas camera={{ position: [0, 600, 400], fov: 60, far: 50000 }} gl={{ preserveDrawingBuffer: true }}>
            <CounterfactualCapture command={captureCommand} onCaptured={handleCaptured} />
            <color attach="background" args={['#050505']} />
            <ambientLight intensity={5.0} />
            <directionalLight position={sunPositionFromAngles(sunAngle.azimuthDeg, sunAngle.elevationDeg)} intensity={10.0} />
            <Suspense fallback={null}>
              <Terrain />
            </Suspense>
            <SensorFrustum visible={showFrustum} />
            <OrbitControls target={[0, 0, 0]} maxPolarAngle={Math.PI / 2.1} />
          </Canvas>
        </div>

        <DigitalTwinPanel
          sunAngle={sunAngle}
          onSunAngleChange={setSunAngle}
          canSync={!!session.sunSimulation}
          onSync={syncSunFromRegistration}
          showFrustum={showFrustum}
          onToggleFrustum={() => setShowFrustum((v) => !v)}
          onGenerateCounterfactual={handleGenerateCounterfactual}
        />

        <div className="absolute bottom-6 left-6 z-10 text-zinc-500 text-xs font-bold tracking-widest uppercase">
          Digital Twin Mode — run the hazard pipeline for trajectory tools
        </div>
      </div>
    );
  }

  return (
    <div className="w-full relative bg-black flex flex-col pt-24" style={{ height: '100vh', overflow: 'hidden' }}>
      
      {/* 3D Scene */}
      <div className="absolute inset-0 pt-24 w-full h-full cursor-crosshair z-0">
          <Canvas camera={{ position: [0, 600, 400], fov: 60, far: 50000 }} gl={{ preserveDrawingBuffer: true }}>
            <TimeUpdater />
            
            <TerrainRaycaster 
                command={divertCommand} 
                onResult={(x, alt, z, isSafe) => initiateDescent(x, alt, z, isSafe)} 
            />
            <CounterfactualCapture command={captureCommand} onCaptured={handleCaptured} />

            <color attach="background" args={['#050505']} />
            <ambientLight intensity={5.0} />
            <directionalLight position={sunPositionFromAngles(sunAngle.azimuthDeg, sunAngle.elevationDeg)} intensity={10.0} />
            
            <Suspense fallback={null}>
                <Terrain onClick={handleTerrainClick} target={target} />
            </Suspense>
            
            <Suspense fallback={null}>
                {trajectory && (
                    <Lander 
                      trajectory={trajectory} 
                      animationTime={animationTime} 
                      onUpdateTelemetry={(point) =>
                        setTelemetry({
                          ...point,
                          pitch: point.pitch ?? 0,
                          yaw: point.yaw ?? 0,
                          roll: point.roll ?? 0,
                        })
                      }
                    />
                )}
            </Suspense>

            <SensorFrustum visible={showFrustum} />
            
            <OrbitControls target={[0, 0, 0]} maxPolarAngle={Math.PI / 2.1} />
          </Canvas>
      </div>

      <DigitalTwinPanel
        sunAngle={sunAngle}
        onSunAngleChange={setSunAngle}
        canSync={!!session.sunSimulation}
        onSync={syncSunFromRegistration}
        showFrustum={showFrustum}
        onToggleFrustum={() => setShowFrustum((v) => !v)}
        onGenerateCounterfactual={handleGenerateCounterfactual}
      />

      <HUD 
        telemetry={telemetry} 
        status={status} 
        target={target} 
        isCrashing={isCrashing} 
        animationTime={animationTime} 
        onOpenPlanner={() => setIsPlannerOpen(true)}
      />

      {isPlannerOpen && (
        <OrbitalPlanner 
            onClose={() => setIsPlannerOpen(false)} 
            onExecute={handlePlannerExecute} 
        />
      )}
    </div>
  );
}

function DigitalTwinPanel({
  sunAngle,
  onSunAngleChange,
  canSync,
  onSync,
  showFrustum,
  onToggleFrustum,
  onGenerateCounterfactual,
}: {
  sunAngle: { azimuthDeg: number; elevationDeg: number };
  onSunAngleChange: (next: { azimuthDeg: number; elevationDeg: number }) => void;
  canSync: boolean;
  onSync: () => void;
  showFrustum: boolean;
  onToggleFrustum: () => void;
  onGenerateCounterfactual: () => void;
}) {
  return (
    // Positioned left, below HUD's Flight Dynamics box (which is always
    // present, top-left, roughly ~200px tall) rather than top-right, where
    // it previously collided with HUD's trajectory-plot box whenever a
    // target was set mid-descent. Left-top only ever has that one HUD
    // element regardless of state, so stacking below it is deterministic.
    <div className="absolute top-64 left-3 right-3 sm:left-6 sm:right-auto z-10 p-4 sm:p-5 rounded-2xl border border-white/10 backdrop-blur-xl shadow-2xl bg-[#0a0a0a]/60 w-auto sm:w-[280px] max-h-[calc(100vh-18rem)] overflow-y-auto pointer-events-auto">
      <div className="flex items-center gap-2 mb-5">
        <Sun className="w-3.5 h-3.5 text-zinc-500" />
        <h3 className="text-zinc-400 tracking-widest font-bold text-[10px] uppercase">Digital Twin Controls</h3>
      </div>

      <div className="space-y-5">
        <div>
          <div className="flex justify-between text-[10px] font-bold tracking-widest uppercase text-zinc-500 mb-2">
            <span>Azimuth</span>
            <span className="text-zinc-300">{sunAngle.azimuthDeg.toFixed(0)}°</span>
          </div>
          <input
            type="range"
            aria-label="Sun azimuth"
            min={0}
            max={360}
            value={sunAngle.azimuthDeg}
            onChange={(e: ChangeEvent<HTMLInputElement>) => onSunAngleChange({ ...sunAngle, azimuthDeg: Number(e.target.value) })}
            className="w-full accent-sky-400"
          />
        </div>

        <div>
          <div className="flex justify-between text-[10px] font-bold tracking-widest uppercase text-zinc-500 mb-2">
            <span>Elevation</span>
            <span className="text-zinc-300">{sunAngle.elevationDeg.toFixed(0)}°</span>
          </div>
          <input
            type="range"
            aria-label="Sun elevation"
            min={2}
            max={90}
            value={sunAngle.elevationDeg}
            onChange={(e: ChangeEvent<HTMLInputElement>) => onSunAngleChange({ ...sunAngle, elevationDeg: Number(e.target.value) })}
            className="w-full accent-sky-400"
          />
        </div>

        <button
          type="button"
          onClick={onSync}
          disabled={!canSync}
          className="w-full text-left text-[10px] font-bold tracking-widest uppercase text-zinc-500 hover:text-zinc-300 disabled:opacity-40 disabled:hover:text-zinc-500 transition-colors"
        >
          ↳ Sync from Registration
        </button>

        <label className="flex items-center gap-3 pt-1 cursor-pointer border-t border-white/5">
          <input type="checkbox" checked={showFrustum} onChange={onToggleFrustum} className="accent-sky-400 mt-3" />
          <span className="text-[10px] font-bold tracking-widest uppercase text-zinc-400 mt-3 flex items-center gap-1.5">
            <Aperture className="w-3 h-3" /> Show Sensor Frustum
          </span>
        </label>

        <button
          type="button"
          onClick={onGenerateCounterfactual}
          className="w-full flex items-center justify-center gap-2 bg-zinc-200 hover:bg-white text-black font-bold tracking-widest text-[10px] uppercase py-3 transition-colors"
        >
          Generate Counterfactual
          <ArrowRight className="w-3 h-3" />
        </button>
        <p className="text-[9px] text-zinc-600 tracking-wide leading-relaxed">
          Captures this view under the current sun angle and opens it as a synthetic dataset in a fresh Registration session.
        </p>
      </div>
    </div>
  );
}