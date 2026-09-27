import React, { useEffect, useState } from 'react';
import { AuditLog, ChainVerificationResult, BlockchainAnchor } from '../types';
import { api } from '../services/api';
import { ScrollShadowX } from '../components/ScrollShadowX';
import { SectionHeading } from '../components/SectionHeading';
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
  Loader2
} from 'lucide-react';

interface AuditTrailPageProps {
  onSelectCase: (caseId: string) => void;
}

const LoadingState: React.FC = () => (
  <div className="p-8 text-center">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-8 h-8">
        <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
        <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
      </div>
      <span className="text-sm text-graphite-500">Loading audit blocks…</span>
    </div>
  </div>
);

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="p-8 text-center">
    <Lock className="w-10 h-10 text-graphite-600 mx-auto mb-3" />
    <p className="text-sm font-semibold text-graphite-300">{title}</p>
    <p className="text-xs text-graphite-500 mt-1">{description}</p>
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
      {/* Header: title + chain status + actions, one row */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-graphite-100">Audit trail</h1>
          <p className="text-sm text-graphite-500 mt-0.5">
            Every screening event, AI evaluation, and officer action — chained with SHA-256 so nothing can be altered after the fact.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="px-3 py-1.5 rounded-lg border border-graphite-800/80 text-graphite-300 text-xs font-medium flex items-center gap-1.5 hover:border-graphite-700 hover:text-graphite-100 hover:bg-graphite-900/60 transition-all cursor-pointer disabled:opacity-50"
            title="Re-run mathematical hash verification across every block"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{verifying ? 'Verifying…' : 'Re-verify chain'}</span>
          </button>

          <button
            onClick={fetchLogsAndVerify}
            className="p-1.5 rounded-lg border border-graphite-800/80 text-graphite-400 hover:text-graphite-200 hover:border-graphite-700 hover:bg-graphite-900/60 transition-all cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Chain integrity — one quiet line, not a banner */}
      {verification && (
        <div className={`flex flex-wrap items-center gap-2 text-sm animate-fade-in ${
          verification.valid ? 'text-emerald-400' : 'text-rose-400'
        }`}>
          {verification.valid ? <Lock className="w-4 h-4 shrink-0" /> : <ShieldAlert className="w-4 h-4 shrink-0" />}
          <span className="font-medium">
            {verification.valid ? 'Chain intact' : 'Tamper detected'}
          </span>
          <span className="text-graphite-500 font-normal">
            — {verification.total_records} blocks verified
          </span>
          {verification.head_hash && (
            <span className="text-graphite-500 font-mono text-xs ml-auto truncate">
              head {verification.head_hash.substring(0, 10)}…{verification.head_hash.substring(56)}
            </span>
          )}
        </div>
      )}

      {/* Testnet anchoring — publishes the head hash above to a public
          blockchain so it can be verified independently of this app */}
      <ScrollReveal className="glass-panel rounded-xl p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="p-2 rounded-lg bg-brass-950/50 border border-brass-500/30">
              <Link2 className="w-4 h-4 text-brass-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-graphite-200">Public testnet anchor</p>
              <p className="text-xs text-graphite-500 mt-0.5 max-w-lg">
                Publishes the chain's current head hash to Ethereum Sepolia (a free public testnet) as a plain
                transaction — anyone can verify the hash independently on a block explorer, without trusting
                this app's own database.
              </p>
            </div>
          </div>
          <button
            onClick={handleAnchorNow}
            disabled={anchoring || !verification || verification.total_records === 0}
            className="btn-brass px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer shrink-0"
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>{anchoring ? 'Publishing to testnet…' : 'Anchor now'}</span>
          </button>
        </div>

        {anchors.length > 0 && (
          <div className="divide-y divide-graphite-800/50 border-t border-graphite-800/60 pt-2 animate-fade-in">
            {anchors.slice(0, 5).map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-xs">
                <span className="text-graphite-500 font-mono whitespace-nowrap">
                  {new Date(a.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="px-2 py-0.5 rounded bg-graphite-800/60 text-graphite-400 border border-graphite-700/60">{a.network}</span>
                <span className="text-graphite-500 font-mono truncate max-w-[10rem]" title={`Head hash: ${a.head_hash}`}>
                  {a.head_hash.substring(0, 10)}…{a.head_hash.substring(56)}
                </span>
                <a
                  href={a.explorer_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brass-400 hover:text-brass-300 flex items-center gap-1 ml-auto transition-colors"
                >
                  <span className="font-mono">{a.tx_hash.substring(0, 10)}…{a.tx_hash.substring(a.tx_hash.length - 6)}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            ))}
          </div>
        )}
      </ScrollReveal>

      {/* Filters + search — plain row, no card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1 bg-graphite-950/60 p-1 rounded-lg border border-graphite-800/80">
          {(['ALL', 'OFFICER', 'AI', 'PURGED'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer ${
                filterType === t
                  ? 'bg-brass-950/80 text-brass-300 font-bold border border-brass-500/40 shadow-sm'
                  : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60'
              }`}
            >
              {t === 'ALL' && 'All'}
              {t === 'OFFICER' && 'Officer actions'}
              {t === 'AI' && 'AI forensics'}
              {t === 'PURGED' && 'Biometrics purged'}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-graphite-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search action, actor, hash…"
            className="w-full bg-graphite-950/80 border border-graphite-800/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-graphite-200 placeholder-graphite-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
          />
        </div>
      </div>

      {/* Logs table — the one real surface on this page */}
      <ScrollReveal className="glass-panel rounded-xl overflow-hidden">
        {loading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No audit records match this search"
            description="Try adjusting your filter or search criteria."
          />
        ) : (
          <ScrollShadowX>
            <table className="w-full text-left text-sm">
              <thead className="bg-graphite-950/80 text-graphite-400 uppercase text-[10px] tracking-wider border-b border-graphite-800/60">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Time</th>
                  <th className="px-4 py-2.5 font-medium">Event</th>
                  <th className="px-4 py-2.5 font-medium">Actor</th>
                  <th className="px-4 py-2.5 font-medium">Case</th>
                  <th className="px-4 py-2.5 font-medium">Hash</th>
                  <th className="px-4 py-2.5 font-medium">Details</th>
                  <th className="px-4 py-2.5 font-medium text-right pr-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-graphite-800/40">
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
                  const isAI = item.actor.startsWith('AI');

                  return (
                    <tr key={item.id || idx} className="hover:bg-graphite-800/40 transition-colors duration-150">
                      <td className="px-4 py-2.5 text-graphite-500 whitespace-nowrap font-mono text-xs">
                        {dateStr}
                      </td>

                      <td className={`px-4 py-2.5 font-medium whitespace-nowrap ${isPurge ? 'text-amber-400' : 'text-graphite-200'}`}>
                        {item.action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())}
                      </td>

                      <td className="px-4 py-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-lg text-xs font-medium ${
                            isOfficer
                              ? 'text-brass-300 bg-brass-500/10 border border-brass-500/20'
                              : isPurge
                              ? 'text-amber-300 bg-amber-500/10 border border-amber-500/20'
                              : isAI
                              ? 'text-emerald-300 bg-emerald-500/10 border border-emerald-500/20'
                              : 'text-graphite-400 bg-graphite-800/60 border border-graphite-700/60'
                          }`}
                        >
                          {item.actor}
                        </span>
                      </td>

                      <td className="px-4 py-2.5 text-graphite-400 font-mono text-xs">
                        {item.case_id ? item.case_id.substring(0, 8) : '—'}
                      </td>

                      <td className="px-4 py-2.5">
                        {item.entry_hash ? (
                          <span
                            className="text-xs font-mono text-graphite-500 px-2 py-0.5 rounded bg-graphite-900/60 border border-graphite-800/60"
                            title={`Full SHA-256: ${item.entry_hash}\nPrev: ${item.previous_hash || 'GENESIS'}`}
                          >
                            {item.entry_hash.substring(0, 8)}…{item.entry_hash.substring(58)}
                          </span>
                        ) : (
                          <span className="text-graphite-600">—</span>
                        )}
                      </td>

                      <td className="px-4 py-2.5 text-graphite-500 text-xs max-w-xs truncate">
                        {item.metadata_json ? JSON.stringify(item.metadata_json) : '—'}
                      </td>

                      <td className="px-4 py-2.5 text-right pr-4">
                        {item.case_id && (
                          <button
                            onClick={() => onSelectCase(item.case_id!)}
                            className="text-graphite-500 hover:text-brass-400 flex items-center gap-0.5 ml-auto cursor-pointer transition-colors px-2 py-1 rounded hover:bg-graphite-800/60"
                          >
                            <span className="text-xs">Case</span>
                            <ChevronRight className="w-3 h-3" />
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
