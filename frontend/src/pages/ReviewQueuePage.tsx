import React, { useEffect, useState } from 'react';
import { CaseItem, RiskCheck } from '../types';
import { api } from '../services/api';
import { RiskBadge } from '../components/RiskBadge';
import { RiskReasons } from '../components/RiskReasons';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { Inbox, Search, ChevronRight, ChevronDown, Loader2 } from 'lucide-react';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';

interface ReviewQueuePageProps {
  onSelectCase: (caseId: string) => void;
}

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <Inbox className="w-8 h-8 text-muted mx-auto mb-3" strokeWidth={1.5} />
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
      <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading queue cases&hellip;</span>
    </div>
  </div>
);

export const ReviewQueuePage: React.FC<ReviewQueuePageProps> = ({ onSelectCase }) => {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);
  const [checksByCase, setChecksByCase] = useState<Record<string, RiskCheck[] | 'loading' | 'error'>>({});

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

  const toggleExpand = async (caseId: string) => {
    if (expandedCaseId === caseId) {
      setExpandedCaseId(null);
      return;
    }
    setExpandedCaseId(caseId);
    if (!checksByCase[caseId]) {
      setChecksByCase((prev) => ({ ...prev, [caseId]: 'loading' }));
      try {
        const checks = await api.getCaseChecks(caseId);
        setChecksByCase((prev) => ({ ...prev, [caseId]: checks }));
      } catch (err) {
        console.error('Failed to load risk checks for', caseId, err);
        setChecksByCase((prev) => ({ ...prev, [caseId]: 'error' }));
      }
    }
  };

  return (
    <div className="space-y-7">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <SectionHeading
          title="Officer review queue"
          description="Cases flagged by the AI risk engine requiring human review and disposition."
          icon={<Inbox className="w-5 h-5 text-accent" strokeWidth={1.5} />}
        />

        {/* Search field -- a hairline, not a bordered box */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 text-muted absolute left-1 top-1/2 -translate-y-1/2" strokeWidth={1.75} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search Case ID or Country…"
            className="field w-full pl-6"
          />
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-6 border-b border-hairline pb-0 flex-wrap">
        {[
          { id: 'ALL', label: 'All Pending Review' },
          { id: 'CRITICAL', label: 'Critical Risk' },
          { id: 'HIGH', label: 'High Risk' },
          { id: 'MEDIUM', label: 'Medium Risk' },
          { id: 'CLEARED', label: 'Cleared Archive' },
        ].map((tab) => (
          <button
            key={tab.id}
            aria-pressed={filterLevel === tab.id}
            onClick={() => setFilterLevel(tab.id)}
            className="tab-flat tab-flat-accent"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Queue table */}
      <ScrollReveal>
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={filterLevel === 'ALL' ? 'No pending review cases' : 'No cases in this filter'}
            description={filterLevel === 'ALL' ? 'All caught up — no cases currently require officer attention.' : 'Try adjusting your filter or search criteria.'}
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-[11px]">
              <thead className="text-muted uppercase tracking-[0.06em] border-b border-hairline">
                <tr>
                  <th className="px-4 py-3 font-normal">Case ID</th>
                  <th className="px-4 py-3 font-normal">Jurisdiction</th>
                  <th className="px-4 py-3 font-normal">Document</th>
                  <th className="px-4 py-3 font-normal">Risk Level</th>
                  <th className="px-4 py-3 font-normal">Recommendation</th>
                  <th className="px-4 py-3 font-normal">Officer Status</th>
                  <th className="px-4 py-3 font-normal text-right pr-4">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const isExpanded = expandedCaseId === c.id;
                  const checksState = checksByCase[c.id];
                  return (
                  <React.Fragment key={c.id}>
                    <tr
                      onClick={() => onSelectCase(c.id)}
                      className="border-b border-hairline hover:bg-paper-dim cursor-pointer transition-colors duration-150"
                    >
                      <td className="px-4 py-3 figure font-bold text-ink">
                        {c.case_number}
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
                      <td className="px-4 py-3 text-muted max-w-xs">
                        <div className="truncate">{c.recommendation}</div>
                        {/* Why this case is flagged, right in the queue -- not
                            just a badge. See RiskReasons for the full detail
                            behind this summary. */}
                        {(c.flagged_check_count ?? 0) > 0 && (
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleExpand(c.id); }}
                            className="mt-1 flex items-center gap-1 text-[10px] text-signal-high cursor-pointer"
                          >
                            <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                            <span className="truncate">
                              {c.flagged_check_count} flagged{c.top_flagged_checks?.length ? `: ${c.top_flagged_checks.join(', ')}` : ''}
                            </span>
                          </button>
                        )}
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
                    {isExpanded && (
                      <tr onClick={(e) => e.stopPropagation()} className="bg-paper-dim cursor-default border-b border-hairline">
                        <td colSpan={7} className="px-4 py-4">
                          {checksState === 'loading' && (
                            <div className="flex items-center gap-2 text-[11px] text-muted">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading risk checks&hellip;
                            </div>
                          )}
                          {checksState === 'error' && (
                            <p className="text-[11px] text-signal-critical">Failed to load risk checks for this case.</p>
                          )}
                          {Array.isArray(checksState) && <RiskReasons checks={checksState} compact />}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </ScrollShadowX>
        )}
      </ScrollReveal>
    </div>
  );
};
