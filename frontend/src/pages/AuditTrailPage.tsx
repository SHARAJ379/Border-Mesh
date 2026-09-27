import React, { useEffect, useState } from 'react';
import { AuditLog, ChainVerificationResult, BlockchainAnchor } from '../types';
import { api } from '../services/api';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { ScrollReveal } from '../components/ScrollReveal';
import {
  ShieldCheck,
  ShieldAlert,
  Search,
  RefreshCw,
  ChevronRight,
  Lock,
  Link2,
  ExternalLink,
} from 'lucide-react';

interface AuditTrailPageProps {
  onSelectCase: (caseId: string) => void;
}

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-7 h-7">
        <div className="absolute inset-0 border border-hairline" />
        <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
      </div>
      <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading audit blocks&hellip;</span>
    </div>
  </div>
);

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <Lock className="w-8 h-8 text-muted mx-auto mb-3" strokeWidth={1.5} />
    <p className="text-[13px] font-bold text-ink">{title}</p>
    <p className="text-[11px] text-muted mt-1">{description}</p>
  </div>
);

export const AuditTrailPage: React.FC<AuditTrailPageProps> = ({ onSelectCase }) => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('ALL');

  // Blockchain Ledger Verification State
  const [verification, setVerification] = useState<ChainVerificationResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  // Testnet anchor history + on-demand anchoring state
  const [anchors, setAnchors] = useState<BlockchainAnchor[]>([]);
  const [anchoring, setAnchoring] = useState(false);

  useEffect(() => {
    fetchLogsAndVerify();
    fetchAnchors();
  }, []);

  const fetchLogsAndVerify = async () => {
    try {
      setLoading(true);
      const [logsData, verifyData] = await Promise.all([
        api.getAuditLogs({ limit: 100 }),
        api.verifyAuditChain().catch(() => null)
      ]);
      setLogs(logsData);
      if (verifyData) setVerification(verifyData);
    } catch (err: any) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchAnchors = async () => {
    try {
      setAnchors(await api.listBlockchainAnchors());
    } catch (err: any) {
      console.error('Failed to load blockchain anchor history', err);
    }
  };

  const handleVerifyChain = async () => {
    try {
      setVerifying(true);
      const res = await api.verifyAuditChain();
      setVerification(res);
    } catch (err: any) {
      alert(`Verification error: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  const handleAnchorNow = async () => {
    try {
      setAnchoring(true);
      const anchor = await api.anchorAuditChain();
      setAnchors((prev) => [anchor, ...prev]);
    } catch (err: any) {
      alert(`Blockchain anchor error: ${err.message}`);
    } finally {
      setAnchoring(false);
    }
  };

  const filtered = logs.filter((l) => {
    const matchesSearch =
      l.action.toLowerCase().includes(search.toLowerCase()) ||
      l.actor.toLowerCase().includes(search.toLowerCase()) ||
      (l.case_id && l.case_id.toLowerCase().includes(search.toLowerCase())) ||
      (l.entry_hash && l.entry_hash.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterType === 'OFFICER') return l.actor.includes('OFFICER');
    if (filterType === 'PURGED') return l.action.includes('PURGE');
    if (filterType === 'AI') return l.actor.startsWith('AI');
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header: title + chain status + actions */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-[26px] text-ink">Audit trail</h1>
          <p className="text-[12px] text-muted mt-0.5">
            Every screening event, AI evaluation, and officer action — chained with SHA-256 so nothing can be altered after the fact.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="btn-secondary px-3 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Re-run mathematical hash verification across every block"
          >
            <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.75} />
            <span>{verifying ? 'Verifying…' : 'Re-verify chain'}</span>
          </button>

          <button
            onClick={fetchLogsAndVerify}
            className="btn-secondary p-1.5 cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {/* Chain integrity — one quiet line, not a banner */}
      {verification && (
        <div className={`flex flex-wrap items-center gap-2 text-[13px] animate-fade-in ${
          verification.valid ? 'text-signal-low' : 'text-signal-critical'
        }`}>
          {verification.valid ? <Lock className="w-4 h-4 shrink-0" strokeWidth={1.75} /> : <ShieldAlert className="w-4 h-4 shrink-0" strokeWidth={1.75} />}
          <span className="font-bold">
            {verification.valid ? 'Chain intact' : 'Tamper detected'}
          </span>
          <span className="text-muted font-normal">
            — {verification.total_records} blocks verified
          </span>
          {verification.head_hash && (
            <span className="text-muted figure text-[11px] ml-auto truncate">
              head {verification.head_hash.substring(0, 10)}…{verification.head_hash.substring(56)}
            </span>
          )}
        </div>
      )}

      {/* Testnet anchoring — publishes the head hash above to a public
          blockchain so it can be verified independently of this app */}
      <ScrollReveal className="border border-hairline p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <Link2 className="w-4 h-4 text-accent mt-0.5" strokeWidth={1.75} />
            <div>
              <p className="text-[13px] font-bold text-ink">Public testnet anchor</p>
              <p className="text-[11px] text-muted mt-0.5 max-w-lg">
                Publishes the chain's current head hash to Ethereum Sepolia (a free public testnet) as a plain
                transaction — anyone can verify the hash independently on a block explorer, without trusting
                this app's own database.
              </p>
            </div>
          </div>
          <button
            onClick={handleAnchorNow}
            disabled={anchoring || !verification || verification.total_records === 0}
            className="btn-primary px-4 py-2 text-[11px] flex items-center gap-1.5 cursor-pointer shrink-0"
          >
            <Link2 className="w-3.5 h-3.5" strokeWidth={1.75} />
            <span>{anchoring ? 'Publishing to testnet…' : 'Anchor now'}</span>
          </button>
        </div>

        {anchors.length > 0 && (
          <div className="border-t border-hairline pt-2 animate-fade-in">
            {anchors.slice(0, 5).map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 border-t border-hairline first:border-t-0 text-[11px]">
                <span className="text-muted figure whitespace-nowrap">
                  {new Date(a.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="label-eyebrow">{a.network}</span>
                <span className="text-muted figure truncate max-w-[10rem]" title={`Head hash: ${a.head_hash}`}>
                  {a.head_hash.substring(0, 10)}…{a.head_hash.substring(56)}
                </span>
                <a
                  href={a.explorer_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:opacity-70 flex items-center gap-1 ml-auto transition-opacity"
                >
                  <span className="figure">{a.tx_hash.substring(0, 10)}…{a.tx_hash.substring(a.tx_hash.length - 6)}</span>
                  <ExternalLink className="w-3 h-3" strokeWidth={1.75} />
                </a>
              </div>
            ))}
          </div>
        )}
      </ScrollReveal>

      {/* Filters + search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-hairline pb-0">
        <div className="flex flex-wrap items-center gap-6">
          {(['ALL', 'OFFICER', 'AI', 'PURGED'] as const).map((t) => (
            <button
              key={t}
              aria-pressed={filterType === t}
              onClick={() => setFilterType(t)}
              className="tab-flat tab-flat-accent"
            >
              {t === 'ALL' && 'All'}
              {t === 'OFFICER' && 'Officer actions'}
              {t === 'AI' && 'AI forensics'}
              {t === 'PURGED' && 'Biometrics purged'}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64 pb-3 sm:pb-0">
          <Search className="w-3.5 h-3.5 text-muted absolute left-1 top-1/2 -translate-y-1/2" strokeWidth={1.75} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search action, actor, hash…"
            className="field w-full pl-6"
          />
        </div>
      </div>

      {/* Logs table — the one real surface on this page */}
      <ScrollReveal>
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No audit records match this search"
            description="Try adjusting your filter or search criteria."
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-[12px]">
              <thead className="text-muted uppercase tracking-[0.06em] text-[10px] border-b border-hairline">
                <tr>
                  <th className="px-4 py-2.5 font-normal">Time</th>
                  <th className="px-4 py-2.5 font-normal">Event</th>
                  <th className="px-4 py-2.5 font-normal">Actor</th>
                  <th className="px-4 py-2.5 font-normal">Case</th>
                  <th className="px-4 py-2.5 font-normal">Hash</th>
                  <th className="px-4 py-2.5 font-normal">Details</th>
                  <th className="px-4 py-2.5 font-normal text-right pr-4"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item, idx) => {
                  const dateStr = new Date(item.timestamp).toLocaleString([], {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  });
                  const isOfficer = item.actor.includes('OFFICER');
                  const isPurge = item.action.includes('PURGE');
                  const actorBadgeCls = isOfficer ? 'badge-accent' : isPurge ? 'badge-medium' : item.actor.startsWith('AI') ? 'badge-low' : 'badge-neutral';

                  return (
                    <tr key={item.id || idx} className="border-b border-hairline hover:bg-paper-dim transition-colors duration-150">
                      <td className="px-4 py-2.5 text-muted whitespace-nowrap figure text-[11px]">
                        {dateStr}
                      </td>

                      <td className={`px-4 py-2.5 font-bold whitespace-nowrap ${isPurge ? 'text-signal-medium' : 'text-ink'}`}>
                        {item.action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())}
                      </td>

                      <td className="px-4 py-2.5">
                        <span className={`badge-signal ${actorBadgeCls}`}>
                          {item.actor}
                        </span>
                      </td>

                      <td className="px-4 py-2.5 text-muted figure text-[11px]">
                        {item.case_id ? item.case_id.substring(0, 8) : '—'}
                      </td>

                      <td className="px-4 py-2.5">
                        {item.entry_hash ? (
                          <span
                            className="text-[11px] figure text-muted"
                            title={`Full SHA-256: ${item.entry_hash}\nPrev: ${item.previous_hash || 'GENESIS'}`}
                          >
                            {item.entry_hash.substring(0, 8)}…{item.entry_hash.substring(58)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      <td className="px-4 py-2.5 text-muted text-[11px] max-w-xs truncate">
                        {item.metadata_json ? JSON.stringify(item.metadata_json) : '—'}
                      </td>

                      <td className="px-4 py-2.5 text-right pr-4">
                        {item.case_id && (
                          <button
                            onClick={() => onSelectCase(item.case_id!)}
                            className="text-accent hover:opacity-70 flex items-center gap-0.5 ml-auto cursor-pointer transition-opacity uppercase tracking-[0.06em]"
                          >
                            <span className="text-[11px]">Case</span>
                            <ChevronRight className="w-3 h-3" strokeWidth={1.75} />
                          </button>
                        )}
                      </td>
                    </tr>
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
