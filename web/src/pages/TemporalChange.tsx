import { useState, useEffect } from 'react';
import { AppShell } from '../components/layout/AppShell';

export function TemporalChange() {
  const [imageA, setImageA] = useState<File | null>(null);
  const [imageB, setImageB] = useState<File | null>(null);
  const [previewA, setPreviewA] = useState<string | null>(null);
  const [previewB, setPreviewB] = useState<string | null>(null);

  useEffect(() => {
    if (!imageA) { setPreviewA(null); return; }
    const url = URL.createObjectURL(imageA);
    setPreviewA(url);
    return () => URL.revokeObjectURL(url);
  }, [imageA]);

  useEffect(() => {
    if (!imageB) { setPreviewB(null); return; }
    const url = URL.createObjectURL(imageB);
    setPreviewB(url);
    return () => URL.revokeObjectURL(url);
  }, [imageB]);

  const [isProcessing, setIsProcessing] = useState(false);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [changesDetected, setChangesDetected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = error => reject(error);
    });
  };

  const handleGenerate = async () => {
    if (!imageA || !imageB) return;
    setIsProcessing(true);
    setError(null);
    try {
      const b64A = await fileToBase64(imageA);
      const b64B = await fileToBase64(imageB);
      
      const response = await fetch('http://127.0.0.1:8000/api/temporal/compute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_a_b64: b64A.split(',')[1],
          image_b_b64: b64B.split(',')[1],
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      setResultImage('data:image/png;base64,' + result.temporal_map_b64);
      setChangesDetected(result.changes_detected);
    } catch (e: any) {
      setError(e.message || 'Failed to compute temporal change');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <AppShell
      title="Temporal Workspace"
      subtitle="Automated Image Subtraction & Change Detection"
    >
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-8">
        


        <section className="grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-6">
          <div className="rounded-2xl border border-white/10 bg-[#0d0d10] p-6 shadow-2xl">
            <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-6">
              Observation A (Before)
            </p>
            
            <div className="rounded-xl border border-white/10 bg-black p-4 mb-4">
              <input type="file" accept="image/*" onChange={(e) => setImageA(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-bold file:tracking-wide file:bg-zinc-200 file:text-black hover:file:bg-white transition-colors cursor-pointer" />
            </div>
            {imageA && previewA && (
              <div className="mt-4">
                <img src={previewA} alt="Preview A" className="w-full h-auto max-h-[400px] object-contain rounded-lg border border-white/10" />
                <p className="text-xs text-emerald-400 font-mono mt-2">Loaded: {imageA.name}</p>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0d0d10] p-6 shadow-2xl">
            <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-6">
              Observation B (After)
            </p>
            
            <div className="rounded-xl border border-white/10 bg-black p-4 mb-4">
              <input type="file" accept="image/*" onChange={(e) => setImageB(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-bold file:tracking-wide file:bg-zinc-200 file:text-black hover:file:bg-white transition-colors cursor-pointer" />
            </div>
            {imageB && previewB && (
              <div className="mt-4">
                <img src={previewB} alt="Preview B" className="w-full h-auto max-h-[400px] object-contain rounded-lg border border-white/10" />
                <p className="text-xs text-emerald-400 font-mono mt-2">Loaded: {imageB.name}</p>
              </div>
            )}
          </div>
        </section>

        <button 
          onClick={handleGenerate}
          disabled={!imageA || !imageB || isProcessing}
          className="w-full bg-white hover:bg-zinc-200 text-black font-bold tracking-widest uppercase text-[11px] py-4 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-white/20"
        >
          {isProcessing ? 'Subtracting Images...' : 'Detect Temporal Changes'}
        </button>

        {error && (
          <div className="mt-4 p-4 rounded-xl border border-red-500/20 bg-red-500/10 text-red-400 text-xs">
            {error}
          </div>
        )}

        {resultImage && (
          <div className="mt-8 rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden flex flex-col items-center p-6 shadow-2xl shadow-amber-900/20">
            <div className="w-full flex justify-between items-center mb-6">
              <p className="text-[10px] uppercase tracking-[0.25em] text-amber-400 font-bold flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                Temporal Change Map
              </p>
              <p className="text-xs font-mono text-amber-300 bg-amber-500/10 px-3 py-1 rounded-full">
                Anomalies Detected: {changesDetected}
              </p>
            </div>
            <img src={resultImage} alt="Temporal Change" className="max-w-full h-auto object-contain rounded-lg border border-white/10 shadow-2xl" />
          </div>
        )}
      </div>
    </AppShell>
  );
}
