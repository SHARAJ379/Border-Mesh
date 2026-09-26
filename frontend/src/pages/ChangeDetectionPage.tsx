import React, { useState } from 'react';
import { ChangeDetectionResult } from '../types';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
import { RiskBadge } from '../components/RiskBadge';
import { GitCompare, Loader2, Play, CheckCircle2, XCircle, ScanFace } from 'lucide-react';

/**
 * Same-Identity Change Detection demo: generates two synthetic specimens
 * for ONE claimed identity ("Version 1" and a later "Version 2" claiming
 * the same name/document number/nationality/country, but with date of
 * birth, date of expiry, and the portrait photo altered), then shows
 * exactly which fields the system flags as changed between them. Both
 * specimens independently pass MRZ checksum validation -- the point of
 * this page is demonstrating that checksum validation alone can't catch a
 * consistently re-forged field, only comparing it against the prior
 * submission can.
 */
const IntroState: React.FC = () => (
  <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-6 text-xs text-graphite-400 space-y-2 transition-all duration-300 hover:border-graphite-700/60">
    <p>
      This generates two fictional "REPUBLIC OF UTOPIA" specimens claiming the
      same identity — same surname, given names, document number, nationality
      and issuing country in both — but Version 2 has a different date of
      birth, date of expiry, and portrait photo.
    </p>
    <p>
      Version 2's MRZ check digits are computed fresh for the new values, so
      it validates perfectly on its own. Checksum validation alone cannot
      tell it apart from a legitimate resubmission — only comparing it
      against what Version 1 actually said can. Zero real-identity risk:
      entirely synthetic, generated fresh on every run.
    </p>
  </div>
);

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <GitCompare className="w-10 h-10 text-graphite-600 mx-auto mb-3" />
    <p className="text-sm font-semibold text-graphite-300">{title}</p>
    <p className="text-xs text-graphite-500 mt-1">{description}</p>
  </div>
);

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-8 h-8">
        <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
        <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
      </div>
      <span className="text-xs text-graphite-400 font-medium">Running comparison…</span>
    </div>
  </div>
);

export const ChangeDetectionPage: React.FC = () => {
  const [result, setResult] = useState<ChangeDetectionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.runChangeDetectionDemo();
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Change detection demo failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <SectionHeading
        title="Same-identity change detection"
        description="Two synthetic submissions of one claimed identity, diffed field-by-field to show exactly what changed between them."
        icon={<GitCompare className="w-4 h-4 text-graphite-500" />}
        action={
          <button
            onClick={handleRun}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-brass-950/70 text-brass-300 border border-brass-500/30 hover:bg-brass-900/70 active:bg-brass-800/70 transition-all duration-200 disabled:opacity-50 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brass-500/50"
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Running comparison…
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                {result ? 'Run again' : 'Run comparison'}
              </>
            )}
          </button>
        }
      />

      {!result && !loading && (
        <IntroState />
      )}

      {error && (
        <div className="bg-rose-950/40 border border-rose-500/30 rounded-xl p-4 text-xs text-rose-300 animate-fade-in">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-5 animate-fade-in">
          {/* Identity summary */}
          <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs transition-all duration-300 hover:border-graphite-700/60">
            <div>
              <span className="text-graphite-500">Claimed identity: </span>
              <span className="text-graphite-200 font-semibold">
                {result.identity.surname} {result.identity.given_names}
              </span>
            </div>
            <div>
              <span className="text-graphite-500">Document No: </span>
              <span className="text-graphite-200 font-semibold">{result.identity.document_number}</span>
            </div>
            <div>
              <span className="text-graphite-500">Country: </span>
              <span className="text-graphite-200 font-semibold">{result.identity.country}</span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <RiskBadge
                level={result.changed_field_count > 0 ? 'HIGH' : 'LOW'}
                size="md"
              />
              <span className="text-graphite-300 font-semibold">
                {result.changed_field_count} of {result.field_diffs.length} fields changed
              </span>
            </div>
          </div>

          {/* Side-by-side specimens */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(['v1', 'v2'] as const).map((v) => {
              const version = result[v];
              return (
                <div key={v} className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-4 space-y-3 transition-all duration-300 hover:border-graphite-700/60">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-graphite-200">{version.label}</span>
                    <span
                      className={`flex items-center gap-1 text-[11px] font-semibold ${
                        version.mrz_checksum_valid ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {version.mrz_checksum_valid ? (
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5" />
                      )}
                      MRZ checksum {version.mrz_checksum_valid ? 'valid' : 'invalid'}
                    </span>
                  </div>
                  <div className="rounded-lg overflow-hidden border border-graphite-800/80 bg-graphite-950">
                    <img src={version.document_image_url} alt={version.label} className="w-full object-contain" />
                  </div>
                  <div className="text-[11px] text-graphite-500">
                    OCR confidence: {Math.round(version.ocr_confidence * 100)}%
                  </div>
                </div>
              );
            })}
          </div>

          {/* Field diff table */}
          <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-4 transition-all duration-300 hover:border-graphite-700/60">
            <h3 className="text-sm font-semibold text-graphite-200 mb-3">Field-level comparison</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-graphite-500 text-left border-b border-graphite-800/60">
                    <th className="py-2 pr-3 font-medium">Field</th>
                    <th className="py-2 pr-3 font-medium">Version 1</th>
                    <th className="py-2 pr-3 font-medium">Version 2</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.field_diffs.map((diff) => (
                    <tr
                      key={diff.field}
                      className={`border-b border-graphite-800/40 last:border-0 transition-colors ${
                        diff.changed ? 'bg-rose-950/20' : ''
                      }`}
                    >
                      <td className="py-2 pr-3 text-graphite-300 font-medium">{diff.label}</td>
                      <td className="py-2 pr-3 text-graphite-400">{diff.v1_value ?? '—'}</td>
                      <td className={`py-2 pr-3 ${diff.changed ? 'text-rose-300 font-semibold' : 'text-graphite-400'}`}>
                        {diff.v2_value ?? '—'}
                      </td>
                      <td className="py-2 pr-3">
                        {diff.changed ? (
                          <RiskBadge level={diff.severity} size="sm" />
                        ) : (
                          <span className="text-[11px] text-graphite-500">Unchanged</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Portrait comparison */}
          <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 space-y-4 transition-all duration-300 hover:border-graphite-700/60">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-graphite-200 flex items-center gap-2">
                <ScanFace className="w-4 h-4 text-graphite-500" />
                Portrait comparison
              </span>
              <span className="text-xs font-semibold text-graphite-200 px-2.5 py-1 rounded-lg bg-graphite-800/60 border border-graphite-700">
                Similarity: {Math.round(result.portrait_comparison.similarity * 100)}%
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col items-center p-3 rounded-xl bg-graphite-950/60 border border-graphite-800/80 transition-colors hover:border-graphite-700/60">
                <span className="text-[10px] text-graphite-400 mb-2 uppercase tracking-wider">Version 1 Portrait</span>
                <div className="w-full max-w-xs mx-auto aspect-[3/4] rounded-lg overflow-hidden bg-graphite-900 border border-graphite-700/60 flex items-center justify-center shadow-lg shadow-black/30">
                  {result.portrait_comparison.v1_portrait_url ? (
                    <img
                      src={result.portrait_comparison.v1_portrait_url}
                      alt="Version 1 portrait"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <span className="text-[11px] text-graphite-500">Not detected</span>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-center p-3 rounded-xl bg-graphite-950/60 border border-graphite-800/80 transition-colors hover:border-graphite-700/60">
                <span className="text-[10px] text-graphite-400 mb-2 uppercase tracking-wider">Version 2 Portrait</span>
                <div className="w-full max-w-xs mx-auto aspect-[3/4] rounded-lg overflow-hidden bg-graphite-900 border border-graphite-700/60 flex items-center justify-center shadow-lg shadow-black/30">
                  {result.portrait_comparison.v2_portrait_url ? (
                    <img
                      src={result.portrait_comparison.v2_portrait_url}
                      alt="Version 2 portrait"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <span className="text-[11px] text-graphite-500">Not detected</span>
                  )}
                </div>
              </div>
            </div>
            <div className="p-3 rounded-xl bg-graphite-950/70 border border-graphite-800/80 flex items-center justify-between text-xs">
              <span className="text-graphite-400">Decision:</span>
              <span
                className={`font-bold ${
                  result.portrait_comparison.status === 'SAME_PORTRAIT' ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {result.portrait_comparison.status.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
