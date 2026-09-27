import React, { useState, useEffect } from 'react';
import { Settings, Sliders, Check, Loader2, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';

export const SettingsPage: React.FC = () => {
  const [weights, setWeights] = useState({
    mrz: 25,
    tamper: 30,
    face: 30,
    consistency: 10,
    watchlist: 5
  });

  const [thresholds, setThresholds] = useState({
    low: 24,
    medium: 49,
    high: 74
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPolicy()
      .then((policy) => {
        setWeights({
          mrz: Math.round(policy.weight_mrz * 100),
          tamper: Math.round(policy.weight_tamper * 100),
          face: Math.round(policy.weight_face * 100),
          consistency: Math.round(policy.weight_consistency * 100),
          watchlist: Math.round(policy.weight_watchlist * 100)
        });
        setThresholds({
          low: policy.threshold_low,
          medium: policy.threshold_medium,
          high: policy.threshold_high
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.updatePolicy({
        weight_mrz: weights.mrz / 100,
        weight_tamper: weights.tamper / 100,
        weight_face: weights.face / 100,
        weight_consistency: weights.consistency / 100,
        weight_watchlist: weights.watchlist / 100,
        threshold_low: thresholds.low,
        threshold_medium: thresholds.medium,
        threshold_high: thresholds.high
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: any) {
      setError(err.message || 'Failed to apply policy configuration');
    } finally {
      setSaving(false);
    }
  };

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
            <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
          </div>
          <span className="text-xs text-graphite-400 font-medium tracking-wide">Loading live policy configuration…</span>
        </div>
      </div>
    );
  }

  const subsystems = [
    { name: 'OCR extraction', value: 'PyTesseract 5.5 (active)' },
    { name: 'MRZ parser & checksums', value: 'ICAO 9303 (active)' },
    { name: 'Tamper AI model', value: 'PyTorch CNN + ELA (active)' },
    { name: 'Face verification', value: 'Cosine embedding net (active)' },
    { name: 'Watchlist provider', value: 'DatabaseWatchlistProvider (DB-backed, simulated sandbox data)', accent: true },
  ];

  const weightFields = [
    { key: 'mrz', label: 'MRZ & validation rules', max: 60 },
    { key: 'tamper', label: 'Forensic tamper AI (ELA)', max: 60 },
    { key: 'face', label: 'Biometric face verification', max: 60 },
    { key: 'consistency', label: 'Data consistency crosscheck', max: 40 },
    { key: 'watchlist', label: 'Simulated watchlist adapter (demo sandboxed)', max: 20 },
  ] as const;

  return (
    <div className="space-y-7 max-w-4xl mx-auto">
      <SectionHeading
        title="Settings"
        description="Adjust risk engine weights, decision thresholds, and view connected subsystems."
        icon={<Settings className="w-5 h-5 text-brass-400" />}
      />

      <form onSubmit={handleSave} className="space-y-6">
        {/* Risk Engine Weights -- the one real interactive control, keeps a card */}
        <ScrollReveal className="glass-panel rounded-xl p-5 space-y-5">
          <SectionHeading
            level="h3"
            title="Risk engine factor weights"
            icon={<Sliders className="w-4 h-4 text-brass-400" />}
            action={
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-lg ${
                  totalWeight === 100
                    ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-950/60 text-rose-300 border border-rose-500/30'
                }`}
              >
                {totalWeight === 100 ? 'Valid — 100%' : `Must total 100% — currently ${totalWeight}%`}
              </span>
            }
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            {weightFields.map((field) => (
              <div key={field.key}>
                <label className="text-graphite-300 block mb-1.5 flex items-center justify-between">
                  <span>{field.label}</span>
                  <span className="text-brass-400 font-bold">
                    {weights[field.key as keyof typeof weights]}%
                  </span>
                </label>
                <input
                  type="range"
                  min="0"
                  max={field.max}
                  value={weights[field.key as keyof typeof weights]}
                  onChange={(e) => setWeights({ ...weights, [field.key]: parseInt(e.target.value) })}
                  className="w-full accent-brass-500 bg-graphite-950/80 rounded-lg cursor-pointer h-2"
                />
              </div>
            ))}
            <div className="sm:col-span-2">
              <label className="text-graphite-300 block mb-1.5 flex items-center justify-between">
                <span>Simulated watchlist adapter (demo sandboxed)</span>
                <span className="text-brass-400 font-bold">{weights.watchlist}%</span>
              </label>
              <input
                type="range"
                min="0"
                max={20}
                value={weights.watchlist}
                onChange={(e) => setWeights({ ...weights, watchlist: parseInt(e.target.value) })}
                className="w-full accent-brass-500 bg-graphite-950/80 rounded-lg cursor-pointer h-2"
              />
            </div>
          </div>
        </ScrollReveal>

        {/* Risk tier cutoffs -- read-only reference data, a plain row not a card */}
        <ScrollReveal>
          <h3 className="text-sm font-semibold text-graphite-200 mb-3">Risk tier classification cutoffs</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="glass-panel p-3 rounded-lg">
              <span className="text-emerald-400 font-semibold block mb-1">Low risk</span>
              <span className="text-graphite-500 block mb-1">0–{thresholds.low}</span>
              <span className="text-graphite-500">Clear for entry</span>
            </div>
            <div className="glass-panel p-3 rounded-lg">
              <span className="text-amber-400 font-semibold block mb-1">Medium risk</span>
              <span className="text-graphite-500 block mb-1">{thresholds.low + 1}–{thresholds.medium}</span>
              <span className="text-graphite-500">Routine confirmation</span>
            </div>
            <div className="glass-panel p-3 rounded-lg">
              <span className="text-rose-400 font-semibold block mb-1">High & critical</span>
              <span className="text-graphite-500 block mb-1">{thresholds.medium + 1}–100</span>
              <span className="text-graphite-500">Secondary inspection / detain</span>
            </div>
          </div>
        </ScrollReveal>

        {/* Connected subsystems -- plain label/value list, not a grid of boxes */}
        <ScrollReveal>
          <h3 className="text-sm font-semibold text-graphite-200 mb-3">Connected subsystem modules</h3>
          <div className="glass-panel rounded-xl overflow-hidden">
            {subsystems.map((sub) => (
              <div key={sub.name} className="flex items-center justify-between py-2.5 px-4 text-xs border-b border-graphite-800/40 last:border-0">
                <span className="text-graphite-300">{sub.name}</span>
                <span className={`font-semibold ${sub.accent ? 'text-brass-400' : 'text-emerald-400'}`}>
                  {sub.value}
                </span>
              </div>
            ))}
          </div>
        </ScrollReveal>

        {/* Save Button */}
        <div className="flex items-center justify-end gap-3">
          {error && (
            <span className="text-xs text-rose-400 flex items-center gap-1 animate-fade-in">
              <AlertTriangle className="w-3.5 h-3.5" /> {error}
            </span>
          )}
          {saved && !error && (
            <span className="text-xs text-emerald-400 flex items-center gap-1 animate-fade-in">
              <Check className="w-3.5 h-3.5" /> Policy weights updated — takes effect on the next screening
            </span>
          )}
          <button
            type="submit"
            disabled={saving || totalWeight !== 100}
            className="px-6 py-2.5 rounded-lg bg-brass-600 hover:bg-brass-500 active:bg-brass-700 text-white text-xs font-semibold transition-all duration-200 shadow-md shadow-brass-950/40 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-brass-500/50"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Apply policy configuration
          </button>
        </div>
      </form>
    </div>
  );
};
