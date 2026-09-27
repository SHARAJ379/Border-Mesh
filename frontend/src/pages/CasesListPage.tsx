import React, { useEffect, useState } from 'react';
import { CaseItem } from '../types';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { FileText, Search, ChevronRight, RefreshCw, Loader2 } from 'lucide-react';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';

interface CasesListPageProps {
  onSelectCase: (caseId: string) => void;
}

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <FileText className="w-10 h-10 text-graphite-600 mx-auto mb-3" />
    <p className="text-sm font-semibold text-graphite-300">{title}</p>
    <p className="text-xs text-graphite-500 mt-1">{description}</p>
  </div>
);

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-8 h-8">
        <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
        <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
      </div>
      <span className="text-xs text-graphite-400 font-medium">Loading cases…</span>
    </div>
  </div>
);

export const CasesListPage: React.FC<CasesListPageProps> = ({ onSelectCase }) => {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    try {
      setLoading(true);
      const data = await api.listCases({ limit: 150 });
      setCases(data);
    } catch (err: any) {
      console.error('Failed to load cases', err);
    } finally {
      setLoading(false);
    }
  };

  const filtered = cases.filter((c) => {
    const matchesStatus =
      statusFilter === 'ALL' ||
      c.status === statusFilter ||
      c.risk_level === statusFilter ||
      c.officer_decision === statusFilter;

    const matchesSearch =
      c.case_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.country.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.recommendation.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-7">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <SectionHeading
          title="Cases archive"
          description="Complete database of screened travel documents and officer determinations."
          icon={<FileText className="w-5 h-5 text-brass-400" />}
        />

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 text-graphite-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Case ID or Country…"
              className="w-full bg-graphite-950/80 border border-graphite-800/80 rounded-lg pl-9 pr-3 py-2 text-xs text-graphite-200 placeholder-graphite-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
            />
          </div>

          <button
            onClick={fetchCases}
            className="glass-panel p-2.5 rounded-lg text-graphite-400 hover:text-graphite-200 cursor-pointer"
            title="Refresh cases"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Chips */}
      <div className="flex items-center gap-2 border-b border-graphite-800/60 pb-3 flex-wrap text-xs">
        {['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'CLEARED', 'REQUIRES_INSPECTION', 'ESCALATED'].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all duration-200 cursor-pointer ${
              statusFilter === st
                ? 'bg-brass-950/80 text-brass-300 font-bold border border-brass-500/40 shadow-sm'
                : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60'
            }`}
          >
            {st.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Table */}
      <ScrollReveal className="glass-panel rounded-xl overflow-hidden">
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No cases match the query criteria"
            description="Try adjusting your search or filter criteria."
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-xs">
              <thead className="bg-graphite-950/80 text-graphite-400 uppercase text-[10px] tracking-wider border-b border-graphite-800/60">
                <tr>
                  <th className="px-4 py-3 font-medium">Case ID</th>
                  <th className="px-4 py-3 font-medium">Date Screened</th>
                  <th className="px-4 py-3 font-medium">Jurisdiction</th>
                  <th className="px-4 py-3 font-medium">Document</th>
                  <th className="px-4 py-3 font-medium">Risk Score</th>
                  <th className="px-4 py-3 font-medium">Recommendation</th>
                  <th className="px-4 py-3 font-medium">Officer Decision</th>
                  <th className="px-4 py-3 font-medium text-right pr-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-graphite-800/40">
                {filtered.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => onSelectCase(c.id)}
                    className="hover:bg-graphite-800/40 cursor-pointer transition-colors duration-150"
                  >
                    <td className="px-4 py-3.5 font-mono font-semibold text-brass-300">
                      {c.case_number}
                    </td>
                    <td className="px-4 py-3.5 text-graphite-400">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3.5 text-graphite-300">
                      {c.country}
                    </td>
                    <td className="px-4 py-3.5 text-graphite-400">
                      {c.document_type}
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
                      <RiskBadge status={c.officer_decision} size="sm" />
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
        )}
      </ScrollReveal>
    </div>
  );
};
