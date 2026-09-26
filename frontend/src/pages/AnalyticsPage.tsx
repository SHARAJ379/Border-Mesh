import React, { useEffect, useState } from 'react';
import { DashboardStats } from '../types';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
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
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
        <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
      </div>
      <span className="text-xs text-graphite-400 font-medium tracking-wide">Loading analytics engine…</span>
    </div>
  </div>
);

const ErrorState: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => (
  <div className="p-8 flex flex-col items-center gap-3 text-center max-w-sm mx-auto animate-fade-in">
    <AlertTriangle className="w-8 h-8 text-rose-400" />
    <p className="text-sm text-graphite-200 font-medium">Couldn't load analytics</p>
    <p className="text-xs text-graphite-500">{message}</p>
    <button
      onClick={onRetry}
      className="mt-2 px-5 py-2.5 rounded-lg bg-brass-600 hover:bg-brass-500 text-white text-xs font-semibold transition-all shadow-md shadow-brass-950/40 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brass-500/50"
    >
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
      color: 'text-brass-300',
      icon: Zap,
      iconColor: 'text-brass-400',
      note: 'Target: under 5.0s'
    },
    {
      label: 'Risk mitigation rate',
      value: `${stats.documents_screened > 0 ? Math.round((stats.cleared_cases / stats.documents_screened) * 100) : 0}%`,
      color: 'text-emerald-400',
      icon: ShieldCheck,
      iconColor: 'text-emerald-400',
      note: 'Admitted without secondary inspection'
    },
    {
      label: 'Anomaly detection yield',
      value: `${stats.documents_screened > 0 ? Math.round(((stats.high_risk_cases + stats.critical_cases) / stats.documents_screened) * 100) : 0}%`,
      color: 'text-orange-400',
      icon: Activity,
      iconColor: 'text-orange-400',
      note: 'Cases escalated for manual inspection'
    },
  ];

  return (
    <div className="space-y-7">
      <SectionHeading
        title="Analytics"
        description="Deep-dive telemetry into AI module triggers, latency profiles, and risk distributions."
        icon={<BarChart3 className="w-5 h-5 text-brass-400" />}
      />

      {/* KPI strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div key={kpi.label} className="rounded-xl bg-graphite-900/90 border border-graphite-800/80 p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60 hover:shadow-lg hover:shadow-brass-950/20">
              <div className="flex items-start justify-between mb-3">
                <span className="text-[11px] font-medium text-graphite-500 uppercase tracking-wider">{kpi.label}</span>
                <div className="p-1.5 rounded-lg bg-graphite-950/60 border border-graphite-800/50">
                  <Icon className={`w-4 h-4 ${kpi.iconColor}`} />
                </div>
              </div>
              <div className="space-y-1">
                <div className={`text-3xl font-bold ${kpi.color} tracking-tight`}>
                  {kpi.value}
                </div>
                <div className="text-[10px] text-graphite-500">{kpi.note}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Latency by Module & Document Breakdown -- asymmetric: latency has
          more rows, so it gets more room. */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading level="h3" title="Component processing latency" description="Milliseconds per pipeline module" />
          <div className="h-64 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyBreakdown} layout="vertical" margin={{ right: 36 }}>
                <XAxis
                  type="number"
                  stroke="#6B655A"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#8C8579' }}
                />
                <YAxis
                  type="category"
                  dataKey="module"
                  stroke="#8C8579"
                  fontSize={11}
                  width={140}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#B8B3A8' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#17171A',
                    borderColor: '#3D3933',
                    borderRadius: '10px',
                    fontSize: '12px',
                    padding: '8px 12px',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.4)'
                  }}
                  itemStyle={{ color: '#EBE9E5' }}
                  formatter={(value: any) => `${value}ms`}
                />
                <Bar
                  dataKey="time"
                  fill="#5C948C"
                  radius={[0, 6, 6, 0]}
                  maxBarSize={32}
                >
                  <LabelList
                    dataKey="time"
                    position="right"
                    formatter={(value?: React.ReactNode) => `${value}ms`}
                    fill="#C9C4B8"
                    fontSize={11}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-5 bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading level="h3" title="Document types screened" />
          <div className="h-64 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={docTypeData} margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                <XAxis
                  dataKey="type"
                  stroke="#6B655A"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#8C8579' }}
                />
                <YAxis
                  stroke="#8C8579"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#B8B3A8' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#17171A',
                    borderColor: '#3D3933',
                    borderRadius: '10px',
                    fontSize: '12px',
                    padding: '8px 12px',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.4)'
                  }}
                  itemStyle={{ color: '#EBE9E5' }}
                  formatter={(value: any) => `${value}`}
                />
                <Bar
                  dataKey="count"
                  fill="#5C948C"
                  radius={[6, 6, 0, 0]}
                  maxBarSize={40}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
