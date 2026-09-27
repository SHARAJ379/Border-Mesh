import React from 'react';
import { RiskLevel } from '../types';
import { ShieldAlert, ShieldCheck, AlertTriangle, ShieldX, Info } from 'lucide-react';

interface RiskScoreProps {
  score: number;
  level: RiskLevel;
  recommendation: string;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskScore: React.FC<RiskScoreProps> = ({
  score,
  level,
  recommendation,
  size = 'md'
}) => {
  const getTheme = () => {
    switch (level) {
      case 'LOW':
        return { stroke: 'var(--color-signal-low)', textCls: 'text-signal-low', icon: ShieldCheck };
      case 'MEDIUM':
        return { stroke: 'var(--color-signal-medium)', textCls: 'text-signal-medium', icon: AlertTriangle };
      case 'HIGH':
        return { stroke: 'var(--color-signal-high)', textCls: 'text-signal-high', icon: ShieldAlert };
      case 'CRITICAL':
      default:
        return { stroke: 'var(--color-signal-critical)', textCls: 'text-signal-critical', icon: ShieldX };
    }
  };

  const theme = getTheme();
  const Icon = theme.icon;

  // Self-drawing SVG meter, the same technique as the /welcome
  // demonstration panel's gauge -- a real forensic reading here, not a
  // marketing device, so the arc is colored by the signal-ink severity
  // family instead of the single accent blue.
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;

  const sizeStyles = {
    sm: { svg: 'w-24 h-24', score: 'text-2xl', label: 'text-sm', rec: 'text-xs', pad: 'p-4' },
    md: { svg: 'w-32 h-32', score: 'text-3xl', label: 'text-xl', rec: 'text-sm', pad: 'p-5' },
    lg: { svg: 'w-40 h-40', score: 'text-4xl', label: 'text-2xl', rec: 'text-base', pad: 'p-6' },
  }[size];

  return (
    <div className={`border border-hairline ${sizeStyles.pad}`}>
      <div className="flex flex-col sm:flex-row items-center gap-6">
        {/* Circular gauge */}
        <div className="relative flex items-center justify-center flex-shrink-0">
          <svg className={`${sizeStyles.svg} transform -rotate-90`} viewBox="0 0 120 120">
            <circle cx="60" cy="60" r={radius} stroke="var(--color-hairline)" strokeWidth="1.5" fill="transparent" />
            <circle
              cx="60" cy="60" r={radius}
              stroke={theme.stroke}
              strokeWidth="2"
              fill="transparent"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="square"
              className="transition-all duration-1000 ease-out"
            />
          </svg>

          <div className="absolute flex flex-col items-center justify-center text-center">
            {/* One decimal place, not a rounded integer -- an isolated
                CRITICAL signal floors the true score to just above the
                Medium/High boundary (e.g. 49.1), which a rounded "49"
                visually contradicts System Settings' own stated 25-49
                Medium band. */}
            <span className={`font-display ${sizeStyles.score} text-ink`}>
              {score.toFixed(1)}
            </span>
            <span className="text-[10px] uppercase text-muted tracking-[0.06em]">
              / 100
            </span>
          </div>
        </div>

        {/* Details & recommendation */}
        <div className="flex-1 text-center sm:text-left space-y-3">
          <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
            <Icon className={`w-4 h-4 ${theme.textCls}`} strokeWidth={1.75} />
            <span className={`${sizeStyles.label} font-bold uppercase tracking-[0.04em] ${theme.textCls}`}>
              {level} RISK
            </span>
          </div>

          <div className="border-t border-hairline pt-3">
            <p className="label-eyebrow mb-1">
              Recommended Action
            </p>
            <p className={`${sizeStyles.rec} font-bold ${theme.textCls}`}>
              {recommendation}
            </p>
          </div>

          <p className="text-[11px] text-muted flex items-center gap-1.5">
            <Info className="w-3 h-3 shrink-0" strokeWidth={1.75} /> AI decision-support indicator. Final border determination rests with the screening officer.
          </p>
        </div>
      </div>
    </div>
  );
};
