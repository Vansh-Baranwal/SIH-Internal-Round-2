import { useState, useEffect, useRef } from 'react';
import { useMission } from '../context/useMission';
import { useNavigate } from 'react-router-dom';
import { API_BASE, API_ROOT } from '../api/client';
import { ProgressBar, StatusPanel } from '../components/ui/StatusPanel';

export function Imagery() {
  const { result, setResult } = useMission();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [autoLoadedFromRegistration, setAutoLoadedFromRegistration] = useState(false);
  const [preloadState, setPreloadState] = useState<'idle' | 'loading' | 'error'>('idle');
  const [preloadError, setPreloadError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [preloadAttempt, setPreloadAttempt] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const preloadSource = result?.from_registration && result?.source_image_url ? result.source_image_url : null;
  const hasRegisteredSource = Boolean(preloadSource);

  const isHttpResponseUsable = (response: Response) => {
    if (!response.ok) throw new Error(`Registered image could not be loaded (${response.status}).`);
    return response;
  };

  const navigate = useNavigate();



  const retryPreload = () => {
    setFile(null);
    setAutoLoadedFromRegistration(false);
    setPreloadError(null);
    setPreloadState('idle');
    setPreloadAttempt((attempt) => attempt + 1);
  };

  const handleFileChange = (picked: File | null) => {
    setFile(picked);
    setAutoLoadedFromRegistration(false);
    setPreloadError(null);
    setPreloadState('idle');
    setUploadError(null);
  };

  const clearSelectedFile = () => {
    setFile(null);
    setAutoLoadedFromRegistration(false);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const isPreloading = preloadState === 'loading' && !file;
  const canRunPipeline = !!file && !uploading && !isPreloading;

  const handleUpload = async () => {
    if (!file || !canRunPipeline) return;
    setUploading(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/pipeline/run`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(`Pipeline request failed (${res.status}).`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'The optical pipeline could not be started.';
      setUploadError(message);
      console.error(e);
    } finally {
      setUploading(false);
    }
  };

  const p = result?.pipeline;
  const originalUrl = result?.original_url || p?.original_url;
  const srUrl = result?.sr_url || p?.sr_url;
  const hasEnhancementData = !!(originalUrl && srUrl);

  return (
    <div className="max-w-7xl mx-auto w-full pt-32 pb-16 px-8 font-sans">
      <div className="mb-16 pb-8 border-b border-white/5">
        <h1 className="text-2xl lg:text-3xl font-medium text-white tracking-[0.2em] uppercase mb-4">Optical Processing</h1>
        <p className="text-zinc-500 font-medium tracking-wide">Upload orbital imagery for AI Super-Resolution enhancement.</p>
      </div>

      {!hasEnhancementData ? (
        <div className="flex flex-col items-start border-l border-white/5 pl-8 py-4">
          {isPreloading && (
            <StatusPanel
              title="Loading registered output"
              message="Staging the registered image as a local upload before the optical enhancement step."
              className="w-full mb-6"
              action={<ProgressBar label="Preparing image" />}
            />
          )}

          {hasRegisteredSource && preloadState === 'error' && (
            <StatusPanel
              tone="error"
              title="Registered output could not be staged"
              message={preloadError ?? 'Choose a local image to continue with optical enhancement.'}
              className="w-full mb-6"
              action={
                <button
                  type="button"
                  onClick={retryPreload}
                  className="shrink-0 border border-rose-300/30 px-3 py-2 text-[10px] font-bold tracking-widest uppercase text-rose-200 transition-colors hover:bg-rose-300/10 focus-visible:ring-2 focus-visible:ring-rose-300/80 focus-visible:outline-none"
                >
                  Retry load
                </button>
              }
            />
          )}

          {result?.from_registration && autoLoadedFromRegistration && (
            <div className="w-full mb-10 border border-amber-500/20 bg-amber-500/5 px-6 py-6 flex flex-col sm:flex-row items-start sm:items-center gap-6">
              {result.source_image_url && (
                <div className="w-40 h-28 bg-[#030303] border border-white/10 flex items-center justify-center overflow-hidden shrink-0">
                  <img
                    src={result.source_image_url}
                    alt="Registered source"
                    className="max-h-full max-w-full object-contain opacity-80"
                  />
                </div>
              )}
              <div>
                <p className="text-amber-500 text-xs font-bold tracking-widest uppercase mb-2">
                  Registered Image Loaded as Upload
                </p>
                <p className="text-zinc-500 text-sm leading-relaxed">
                  This registered image is already staged below as your upload file. Click Run Pipeline to continue, or choose a different file to override it.
                </p>
              </div>
            </div>
          )}

          <h2 className="text-sm font-bold text-zinc-300 tracking-widest uppercase mb-8">Data Ingestion</h2>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.tif,.tiff"
            aria-label="Select orbital image"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            className="w-full text-xs text-zinc-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer mb-4"
          />

          {file && (
            <div className="mb-8 flex w-full max-w-2xl flex-wrap items-center justify-between gap-4 border border-white/10 bg-white/[0.02] px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-zinc-200">{file.name}</p>
                <p className="mt-1 text-xs tracking-wide text-zinc-500">
                  {file.type || 'Unknown format'} · {(file.size / 1024 / 1024).toFixed(2)} MB
                  {autoLoadedFromRegistration ? ' · registered output' : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={clearSelectedFile}
                className="shrink-0 text-[10px] font-bold tracking-widest uppercase text-zinc-500 transition-colors hover:text-zinc-200 focus-visible:ring-2 focus-visible:ring-sky-400/80 focus-visible:outline-none"
              >
                Remove file
              </button>
            </div>
          )}

          {uploadError && (
            <StatusPanel
              tone="error"
              title="Pipeline request failed"
              message={uploadError}
              className="mb-6 w-full max-w-2xl"
            />
          )}

          {uploading && (
            <div className="mb-6 w-full max-w-2xl space-y-4">
              <ProgressBar label="Running optical enhancement" />
              <p className="text-zinc-300 font-mono text-sm animate-pulse tracking-widest">
                INITIALIZING NEURAL NETWORKS...
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={handleUpload}
            disabled={!canRunPipeline}
            className={`px-8 py-3 rounded font-bold tracking-wide uppercase transition-all focus-visible:ring-2 focus-visible:ring-sky-400/80 focus-visible:outline-none ${
              !canRunPipeline
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                : 'bg-zinc-200 hover:bg-white text-black'
            }`}
          >
            {uploading ? 'Processing Data...' : 'Run Pipeline'}
          </button>
        </div>
      ) : (
        <div className="w-full">
          <div className="flex justify-between items-end mb-12 border-b border-white/5 pb-6">
            <h2 className="text-2xl font-bold text-white tracking-tight">Enhancement Results</h2>
            <button
              onClick={() => navigate('/hazard-map')}
              className="bg-zinc-200 hover:bg-white text-black font-semibold py-2 px-6 rounded transition-colors"
            >
              Analyze Terrain Hazards →
            </button>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-16">
            <div className="border-l border-white/5 pl-8">
              <h3 className="text-zinc-500 font-bold tracking-widest text-xs uppercase mb-6">Original Orbital Telemetry</h3>
              <div className="w-full bg-[#030303] flex items-center justify-center min-h-[400px]">
                <img
                  src={`${API_ROOT}${originalUrl}`}
                  alt="Original"
                  className="max-h-[700px] object-contain opacity-75 grayscale"
                />
              </div>
            </div>

            <div className="border-l border-white/20 pl-8 relative">
              <h3 className="text-zinc-300 font-bold tracking-widest text-xs uppercase mb-6">Phase II: Super Resolution</h3>
              <div className="w-full bg-[#030303] flex items-center justify-center min-h-[400px]">
                <img
                  src={`${API_ROOT}${srUrl}`}
                  alt="Super Resolution"
                  className="max-h-[700px] object-contain"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}