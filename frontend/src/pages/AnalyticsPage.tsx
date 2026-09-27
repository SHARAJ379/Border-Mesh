import React, { useEffect, useState } from 'react';
import { DashboardStats } from '../types';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';
import { BarChart3, Activity, ShieldCheck, Zap, AlertTriangle } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LabelList
} from 'recharts';

const LoadingState: React.FC = () => (
  <div className="flex items-center justify-center min-h-[40vh]">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-8 h-8">
        <div className="absolute inset-0 border border-hairline" />
        <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
      </div>
      <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading analytics engine&hellip;</span>
    </div>
  </div>
);

const ErrorState: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => (
  <div className="p-8 flex flex-col items-center gap-3 text-center max-w-sm mx-auto animate-fade-in">
    <AlertTriangle className="w-6 h-6 text-signal-high" strokeWidth={1.5} />
    <p className="text-[13px] text-ink font-bold">Couldn't load analytics</p>
    <p className="text-[11px] text-muted">{message}</p>
    <button onClick={onRetry} className="btn-primary mt-2 px-5 py-2.5 text-[11px]">
      Retry
    </button>
  </div>
);

export const AnalyticsPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getDashboardStats();
      setStats(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error || !stats) {
    return <ErrorState message={error || 'No data returned from the server.'} onRetry={loadData} />;
  }

  const docTypeData = Object.entries(stats.document_types || {}).map(([k, v]) => ({
    type: k,
    count: v
  }));

  // Real per-module averages computed server-side from each case's own audit
  // trail timestamps (see backend/app/api/routes/dashboard.py) -- a module
  // with zero completed cases so far reports 0ms rather than a guess.
  const latencyBreakdown = stats.latency_breakdown.map((entry) => ({
    module: entry.module,
    time: entry.time_ms
  }));

  const kpis = [
    {
      label: 'Average pipeline latency',
      value: `${(stats.avg_processing_time_ms / 1000).toFixed(2)}s`,
      icon: Zap,
      note: 'Target: under 5.0s'
    },
    {
      label: 'Risk mitigation rate',
      value: `${stats.documents_screened > 0 ? Math.round((stats.cleared_cases / stats.documents_screened) * 100) : 0}%`,
      icon: ShieldCheck,
      note: 'Admitted without secondary inspection'
    },
    {
      label: 'Anomaly detection yield',
      value: `${stats.documents_screened > 0 ? Math.round(((stats.high_risk_cases + stats.critical_cases) / stats.documents_screened) * 100) : 0}%`,
      icon: Activity,
      note: 'Cases escalated for manual inspection'
    },
  ];

  const chartAxisStyle = { stroke: '#767E8C', fontSize: 10 };
  const tooltipStyle = {
    contentStyle: { backgroundColor: '#EFE9DD', border: '1px solid #141C2B29', borderRadius: 0, fontSize: '11px', padding: '8px 12px', fontFamily: 'Courier Prime, monospace' },
    itemStyle: { color: '#141C2B' },
    cursor: { fill: '#141C2B0A' },
  };

  return (
    <div className="space-y-10">
      <SectionHeading
        title="Analytics"
        description="Deep-dive telemetry into AI module triggers, latency profiles, and risk distributions."
        icon={<BarChart3 className="w-5 h-5 text-accent" strokeWidth={1.75} />}
      />

      {/* KPI strip */}
      <ScrollReveal>
        <div className="grid grid-cols-1 sm:grid-cols-3 border-t border-b border-hairline divide-x divide-hairline">
          {kpis.map((kpi) => {
            const Icon = kpi.icon;
            return (
              <div key={kpi.label} className="px-5 py-4">
                <div className="flex items-start justify-between mb-2">
                  <span className="label-eyebrow">{kpi.label}</span>
                  <Icon className="w-4 h-4 text-muted" strokeWidth={1.75} />
                </div>
                <div className="figure text-[26px] font-display text-ink leading-none">
                  {kpi.value}
                </div>
                <div className="text-[10px] text-muted mt-1.5">{kpi.note}</div>
              </div>
            );
          })}
        </div>
      </ScrollReveal>

      {/* Latency by module & document breakdown */}
      <ScrollReveal className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <div className="lg:col-span-7">
          <SectionHeading level="h3" title="Component processing latency" description="Milliseconds per pipeline module" />
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyBreakdown} layout="vertical" margin={{ right: 36 }}>
                <XAxis type="number" tickLine={false} axisLine={{ stroke: '#141C2B29' }} tick={{ fill: chartAxisStyle.stroke, fontSize: chartAxisStyle.fontSize }} />
                <YAxis type="category" dataKey="module" width={140} tickLine={false} axisLine={false} tick={{ fill: '#4A5364', fontSize: chartAxisStyle.fontSize }} />
                <Tooltip {...tooltipStyle} formatter={(value: any) => `${value}ms`} />
                <Bar dataKey="time" fill="#2C4A8F" radius={[0, 0, 0, 0]} maxBarSize={10}>
                  <LabelList dataKey="time" position="right" formatter={(value?: React.ReactNode) => `${value}ms`} fill="#4A5364" fontSize={10} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-5">
          <SectionHeading level="h3" title="Document types screened" />
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={docTypeData} margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                <XAxis dataKey="type" tickLine={false} axisLine={{ stroke: '#141C2B29' }} tick={{ fill: chartAxisStyle.stroke, fontSize: chartAxisStyle.fontSize }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#4A5364', fontSize: chartAxisStyle.fontSize }} />
                <Tooltip {...tooltipStyle} formatter={(value: any) => `${value}`} />
                <Bar dataKey="count" fill="#2C4A8F" radius={[0, 0, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </ScrollReveal>
    </div>
  );
};
