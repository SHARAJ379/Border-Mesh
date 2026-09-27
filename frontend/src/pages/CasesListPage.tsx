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
    <FileText className="w-8 h-8 text-muted mx-auto mb-3" strokeWidth={1.5} />
    <p className="text-[13px] font-bold text-ink">{title}</p>
    <p className="text-[11px] text-muted mt-1">{description}</p>
  </div>
);

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-7 h-7">
        <div className="absolute inset-0 border border-hairline" />
        <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
      </div>
      <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading cases&hellip;</span>
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
          icon={<FileText className="w-5 h-5 text-accent" strokeWidth={1.5} />}
        />

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-3.5 h-3.5 text-muted absolute left-1 top-1/2 -translate-y-1/2" strokeWidth={1.75} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Case ID or Country…"
              className="field w-full pl-6"
            />
          </div>

          <button
            onClick={fetchCases}
            className="btn-secondary p-2.5 cursor-pointer"
            title="Refresh cases"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-6 border-b border-hairline flex-wrap">
        {['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'CLEARED', 'REQUIRES_INSPECTION', 'ESCALATED'].map((st) => (
          <button
            key={st}
            aria-pressed={statusFilter === st}
            onClick={() => setStatusFilter(st)}
            className="tab-flat tab-flat-accent"
          >
            {st.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Table */}
      <ScrollReveal>
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No cases match the query criteria"
            description="Try adjusting your search or filter criteria."
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-[11px]">
              <thead className="text-muted uppercase tracking-[0.06em] border-b border-hairline">
                <tr>
                  <th className="px-4 py-3 font-normal">Case ID</th>
                  <th className="px-4 py-3 font-normal">Date Screened</th>
                  <th className="px-4 py-3 font-normal">Jurisdiction</th>
                  <th className="px-4 py-3 font-normal">Document</th>
                  <th className="px-4 py-3 font-normal">Risk Score</th>
                  <th className="px-4 py-3 font-normal">Recommendation</th>
                  <th className="px-4 py-3 font-normal">Officer Decision</th>
                  <th className="px-4 py-3 font-normal text-right pr-4">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => onSelectCase(c.id)}
                    className="border-b border-hairline hover:bg-paper-dim cursor-pointer transition-colors duration-150"
                  >
                    <td className="px-4 py-3 figure font-bold text-ink">
                      {c.case_number}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-ink-soft">
                      {c.country}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {c.document_type}
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
                      <RiskBadge status={c.officer_decision} size="sm" />
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
        )}
      </ScrollReveal>
    </div>
  );
};
