import { useState, useEffect, Suspense, useCallback } from 'react';
import { useMission } from '../context/MissionContext';
import { ApiError, fetchMissionData } from '../api/client';
import { adaptM6TrajectoryForDigitalTwin, isM6Trajectory, type DigitalTwinTrajectory, type DigitalTwinTrajectoryPoint } from '../spatial/m6Trajectory';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Terrain, type TerrainViewState } from '../components/Terrain';
import { TmcCameraFrustum, type TmcCameraViewState } from '../components/TmcCameraFrustum';
import { OhrcCameraFrustum, type OhrcCameraViewState } from '../components/OhrcCameraFrustum';
import { IirsFootprint, type IirsFootprintViewState } from '../components/IirsFootprint';
import { LandmarkMarkers, type LandmarkViewState } from '../components/LandmarkMarkers';
import { HazardOverlay, type HazardViewState } from '../components/HazardOverlay';
import { SpectralOverlay, type SpectralViewState } from '../components/SpectralOverlay';
import { WaterIceOverlay, type WaterIceViewState } from '../components/WaterIceOverlay';
import { SunLight, SunControlPanel, DEFAULT_SUN_SCENARIO, getActiveSunConfig, type SunScenarioState } from '../components/SunControl';
import { Lander } from '../components/Lander';
import { HUD } from '../components/HUD';
import { OrbitalPlanner } from '../components/OrbitalPlanner';
import * as THREE from 'three';

// A helper component inside the Canvas that can raycast the 3D terrain
function TerrainRaycaster({ command, onResult }: { command: {x: number, z: number, id: number} | null, onResult: (x: number, y: number, z: number, isSafe: boolean) => void }) {
  const { scene } = useThree();
  
  useEffect(() => {
    if (command) {
      const { x, z } = command;
      const raycaster = new THREE.Raycaster();
      // Cast a ray from high above the map directly downward
      raycaster.set(new THREE.Vector3(x, 5000, z), new THREE.Vector3(0, -1, 0));
      
      // Planner picking only needs the DEM. Avoid traversing cameras, markers,
      // and every overlay on each command.
      const terrain = scene.getObjectByName('dem-terrain');
      const intersects = terrain ? raycaster.intersectObject(terrain, false) : [];
      
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

export function Simulation() {
  const { result } = useMission();
  
  const [target, setTarget] = useState<{x: number, y: number, z: number} | null>(null);
  const [trajectory, setTrajectory] = useState<DigitalTwinTrajectory | { source: 'legacy-simulation'; points: DigitalTwinTrajectoryPoint[] } | null>(null);
  const [m6State, setM6State] = useState<'loading' | 'ready' | 'unavailable' | 'invalid'>('loading');
  const [animationTime, setAnimationTime] = useState(0);
  const [status, setStatus] = useState('STANDBY');
  const [isCrashing, setIsCrashing] = useState(false);
  const [telemetry, setTelemetry] = useState<any>(null);
  const [isPlannerOpen, setIsPlannerOpen] = useState(false);
  const [terrainViewState, setTerrainViewState] = useState<TerrainViewState>({ kind: 'loading', message: 'Loading DEM terrain…' });
  const [tmcCameraViewState, setTmcCameraViewState] = useState<TmcCameraViewState>({ kind: 'loading', message: 'Loading TMC camera geometry...' });
  const [ohrcCameraViewState, setOhrcCameraViewState] = useState<OhrcCameraViewState>({ kind: 'loading', message: 'Loading OHRC camera geometry...' });
  const [iirsFootprintViewState, setIirsFootprintViewState] = useState<IirsFootprintViewState>({ kind: 'loading', message: 'Loading IIRS footprint...' });
  const [landmarkViewState, setLandmarkViewState] = useState<LandmarkViewState>({ kind: 'loading', message: 'Loading landmarks...' });
  const [hazardViewState, setHazardViewState] = useState<HazardViewState>({ kind: 'loading', message: 'Loading hazard overlays...' });
  const [spectralViewState, setSpectralViewState] = useState<SpectralViewState>({ kind: 'loading', message: 'Loading spectral overlays...' });
  const [waterIceViewState, setWaterIceViewState] = useState<WaterIceViewState>({ kind: 'loading', message: 'Loading water-ice overlay...' });
  const [sunScenario, setSunScenario] = useState<SunScenarioState>(DEFAULT_SUN_SCENARIO);
  const activeSunConfig = getActiveSunConfig(sunScenario);
  
  // State to trigger the 3D raycaster from the 2D planner
  const [divertCommand, setDivertCommand] = useState<{x: number, z: number, id: number} | null>(null);
  const [layerVisibility, setLayerVisibility] = useState({ tmc: true, ohrc: true, iirs: true, landmarks: true, hazards: true, spectral: true, waterIce: true });
  
  useEffect(() => {
    if (result?.pipeline?.binary_url) {
        setStatus('AWAITING TARGET');
    }
  }, [result]);

  useEffect(() => {
    let active = true;
    fetchMissionData()
      .then((mission) => {
        if (!active) return;
        if (!isM6Trajectory(mission.trajectory_primary)) {
          setM6State('invalid');
          return;
        }
        setTrajectory(adaptM6TrajectoryForDigitalTwin(mission.trajectory_primary));
        setM6State('ready');
        setAnimationTime(0);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setM6State(error instanceof ApiError && error.kind === 'response' ? 'invalid' : 'unavailable');
      });
    return () => { active = false; };
  }, []);

  const initiateDescent = useCallback((x: number, altitude: number, z: number, isSafe: boolean) => {
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
            attitude: null,
            pitch, yaw, roll
        });
    }
    
    setTrajectory({ source: 'legacy-simulation', points });
    setAnimationTime(0);
  }, []);

  const handleTerrainClick = useCallback((x: number, altitude: number, z: number, isSafe: boolean) => {
    initiateDescent(x, altitude, z, isSafe);
  }, [initiateDescent]);

  const handlePlannerExecute = useCallback((x: number, z: number) => {
    // Instead of immediately executing, we send a command to the 3D Raycaster inside the Canvas.
    // The Raycaster will find the exact 3D altitude and slope, and then call initiateDescent!
    setDivertCommand({ x, z, id: Date.now() });
    setIsPlannerOpen(false);
  }, []);

  const toggleLayer = useCallback((layer: keyof typeof layerVisibility) => {
    setLayerVisibility(current => ({ ...current, [layer]: !current[layer] }));
  }, []);

  const TimeUpdater = () => {
    useFrame((_state, delta) => {
        if (status.includes('DESCENDING') || status.includes('CRASH IMMINENT')) {
            setAnimationTime(prev => {
                const speed = 1.5; 
                const next = prev + delta * speed; 
                const duration = trajectory?.points.at(-1)?.t ?? 10;
                if (next > duration) {
                    if (isCrashing) {
                        setStatus('CATASTROPHIC FAILURE (CRASH)');
                    } else {
                        setStatus('TOUCHDOWN - NOMINAL');
                    }
                    return duration;
                }
                return next;
            });
        }
    });
    return null;
  };

  return (
    <div className="w-full relative bg-black flex flex-col pt-24" style={{ height: '100vh', overflow: 'hidden' }}>
      
      {/* 3D Scene */}
      <div className="absolute inset-0 pt-24 w-full h-full cursor-crosshair z-0">
          <Canvas camera={{ position: [0, 600, 400], fov: 60, far: 50000 }}>
            <TimeUpdater />
            
            <TerrainRaycaster 
                command={divertCommand} 
                onResult={(x, alt, z, isSafe) => initiateDescent(x, alt, z, isSafe)} 
            />

            <color attach="background" args={['#050505']} />
            <ambientLight intensity={1.5} />
            <SunLight config={activeSunConfig} />
            
            <Suspense fallback={null}>
                <Terrain onClick={handleTerrainClick} target={target} onStateChange={setTerrainViewState} />
                {layerVisibility.tmc && <TmcCameraFrustum onStateChange={setTmcCameraViewState} />}
                {layerVisibility.ohrc && <OhrcCameraFrustum onStateChange={setOhrcCameraViewState} />}
                {layerVisibility.iirs && <IirsFootprint onStateChange={setIirsFootprintViewState} />}
                {layerVisibility.landmarks && <LandmarkMarkers onStateChange={setLandmarkViewState} />}
                {layerVisibility.hazards && <HazardOverlay onStateChange={setHazardViewState} />}
                {layerVisibility.spectral && <SpectralOverlay onStateChange={setSpectralViewState} />}
                {layerVisibility.waterIce && <WaterIceOverlay onStateChange={setWaterIceViewState} />}
            </Suspense>
            
            <Suspense fallback={null}>
                {trajectory && (
                    <Lander 
                      trajectory={trajectory} 
                      animationTime={animationTime} 
                      onUpdateTelemetry={(point) => setTelemetry(point)} 
                    />
                )}
            </Suspense>
            
            <OrbitControls target={[0, 0, 0]} maxPolarAngle={Math.PI / 2.1} />
          </Canvas>
      </div>

      <div className="absolute top-28 left-4 z-10 max-w-sm border border-amber-400/60 bg-black/80 px-3 py-2 font-mono text-xs text-amber-200">
        <div className="border-b border-amber-500/30 pb-2">M6 TRAJECTORY: {m6State === 'ready' ? 'LOADED' : m6State === 'loading' ? 'LOADING' : 'UNAVAILABLE'}</div>
        <div>{terrainViewState.label ?? 'DEM TERRAIN'}</div>
        <div className="mt-1 text-slate-300">{terrainViewState.kind === 'ready'
          ? 'DEM-derived geometry · local East/North/Up · metres'
          : terrainViewState.message}</div>
        <div className="mt-2 border-t border-sky-300/30 pt-2 text-sky-200">{tmcCameraViewState.label ?? 'TMC CAMERA GEOMETRY'}</div>
        <div className="mt-1 text-slate-300">{tmcCameraViewState.kind === 'ready'
          ? 'Frustum is a development visualization, not observation coverage.'
          : tmcCameraViewState.message}</div>
        <div className="mt-2 border-t border-amber-500/30 pt-2 text-amber-300">{ohrcCameraViewState.label ?? 'OHRC CAMERA GEOMETRY'}</div>
        <div className="mt-1 text-slate-300">{ohrcCameraViewState.kind === 'ready'
          ? 'Frustum is a development visualization, not observation coverage.'
          : ohrcCameraViewState.message}</div>
        <div className="mt-2 border-t border-emerald-500/30 pt-2 text-emerald-300">{iirsFootprintViewState.label ?? 'IIRS FOOTPRINT'}</div>
        <div className="mt-1 text-slate-300">{iirsFootprintViewState.kind === 'ready'
          ? 'Footprint is a development viewing area, not observation coverage.'
          : iirsFootprintViewState.message}</div>
        <div className="mt-2 border-t border-cyan-500/30 pt-2 text-cyan-300">{landmarkViewState.label ?? 'LANDMARK VISUALIZATION'}</div>
        <div className="mt-1 text-slate-300">{landmarkViewState.kind === 'ready'
          ? 'Estimated vs Reference coordinates distinguished.'
          : landmarkViewState.message}</div>
        <div className="mt-2 border-t border-red-500/30 pt-2 text-red-300">{hazardViewState.label ?? 'HAZARD OVERLAYS'}</div>
        <div className="mt-1 text-slate-300">{hazardViewState.kind === 'ready'
          ? 'Spatially positioned on DEM surface.'
          : hazardViewState.message}</div>
        <div className="mt-2 border-t border-indigo-500/30 pt-2 text-indigo-300">{spectralViewState.label ?? 'SPECTRAL OVERLAY'}</div>
        <div className="mt-1 text-slate-300">{spectralViewState.kind === 'ready'
          ? 'Multispectral band values draped on DEM.'
          : spectralViewState.message}</div>
        <div className="mt-2 border-t border-cyan-300/30 pt-2 text-cyan-200">{waterIceViewState.label ?? 'WATER-ICE OVERLAY'}</div>
        <div className="mt-1 text-slate-300">{waterIceViewState.kind === 'ready'
          ? 'Synthetic development data; not a scientific observation.'
          : waterIceViewState.message}</div>
      </div>

      <SunControlPanel scenario={sunScenario} onScenarioChange={setSunScenario} />

      <div className="absolute bottom-5 left-4 z-10 flex flex-wrap gap-2 border border-white/15 bg-black/75 px-3 py-2 font-mono text-[10px] text-slate-200">
        {([['tmc', 'TMC'], ['ohrc', 'OHRC'], ['iirs', 'IIRS'], ['landmarks', 'LANDMARKS'], ['hazards', 'HAZARDS'], ['spectral', 'SPECTRAL'], ['waterIce', 'WATER-ICE']] as const).map(([key, label]) => (
          <label key={key} className="flex cursor-pointer items-center gap-1">
            <input type="checkbox" checked={layerVisibility[key]} onChange={() => toggleLayer(key)} />{label}
          </label>
        ))}
      </div>

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
