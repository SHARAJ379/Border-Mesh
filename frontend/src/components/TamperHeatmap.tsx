import React, { useState } from 'react';
import { TamperResult } from '../types';
import { Layers, Eye, Flame, AlertOctagon, ScanSearch, CheckCircle2, ZoomIn } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';
import { Magnifier } from './Magnifier';
import { appendToken } from '../lib/auth';

interface TamperHeatmapProps {
  originalImageUrl?: string;
  tamperResult?: TamperResult;
}

const EmptyState: React.FC = () => (
  <div className="border border-hairline p-6 text-center">
    <Layers className="w-7 h-7 text-muted mx-auto mb-2" strokeWidth={1.5} />
    <p className="text-[11px] text-muted">No tamper forensic analysis conducted yet.</p>
  </div>
);

export const TamperHeatmap: React.FC<TamperHeatmapProps> = ({
  originalImageUrl,
  tamperResult
}) => {
  const [viewMode, setViewMode] = useState<'original' | 'heatmap' | 'split'>('heatmap');

  if (!tamperResult) {
    return <EmptyState />;
  }

  const tamperRiskPercent = Math.round(tamperResult.tamper_risk * 100);

  const viewTabs = [
    { id: 'original', icon: Eye, label: 'Original' },
    { id: 'heatmap', icon: Flame, label: 'ELA Heatmap' },
    { id: 'split', icon: ScanSearch, label: 'Side-by-Side' }
  ] as const;

  return (
    <ScrollReveal className="border border-hairline p-5 space-y-5">
      {/* Header */}
      <SectionHeading
        level="h3"
        title="Tamper AI & error level analysis"
        icon={<Layers className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <div className="flex items-center gap-3">
            <RiskBadge level={tamperResult.risk_level} size="sm" />
            <span className="figure text-[12px] font-bold text-ink">
              Risk: {tamperRiskPercent}%
            </span>
          </div>
        }
      />

      {/* View toggle -- the spec's own "variant picker" pattern */}
      <div className="flex items-center justify-between border-b border-hairline pb-0 flex-wrap gap-3">
        <span className="text-[11px] text-muted flex items-center gap-1.5">
          Forensic Visualizer Mode:
          <span className="hidden sm:flex items-center gap-1 text-muted">
            <ZoomIn className="w-3 h-3" strokeWidth={1.75} /> hover the image to magnify
          </span>
        </span>
        <div className="flex items-center gap-5">
          {viewTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                aria-pressed={viewMode === tab.id}
                onClick={() => setViewMode(tab.id)}
                className="tab-flat tab-flat-accent flex items-center gap-1.5"
              >
                <Icon className="w-3 h-3" strokeWidth={1.75} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Image evidence -- a real photograph, so it's the one place this
          system allows a shadow (see .photo-shadow / the Foundation
          discussion in git history), sitting directly on the paper ground
          rather than in a bordered card. */}
      <div className="py-2">
        {viewMode === 'split' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="space-y-2">
              <span className="label-eyebrow block">
                Original Specimen
              </span>
              <div className="photo-shadow border border-hairline bg-paper-dim aspect-[3/4] sm:aspect-[4/5] flex items-center justify-center overflow-hidden">
                {originalImageUrl ? (
                  <Magnifier src={originalImageUrl} alt="Original Document" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-[11px] text-muted">No Image</span>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <span className="label-eyebrow flex items-center gap-1">
                <Flame className="w-3 h-3" strokeWidth={1.75} /> ELA Thermal Heatmap Overlay
              </span>
              <div className="photo-shadow border border-hairline bg-paper-dim aspect-[3/4] sm:aspect-[4/5] flex items-center justify-center overflow-hidden">
                {tamperResult.heatmap_url ? (
                  <Magnifier src={appendToken(tamperResult.heatmap_url)} alt="ELA Heatmap" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-[11px] text-muted">Heatmap Processing</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="photo-shadow border border-hairline bg-paper-dim min-h-[420px] max-h-[70vh] flex items-center justify-center overflow-hidden">
            {(() => {
              const activeSrc = viewMode === 'original' ? originalImageUrl : appendToken(tamperResult.heatmap_url) || originalImageUrl;
              return activeSrc ? (
                <Magnifier
                  src={activeSrc}
                  alt="Document Forensic View"
                  className="max-h-[70vh] w-auto object-contain"
                />
              ) : (
                <span className="text-[11px] text-muted">No Image</span>
              );
            })()}
          </div>
        )}
      </div>

      {/* Forensic check breakdown -- secondary to the evidence image above.
          Shows every check that ran, not just failures: a clean scan states
          WHY it's clean (each region/heuristic's own measured evidence),
          not silence. */}
      <div>
        {(() => {
          const flagged = tamperResult.checks.filter((c) => c.status === 'FAIL');
          const clean = tamperResult.checks.filter((c) => c.status !== 'FAIL');
          return (
            <>
              <h4 className="label-eyebrow mb-3">
                Forensic multi-signal indicators ({flagged.length} flagged of {tamperResult.checks.length} checks)
              </h4>

              {flagged.length === 0 ? (
                <div className="py-3 border-t border-hairline text-signal-low text-[12px] flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} /> No significant image manipulation or recompression anomalies detected.
                </div>
              ) : (
                <div>
                  {flagged.map((c, idx) => (
                    <div
                      key={idx}
                      className="py-3 border-t border-hairline text-[12px] space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-signal-high flex items-center gap-1.5">
                          <AlertOctagon className="w-3.5 h-3.5" strokeWidth={1.75} />
                          {c.label}
                        </span>
                        <span className="text-[10px] figure font-bold text-signal-high">
                          Confidence: {Math.round(c.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-ink-soft text-[11px] leading-relaxed">{c.explanation}</p>
                      {c.evidence?.measured_value !== null && c.evidence?.measured_value !== undefined && (
                        <span className="text-[10px] text-muted block figure">
                          Measured: {String(c.evidence.measured_value)}
                          {c.evidence.threshold_value !== null && c.evidence.threshold_value !== undefined
                            ? ` (threshold: ${String(c.evidence.threshold_value)})` : ''}
                          {c.evidence.unit ? ` [${c.evidence.unit}]` : ''}
                        </span>
                      )}
                      {c.evidence?.region && c.evidence.region.length === 4 && (
                        <span className="text-[10px] text-muted block figure">
                          Region Box: [x:{c.evidence.region[0]}, y:{c.evidence.region[1]}, w:{c.evidence.region[2]}, h:{c.evidence.region[3]}]
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {clean.length > 0 && (
                <details className="mt-3 group">
                  <summary className="text-[11px] text-muted cursor-pointer hover:text-ink select-none">
                    {clean.length} clean check{clean.length === 1 ? '' : 's'} (no anomaly found) — click to view
                  </summary>
                  <div className="mt-2">
                    {clean.map((c, idx) => (
                      <div key={idx} className="py-2 border-t border-hairline text-[11px] text-ink-soft flex items-center justify-between gap-3">
                        <span>{c.label}</span>
                        <span className="text-muted shrink-0 figure">
                          {c.evidence?.measured_value !== null && c.evidence?.measured_value !== undefined
                            ? String(c.evidence.measured_value) : 'clean'}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          );
        })()}
      </div>
    </ScrollReveal>
  );
};
