import React from 'react';
import { RiskFactorContribution } from '../types';
import { Sliders } from 'lucide-react';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

interface RiskBreakdownProps {
  breakdown: RiskFactorContribution[];
  totalScore: number;
}

export const RiskBreakdown: React.FC<RiskBreakdownProps> = ({ breakdown, totalScore }) => {
  return (
    <ScrollReveal className="glass-panel rounded-xl p-5 space-y-4">
      <SectionHeading
        level="h3"
        title="Explainable risk breakdown"
        icon={<Sliders className="w-4 h-4 text-graphite-500" />}
        action={
          <span className="text-xs text-graphite-400">
            {/* One decimal place -- an integer-rounded score here can look like
                it contradicts System Settings' plain risk-tier boundaries when
                the critical-signal floor lands just above one (e.g. "49" reads
                as still-Medium against a stated 25-49 Medium band, when the
                real, floored value is 49.1 and genuinely HIGH). */}
            Total: <strong className="text-graphite-100">{totalScore.toFixed(1)} / 100</strong>
          </span>
        }
      />

      <div className="space-y-3">
        {breakdown.map((item, idx) => {
          const hasWeight = item.weight !== null && item.raw_risk !== null;
          return (
            <div key={idx} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-graphite-300 flex items-center gap-2">
                  <span className="text-graphite-200 font-bold">
                    {item.weighted_contribution >= 0 ? '+' : ''}{item.weighted_contribution.toFixed(1)}
                  </span>
                  <span>{item.factor}</span>
                  {hasWeight && (
                    <span className="text-[10px] text-graphite-400">({Math.round((item.weight as number) * 100)}% Weight)</span>
                  )}
                </span>
                {hasWeight && (
                  <span className="text-graphite-400 text-[11px]">
                    Raw Risk: {Math.round(item.raw_risk as number)}%
                  </span>
                )}
              </div>

              {/* Progress bar -- only meaningful for a proportional weighted
                  category; the flat floor-adjustment row has none. */}
              {hasWeight && (
                <div className="w-full bg-graphite-950 h-2 rounded-full overflow-hidden border border-graphite-800/80">
                  <div
                    className="h-full bg-graphite-500 rounded-full transition-all duration-700"
                    style={{ width: `${Math.min(100, Math.max(0, item.raw_risk as number))}%` }}
                  ></div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-graphite-500 pt-1 border-t border-graphite-800/60">
        See the Risk Reasons tab for the full itemized checks (pass and fail) behind these numbers.
      </p>
    </ScrollReveal>
  );
};
