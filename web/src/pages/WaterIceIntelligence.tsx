import { useState } from 'react';
import { AppShell } from '../components/layout/AppShell';

export function WaterIceIntelligence() {
  const [tempImage, setTempImage] = useState<File | null>(null);
  const [cprImage, setCprImage] = useState<File | null>(null);
  const [ohImage, setOhImage] = useState<File | null>(null);
  
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultImage, setResultImage] = useState<string | null>(null);
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
    if (!tempImage || !cprImage || !ohImage) return;
    setIsProcessing(true);
    setError(null);
    try {
      const tempB64 = await fileToBase64(tempImage);
      const cprB64 = await fileToBase64(cprImage);
      const ohB64 = await fileToBase64(ohImage);
      
      const response = await fetch('http://127.0.0.1:8000/api/water-ice/compute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          temp_img_b64: tempB64.split(',')[1],
          cpr_img_b64: cprB64.split(',')[1],
          oh_img_b64: ohB64.split(',')[1],
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      setResultImage('data:image/png;base64,' + result.confidence_map_b64);
    } catch (e: any) {
      setError(e.message || 'Failed to fuse water-ice map');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <AppShell
      title="Water-Ice Intelligence"
      subtitle="Multi-sensor LUPEX fusion workspace"
    >
      <div className="max-w-7xl mx-auto w-full px-8 pt-8 pb-16 space-y-8">
        
        <div className="rounded-2xl border border-blue-500/30 bg-blue-500/5 px-5 py-4">
          <div className="flex items-start gap-3 text-blue-200 text-sm font-medium leading-relaxed">
            <span>
              This workspace runs the actual Phase 13 Multi-Sensor Fusion math engine. Upload 3 sensor inputs to generate a live, scientific Ice Confidence Map.
            </span>
          </div>
        </div>

        <section className="grid grid-cols-1 xl:grid-cols-[1.3fr_0.7fr] gap-6">
          <div className="rounded-2xl border border-white/10 bg-[#0d0d10] p-6 shadow-2xl">
            <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-bold mb-6">
              Interactive Water-Ice Fusion Engine
            </p>
            
            <div className="space-y-4 mb-8">
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <p className="text-[10px] text-zinc-500 font-bold mb-2 uppercase tracking-widest flex items-center justify-between">
                  1. Temperature Map (Diviner)
                  <span className="text-blue-500/50">Base Frame</span>
                </p>
                <input type="file" accept="image/*" onChange={(e) => setTempImage(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-500/10 file:text-blue-400 hover:file:bg-blue-500/20" />
              </div>

              <div className="rounded-xl border border-white/10 bg-black p-4">
                <p className="text-[10px] text-zinc-500 font-bold mb-2 uppercase tracking-widest flex items-center justify-between">
                  2. Radar CPR Map (Mini-SAR)
                  <span className="text-emerald-500/50">Roughness</span>
                </p>
                <input type="file" accept="image/*" onChange={(e) => setCprImage(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-emerald-500/10 file:text-emerald-400 hover:file:bg-emerald-500/20" />
              </div>

              <div className="rounded-xl border border-white/10 bg-black p-4">
                <p className="text-[10px] text-zinc-500 font-bold mb-2 uppercase tracking-widest flex items-center justify-between">
                  3. OH Reflectance Map (IIRS)
                  <span className="text-violet-500/50">Chemical</span>
                </p>
                <input type="file" accept="image/*" onChange={(e) => setOhImage(e.target.files?.[0] || null)} className="w-full text-xs text-zinc-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-violet-500/10 file:text-violet-400 hover:file:bg-violet-500/20" />
              </div>
            </div>

            <button 
              onClick={handleGenerate}
              disabled={!tempImage || !cprImage || !ohImage || isProcessing}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold tracking-widest uppercase text-[11px] py-4 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-cyan-900/20"
            >
              {isProcessing ? 'Running Fusion Engine...' : 'Fuse Sensor Data ->'}
            </button>

            {error && (
              <div className="mt-4 p-4 rounded-xl border border-red-500/20 bg-red-500/10 text-red-400 text-xs">
                {error}
              </div>
            )}

            {resultImage && (
              <div className="mt-8 rounded-xl border border-cyan-500/30 bg-cyan-500/5 overflow-hidden flex flex-col items-center p-6 shadow-2xl shadow-cyan-900/20">
                <p className="text-[10px] uppercase tracking-[0.25em] text-cyan-400 font-bold mb-6 self-start flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                  LUPEX Ice Confidence Map
                </p>
                <img src={resultImage} alt="Ice Confidence Overlay" className="max-w-full h-auto object-contain rounded-lg border border-white/10 shadow-2xl" />
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-5 space-y-4">
              <p className="text-[10px] uppercase tracking-[0.3em] text-cyan-400 font-bold">
                Algorithm Math Guide
              </p>
              
              <div className="space-y-4">
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">Temperature Normalization</p>
                  <p className="text-xs text-zinc-500 mt-1">Pixels are clamped between 40K and 250K. Inverted so that 40K produces maximum confidence weight (1.0) and 250K drops to zero.</p>
                </div>
                <div className="h-px bg-white/10" />
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">CPR Roughness</p>
                  <p className="text-xs text-zinc-500 mt-1">Circular Polarization Ratio &gt; 1.0 strongly indicates volume scattering from thick ice. Values are normalized directly to a 0.0-1.0 confidence boost.</p>
                </div>
                <div className="h-px bg-white/10" />
                <div>
                  <p className="text-[10px] font-bold text-zinc-300 uppercase tracking-widest">OH Absorption</p>
                  <p className="text-xs text-zinc-500 mt-1">The 3.0 μm band anomaly acts as the definitive chemical signature, scaling the final probability.</p>
                </div>
                <div className="h-px bg-white/10" />
                <div>
                  <p className="text-[10px] font-bold text-cyan-300 uppercase tracking-widest">Final Fusion</p>
                  <p className="text-xs text-zinc-400 mt-1">Weights: Temp (50%), CPR (30%), OH (20%). Displayed via OCEAN colormap where deep blue is dry regolith and bright cyan/white is highly probable frost.</p>
                </div>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </AppShell>
  );
}
