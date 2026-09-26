import React, { useEffect, useState } from 'react';
import { CaseItem } from '../types';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { Inbox, Search, ChevronRight, Loader2 } from 'lucide-react';
import { SectionHeading } from '../components/SectionHeading';

interface ReviewQueuePageProps {
  onSelectCase: (caseId: string) => void;
}

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <Inbox className="w-10 h-10 text-graphite-600 mx-auto mb-3" />
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
      <span className="text-xs text-graphite-400 font-medium">Loading queue cases…</span>
    </div>
  </div>
);

export const ReviewQueuePage: React.FC<ReviewQueuePageProps> = ({ onSelectCase }) => {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      const data = await api.listCases({ limit: 100 });
      // Queue prioritizes cases needing officer attention
      setCases(data);
    } catch (err: any) {
      console.error('Failed to load queue', err);
    } finally {
      setLoading(false);
    }
  };

  const filtered = cases.filter((c) => {
    const matchesFilter =
      filterLevel === 'ALL'
        ? c.officer_decision === 'PENDING'
        : filterLevel === 'CLEARED'
        ? c.officer_decision === 'CLEARED'
        : c.risk_level === filterLevel;

    const matchesSearch =
      c.case_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.country.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.recommendation.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  return (
    <div className="space-y-7">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <SectionHeading
          title="Officer review queue"
          description="Cases flagged by the AI risk engine requiring human review and disposition."
          icon={<Inbox className="w-5 h-5 text-brass-400" />}
        />

        {/* Search Bar */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-graphite-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search Case ID or Country…"
            className="w-full bg-graphite-950/80 border border-graphite-800/80 rounded-lg pl-9 pr-3 py-2 text-xs text-graphite-200 placeholder-graphite-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-graphite-800/60 pb-3 flex-wrap">
        {[
          { id: 'ALL', label: 'All Pending Review' },
          { id: 'CRITICAL', label: 'Critical Risk' },
          { id: 'HIGH', label: 'High Risk' },
          { id: 'MEDIUM', label: 'Medium Risk' },
          { id: 'CLEARED', label: 'Cleared Archive' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterLevel(tab.id)}
            className={`px-3.5 py-1.5 rounded-lg text-xs transition-all duration-200 cursor-pointer ${
              filterLevel === tab.id
                ? 'bg-brass-950/80 text-brass-300 font-bold border border-brass-500/40 shadow-sm'
                : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Queue Table */}
      <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl overflow-hidden backdrop-blur transition-all duration-300 hover:border-graphite-700/60">
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={filterLevel === 'ALL' ? 'No pending review cases' : 'No cases in this filter'}
            description={filterLevel === 'ALL' ? 'All caught up — no cases currently require officer attention.' : 'Try adjusting your filter or search criteria.'}
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-xs">
              <thead className="bg-graphite-950/80 text-graphite-400 uppercase text-[10px] tracking-wider border-b border-graphite-800/60">
                <tr>
                  <th className="px-4 py-3 font-medium">Case ID</th>
                  <th className="px-4 py-3 font-medium">Jurisdiction</th>
                  <th className="px-4 py-3 font-medium">Document</th>
                  <th className="px-4 py-3 font-medium">Risk Level</th>
                  <th className="px-4 py-3 font-medium">Recommendation</th>
                  <th className="px-4 py-3 font-medium">Officer Status</th>
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
      </div>
    </div>
  );
};
