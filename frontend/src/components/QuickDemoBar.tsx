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
    <div className="border-b border-graphite-800/60 px-6 py-1.5 flex flex-wrap items-center gap-3 text-xs">
      <span className="text-graphite-500 shrink-0">Demo scenario:</span>

      <select
        value={selectedScenario}
        onChange={(e) => setSelectedScenario(e.target.value)}
        disabled={loading}
        className="bg-transparent text-graphite-300 border-0 py-0.5 focus:outline-none disabled:opacity-50 cursor-pointer max-w-xs sm:max-w-sm"
      >
        {scenarios.map((sc) => (
          <option key={sc.key} value={sc.key} className="bg-graphite-900">
            {sc.label} — {sc.desc}
          </option>
        ))}
      </select>

      <button
        onClick={handleRun}
        disabled={loading}
        className="flex items-center gap-1.5 text-brass-400 hover:text-brass-300 font-medium transition-colors disabled:opacity-50 shrink-0 cursor-pointer ml-auto"
      >
        {loading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Running…</span>
          </>
        ) : (
          <>
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Run</span>
          </>
        )}
      </button>
    </div>
  );
};
