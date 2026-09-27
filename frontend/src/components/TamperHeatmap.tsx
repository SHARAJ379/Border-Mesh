import React, { useState } from 'react';
import { TamperResult } from '../types';
import { Layers, Eye, Flame, AlertOctagon, ScanSearch, CheckCircle2, ZoomIn } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';
import { Magnifier } from './Magnifier';

interface TamperHeatmapProps {
  originalImageUrl?: string;
  tamperResult?: TamperResult;
}

const EmptyState: React.FC = () => (
  <div className="glass-panel rounded-xl p-6 text-center">
    <Layers className="w-8 h-8 text-graphite-600 mx-auto mb-2" />
    <p className="text-xs text-graphite-500">No tamper forensic analysis conducted yet.</p>
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
    <ScrollReveal className="glass-panel rounded-xl p-5 space-y-5">
      {/* Header */}
      <SectionHeading
        level="h3"
        title="Tamper AI & error level analysis"
        icon={<Layers className="w-4 h-4 text-graphite-500" />}
        action={
          <div className="flex items-center gap-2">
            <RiskBadge level={tamperResult.risk_level} size="sm" />
            <span className="text-xs font-semibold text-graphite-200 px-2.5 py-1 rounded-lg bg-graphite-800/60 border border-graphite-700">
              Risk: {tamperRiskPercent}%
            </span>
          </div>
        }
      />

      {/* View Toggle Tabs */}
      <div className="flex items-center justify-between border-b border-graphite-800/60 pb-3">
        <span className="text-[11px] text-graphite-400 flex items-center gap-1.5">
          Forensic Visualizer Mode:
          <span className="hidden sm:flex items-center gap-1 text-graphite-500">
            <ZoomIn className="w-3 h-3" /> hover the image to magnify
          </span>
        </span>
        <div className="flex items-center gap-1 bg-graphite-950/60 p-1 rounded-lg border border-graphite-800/80 text-xs">
          {viewTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = viewMode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setViewMode(tab.id)}
                className={`px-3 py-1.5 rounded-lg transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-brass-950/80 text-brass-300 border border-brass-500/40 font-semibold shadow-sm'
                    : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60'
                }`}
              >
                <Icon className="w-3 h-3" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Image Preview Area -- the evidence is the hero of this view: large,
          minimal framing, everything else here is secondary. */}
      <div className="rounded-xl overflow-hidden bg-graphite-950 border border-graphite-800/80 p-2 transition-colors">
        {viewMode === 'split' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-2">
              <span className="text-[10px] text-graphite-400 uppercase tracking-wider block">
                Original Specimen
              </span>
              <div className="relative rounded-lg overflow-hidden bg-black/40 border border-graphite-800/60 aspect-[3/4] sm:aspect-[4/5] flex items-center justify-center">
                {originalImageUrl ? (
                  <Magnifier src={originalImageUrl} alt="Original Document" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-xs text-graphite-500">No Image</span>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <span className="text-[10px] text-graphite-400 uppercase tracking-wider block flex items-center gap-1">
                <Flame className="w-3 h-3" /> ELA Thermal Heatmap Overlay
              </span>
              <div className="relative rounded-lg overflow-hidden bg-black/40 border border-graphite-800/60 aspect-[3/4] sm:aspect-[4/5] flex items-center justify-center">
                {tamperResult.heatmap_url ? (
                  <Magnifier src={tamperResult.heatmap_url} alt="ELA Heatmap" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-xs text-graphite-500">Heatmap Processing</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="relative rounded-lg overflow-hidden bg-black/40 border border-graphite-800/60 min-h-[420px] max-h-[70vh] flex items-center justify-center">
            {(() => {
              const activeSrc = viewMode === 'original' ? originalImageUrl : tamperResult.heatmap_url || originalImageUrl;
              return activeSrc ? (
                <Magnifier
                  src={activeSrc}
                  alt="Document Forensic View"
                  className="max-h-[70vh] w-auto object-contain"
                />
              ) : (
                <span className="text-xs text-graphite-500">No Image</span>
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
              <h4 className="text-[11px] font-medium text-graphite-500 mb-3">
                Forensic multi-signal indicators ({flagged.length} flagged of {tamperResult.checks.length} checks)
              </h4>

              {flagged.length === 0 ? (
                <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5" /> No significant image manipulation or recompression anomalies detected.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {flagged.map((c, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-graphite-950/70 border border-graphite-800/80 text-xs space-y-1.5 transition-colors hover:border-graphite-700/60"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-orange-300 flex items-center gap-1.5">
                          <AlertOctagon className="w-3.5 h-3.5 text-orange-400" />
                          {c.label}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-orange-950/80 text-orange-300 border border-orange-500/40 font-bold">
                          Confidence: {Math.round(c.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-graphite-400 text-[11px] leading-relaxed">{c.explanation}</p>
                      {c.evidence?.measured_value !== null && c.evidence?.measured_value !== undefined && (
                        <span className="text-[10px] text-graphite-400 block font-mono">
                          Measured: {String(c.evidence.measured_value)}
                          {c.evidence.threshold_value !== null && c.evidence.threshold_value !== undefined
                            ? ` (threshold: ${String(c.evidence.threshold_value)})` : ''}
                          {c.evidence.unit ? ` [${c.evidence.unit}]` : ''}
                        </span>
                      )}
                      {c.evidence?.region && c.evidence.region.length === 4 && (
                        <span className="text-[10px] text-graphite-400 block font-mono">
                          Region Box: [x:{c.evidence.region[0]}, y:{c.evidence.region[1]}, w:{c.evidence.region[2]}, h:{c.evidence.region[3]}]
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {clean.length > 0 && (
                <details className="mt-3 group">
                  <summary className="text-[11px] text-graphite-500 cursor-pointer hover:text-graphite-300 select-none">
                    {clean.length} clean check{clean.length === 1 ? '' : 's'} (no anomaly found) — click to view
                  </summary>
                  <div className="mt-2 space-y-1.5">
                    {clean.map((c, idx) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-graphite-950/50 border border-graphite-800/60 text-[11px] text-graphite-400 flex items-center justify-between gap-3">
                        <span>{c.label}</span>
                        <span className="text-graphite-500 shrink-0">
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
