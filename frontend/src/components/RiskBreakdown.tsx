import React, { useEffect, useState } from 'react';
import { RiskFactorContribution } from '../types';
import { Sliders } from 'lucide-react';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';
import { prefersReducedMotion } from '../lib/deviceCapability';

interface RiskBreakdownProps {
  breakdown: RiskFactorContribution[];
  totalScore: number;
}

export const RiskBreakdown: React.FC<RiskBreakdownProps> = ({ breakdown, totalScore }) => {
  // Mounts every line at 0 width and flips to its real value a tick later,
  // so the CSS transition has a "from" state to draw in from -- same
  // reasoning as RiskScore's gauge (setting the final width directly on
  // mount gives the browser nothing to transition from).
  const [drawn, setDrawn] = useState(prefersReducedMotion());
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const t = setTimeout(() => setDrawn(true), 60);
    return () => clearTimeout(t);
  }, []);

  return (
    <ScrollReveal className="border border-hairline p-5 space-y-4">
      <SectionHeading
        level="h3"
        title="Explainable risk breakdown"
        icon={<Sliders className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <span className="text-[11px] text-muted">
            {/* One decimal place -- an integer-rounded score here can look like
                it contradicts System Settings' plain risk-tier boundaries when
                the critical-signal floor lands just above one (e.g. "49" reads
                as still-Medium against a stated 25-49 Medium band, when the
                real, floored value is 49.1 and genuinely HIGH). */}
            Total: <strong className="text-ink figure">{totalScore.toFixed(1)} / 100</strong>
          </span>
        }
      />

      <div className="space-y-3">
        {breakdown.map((item, idx) => {
          const hasWeight = item.weight !== null && item.raw_risk !== null;
          return (
            <div key={idx} className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-ink-soft flex items-center gap-2">
                  <span className="figure text-ink font-bold">
                    {item.weighted_contribution >= 0 ? '+' : ''}{item.weighted_contribution.toFixed(1)}
                  </span>
                  <span>{item.factor}</span>
                  {hasWeight && (
                    <span className="text-[10px] text-muted">({Math.round((item.weight as number) * 100)}% Weight)</span>
                  )}
                </span>
                {hasWeight && (
                  <span className="text-muted figure text-[11px]">
                    Raw Risk: {Math.round(item.raw_risk as number)}%
                  </span>
                )}
              </div>

              {/* A thin drawn ink line, not a filled rounded-pill bar. */}
              {hasWeight && (
                <div className="w-full h-[3px] bg-hairline overflow-hidden">
                  <div
                    className="h-full bg-ink transition-all duration-700"
                    style={{ width: drawn ? `${Math.min(100, Math.max(0, item.raw_risk as number))}%` : '0%' }}
                  ></div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-muted pt-2 border-t border-hairline">
        See the Risk Reasons tab for the full itemized checks (pass and fail) behind these numbers.
      </p>
    </ScrollReveal>
  );
};
