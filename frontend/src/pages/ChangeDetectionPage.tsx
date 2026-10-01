import React, { useState } from 'react';
import { ChangeDetectionResult } from '../types';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
import { RiskBadge } from '../components/RiskBadge';
import { ScrollReveal } from '../components/ScrollReveal';
import { GitCompare, Loader2, Play, CheckCircle2, XCircle, ScanFace } from 'lucide-react';
import { appendToken } from '../lib/auth';

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
  <div className="border border-hairline p-6 text-[12px] text-ink-soft space-y-3">
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

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-7 h-7">
        <div className="absolute inset-0 border border-hairline" />
        <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
      </div>
      <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Running comparison&hellip;</span>
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
    <div className="space-y-6">
      <SectionHeading
        title="Same-identity change detection"
        description="Two synthetic submissions of one claimed identity, diffed field-by-field to show exactly what changed between them."
        icon={<GitCompare className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <button
            onClick={handleRun}
            disabled={loading}
            className="btn-primary flex items-center gap-2 px-4 py-2 text-[11px] disabled:opacity-50 cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />
                Running comparison…
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" strokeWidth={1.75} />
                {result ? 'Run again' : 'Run comparison'}
              </>
            )}
          </button>
        }
      />

      {!result && !loading && (
        <IntroState />
      )}

      {loading && <LoadingState />}

      {error && (
        <div className="strip py-4 text-[12px] text-signal-critical animate-fade-in">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6 animate-fade-in">
          {/* Identity summary */}
          <ScrollReveal className="border-t border-b border-hairline py-4 flex flex-wrap items-center gap-x-8 gap-y-2 text-[12px]">
            <div>
              <span className="text-muted">Claimed identity: </span>
              <span className="text-ink font-bold">
                {result.identity.surname} {result.identity.given_names}
              </span>
            </div>
            <div>
              <span className="text-muted">Document No: </span>
              <span className="text-ink figure font-bold">{result.identity.document_number}</span>
            </div>
            <div>
              <span className="text-muted">Country: </span>
              <span className="text-ink font-bold">{result.identity.country}</span>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <RiskBadge
                level={result.changed_field_count > 0 ? 'HIGH' : 'LOW'}
                size="md"
              />
              <span className="text-ink figure font-bold">
                {result.changed_field_count} of {result.field_diffs.length} fields changed
              </span>
            </div>
          </ScrollReveal>

          {/* Side-by-side specimens -- real photographs, so they get the
              one shadow this system allows. */}
          <ScrollReveal className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {(['v1', 'v2'] as const).map((v) => {
              const version = result[v];
              return (
                <div key={v} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-bold text-ink">{version.label}</span>
                    <span className={`badge-signal ${version.mrz_checksum_valid ? 'badge-low' : 'badge-critical'}`}>
                      {version.mrz_checksum_valid ? (
                        <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} />
                      ) : (
                        <XCircle className="w-3.5 h-3.5" strokeWidth={1.75} />
                      )}
                      MRZ checksum {version.mrz_checksum_valid ? 'valid' : 'invalid'}
                    </span>
                  </div>
                  <div className="photo-shadow border border-hairline bg-paper-dim overflow-hidden">
                    <img src={appendToken(version.document_image_url)} alt={version.label} className="w-full object-contain" />
                  </div>
                  <div className="text-[11px] text-muted figure">
                    OCR confidence: {Math.round(version.ocr_confidence * 100)}%
                  </div>
                </div>
              );
            })}
          </ScrollReveal>

          {/* Field diff table */}
          <ScrollReveal>
            <h3 className="font-display text-[17px] text-ink mb-3">Field-level comparison</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-muted uppercase tracking-[0.06em] text-[10px] text-left border-b border-hairline">
                    <th className="py-2 pr-3 font-normal">Field</th>
                    <th className="py-2 pr-3 font-normal">Version 1</th>
                    <th className="py-2 pr-3 font-normal">Version 2</th>
                    <th className="py-2 pr-3 font-normal">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.field_diffs.map((diff) => (
                    <tr
                      key={diff.field}
                      className="border-b border-hairline last:border-0"
                    >
                      <td className="py-2 pr-3 text-ink font-bold">{diff.label}</td>
                      <td className="py-2 pr-3 text-muted figure">{diff.v1_value ?? '—'}</td>
                      <td className={`py-2 pr-3 figure ${diff.changed ? 'text-signal-critical font-bold' : 'text-muted'}`}>
                        {diff.v2_value ?? '—'}
                      </td>
                      <td className="py-2 pr-3">
                        {diff.changed ? (
                          <RiskBadge level={diff.severity} size="sm" />
                        ) : (
                          <span className="text-[11px] text-muted">Unchanged</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ScrollReveal>

          {/* Portrait comparison */}
          <ScrollReveal className="border border-hairline p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-bold text-ink flex items-center gap-2">
                <ScanFace className="w-4 h-4 text-muted" strokeWidth={1.75} />
                Portrait comparison
              </span>
              <span className="figure text-[12px] font-bold text-ink">
                Similarity: {Math.round(result.portrait_comparison.similarity * 100)}%
              </span>
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="flex flex-col items-center">
                <span className="label-eyebrow mb-2">Version 1 Portrait</span>
                <div className="photo-shadow border border-hairline w-full max-w-xs mx-auto aspect-[3/4] bg-paper-dim flex items-center justify-center overflow-hidden">
                  {result.portrait_comparison.v1_portrait_url ? (
                    <img
                      src={appendToken(result.portrait_comparison.v1_portrait_url)}
                      alt="Version 1 portrait"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <span className="text-[11px] text-muted">Not detected</span>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-center">
                <span className="label-eyebrow mb-2">Version 2 Portrait</span>
                <div className="photo-shadow border border-hairline w-full max-w-xs mx-auto aspect-[3/4] bg-paper-dim flex items-center justify-center overflow-hidden">
                  {result.portrait_comparison.v2_portrait_url ? (
                    <img
                      src={appendToken(result.portrait_comparison.v2_portrait_url)}
                      alt="Version 2 portrait"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <span className="text-[11px] text-muted">Not detected</span>
                  )}
                </div>
              </div>
            </div>
            <div className="pt-3 border-t border-hairline flex items-center justify-between text-[12px]">
              <span className="text-muted">Decision:</span>
              <span className={`font-bold ${
                result.portrait_comparison.status === 'SAME_PORTRAIT' ? 'text-signal-low' : 'text-signal-critical'
              }`}>
                {result.portrait_comparison.status.replace(/_/g, ' ')}
              </span>
            </div>
          </ScrollReveal>
        </div>
      )}
    </div>
  );
};
