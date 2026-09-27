import React, { useState } from 'react';
import { TamperResult } from '../types';
import { Layers, Eye, Flame, AlertOctagon, ScanSearch, CheckCircle2 } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

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
        <span className="text-[11px] text-graphite-400">
          Forensic Visualizer Mode:
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
                  <img src={originalImageUrl} alt="Original Document" className="w-full h-full object-contain" />
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
                  <img src={tamperResult.heatmap_url} alt="ELA Heatmap" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-xs text-graphite-500">Heatmap Processing</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="relative rounded-lg overflow-hidden bg-black/40 border border-graphite-800/60 min-h-[420px] max-h-[70vh] flex items-center justify-center">
            <img
              src={viewMode === 'original' ? originalImageUrl : tamperResult.heatmap_url || originalImageUrl}
              alt="Document Forensic View"
              className="max-h-[70vh] w-auto object-contain"
            />
          </div>
        )}
      </div>

      {/* Forensic Signal Breakdown -- secondary to the evidence image above */}
      <div>
        <h4 className="text-[11px] font-medium text-graphite-500 mb-3">
          Forensic multi-signal indicators ({tamperResult.signals.length} detected)
        </h4>

        {tamperResult.signals.length === 0 ? (
          <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" /> No significant image manipulation or recompression anomalies detected.
          </div>
        ) : (
          <div className="space-y-2.5">
            {tamperResult.signals.map((sig, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-graphite-950/70 border border-graphite-800/80 text-xs space-y-1.5 transition-colors hover:border-graphite-700/60"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-orange-300 capitalize flex items-center gap-1.5">
                    <AlertOctagon className="w-3.5 h-3.5 text-orange-400" />
                    {sig.type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-orange-950/80 text-orange-300 border border-orange-500/40 font-bold">
                    Confidence: {Math.round(sig.confidence * 100)}%
                  </span>
                </div>
                <p className="text-graphite-400 text-[11px] leading-relaxed">{sig.explanation}</p>
                {sig.region && sig.region.length === 4 && (
                  <span className="text-[10px] text-graphite-400 block font-mono">
                    Region Box: [x:{sig.region[0]}, y:{sig.region[1]}, w:{sig.region[2]}, h:{sig.region[3]}]
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </ScrollReveal>
  );
};
