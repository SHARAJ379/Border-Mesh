import React, { useState } from 'react';
import { Play, Loader2 } from 'lucide-react';
import { api } from '../services/api';

interface QuickDemoBarProps {
  onScenarioLoaded: (caseId: string) => void;
}

export const QuickDemoBar: React.FC<QuickDemoBarProps> = ({ onScenarioLoaded }) => {
  const [loading, setLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState('genuine');

  const scenarios = [
    { key: 'genuine', label: '1. Genuine Document', desc: 'Authentic passport, valid checksums, face match' },
    { key: 'mrz_tampering', label: '2. MRZ Tampering', desc: 'Corrupted check digits, invalid MRZ checksum' },
    { key: 'photo_replacement', label: '3. Photo Replacement', desc: 'Spliced portrait seam, biometric mismatch' },
    { key: 'expired', label: '4. Expired Document', desc: 'Expired travel validity, rule engine trigger' },
    { key: 'multiple_anomalies', label: '5. Multiple Anomalies', desc: 'Tampered MRZ + replaced photo + demo watchlist' },
    { key: 'watchlist_evasion', label: '6. Watchlist Evasion Attempt', desc: 'Clean document, but name & number are 1-character off a flagged record' },
    { key: 'pan_card', label: '7. PAN Card Verification', desc: 'Genuine PAN, structural format check passes, entity type decoded' },
    { key: 'driving_license', label: '8. Driving Licence — Expired', desc: 'No MRZ, but a genuine printed expiry the rules engine now checks' },
    { key: 'voter_id', label: '9. Voter ID (EPIC) Verification', desc: 'Genuine EPIC, structural format check passes' },
    { key: 'duplicate_identity', label: '10. Duplicate Identity Detection', desc: 'Two different fabricated identities, same real face — caught by cross-case gallery match' },
    { key: 'visa', label: '11. Travel Visa — Stay Duration Expired', desc: 'No MRZ, but an overstayed printed stay duration the rules engine now checks' },
    { key: 'permit', label: '12. Residence Permit — Expired', desc: 'No MRZ, but a genuine printed expiry hooked into the same expiration rule as a Driving Licence' },
  ];

  const handleRun = async () => {
    try {
      setLoading(true);
      const res = await api.runDemoScenario(selectedScenario);
      onScenarioLoaded(res.case_id);
    } catch (err: any) {
      alert(`Demo Scenario Error: ${err.message || 'Execution failed'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-b border-hairline px-6 py-1.5 flex flex-wrap items-center gap-3 text-[11px]">
      <span className="text-muted shrink-0 uppercase tracking-[0.06em]">Demo scenario:</span>

      <select
        value={selectedScenario}
        onChange={(e) => setSelectedScenario(e.target.value)}
        disabled={loading}
        className="bg-transparent text-ink-soft border-0 py-0.5 focus:outline-none disabled:opacity-50 cursor-pointer max-w-xs sm:max-w-sm"
        style={{ colorScheme: 'dark' }}
      >
        {/* Explicit bg/text per option -- a native <option>'s popup list
            doesn't reliably inherit color from its <select> in Chromium,
            falling back to a near-unreadable system default against this
            app's dark theme. */}
        {scenarios.map((sc) => (
          <option key={sc.key} value={sc.key} className="bg-paper-dim text-ink">
            {sc.label} — {sc.desc}
          </option>
        ))}
      </select>

      <button
        onClick={handleRun}
        disabled={loading}
        className="flex items-center gap-1.5 text-accent hover:opacity-70 font-bold uppercase tracking-[0.06em] transition-opacity disabled:opacity-50 shrink-0 cursor-pointer ml-auto"
      >
        {loading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />
            <span>Running…</span>
          </>
        ) : (
          <>
            <Play className="w-3.5 h-3.5 fill-current" strokeWidth={1.75} />
            <span>Run</span>
          </>
        )}
      </button>
    </div>
  );
};
