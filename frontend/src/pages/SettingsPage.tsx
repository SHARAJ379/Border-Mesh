import React, { useState, useEffect } from 'react';
import { Settings, Sliders, Check, Loader2, AlertTriangle, Scale, ChevronRight } from 'lucide-react';
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
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 border border-hairline" />
            <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
          </div>
          <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading live policy configuration&hellip;</span>
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
  ] as const;

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <SectionHeading
        title="Settings"
        description="Adjust risk engine weights, decision thresholds, and view connected subsystems."
        icon={<Settings className="w-5 h-5 text-accent" strokeWidth={1.75} />}
      />

      <form onSubmit={handleSave} className="space-y-8">
        {/* Risk engine weights -- the one real interactive control */}
        <ScrollReveal className="border border-hairline p-5 space-y-5">
          <SectionHeading
            level="h3"
            title="Risk engine factor weights"
            icon={<Sliders className="w-4 h-4 text-accent" strokeWidth={1.75} />}
            action={
              <span className={`badge-signal ${totalWeight === 100 ? 'badge-low' : 'badge-critical'}`}>
                {totalWeight === 100 ? 'Valid — 100%' : `Must total 100% — currently ${totalWeight}%`}
              </span>
            }
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            {weightFields.map((field) => (
              <div key={field.key} className="rule-row flex-col items-stretch gap-1">
                <label className="text-ink-soft flex items-center justify-between text-[12px]">
                  <span>{field.label}</span>
                  <span className="figure text-accent font-bold">
                    {weights[field.key as keyof typeof weights]}%
                  </span>
                </label>
                <input
                  type="range"
                  min="0"
                  max={field.max}
                  value={weights[field.key as keyof typeof weights]}
                  onChange={(e) => setWeights({ ...weights, [field.key]: parseInt(e.target.value) })}
                  className="field-range"
                />
              </div>
            ))}
            <div className="sm:col-span-2 rule-row flex-col items-stretch gap-1">
              <label className="text-ink-soft flex items-center justify-between text-[12px]">
                <span>Simulated watchlist adapter (demo sandboxed)</span>
                <span className="figure text-accent font-bold">{weights.watchlist}%</span>
              </label>
              <input
                type="range"
                min="0"
                max={20}
                value={weights.watchlist}
                onChange={(e) => setWeights({ ...weights, watchlist: parseInt(e.target.value) })}
                className="field-range"
              />
            </div>
          </div>
        </ScrollReveal>

        {/* Risk tier cutoffs -- read-only reference data */}
        <ScrollReveal>
          <h3 className="font-display text-[17px] text-ink mb-3">Risk tier classification cutoffs</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 border-t border-b border-hairline divide-x divide-hairline text-[12px]">
            <div className="p-3">
              <span className="badge-signal badge-low block mb-1.5">Low risk</span>
              <span className="figure text-ink block mb-1">0–{thresholds.low}</span>
              <span className="text-muted">Clear for entry</span>
            </div>
            <div className="p-3">
              <span className="badge-signal badge-medium block mb-1.5">Medium risk</span>
              <span className="figure text-ink block mb-1">{thresholds.low + 1}–{thresholds.medium}</span>
              <span className="text-muted">Routine confirmation</span>
            </div>
            <div className="p-3">
              <span className="badge-signal badge-critical block mb-1.5">High & critical</span>
              <span className="figure text-ink block mb-1">{thresholds.medium + 1}–100</span>
              <span className="text-muted">Secondary inspection / detain</span>
            </div>
          </div>
        </ScrollReveal>

        {/* Connected subsystems */}
        <ScrollReveal>
          <h3 className="font-display text-[17px] text-ink mb-3">Connected subsystem modules</h3>
          <div>
            {subsystems.map((sub) => (
              <div key={sub.name} className="rule-row text-[12px]">
                <span className="text-ink-soft">{sub.name}</span>
                <span className={`figure font-bold ${sub.accent ? 'text-accent' : 'text-signal-low'}`}>
                  {sub.value}
                </span>
              </div>
            ))}
          </div>
        </ScrollReveal>

        {/* Save button */}
        <div className="flex items-center justify-end gap-4">
          {error && (
            <span className="text-[11px] text-signal-critical flex items-center gap-1 animate-fade-in">
              <AlertTriangle className="w-3.5 h-3.5" strokeWidth={1.75} /> {error}
            </span>
          )}
          {saved && !error && (
            <span className="text-[11px] text-signal-low flex items-center gap-1 animate-fade-in">
              <Check className="w-3.5 h-3.5" strokeWidth={1.75} /> Policy weights updated — takes effect on the next screening
            </span>
          )}
          <button
            type="submit"
            disabled={saving || totalWeight !== 100}
            className="btn-primary px-6 py-2.5 text-[11px] cursor-pointer disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />}
            Apply policy configuration
          </button>
        </div>
      </form>

      {/* Legal & compliance -- plain link list */}
      <ScrollReveal>
        <h3 className="font-display text-[17px] text-ink mb-3">Legal &amp; compliance</h3>
        <div>
          {[
            { href: '/privacy', label: 'Privacy Policy', description: 'What data this system processes and how it is protected.' },
            { href: '/terms', label: 'Terms & Conditions', description: 'Prototype status, known accuracy limitations, and acceptable use.' },
          ].map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="flex items-center justify-between gap-3 py-3 border-t border-hairline last:border-b text-[12px] hover:bg-paper-dim transition-colors group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <Scale className="w-4 h-4 text-muted shrink-0" strokeWidth={1.75} />
                <div className="min-w-0">
                  <span className="text-ink font-bold block">{link.label}</span>
                  <span className="text-muted text-[11px] block truncate">{link.description}</span>
                </div>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-muted group-hover:text-accent transition-colors shrink-0" strokeWidth={1.75} />
            </a>
          ))}
        </div>
      </ScrollReveal>
    </div>
  );
};
