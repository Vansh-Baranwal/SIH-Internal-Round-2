import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, Layers3, ScanLine } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { ApiError, fetchSpectralOverlay, type SpectralBandPayload, type SpectralOverlayPayload } from '../api/client';
import { useDatasetSelection } from '../context/datasetSelectionContext';

export interface SpectralMetricsSummary {
  value?: number | null;
  label?: string | null;
  status?: string | null;
}

export interface SpectralWorkspaceData {
  displayLabel: string;
  dataStatus: string;
  regionCount: number;
  coordinateConvention: Record<string, string>;
  availableBands: SpectralBandPayload[];
  regions: Array<{
    regionId: string;
    displayLabel: string;
    value: number;
    scalarIndex: number;
    center: { x: number; y: number; z: number } | null;
    provenance: Record<string, unknown>;
  }>;
  classification?: SpectralOverlayPayload['classification'];
  provenance: Record<string, unknown>;
}

export type SpectralWorkspaceStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'unavailable' | 'error';

function formatConvention(convention: Record<string, string>): string {
  return Object.entries(convention)
    .map(([key, value]) => `${key}=${value}`)
    .join(' · ');
}

function provenanceNote(provenance: Record<string, unknown>): string {
  const note = provenance.note;
  return typeof note === 'string' ? note : '';
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

function normalizeBandValue(value: number | undefined | null): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return 0;
  return clamp(value / 0.35);
}

function toDisplayMetrics(data: SpectralWorkspaceData, bandId: string): SpectralMetricsSummary {
  const selectedBand = data.availableBands.find((band) => band.band_id === bandId);
  const maxValue = data.regions.reduce((acc, region) => Math.max(acc, region.value), 0);
  const averageValue = data.regions.length
    ? data.regions.reduce((acc, region) => acc + region.value, 0) / data.regions.length
    : 0;

  return {
    value: maxValue,
    label: selectedBand ? selectedBand.name : bandId,
    status: `Avg ${averageValue.toFixed(3)} · Max ${maxValue.toFixed(3)}`,
  };
}

export function SpectralIntelligence() {
  const { datasets } = useDatasetSelection();
  const [status, setStatus] = useState<SpectralWorkspaceStatus>('loading');
  const [error, setError] = useState<string | null>(null);

  const [iirsImage, setIirsImage] = useState<File | null>(null);
  const [opticalImage, setOpticalImage] = useState<File | null>(null);
  const [overlayProcessing, setOverlayProcessing] = useState(false);
  const [overlayResult, setOverlayResult] = useState<string | null>(null);
  const [overlayError, setOverlayError] = useState<string | null>(null);

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = error => reject(error);
    });
  };

  const handleGenerateOverlay = async () => {
    if (!iirsImage || !opticalImage) return;
    setOverlayProcessing(true);
    setOverlayError(null);
    try {
      const iirsB64 = await fileToBase64(iirsImage);
      const opticalB64 = await fileToBase64(opticalImage);
      
      const response = await fetch('http://127.0.0.1:8000/api/spectral/overlay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          iirs_band_b64: iirsB64.split(',')[1],
          optical_image_b64: opticalB64.split(',')[1],
          iirs_gsd_m: 80.0,
          optical_gsd_m: 5.0,
          band_id: selectedBandId
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      setOverlayResult('data:image/png;base64,' + result.registered_band_b64);
    } catch (e: any) {
      setOverlayError(e.message || 'Failed to generate overlay');
    } finally {
      setOverlayProcessing(false);
    }
  };

  const [data, setData] = useState<SpectralWorkspaceData | null>(null);
  const [selectedBandId, setSelectedBandId] = useState<string>('');

  const iirsDataset = datasets.iirs;

  const loadSpectralData = () => {
    let active = true;

    setStatus('loading');
    setError(null);

    fetchSpectralOverlay()
      .then((payload: SpectralOverlayPayload) => {
        if (!active) return;

        if (!payload || !Array.isArray(payload.regions)) {
          setStatus('error');
          setError('Spectral metadata is malformed.');
          return;
        }

        if (payload.regions.length === 0) {
          setData({
            displayLabel: payload.display_label,
            dataStatus: payload.data_status,
            regionCount: 0,
            coordinateConvention: payload.coordinate_convention,
            availableBands: payload.available_bands,
            regions: [],
            classification: payload.classification,
            provenance: payload.provenance,
          });
          setSelectedBandId(payload.available_bands[0]?.band_id ?? '');
          setStatus('empty');
          return;
        }

        const normalized: SpectralWorkspaceData = {
          displayLabel: payload.display_label,
          dataStatus: payload.data_status,
          regionCount: payload.region_count,
          coordinateConvention: payload.coordinate_convention,
          availableBands: payload.available_bands,
          regions: payload.regions.map((region) => {
            const bandValues = region.band_values ?? {};
            const bandValue = Object.values(bandValues).find((value) => typeof value === 'number');
            return {
              regionId: region.region_id,
              displayLabel: region.display_label,
              value: typeof bandValue === 'number' ? bandValue : region.scalar_index,
              scalarIndex: region.scalar_index,
              center: region.center_m ?? null,
              provenance: region.provenance ?? {},
            };
          }),
          classification: payload.classification,
          provenance: payload.provenance,
        };

        const defaultBand = payload.available_bands[0]?.band_id ?? '';
        setData(normalized);
        setSelectedBandId(defaultBand);
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (!active) return;
        const errorMessage = reason instanceof Error ? reason.message : 'Spectral data is unavailable.';
        const isUnavailable = reason instanceof ApiError && reason.status === 404;
        setStatus(isUnavailable ? 'unavailable' : 'error');
        setError(errorMessage);
      });

    return () => {
      active = false;
    };
  };

  useEffect(() => {
    return loadSpectralData();
  }, []);

  const bandOptions = useMemo(() => data?.availableBands ?? [], [data]);
  const summary = useMemo(
    () => (data && selectedBandId ? toDisplayMetrics(data, selectedBandId) : null),
    [data, selectedBandId],
  );

  return (
    <AppShell
      title="Spectral Intelligence"
      subtitle="IIRS and optical spectral inspection workspace"
    >
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-8">

        <section className="grid grid-cols-1 xl:grid-cols-[1.3fr_0.7fr] gap-6">
          <div className="border-l border-white/5 pl-8 py-4">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div>
                <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">
                  Spectral Viewer
                </p>
                <p className="text-sm text-zinc-300 mt-2">
                  {data ? data.displayLabel : 'Waiting for spectral data'}
                </p>
              </div>
              {data && (
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                  {data.dataStatus}
                </span>
              )}
            </div>

            {status === 'loading' && (
              <div className="min-h-[18rem] rounded-xl border border-dashed border-white/10 flex items-center justify-center p-4">
                <LoadingState title="Loading" message="Loading spectral overlay…" className="min-w-[17rem] justify-center" />
              </div>
            )}

            {status === 'unavailable' && (
              <div className="min-h-[18rem] rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                <ErrorState
                  title="Spectral endpoint unavailable"
                  message={error ?? 'Spectral data is unavailable in this build.'}
                  onRetry={loadSpectralData}
                />
              </div>
            )}

            {status === 'error' && (
              <div className="min-h-[18rem] rounded-xl border border-red-500/30 bg-red-500/5 p-4">
                <ErrorState
                  title="Unable to load spectral data"
                  message={error ?? 'Spectral metadata could not be loaded.'}
                  detail="Check the API response and retry."
                  onRetry={loadSpectralData}
                />
              </div>
            )}

            {status === 'empty' && (
              <div className="space-y-4">
                <div className="min-h-[18rem] rounded-xl border border-dashed border-white/15 bg-white/[0.015] flex items-center justify-center px-8 text-center">
                  <div className="text-zinc-400 text-sm font-medium leading-relaxed">
                    No spectral regions are available for the current dataset pair.
                  </div>
                </div>
                
              </div>
            )}

            {status === 'ready' && data && (
              <div className="mt-8 pt-8 border-t border-white/10">
                <h2 className="text-sm font-bold text-zinc-300 tracking-widest uppercase mb-8">
                    Data Ingestion
                  </h2>
                <div className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex flex-col mb-4">
                        <p className="text-[10px] text-zinc-500 font-bold mb-3 uppercase tracking-widest">1. Upload Optical Base Image</p>
                      <input type="file" accept="image/*" onChange={(e) => setOpticalImage(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-bold file:tracking-wide file:bg-zinc-200 file:text-black hover:file:bg-white transition-colors cursor-pointer" />
                    </div>
                    <div className="flex flex-col mb-4">
                        <p className="text-[10px] text-zinc-500 font-bold mb-3 uppercase tracking-widest">2. Upload IIRS Band Image</p>
                      <input type="file" accept="image/*" onChange={(e) => setIirsImage(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-bold file:tracking-wide file:bg-zinc-200 file:text-black hover:file:bg-white transition-colors cursor-pointer" />
                    </div>
                  </div>

                  <button 
                    onClick={handleGenerateOverlay}
                    disabled={!iirsImage || !opticalImage || overlayProcessing}
                    className={`w-full font-bold tracking-widest uppercase text-[11px] py-3 rounded transition-all ${(!iirsImage || !opticalImage || overlayProcessing) ? "bg-zinc-800 text-zinc-500 cursor-not-allowed" : "bg-zinc-200 hover:bg-white text-black"}`}
                  >
                    {overlayProcessing ? 'Generating Mineral Overlay...' : 'Generate Spectral Overlay'}
                  </button>

                  {overlayError && (
                    <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/10 text-red-400 text-xs">
                      {overlayError}
                    </div>
                  )}

                  {overlayResult && (
                    <div className="mt-8 rounded-xl border border-emerald-500/30 bg-emerald-500/5 overflow-hidden flex flex-col items-center p-6 shadow-2xl shadow-emerald-900/20">
                      <p className="text-[10px] uppercase tracking-[0.25em] text-emerald-400 font-bold mb-6 self-start flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        Generated Overlay Result
                      </p>
                      <img src={overlayResult} alt="Spectral Overlay" className="max-w-full h-auto object-contain rounded-lg border border-white/10 shadow-2xl" />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className="border-l border-white/5 pl-8 py-4">
              <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold mb-3">
                Spectral Controls
              </p>

              <label className="block text-[9px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-2">
                Band / Channel
              </label>
              <select
                value={selectedBandId}
                onChange={(event) => setSelectedBandId(event.target.value)}
                disabled={bandOptions.length === 0 || status !== 'ready'}
                className="w-full rounded-lg border border-white/10 bg-[#0d0d10] px-3 py-2 text-sm text-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {bandOptions.length === 0 ? (
                  <option value="">No bands available</option>
                ) : (
                  bandOptions.map((band) => (
                    <option key={band.band_id} value={band.band_id}>
                      {band.name}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div className="border-l border-white/5 pl-8 py-4 space-y-4">
              <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-bold">
                Band Guide (Hackathon Demo)
              </p>
              
              <div className="space-y-3">
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">Band 1 (TURBO Heatmap)</p>
                  <p className="text-xs text-zinc-500 mt-1">Simulates standard multispectral reflectance. Hot colors (reds) indicate high albedo surfaces like Anorthosite highlands.</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">Band 2 (MAGMA Inversion)</p>
                  <p className="text-xs text-zinc-500 mt-1">Simulates a deep-absorption feature like the 1.0 μm Pyroxene band or 2.0 μm Olivine band. Intensities are inverted to highlight absorption pits.</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">Band 3 (OCEAN Threshold)</p>
                  <p className="text-xs text-zinc-500 mt-1">Simulates the critical 3.0 μm Water-Ice absorption band. Uses strict thresholding to rigidly classify valid ice-bearing pixels in permanently shadowed regions.</p>
                </div>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </AppShell>
  );
}

function classColor(className: string, index: number): string {
  const colors = ['#38bdf8', '#f59e0b', '#34d399', '#f472b6', '#a1a1aa'];
  return colors[(className.length + index) % colors.length];
}

function MaterialClassification({
  classification,
}: {
  classification: SpectralOverlayPayload['classification'];
}) {
  return (
    <section className="rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-3">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.25em] text-amber-200 font-bold">
            Material / Mineral Identification
          </p>
          <p className="mt-2 text-[10px] uppercase tracking-[0.18em] text-amber-300/80">
            Illustrative - Synthetic Development Data
          </p>
        </div>
      </div>

      {!classification ? (
        <p className="text-sm text-zinc-400">Classification is unavailable for this response.</p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-zinc-400 leading-relaxed">
            Existing Phase 8 rule-based output over synthetic development data. Not scientifically
            validated and not publication-grade.
          </p>
          <div className="flex flex-wrap gap-2">
            {classification.classes.map((className, index) => (
              <span
                key={className}
                className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-2.5 py-1.5 text-[10px] font-bold tracking-[0.12em] text-zinc-200"
              >
                <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: classColor(className, index) }} />
                {className}
              </span>
            ))}
          </div>
          <div>
            <p className="mb-2 text-[10px] uppercase tracking-[0.22em] text-zinc-500 font-bold">
              Material Class Map
            </p>
            <div
              className="grid gap-1 rounded-lg border border-white/10 bg-[#0d0d10] p-2"
              style={{ gridTemplateColumns: `repeat(${classification.shape.width}, minmax(0, 1fr))` }}
            >
              {classification.class_map.flatMap((row, rowIndex) =>
                row.map((className, columnIndex) => {
                  const valid = classification.valid_mask[rowIndex]?.[columnIndex] ?? false;
                  return (
                    <div
                      key={`${rowIndex}-${columnIndex}`}
                      className="flex min-h-12 items-center justify-center rounded-md border border-white/10 p-1 text-center text-[9px] font-bold tracking-[0.08em]"
                      style={{ backgroundColor: `${classColor(className, rowIndex + columnIndex)}33` }}
                      title={`${className}${valid ? '' : ' (invalid)'}`}
                    >
                      <span className={valid ? 'text-zinc-200' : 'text-zinc-500'}>{className}</span>
                    </div>
                  );
                }),
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {classification.summary.map((item) => (
              <div key={item.class_name} className="rounded-lg border border-white/10 bg-[#0d0d10] px-3 py-2">
                <p className="text-[10px] font-bold tracking-[0.12em] text-zinc-200">{item.class_name}</p>
                <p className="mt-1 text-[10px] text-zinc-500">
                  {item.pixel_count} pixels · {item.valid_pixel_percentage.toFixed(1)}% of valid pixels
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-zinc-500 font-bold uppercase tracking-widest text-[9px]">{label}</span>
      <span className="text-zinc-300 text-right break-all">{value}</span>
    </div>
  );
}
