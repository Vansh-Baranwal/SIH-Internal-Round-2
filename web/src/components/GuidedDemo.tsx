import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Compass,
  SkipForward,
  Sparkles,
  X,
} from 'lucide-react';

type DemoStatus = 'available' | 'synthetic' | 'unavailable';

interface GuidedDemoStep {
  id: string;
  title: string;
  path: string;
  status: DemoStatus;
  summary: string;
  whyItMatters: string;
  inspect: string;
  label: string;
}

const DEMO_STEPS: GuidedDemoStep[] = [
  {
    id: 'mission-control',
    title: 'Mission overview / system status',
    path: '/',
    status: 'available',
    label: 'Available',
    summary: 'Mission Control surfaces the live system state, the selected dataset context, and the application structure.',
    whyItMatters: 'It anchors the judge in the operational picture before moving into detailed lunar hazard mapping workflows.',
    inspect: 'Review backend status, mission exports, dataset provenance, and the workspace entry points.',
  },
  {
    id: 'multi-sensor',
    title: 'Multi-sensor dataset selection',
    path: '/sensors',
    status: 'synthetic',
    label: 'Synthetic / Demo',
    summary: 'Select and inspect the active sensor datasets that feed downstream workspaces.',
    whyItMatters: 'This defines the mission context for registration, spectral and water-ice evaluation in an auditable, explainable way.',
    inspect: 'Toggle sensor selections, confirm provenance labels, and review the metadata that is shared across the app.',
  },
  {
    id: 'registration',
    title: 'Registration Cockpit',
    path: '/registration',
    status: 'unavailable',
    label: 'Unavailable',
    summary: 'The Registration Cockpit sets up source/reference image pairs and clarifies the current system readiness.',
    whyItMatters: 'Registration is a central Member 4 workflow, but the correspondence engine is not available in this build.',
    inspect: 'Inspect dataset selection, the side-by-side viewer layout, and the clear unavailable messaging for match points and metrics.',
  },
  {
    id: 'spectral',
    title: 'Spectral Intelligence',
    path: '/scientific',
    status: 'available',
    label: 'Available',
    summary: 'The spectral workspace visualizes the current IIRS/frontend spectral contract without inventing scientific conclusions.',
    whyItMatters: 'It helps the user understand how spectral signatures are presented and how scientific outputs must remain traceable and honest.',
    inspect: 'Check the spectral bands, region preview cards, and the explicit no-fabrication messaging.',
  },
  {
    id: 'water-ice',
    title: 'Water-Ice Intelligence',
    path: '/water-ice',
    status: 'synthetic',
    label: 'Synthetic / Demo',
    summary: 'This workspace preserves the current synthetic/development-only Water-Ice semantics in the UI.',
    whyItMatters: 'It makes the scientific boundary clear: model output is not presented as real water-ice detection when the backend is still deferred.',
    inspect: 'Review the overlay summary, item list, and the explicit note that no concentration or confidence values are being fabricated.',
  },
  {
    id: 'temporal',
    title: 'Temporal Change',
    path: '/temporal',
    status: 'unavailable',
    label: 'Unavailable',
    summary: 'The temporal workspace is intentionally presented as a capability seam, not as a real change-detection pipeline.',
    whyItMatters: 'This prevents false claims about multi-date landform change while still showing the intended workflow structure.',
    inspect: 'Review the selected observation pair and the honest statement that no genuine temporal change map is available yet.',
  },
];

function statusStyles(status: DemoStatus) {
  switch (status) {
    case 'available':
      return 'border-green-500/30 bg-green-500/10 text-green-200';
    case 'synthetic':
      return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    case 'unavailable':
      return 'border-red-500/30 bg-red-500/10 text-red-200';
    default:
      return 'border-white/10 bg-white/[0.03] text-zinc-200';
  }
}

export function GuidedDemo() {
  const navigate = useNavigate();
  const [currentIndex, setCurrentIndex] = useState(0);

  const currentStep = DEMO_STEPS[currentIndex];

  const progressLabel = useMemo(
    () => `${currentIndex + 1} / ${DEMO_STEPS.length}`,
    [currentIndex],
  );

  const goToStep = (index: number) => {
    const nextIndex = Math.min(Math.max(index, 0), DEMO_STEPS.length - 1);
    setCurrentIndex(nextIndex);
    navigate(DEMO_STEPS[nextIndex].path);
  };

  const canGoBack = currentIndex > 0;
  const canGoForward = currentIndex < DEMO_STEPS.length - 1;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.015] p-5 backdrop-blur-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
            <Compass className="h-4 w-4 text-amber-200" />
          </span>
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">Guided demo</p>
            <h3 className="text-lg font-semibold text-white tracking-tight">Member 4 mission workflow</h3>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] text-zinc-500">
          <span className="rounded-full border border-white/10 bg-white/[0.02] px-2 py-1">{progressLabel}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-2">
          {DEMO_STEPS.map((step, index) => {
            const active = index === currentIndex;
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => goToStep(index)}
                className={[
                  'w-full rounded-2xl border px-3 py-3 text-left transition-colors',
                  active
                    ? 'border-amber-400/40 bg-amber-500/10'
                    : 'border-white/10 bg-black/10 hover:border-white/20 hover:bg-white/[0.025]',
                ].join(' ')}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[9px] uppercase tracking-[0.26em] text-zinc-500">Step {index + 1}</p>
                    <p className="mt-1 text-sm font-semibold text-zinc-100">{step.title}</p>
                  </div>
                  <span className={`inline-flex rounded-full border px-2 py-1 text-[9px] font-bold uppercase tracking-[0.18em] ${statusStyles(step.status)}`}>
                    {step.label}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.28em] text-zinc-500">Current step</p>
              <h4 className="mt-2 text-xl font-semibold tracking-tight text-white">{currentStep.title}</h4>
            </div>
            <span className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.18em] ${statusStyles(currentStep.status)}`}>
              {currentStep.label}
            </span>
          </div>

          <p className="mt-4 text-sm leading-relaxed text-zinc-300">{currentStep.summary}</p>

          <div className="mt-4 space-y-3 rounded-xl border border-white/10 bg-white/[0.02] p-3">
            <div>
              <p className="text-[9px] uppercase tracking-[0.28em] text-zinc-500">Why it matters</p>
              <p className="mt-2 text-sm text-zinc-300">{currentStep.whyItMatters}</p>
            </div>
            <div>
              <p className="text-[9px] uppercase tracking-[0.28em] text-zinc-500">What to inspect</p>
              <p className="mt-2 text-sm text-zinc-300">{currentStep.inspect}</p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => goToStep(0)}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-300 hover:bg-white/[0.05]"
            >
              <SkipForward className="h-3.5 w-3.5" />
              Restart
            </button>
            <button
              type="button"
              onClick={() => navigate(currentStep.path)}
              className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-black hover:bg-zinc-200"
            >
              Open workspace
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="mt-5 flex items-center justify-between gap-3 border-t border-white/10 pt-4">
            <button
              type="button"
              onClick={() => canGoBack && goToStep(currentIndex - 1)}
              disabled={!canGoBack}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-black/10 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Back
            </button>

            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.2em] text-zinc-500">
              <Sparkles className="h-3.5 w-3.5 text-amber-200" />
              Guided path
            </div>

            <button
              type="button"
              onClick={() => canGoForward ? goToStep(currentIndex + 1) : goToStep(0)}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-300 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-black hover:bg-amber-200"
            >
              {canGoForward ? 'Next' : 'Exit demo'}
              {canGoForward ? <ChevronRight className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-2 text-xs text-zinc-500">
        <CheckCircle2 className="h-3.5 w-3.5 text-green-300" />
        Scientific guardrails are preserved: no fabricated match points, no invented temporal change values, and no false geological conclusions.
      </div>
    </section>
  );
}
