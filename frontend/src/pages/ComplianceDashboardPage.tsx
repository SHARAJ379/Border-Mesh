import React, { useEffect, useState } from 'react';
import { DpdpComplianceStatus } from '../types';
import { api } from '../services/api';
import { SectionHeading } from '../components/SectionHeading';
import {
  Scale,
  Lock,
  Trash2,
  Link2,
  Fingerprint,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

/**
 * Read-only view mapping this app's ALREADY-IMPLEMENTED privacy/security
 * controls to the DPDP Act 2023 principles they actually serve. Every
 * number here comes straight from GET /api/compliance/dpdp-status, which is
 * itself a pure read over existing tables/services -- no new write path, no
 * new data model. This page presents; it does not certify.
 */

interface Principle {
  key: string;
  name: string;
  section: string;
  description: string;
  icon: React.ReactNode;
}

const PRINCIPLES: Principle[] = [
  {
    key: 'security',
    name: 'Reasonable Security Safeguards',
    section: 'DPDP Act 2023, Sec. 8(5)',
    description:
      'Personal data must be protected by reasonable security safeguards to prevent a data breach.',
    icon: <Lock className="w-4 h-4" />,
  },
  {
    key: 'storage',
    name: 'Storage Limitation & Erasure',
    section: 'DPDP Act 2023, Sec. 8(7)–8(8)',
    description:
      'Personal data should be erased once the purpose it was collected for is served, unless retention is required by law.',
    icon: <Trash2 className="w-4 h-4" />,
  },
  {
    key: 'accountability',
    name: 'Accountability',
    section: 'DPDP Act 2023, Sec. 8 (general Data Fiduciary obligations)',
    description:
      'A Data Fiduciary must be able to demonstrate, and prove, exactly how personal data was processed.',
    icon: <Link2 className="w-4 h-4" />,
  },
  {
    key: 'minimization',
    name: 'Data Minimization',
    section: "Implicit in Sec. 5's purpose-limitation regime",
    description:
      'Only the data actually needed for the stated purpose should be collected or retained in identifiable form.',
    icon: <Fingerprint className="w-4 h-4" />,
  },
];

const NOT_IMPLEMENTED = [
  'Consent management — no consent-capture flow exists; this app processes synthetic demo identities only.',
  'Data Principal rights portal — no self-service access/correction/erasure request flow for the individual.',
  'Data breach notification to the Data Protection Board or affected individuals.',
  'Cross-border data transfer safeguards.',
  'Significant Data Fiduciary obligations (DPIA, independent data auditor, Data Protection Officer).',
];

const LoadingState: React.FC = () => (
  <div className="flex items-center justify-center min-h-[40vh]">
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
        <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
      </div>
      <span className="text-xs text-graphite-400 font-medium tracking-wide">Loading compliance status…</span>
    </div>
  </div>
);

const ErrorState: React.FC<{ message: string }> = ({ message }) => (
  <div className="bg-rose-950/40 border border-rose-500/30 rounded-xl p-4 text-xs text-rose-300 animate-fade-in">
    {message}
  </div>
);

export const ComplianceDashboardPage: React.FC = () => {
  const [status, setStatus] = useState<DpdpComplianceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      setStatus(await api.getDpdpComplianceStatus());
    } catch (err: any) {
      setError(err.message || 'Failed to load compliance status');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error || !status) {
    return <ErrorState message={error || 'No compliance data available'} />;
  }

  const hashCoverage =
    status.identifier_hashing.total_cases > 0
      ? Math.round(
          (status.identifier_hashing.cases_with_hashed_identifier / status.identifier_hashing.total_cases) * 100
        )
      : 100;

  return (
    <div className="space-y-5">
      <SectionHeading
        title="DPDP Act 2023 compliance mapping"
        description="A live view of which existing controls back which DPDP principles — not a legal compliance certification."
        icon={<Scale className="w-4 h-4 text-graphite-500" />}
      />

      <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl p-4 text-xs text-amber-200 flex items-start gap-2.5 animate-fade-in">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <p>
          This page presents controls already implemented in this codebase, mapped to the DPDP Act 2023
          principles they genuinely serve. It is illustrative for a hackathon prototype, not a legal
          compliance opinion — section references should be independently verified before any real-world
          claim is made from them. Principles with no corresponding implementation are listed as{' '}
          <span className="font-semibold">not implemented</span> below, not silently omitted.
        </p>
      </div>

      {/* Principle cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Security Safeguards */}
        <PrincipleCard principle={PRINCIPLES[0]}>
          <Fact label="Encryption algorithm" value={status.encryption.algorithm} />
          <Fact label="Applies to" value={status.encryption.applies_to.join(', ')} />
          <Fact label="Identifier hashing" value={status.identifier_hashing.algorithm} />
          <div className="flex items-center justify-between text-[11px] pt-1">
            <span className="text-graphite-400">Encryption key</span>
            <span className={status.encryption.using_default_demo_key ? 'text-amber-300' : 'text-emerald-400'}>
              {status.encryption.using_default_demo_key ? 'Shipped demo key (not production-safe)' : 'Custom key configured'}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-graphite-400">Cases with hashed identifier</span>
            <span className="text-graphite-200 font-semibold">
              {status.identifier_hashing.cases_with_hashed_identifier} / {status.identifier_hashing.total_cases} ({hashCoverage}%)
            </span>
          </div>
          <div className="text-[11px] text-graphite-400 pt-1">
            Access control: {status.access_control.mechanism}, required for{' '}
            {status.access_control.officer_key_required_for.join(', ')}.
          </div>
        </PrincipleCard>

        {/* Storage Limitation / Erasure */}
        <PrincipleCard principle={PRINCIPLES[1]}>
          <Fact label="Mechanism" value={status.biometric_purge.endpoint} />
          <div className="flex items-center justify-between text-[11px] pt-1">
            <span className="text-graphite-400">Cases with biometrics purged</span>
            <span className="text-graphite-200 font-semibold">
              {status.biometric_purge.cases_purged} / {status.biometric_purge.total_cases}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-graphite-400">BIOMETRICS_PURGED audit events logged</span>
            <span className="text-graphite-200 font-semibold">{status.biometric_purge.audit_events_logged}</span>
          </div>
          <p className="text-[11px] text-graphite-500 pt-1">
            Purging deletes raw biometric artifacts and the cross-case face embedding while preserving the
            anonymized case record and risk score for regulatory audit integrity.
          </p>
        </PrincipleCard>

        {/* Accountability */}
        <PrincipleCard principle={PRINCIPLES[2]}>
          <div className="flex items-center justify-between text-[11px] pt-1">
            <span className="text-graphite-400">Audit chain status</span>
            <span className={`flex items-center gap-1 font-semibold ${status.audit_chain.valid ? 'text-emerald-400' : 'text-rose-400'}`}>
              {status.audit_chain.valid ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
              {status.audit_chain.valid ? 'Valid' : 'Broken'}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-graphite-400">Total chained records</span>
            <span className="text-graphite-200 font-semibold">{status.audit_chain.total_records}</span>
          </div>
          <p className="text-[11px] text-graphite-500 pt-1">{status.audit_chain.reason}</p>
        </PrincipleCard>

        {/* Data Minimization */}
        <PrincipleCard principle={PRINCIPLES[3]}>
          <p className="text-[11px] text-graphite-400">
            Document numbers and other sensitive identifiers are stored only as SHA-256 hashes for indexing
            and cross-referencing — the original plaintext value is never persisted in the case record.
          </p>
          <div className="flex items-center justify-between text-[11px] pt-1">
            <span className="text-graphite-400">Coverage</span>
            <span className="text-graphite-200 font-semibold">{hashCoverage}% of stored cases</span>
          </div>
        </PrincipleCard>
      </div>

      {/* Known gaps — not hidden */}
      <div className="bg-rose-950/30 border border-rose-500/30 rounded-xl p-4 space-y-2 animate-fade-in">
        <h3 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Known gaps
        </h3>
        {status.known_gaps.map((gap, i) => (
          <div key={i} className="text-xs text-rose-200/90">
            <span className="font-semibold">{gap.control}:</span> {gap.gap}
          </div>
        ))}
      </div>

      {/* What's not claimed */}
      <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-4 space-y-2 transition-all duration-300 hover:border-graphite-700/60 animate-fade-in">
        <h3 className="text-sm font-semibold text-graphite-300">Not implemented — not claimed</h3>
        <ul className="text-xs text-graphite-500 space-y-1 list-disc list-inside">
          {NOT_IMPLEMENTED.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </div>

      <p className="text-[10px] text-graphite-500">
        Generated {new Date(status.generated_at).toLocaleString()}
      </p>
    </div>
  );
};

const PrincipleCard: React.FC<{ principle: Principle; children: React.ReactNode }> = ({ principle, children }) => (
  <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-4 space-y-2.5 transition-all duration-300 hover:border-graphite-700/60 animate-fade-in" style={{ animationDelay: '0ms' }}>
    <div className="flex items-start justify-between gap-2">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg bg-brass-950/50 border border-brass-500/30">
          <span className="text-brass-400">{principle.icon}</span>
        </div>
        <span className="text-sm font-semibold text-graphite-200">{principle.name}</span>
      </div>
      <span className="inline-flex items-center gap-1.5 rounded-full font-semibold tracking-wider uppercase border text-xs px-2.5 py-1 bg-emerald-950/60 text-emerald-300 border-emerald-500/40">
        <span className="h-1.5 w-1.5 rounded-full bg-current"></span>
        Implemented
      </span>
    </div>
    <p className="text-[10px] text-graphite-500 uppercase tracking-wider">{principle.section}</p>
    <p className="text-[11px] text-graphite-400">{principle.description}</p>
    <div className="pt-1 border-t border-graphite-800/60 space-y-1.5">{children}</div>
  </div>
);

const Fact: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-start justify-between gap-3 text-[11px]">
    <span className="text-graphite-400 shrink-0">{label}</span>
    <span className="text-graphite-200 text-right">{value}</span>
  </div>
);
