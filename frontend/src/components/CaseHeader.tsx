import React, { useEffect, useState } from 'react';
import { CaseDetail, OfficerDecision } from '../types';
import { RiskBadge } from './RiskBadge';
import { Shield, Clock, Globe, FileText, CheckCircle, Send, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { getOfficer } from '../lib/auth';

interface CaseHeaderProps {
  caseData: CaseDetail;
  onDecisionUpdated: (updated: any) => void;
  onDeleted?: () => void;
}

export const CaseHeader: React.FC<CaseHeaderProps> = ({
  caseData,
  onDecisionUpdated,
  onDeleted
}) => {
  const [decision, setDecision] = useState<OfficerDecision>(
    caseData.officer_decision !== 'PENDING' ? caseData.officer_decision : 'CLEARED'
  );
  const [notes, setNotes] = useState(caseData.officer_notes || '');
  const [submitting, setSubmitting] = useState(false);
  const [purging, setPurging] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // useState's initial value only runs once, on mount -- so if the parent
  // re-fetches this same case (the "Refresh" button, or another officer's
  // decision landing between polls) with a different officer_decision /
  // officer_notes than what this form was seeded with, the form silently
  // kept showing the stale value instead of the freshly fetched one. Only
  // resyncs when the SERVER value actually changes, so an officer's own
  // in-progress, not-yet-submitted edit here is never clobbered by an
  // unrelated caseData update (e.g. a biometrics purge).
  useEffect(() => {
    setDecision(caseData.officer_decision !== 'PENDING' ? caseData.officer_decision : 'CLEARED');
    setNotes(caseData.officer_notes || '');
  }, [caseData.officer_decision, caseData.officer_notes]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      const updated = await api.recordOfficerDecision(caseData.id, decision, notes);
      onDecisionUpdated(updated);
      alert('Officer decision recorded and audit trail updated.');
    } catch (err: any) {
      alert(`Failed to save decision: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePurgeBiometrics = async () => {
    if (!confirm('Execute GDPR Article 17 Biometric Purge?\n\nThis will permanently scrub the document image, face selfie, and biometric crops from disk while retaining anonymized case hashes for regulatory audit.')) return;
    try {
      setPurging(true);
      const res = await api.purgeBiometrics(caseData.id);
      onDecisionUpdated({ ...caseData, biometrics_purged: true });
      alert(`Biometric Scrub Completed:\n${res.message}\n\nCryptographic Audit Hash: ${res.audit_hash.substring(0, 16)}...`);
    } catch (err: any) {
      alert(`Purge error: ${err.message}`);
    } finally {
      setPurging(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Permanently delete this entire screening case record from the system?')) return;
    try {
      setDeleting(true);
      await api.deleteCase(caseData.id);
      if (onDeleted) onDeleted();
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const createdFormatted = new Date(caseData.created_at).toLocaleString();

  return (
    <div className="border border-hairline p-5 space-y-5">
      {/* Top banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-hairline">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="figure text-xl sm:text-2xl font-bold text-ink tracking-tight">
              {caseData.case_number}
            </h1>
            <RiskBadge level={caseData.risk_level} size="md" />
            <RiskBadge status={caseData.status} size="md" />
            {caseData.biometrics_purged && (
              <span className="badge-signal badge-medium text-[11px] flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5" strokeWidth={1.75} />
                Biometrics Purged (GDPR)
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-ink-soft mt-2">
            <span className="flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
              {caseData.country || 'Unknown Jurisdiction'}
            </span>
            <span className="flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
              {caseData.document_type}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
              {createdFormatted}
            </span>
          </div>
        </div>

        {/* Action controls -- kept low-emphasis so they don't compete with
            the case's own risk content; no color-coded danger fill, but a
            confirm() step gates both, consistent with the system's overall
            restraint (see the design-review discussion in git history). */}
        <div className="flex items-center gap-4 text-[11px] uppercase tracking-[0.05em]">
          {!caseData.biometrics_purged ? (
            <button
              onClick={handlePurgeBiometrics}
              disabled={purging}
              className="text-ink-soft hover:text-signal-medium transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              title="Privacy-by-Design: Purge biometric image files from disk while preserving anonymized record"
            >
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.75} />
              <span>{purging ? 'Purging…' : 'Purge Biometrics'}</span>
            </button>
          ) : (
            <span className="text-muted italic">
              Biometrics scrubbed
            </span>
          )}

          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-ink-soft hover:text-signal-critical transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Delete entire case file"
          >
            <Trash2 className="w-3.5 h-3.5" strokeWidth={1.75} />
            <span>Delete Case</span>
          </button>
        </div>
      </div>

      {/* Officer determination */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-bold text-ink flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
            Screening officer determination
          </span>
          <span className="text-[11px] text-muted">
            Recorded by: {getOfficer()?.badge_id ?? 'Unknown officer'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="label-eyebrow block mb-1.5">
              Officer Action
            </label>
            <select
              value={decision}
              onChange={(e) => setDecision(e.target.value as OfficerDecision)}
              className="field w-full cursor-pointer"
            >
              <option value="CLEARED">CLEARED (Admit Traveler)</option>
              <option value="REQUIRES_INSPECTION">REQUIRES FURTHER INSPECTION (Secondary)</option>
              <option value="ESCALATED">ESCALATED (Supervisor Review)</option>
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="label-eyebrow block mb-1.5">
              Inspection Notes / Justification
            </label>
            <div className="flex gap-3">
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Enter officer notes or document inspection observations..."
                className="field flex-1"
              />
              <button
                type="submit"
                disabled={submitting}
                className="btn-primary px-5 py-2 text-[11px] font-bold flex items-center gap-1.5 cursor-pointer shrink-0"
              >
                <Send className="w-3 h-3" strokeWidth={1.75} />
                <span>Submit</span>
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
