import React, { useMemo, useState } from 'react';
import { RiskCheck, RiskCheckStatus, RiskFactorKey } from '../types';
import { ListChecks, CheckCircle2, XCircle, Info, MinusCircle, ChevronDown } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

interface RiskReasonsProps {
  checks: RiskCheck[];
  /** Compact mode drops the ScrollReveal/glass-panel chrome and section
      heading, for embedding inline (e.g. a Review Queue expanded row). */
  compact?: boolean;
}

const FACTOR_LABELS: Record<string, string> = {
  MRZ_VALIDATION: 'MRZ & Document Validation',
  TAMPER: 'Forensic Tamper AI',
  FACE: 'Biometric Face Verification',
  CONSISTENCY: 'Data Consistency Crosscheck',
  WATCHLIST: 'Simulated Watchlist Adapter',
  IDENTITY: 'Cross-Case Duplicate Identity',
};

const FACTOR_ORDER: (RiskFactorKey | 'OTHER')[] = [
  'MRZ_VALIDATION', 'TAMPER', 'FACE', 'CONSISTENCY', 'WATCHLIST', 'IDENTITY', 'OTHER',
];

const STATUS_META: Record<RiskCheckStatus, { icon: React.FC<any>; color: string; label: string }> = {
  PASS: { icon: CheckCircle2, color: 'text-emerald-400', label: 'PASS' },
  FAIL: { icon: XCircle, color: 'text-rose-400', label: 'FAIL' },
  INFO: { icon: Info, color: 'text-sky-400', label: 'INFO' },
  NOT_APPLICABLE: { icon: MinusCircle, color: 'text-graphite-500', label: 'N/A' },
};

function formatEvidenceValue(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  return String(v);
}

const EvidenceLine: React.FC<{ check: RiskCheck }> = ({ check }) => {
  const ev = check.evidence;
  if (!ev) return null;

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10.5px] font-mono text-graphite-400 mt-1">
      {ev.match && ev.match.length > 0 ? (
        ev.match.map((m, i) => (
          <span key={i} className="px-1.5 py-0.5 rounded bg-graphite-900/70 border border-graphite-800">
            '{m.matched_token}' ↔ '{m.query_token}' via {m.method}
            {m.edit_distance !== null && m.edit_distance !== undefined ? ` (distance ${m.edit_distance})` : ''}
          </span>
        ))
      ) : (
        (ev.measured_value !== null && ev.measured_value !== undefined) && (
          <span>
            Measured: <strong className="text-graphite-300">{formatEvidenceValue(ev.measured_value)}</strong>
            {ev.threshold_value !== null && ev.threshold_value !== undefined && (
              <> vs threshold <strong className="text-graphite-300">{formatEvidenceValue(ev.threshold_value)}</strong></>
            )}
            {ev.unit ? ` [${ev.unit}]` : ''}
          </span>
        )
      )}
      {ev.region && ev.region.length === 4 && (
        <span>
          Region [x:{ev.region[0]}, y:{ev.region[1]}, w:{ev.region[2]}, h:{ev.region[3]}] on {ev.region_source || 'document'}
        </span>
      )}
    </div>
  );
};

const CheckRow: React.FC<{ check: RiskCheck }> = ({ check }) => {
  const meta = STATUS_META[check.status] || STATUS_META.INFO;
  const Icon = meta.icon;
  return (
    <div className="p-3 rounded-lg bg-graphite-950/70 border border-graphite-800/80 hover:border-graphite-700/60 transition-all text-xs">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${meta.color}`} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-graphite-200">{check.label}</span>
              {check.severity && <RiskBadge level={check.severity} size="sm" />}
            </div>
            <p className="text-graphite-400 text-[11px] leading-relaxed mt-0.5">{check.explanation}</p>
            <EvidenceLine check={check} />
          </div>
        </div>
        <div className="flex flex-col items-end shrink-0 text-right">
          {check.status === 'FAIL' && check.score_impact > 0 && (
            <span className="text-rose-400 font-bold">+{check.score_impact.toFixed(1)} pts</span>
          )}
          <span className="text-[10px] text-graphite-500">Conf: {Math.round(check.confidence * 100)}%</span>
        </div>
      </div>
    </div>
  );
};

const EmptyState: React.FC = () => (
  <div className="glass-panel rounded-xl p-6 text-center">
    <ListChecks className="w-8 h-8 text-graphite-600 mx-auto mb-2" />
    <p className="text-xs text-graphite-500">No risk checks recorded for this case yet.</p>
  </div>
);

export const RiskReasons: React.FC<RiskReasonsProps> = ({ checks, compact = false }) => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | RiskCheckStatus>('ALL');
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const grouped = useMemo(() => {
    const byFactor = new Map<string, RiskCheck[]>();
    for (const c of checks) {
      const key = c.factor || 'OTHER';
      if (!byFactor.has(key)) byFactor.set(key, []);
      byFactor.get(key)!.push(c);
    }
    const severityRank: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    const statusRank: Record<string, number> = { FAIL: 0, INFO: 1, PASS: 2, NOT_APPLICABLE: 3 };
    for (const list of byFactor.values()) {
      list.sort((a, b) => {
        const s = statusRank[a.status] - statusRank[b.status];
        if (s !== 0) return s;
        const sev = (severityRank[a.severity || ''] ?? 9) - (severityRank[b.severity || ''] ?? 9);
        if (sev !== 0) return sev;
        return b.score_impact - a.score_impact;
      });
    }
    return FACTOR_ORDER
      .map((key) => ({ key, label: FACTOR_LABELS[key] || 'Other', items: byFactor.get(key) || [] }))
      .filter((g) => g.items.length > 0);
  }, [checks]);

  if (checks.length === 0) {
    return compact
      ? <p className="text-xs text-graphite-500 p-3">No risk checks recorded for this case.</p>
      : <EmptyState />;
  }

  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const failCount = checks.filter((c) => c.status === 'FAIL').length;

  const body = (
    <div className="space-y-4">
      {grouped.map((group) => {
        const visible = statusFilter === 'ALL' ? group.items : group.items.filter((c) => c.status === statusFilter);
        if (visible.length === 0) return null;
        const groupFailCount = group.items.filter((c) => c.status === 'FAIL').length;
        const isCollapsed = collapsedGroups.has(group.key);
        return (
          <div key={group.key}>
            <button
              onClick={() => toggleGroup(group.key)}
              className="w-full flex items-center justify-between gap-2 py-1.5 text-left cursor-pointer group"
            >
              <span className="text-[11px] font-semibold text-graphite-300 uppercase tracking-wide flex items-center gap-2">
                {group.label}
                <span className="text-graphite-500 font-normal normal-case">
                  ({group.items.length} check{group.items.length === 1 ? '' : 's'}
                  {groupFailCount > 0 ? `, ${groupFailCount} flagged` : ', all clean'})
                </span>
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-graphite-500 transition-transform ${isCollapsed ? '-rotate-90' : ''}`} />
            </button>
            {!isCollapsed && (
              <div className="space-y-2 mt-1.5">
                {visible.map((c, idx) => <CheckRow key={c.id || `${group.key}-${idx}`} check={c} />)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  if (compact) {
    return body;
  }

  return (
    <ScrollReveal className="glass-panel rounded-xl p-5 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <SectionHeading
          level="h3"
          title={`Risk reasons — itemized checks (${checks.length})`}
          icon={<ListChecks className="w-4 h-4 text-graphite-500" />}
        />
        <div className="flex items-center gap-1 bg-graphite-950/60 p-1 rounded-lg border border-graphite-800/80 text-[11px]">
          {(['ALL', 'FAIL', 'PASS', 'INFO', 'NOT_APPLICABLE'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 rounded-lg transition-all duration-200 cursor-pointer ${
                statusFilter === s
                  ? 'bg-brass-950/80 text-brass-300 border border-brass-500/40 font-semibold shadow-sm'
                  : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60'
              }`}
            >
              {s === 'NOT_APPLICABLE' ? 'N/A' : s}
            </button>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-graphite-500 -mt-2">
        {failCount === 0
          ? `All ${checks.length} checks passed — this is why the case is clean, not an absence of evidence.`
          : `${failCount} of ${checks.length} checks flagged.`}
      </p>

      {body}
    </ScrollReveal>
  );
};
