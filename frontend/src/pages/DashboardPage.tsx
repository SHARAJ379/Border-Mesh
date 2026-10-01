import React, { useEffect, useState } from 'react';
import { DashboardStats, CaseItem } from '../types';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';
import {
  AlertTriangle,
  ChevronRight,
  ArrowRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip
} from 'recharts';

interface DashboardPageProps {
  onSelectCase: (caseId: string) => void;
  onNavigateNewScreening: () => void;
  onNavigateQueue: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onSelectCase,
  onNavigateNewScreening,
  onNavigateQueue
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getDashboardStats();
      setStats(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load dashboard stats');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 border border-hairline" />
            <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
          </div>
          <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading operations stream&hellip;</span>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm px-4">
          <AlertTriangle className="w-6 h-6 text-signal-high" strokeWidth={1.5} />
          <div className="space-y-1">
            <p className="text-[13px] text-ink font-bold">Couldn't load the operations dashboard</p>
            <p className="text-[11px] text-muted">{error || 'No data returned from the server.'}</p>
          </div>
          <button onClick={fetchStats} className="btn-primary mt-2 px-5 py-2.5 text-[11px]">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const riskTiers = [
    { name: 'Low', value: stats.risk_distribution.LOW || 0, cls: 'badge-low' },
    { name: 'Medium', value: stats.risk_distribution.MEDIUM || 0, cls: 'badge-medium' },
    { name: 'High', value: stats.risk_distribution.HIGH || 0, cls: 'badge-high' },
    { name: 'Critical', value: stats.risk_distribution.CRITICAL || 0, cls: 'badge-critical' },
  ];

  const barData = stats.top_risk_reasons.map((r) => ({
    name: r.reason.length > 34 ? r.reason.substring(0, 32) + '…' : r.reason,
    fullLabel: r.reason,
    count: r.count
  }));

  const kpis = [
    { label: 'Screened', value: stats.documents_screened, trend: '+12%' },
    { label: 'Review queue', value: stats.cases_requiring_review, trend: '+3' },
    { label: 'High risk', value: stats.high_risk_cases, trend: '+2' },
    { label: 'Critical', value: stats.critical_cases, trend: '0' },
    { label: 'Avg latency', value: `${(stats.avg_processing_time_ms / 1000).toFixed(2)}s`, trend: '-0.04s' },
  ];

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="border-b border-hairline pb-6">
        <SectionHeading
          title="Border screening operations"
          description="Real-time AI identity verification and travel document integrity stream."
          action={
            <button onClick={onNavigateNewScreening} className="btn-primary px-4 py-2.5 text-[11px] flex items-center gap-2">
              <span>+ New document screening</span>
            </button>
          }
        />
      </div>

      {/* KPI strip -- one hairline-bounded row, not five separate cards */}
      <ScrollReveal>
        <div className="grid grid-cols-2 sm:grid-cols-5 border-t border-b border-hairline divide-x divide-hairline">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="px-5 py-4">
              <span className="label-eyebrow block mb-2">{kpi.label}</span>
              <div className="figure text-[26px] font-display text-ink leading-none">{kpi.value}</div>
              <div className="text-[10px] text-muted mt-1.5">{kpi.trend} vs last hour</div>
            </div>
          ))}
        </div>
      </ScrollReveal>

      <button
        onClick={onNavigateQueue}
        className="text-[11px] uppercase tracking-[0.06em] text-ink-soft hover:text-accent flex items-center gap-1.5 cursor-pointer transition-colors -mt-4"
      >
        <span>Inspect review queue</span>
        <ArrowRight className="w-3.5 h-3.5" />
      </button>

      {/* Distribution + signals */}
      <ScrollReveal className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <div className="lg:col-span-5">
          <SectionHeading level="h3" title="Risk level distribution" description={`${stats.documents_screened} total specimens`} />
          <div className="mt-4">
            {riskTiers.map((tier) => {
              const pct = stats.documents_screened > 0 ? Math.round((tier.value / stats.documents_screened) * 100) : 0;
              return (
                <div key={tier.name} className="rule-row">
                  <span className={`badge-signal ${tier.cls}`}>{tier.name}</span>
                  <span className="figure text-[13px] text-ink">{tier.value} <span className="text-muted">({pct}%)</span></span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-7">
          <SectionHeading level="h3" title="Most frequent risk indicators" description="Top detections across all screenings" />
          <div className="h-64 mt-4">
            {barData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                  <XAxis type="number" stroke="var(--color-muted)" fontSize={10} tickLine={false} axisLine={{ stroke: 'var(--color-hairline)' }} tick={{ fill: 'var(--color-muted)' }} />
                  <YAxis type="category" dataKey="name" stroke="var(--color-muted)" fontSize={10} width={160} tickLine={false} axisLine={false} tick={{ fill: 'var(--color-ink-soft)' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--color-paper-dim)', border: '1px solid var(--color-hairline)', borderRadius: 0, fontSize: '11px', padding: '8px 12px', fontFamily: 'Courier Prime, monospace' }}
                    itemStyle={{ color: 'var(--color-ink)' }}
                    labelFormatter={(_label, payload) => (payload && payload[0] ? (payload[0].payload as any).fullLabel : _label)}
                    wrapperStyle={{ whiteSpace: 'normal' }}
                    formatter={(value: any) => String(value ?? '0')}
                    cursor={{ fill: 'var(--color-hairline)' }}
                  />
                  <Bar dataKey="count" fill="var(--color-accent)" radius={[0, 0, 0, 0]} maxBarSize={14} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-[11px] text-muted">
                Awaiting screening events
              </div>
            )}
          </div>
        </div>
      </ScrollReveal>

      {/* Live queue */}
      <ScrollReveal>
        <div className="border-t border-hairline pt-4 pb-3 flex items-center justify-between">
          <h3 className="font-display text-[17px] text-ink">Live screening queue</h3>
          <button
            onClick={onNavigateQueue}
            className="text-[11px] uppercase tracking-[0.06em] text-accent hover:opacity-70 flex items-center gap-1 cursor-pointer transition-opacity"
          >
            <span>View all cases</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <ScrollShadowX>
          <table className="w-full text-left text-[11px]">
            <thead className="text-muted uppercase tracking-[0.06em] border-b border-hairline">
              <tr>
                <th className="px-4 py-3 font-normal">Case ID</th>
                <th className="px-4 py-3 font-normal">Document</th>
                <th className="px-4 py-3 font-normal">Jurisdiction</th>
                <th className="px-4 py-3 font-normal">Risk score</th>
                <th className="px-4 py-3 font-normal">Recommendation</th>
                <th className="px-4 py-3 font-normal">Status</th>
                <th className="px-4 py-3 font-normal text-right pr-4">Action</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_cases.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => onSelectCase(c.id)}
                  className="border-b border-hairline hover:bg-paper-dim cursor-pointer transition-colors duration-150"
                >
                  <td className="px-4 py-3 figure font-bold text-ink">
                    {c.case_number}
                  </td>
                  <td className="px-4 py-3 text-ink-soft">
                    {c.document_type}
                  </td>
                  <td className="px-4 py-3 text-ink-soft">
                    {c.country}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="figure font-bold text-ink">
                        {Math.round(c.risk_score)}
                      </span>
                      <RiskBadge level={c.risk_level} size="sm" />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted truncate max-w-xs">
                    {c.recommendation}
                  </td>
                  <td className="px-4 py-3">
                    <RiskBadge status={c.officer_decision !== 'PENDING' ? c.officer_decision : c.status} size="sm" />
                  </td>
                  <td className="px-4 py-3 text-right pr-4">
                    <button className="text-accent hover:opacity-70 font-bold flex items-center gap-1 ml-auto transition-opacity uppercase tracking-[0.06em]">
                      <span>Inspect</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollShadowX>
      </ScrollReveal>
    </div>
  );
};
