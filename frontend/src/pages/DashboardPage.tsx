import React, { useEffect, useState } from 'react';
import { DashboardStats, CaseItem } from '../types';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { SectionHeading } from '../components/SectionHeading';
import {
  FileCheck2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  Inbox,
  ChevronRight,
  Activity,
  ArrowRight,
  TrendingUp
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend
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
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
            <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
          </div>
          <span className="text-xs text-graphite-400 font-medium tracking-wide">Loading operations stream…</span>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm px-4">
          <div className="w-14 h-14 rounded-xl bg-rose-950/40 border border-rose-500/30 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-rose-400" />
          </div>
          <div className="space-y-1">
            <p className="text-sm text-graphite-100 font-semibold">Couldn't load the operations dashboard</p>
            <p className="text-xs text-graphite-500">{error || 'No data returned from the server.'}</p>
          </div>
          <button
            onClick={fetchStats}
            className="mt-2 px-5 py-2.5 rounded-lg bg-brass-600 hover:bg-brass-500 text-white text-xs font-semibold transition-all shadow-md shadow-brass-950/40 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brass-500/50"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Pie chart data for risk distribution - using palette-consistent colors
  const pieData = [
    { name: 'Low Risk', value: stats.risk_distribution.LOW || 0, color: '#10b981' },
    { name: 'Medium Risk', value: stats.risk_distribution.MEDIUM || 0, color: '#f59e0b' },
    { name: 'High Risk', value: stats.risk_distribution.HIGH || 0, color: '#f97316' },
    { name: 'Critical Risk', value: stats.risk_distribution.CRITICAL || 0, color: '#f43f5e' },
  ];

  // Bar chart data for top risk signals
  const barData = stats.top_risk_reasons.map((r) => ({
    name: r.reason.length > 34 ? r.reason.substring(0, 32) + '…' : r.reason,
    fullLabel: r.reason,
    count: r.count
  }));

  const kpis = [
    { label: 'Screened', value: stats.documents_screened, color: 'text-graphite-100', icon: FileCheck2, iconColor: 'text-brass-400', trend: '+12%' },
    { label: 'Review queue', value: stats.cases_requiring_review, color: 'text-amber-400', icon: Inbox, iconColor: 'text-amber-400', trend: '+3' },
    { label: 'High risk', value: stats.high_risk_cases, color: 'text-orange-400', icon: AlertTriangle, iconColor: 'text-orange-400', trend: '+2' },
    { label: 'Critical', value: stats.critical_cases, color: 'text-rose-400', icon: AlertOctagon, iconColor: 'text-rose-400', trend: '0' },
    { label: 'Avg latency', value: `${(stats.avg_processing_time_ms / 1000).toFixed(2)}s`, color: 'text-brass-300', icon: Clock, iconColor: 'text-brass-400', trend: '-0.04s' },
  ];

  return (
    <div className="space-y-7">
      <SectionHeading
        title="Border screening operations"
        description="Real-time AI identity verification and travel document integrity stream."
        action={
          <button
            onClick={onNavigateNewScreening}
            className="bg-brass-600 hover:bg-brass-500 active:bg-brass-700 text-white px-4 py-2.5 rounded-lg text-xs font-semibold transition-all duration-200 shadow-md shadow-brass-950/40 flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brass-500/50"
          >
            <span>+ New document screening</span>
          </button>
        }
      />

      {/* KPI strip -- elevated cards with subtle depth */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
              key={kpi.label}
              className="relative rounded-xl bg-graphite-900/90 border border-graphite-800/80 p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60 hover:shadow-lg hover:shadow-brass-950/20"
            >
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
                <div className="flex items-center gap-1.5 text-[10px] font-medium text-emerald-400">
                  <TrendingUp className="w-3 h-3" />
                  <span>{kpi.trend}</span>
                  <span className="text-graphite-500">vs last hour</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={onNavigateQueue}
        className="text-xs text-graphite-500 hover:text-brass-400 flex items-center gap-1.5 cursor-pointer transition-colors -mt-2"
      >
        <span>Inspect review queue</span>
        <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
      </button>

      {/* Charts -- unequal widths: the actionable list is primary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading level="h3" title="Risk level distribution" description={`${stats.documents_screened} total specimens`} />

          <div className="h-64 relative mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={56}
                  outerRadius={82}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => percent && percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : ''}
                  labelLine={false}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
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
                  formatter={(value: any) => String(value ?? '0')}
                />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconType="circle"
                  iconSize={8}
                  formatter={(val, entry: any) => (
                    <span className="text-xs text-graphite-300 flex items-center gap-2 min-w-[120px]">
                      <span className="w-6">{val}</span>
                      <span className="font-medium text-graphite-200">{entry.payload.value}</span>
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Centered in the donut hole */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="flex flex-col items-center leading-tight text-center">
                <span className="text-4xl font-bold text-graphite-100 tracking-tight">{stats.documents_screened.toLocaleString()}</span>
                <span className="text-[10px] uppercase text-graphite-500 tracking-wider mt-1">Total Specimens</span>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-7 bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading level="h3" title="Most frequent risk indicators" description="Top detections across all screenings" />

          <div className="h-64 mt-3">
            {barData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
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
                    dataKey="name"
                    stroke="#8C8579"
                    fontSize={10}
                    width={160}
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
                      maxWidth: '280px',
                      padding: '10px 12px',
                      boxShadow: '0 4px 24px rgba(0,0,0,0.4)'
                    }}
                    itemStyle={{ color: '#EBE9E5' }}
                    labelFormatter={(_label, payload) => (payload && payload[0] ? (payload[0].payload as any).fullLabel : _label)}
                    wrapperStyle={{ whiteSpace: 'normal' }}
                    formatter={(value: any) => String(value ?? '0')}
                  />
                  <Bar
                    dataKey="count"
                    fill="#5C948C"
                    radius={[0, 6, 6, 0]}
                    maxBarSize={32}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-graphite-500">
                Awaiting screening events
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Live queue -- elevated table card */}
      <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl overflow-hidden backdrop-blur">
        <div className="p-4 border-b border-graphite-800/60 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-brass-950/50 border border-brass-500/30">
              <Activity className="w-4 h-4 text-brass-400" />
            </div>
            <h3 className="text-sm font-semibold text-graphite-100">
              Live screening queue
            </h3>
          </div>
          <button
            onClick={onNavigateQueue}
            className="text-xs text-brass-400 hover:text-brass-300 flex items-center gap-1 cursor-pointer transition-colors px-2 py-1 rounded hover:bg-brass-950/30"
          >
            <span>View all cases</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <ScrollShadowX>
          <table className="w-full text-left text-xs">
            <thead className="bg-graphite-950/80 text-graphite-400 uppercase text-[10px] tracking-wider border-b border-graphite-800/60">
              <tr>
                <th className="px-4 py-3 font-medium">Case ID</th>
                <th className="px-4 py-3 font-medium">Document</th>
                <th className="px-4 py-3 font-medium">Jurisdiction</th>
                <th className="px-4 py-3 font-medium">Risk score</th>
                <th className="px-4 py-3 font-medium">Recommendation</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right pr-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-graphite-800/40">
              {stats.recent_cases.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => onSelectCase(c.id)}
                  className="hover:bg-graphite-800/40 cursor-pointer transition-colors duration-150"
                >
                  <td className="px-4 py-3.5 font-mono font-semibold text-brass-300">
                    {c.case_number}
                  </td>
                  <td className="px-4 py-3.5 text-graphite-300">
                    {c.document_type}
                  </td>
                  <td className="px-4 py-3.5 text-graphite-300">
                    {c.country}
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-graphite-200 tabular-nums">
                        {Math.round(c.risk_score)}
                      </span>
                      <RiskBadge level={c.risk_level} size="sm" />
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-graphite-400 truncate max-w-xs">
                    {c.recommendation}
                  </td>
                  <td className="px-4 py-3.5">
                    <RiskBadge status={c.officer_decision !== 'PENDING' ? c.officer_decision : c.status} size="sm" />
                  </td>
                  <td className="px-4 py-3.5 text-right pr-4">
                    <button className="text-brass-400 hover:text-brass-200 font-semibold flex items-center gap-1 ml-auto transition-colors">
                      <span>Inspect</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollShadowX>
      </div>
    </div>
  );
};
