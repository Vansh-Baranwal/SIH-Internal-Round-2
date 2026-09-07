import { useRef, useMemo, useCallback, useState } from 'react';
import * as THREE from 'three';

// ── Sun direction calculation (mirrors sun_control.py) ──────────────

/** Convert azimuth/elevation to Three.js directional-light position.
 *  Convention:  X = East, Y = Up, Z = North.
 *  Azimuth 0° = North, clockwise.  Elevation 0° = horizon, 90° = zenith. */
export function sunPosition(azimuthDeg: number, elevationDeg: number, distance = 5000): [number, number, number] {
  const az = (azimuthDeg * Math.PI) / 180;
  const el = (elevationDeg * Math.PI) / 180;
  const horiz = distance * Math.cos(el);
  return [
    horiz * Math.sin(az),   // x  East
    distance * Math.sin(el), // y  Up
    horiz * Math.cos(az),   // z  North
  ];
}

// ── Sun state model ─────────────────────────────────────────────────

export interface SunConfig {
  azimuthDeg: number;
  elevationDeg: number;
  intensity: number;
  enabled: boolean;
  dataStatus: 'synthetic' | 'counterfactual' | 'real' | 'unknown';
}

export interface SunScenarioState {
  baseline: SunConfig;
  counterfactual: SunConfig;
  isCounterfactualActive: boolean;
}

export const DEFAULT_SUN_CONFIG: SunConfig = {
  azimuthDeg: 135,
  elevationDeg: 45,
  intensity: 3.0,
  enabled: true,
  dataStatus: 'synthetic',
};

export const DEFAULT_COUNTERFACTUAL_CONFIG: SunConfig = {
  azimuthDeg: 225,
  elevationDeg: 25,
  intensity: 4.0,
  enabled: true,
  dataStatus: 'counterfactual',
};

export const DEFAULT_SUN_SCENARIO: SunScenarioState = {
  baseline: DEFAULT_SUN_CONFIG,
  counterfactual: DEFAULT_COUNTERFACTUAL_CONFIG,
  isCounterfactualActive: false,
};

/** Compute the active illumination configuration based on scenario state. */
export function getActiveSunConfig(scenario: SunScenarioState): SunConfig {
  if (scenario.isCounterfactualActive) {
    return {
      ...scenario.counterfactual,
      dataStatus: 'counterfactual',
    };
  }
  return {
    ...scenario.baseline,
  };
}

// ── 3D Sun Light component (renders inside <Canvas>) ────────────────

interface SunLightProps {
  config: SunConfig;
}

/** Directional light driven by active Sun configuration.  Includes a small
 *  sphere gizmo at 1/10th distance so the user can see where the Sun "is". */
export function SunLight({ config }: SunLightProps) {
  const lightRef = useRef<THREE.DirectionalLight>(null);

  const position = useMemo(
    () => sunPosition(config.azimuthDeg, config.elevationDeg),
    [config.azimuthDeg, config.elevationDeg],
  );

  const gizmoPos = useMemo<[number, number, number]>(
    () => sunPosition(config.azimuthDeg, config.elevationDeg, 800),
    [config.azimuthDeg, config.elevationDeg],
  );

  const isCounterfactual = config.dataStatus === 'counterfactual';
  const lightColor = isCounterfactual ? '#ffeedd' : '#fffbe6';
  const gizmoColor = isCounterfactual ? '#fb923c' : '#fde68a';

  if (!config.enabled) return null;

  return (
    <group name="sun-control-group">
      <directionalLight
        ref={lightRef}
        position={position}
        intensity={config.intensity}
        color={lightColor}
        name="sun-directional-light"
      />
      {/* Sun gizmo indicator */}
      <mesh position={gizmoPos} name="sun-gizmo">
        <sphereGeometry args={[20, 16, 16]} />
        <meshBasicMaterial color={gizmoColor} />
      </mesh>
    </group>
  );
}

// ── 2D HUD Control Panel (renders outside Canvas) ───────────────────

export interface SunControlPanelProps {
  scenario?: SunScenarioState;
  onScenarioChange?: (scenario: SunScenarioState) => void;
  // Legacy backward-compatible props
  config?: SunConfig;
  onChange?: (config: SunConfig) => void;
}

export function SunControlPanel({ scenario, onScenarioChange, config, onChange }: SunControlPanelProps) {
  // If scenario is not passed, create a synthetic fallback adapter for backward compatibility
  const currentScenario = useMemo<SunScenarioState>(() => {
    if (scenario) return scenario;
    if (config) {
      return {
        baseline: config,
        counterfactual: DEFAULT_COUNTERFACTUAL_CONFIG,
        isCounterfactualActive: false,
      };
    }
    return DEFAULT_SUN_SCENARIO;
  }, [scenario, config]);

  const [activeTab, setActiveTab] = useState<'baseline' | 'counterfactual'>('baseline');

  const updateScenario = useCallback(
    (next: SunScenarioState) => {
      if (onScenarioChange) {
        onScenarioChange(next);
      } else if (onChange) {
        onChange(getActiveSunConfig(next));
      }
    },
    [onScenarioChange, onChange],
  );

  // Baseline modifiers
  const setBaselineAzimuth = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      baseline: { ...currentScenario.baseline, azimuthDeg: v },
    });
  }, [currentScenario, updateScenario]);

  const setBaselineElevation = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      baseline: { ...currentScenario.baseline, elevationDeg: v },
    });
  }, [currentScenario, updateScenario]);

  const setBaselineIntensity = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      baseline: { ...currentScenario.baseline, intensity: v },
    });
  }, [currentScenario, updateScenario]);

  const toggleEnabled = useCallback(() => {
    updateScenario({
      ...currentScenario,
      baseline: { ...currentScenario.baseline, enabled: !currentScenario.baseline.enabled },
      counterfactual: { ...currentScenario.counterfactual, enabled: !currentScenario.counterfactual.enabled },
    });
  }, [currentScenario, updateScenario]);

  // Counterfactual modifiers
  const setCounterfactualAzimuth = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      counterfactual: { ...currentScenario.counterfactual, azimuthDeg: v },
    });
  }, [currentScenario, updateScenario]);

  const setCounterfactualElevation = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      counterfactual: { ...currentScenario.counterfactual, elevationDeg: v },
    });
  }, [currentScenario, updateScenario]);

  const setCounterfactualIntensity = useCallback((v: number) => {
    updateScenario({
      ...currentScenario,
      counterfactual: { ...currentScenario.counterfactual, intensity: v },
    });
  }, [currentScenario, updateScenario]);

  // Scenario operations
  const applyCounterfactual = useCallback(() => {
    updateScenario({
      ...currentScenario,
      isCounterfactualActive: true,
    });
  }, [currentScenario, updateScenario]);

  const resetToBaseline = useCallback(() => {
    updateScenario({
      ...currentScenario,
      isCounterfactualActive: false,
    });
  }, [currentScenario, updateScenario]);

  const copyBaselineToCounterfactual = useCallback(() => {
    updateScenario({
      ...currentScenario,
      counterfactual: {
        ...currentScenario.baseline,
        dataStatus: 'counterfactual',
      },
    });
  }, [currentScenario, updateScenario]);

  const isCfActive = currentScenario.isCounterfactualActive;
  const isEnabled = currentScenario.baseline.enabled;

  return (
    <div
      className="absolute top-28 right-4 z-10 w-64 border border-yellow-500/50 bg-black/90 px-3 py-2 font-mono text-xs text-yellow-200 select-none shadow-xl backdrop-blur-md rounded-md"
      id="sun-control-panel"
    >
      {/* Header with Title and Global Toggle */}
      <div className="flex items-center justify-between pb-1 border-b border-yellow-500/30">
        <span className="font-bold tracking-wide flex items-center gap-1">
          <span>☀</span> SUN & WHAT-IF
        </span>
        <button
          onClick={toggleEnabled}
          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
            isEnabled ? 'bg-yellow-500/30 text-yellow-100' : 'bg-zinc-700/50 text-zinc-400'
          }`}
          id="sun-toggle"
        >
          {isEnabled ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Active Illumination Status Banner */}
      <div className="mt-1.5 px-2 py-1 rounded bg-zinc-900/80 border border-zinc-700/50 flex items-center justify-between text-[10px]">
        <span className="text-zinc-400">Illumination:</span>
        {isCfActive ? (
          <span className="font-bold text-orange-400 flex items-center gap-1" id="sun-status-active-counterfactual">
            <span>⚡</span> WHAT-IF ACTIVE
          </span>
        ) : (
          <span className="font-bold text-yellow-300 flex items-center gap-1" id="sun-status-active-baseline">
            <span>☀</span> BASELINE ACTIVE
          </span>
        )}
      </div>

      {/* Tab Navigation: Baseline vs Counterfactual */}
      <div className="mt-2 grid grid-cols-2 gap-1 p-0.5 bg-zinc-900/90 rounded border border-zinc-800 text-[10px]">
        <button
          type="button"
          onClick={() => setActiveTab('baseline')}
          className={`py-1 px-2 rounded font-medium transition-colors ${
            activeTab === 'baseline'
              ? 'bg-yellow-500/20 text-yellow-200 border border-yellow-500/40'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
          id="tab-sun-baseline"
        >
          Baseline Sun
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('counterfactual')}
          className={`py-1 px-2 rounded font-medium transition-colors ${
            activeTab === 'counterfactual'
              ? 'bg-orange-500/20 text-orange-200 border border-orange-500/40'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
          id="tab-sun-counterfactual"
        >
          What-If Sun
        </button>
      </div>

      {isEnabled && (
        <div className="mt-2">
          {activeTab === 'baseline' ? (
            /* ── Baseline Controls ── */
            <div id="baseline-controls-section">
              <div className="text-[10px] text-zinc-400 italic">
                SYNTHETIC DEVELOPMENT SUN CONFIGURATION
              </div>

              {/* Azimuth */}
              <label className="block mt-2">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>Azimuth (0°N CW)</span>
                  <span className="text-yellow-300 font-bold">{currentScenario.baseline.azimuthDeg.toFixed(0)}°</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={359}
                  step={1}
                  value={currentScenario.baseline.azimuthDeg}
                  onChange={(e) => setBaselineAzimuth(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-yellow-400 cursor-pointer"
                  id="sun-azimuth-slider"
                />
              </label>

              {/* Elevation */}
              <label className="block mt-1.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>Elevation (0°-90°)</span>
                  <span className="text-yellow-300 font-bold">{currentScenario.baseline.elevationDeg.toFixed(0)}°</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={90}
                  step={1}
                  value={currentScenario.baseline.elevationDeg}
                  onChange={(e) => setBaselineElevation(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-yellow-400 cursor-pointer"
                  id="sun-elevation-slider"
                />
              </label>

              {/* Intensity */}
              <label className="block mt-1.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>Intensity</span>
                  <span className="text-yellow-300 font-bold">{currentScenario.baseline.intensity.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={15}
                  step={0.5}
                  value={currentScenario.baseline.intensity}
                  onChange={(e) => setBaselineIntensity(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-yellow-400 cursor-pointer"
                  id="sun-intensity-slider"
                />
              </label>

              {isCfActive && (
                <button
                  type="button"
                  onClick={resetToBaseline}
                  className="mt-3 w-full py-1 px-2 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-200 border border-yellow-500/40 rounded text-[11px] font-bold tracking-wide transition-all"
                  id="sun-btn-restore-baseline"
                >
                  ↺ Switch Back to Baseline
                </button>
              )}
            </div>
          ) : (
            /* ── Counterfactual Controls ── */
            <div id="counterfactual-controls-section">
              <div className="text-[10px] text-orange-300/80 italic">
                COUNTERFACTUAL / WHAT-IF SCENARIO
              </div>

              {/* Azimuth */}
              <label className="block mt-2">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>What-If Azimuth</span>
                  <span className="text-orange-300 font-bold">{currentScenario.counterfactual.azimuthDeg.toFixed(0)}°</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={359}
                  step={1}
                  value={currentScenario.counterfactual.azimuthDeg}
                  onChange={(e) => setCounterfactualAzimuth(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-orange-400 cursor-pointer"
                  id="counterfactual-azimuth-slider"
                />
              </label>

              {/* Elevation */}
              <label className="block mt-1.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>What-If Elevation</span>
                  <span className="text-orange-300 font-bold">{currentScenario.counterfactual.elevationDeg.toFixed(0)}°</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={90}
                  step={1}
                  value={currentScenario.counterfactual.elevationDeg}
                  onChange={(e) => setCounterfactualElevation(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-orange-400 cursor-pointer"
                  id="counterfactual-elevation-slider"
                />
              </label>

              {/* Intensity */}
              <label className="block mt-1.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>What-If Intensity</span>
                  <span className="text-orange-300 font-bold">{currentScenario.counterfactual.intensity.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={15}
                  step={0.5}
                  value={currentScenario.counterfactual.intensity}
                  onChange={(e) => setCounterfactualIntensity(Number(e.target.value))}
                  className="w-full h-1 mt-0.5 accent-orange-400 cursor-pointer"
                  id="counterfactual-intensity-slider"
                />
              </label>

              {/* Action Buttons: Apply / Reset / Copy */}
              <div className="mt-3 flex flex-col gap-1.5">
                {!isCfActive ? (
                  <button
                    type="button"
                    onClick={applyCounterfactual}
                    className="w-full py-1.5 px-2 bg-orange-600 hover:bg-orange-500 text-white rounded text-[11px] font-bold tracking-wide transition-all shadow-md flex items-center justify-center gap-1"
                    id="counterfactual-btn-apply"
                  >
                    <span>⚡</span> Apply What-If Illumination
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={resetToBaseline}
                    className="w-full py-1.5 px-2 bg-zinc-800 hover:bg-zinc-700 text-yellow-300 border border-yellow-500/40 rounded text-[11px] font-bold tracking-wide transition-all flex items-center justify-center gap-1"
                    id="counterfactual-btn-reset"
                  >
                    <span>↺</span> Revert to Baseline Sun
                  </button>
                )}

                <button
                  type="button"
                  onClick={copyBaselineToCounterfactual}
                  className="w-full py-0.5 px-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700/50 rounded text-[10px] transition-all"
                  id="counterfactual-btn-copy-baseline"
                >
                  Copy from Baseline
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
