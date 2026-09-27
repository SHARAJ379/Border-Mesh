import React, { useEffect, useState } from 'react';
import { CaseDetail, OfficerDecision } from '../types';
import { RiskBadge } from './RiskBadge';
import { Shield, Clock, Globe, FileText, CheckCircle, AlertTriangle, Send, Trash2 } from 'lucide-react';
import { api } from '../services/api';

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
    <div className="glass-panel rounded-xl p-5 space-y-5">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-graphite-800/60">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-bold font-mono text-graphite-100 tracking-wider">
              {caseData.case_number}
            </h1>
            <RiskBadge level={caseData.risk_level} size="md" />
            <RiskBadge status={caseData.status} size="md" />
            {caseData.biometrics_purged && (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-950/80 border border-amber-500/40 text-amber-300 flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5 text-amber-400" />
                Biometrics Purged (GDPR)
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-graphite-400 mt-2">
            <span className="flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-graphite-500" />
              {caseData.country || 'Unknown Jurisdiction'}
            </span>
            <span className="flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-graphite-500" />
              {caseData.document_type}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-graphite-500" />
              {createdFormatted}
            </span>
          </div>
        </div>

        {/* Action Controls -- kept low-emphasis so they don't compete with the case's own risk content */}
        <div className="flex items-center gap-3 text-xs">
          {!caseData.biometrics_purged ? (
            <button
              onClick={handlePurgeBiometrics}
              disabled={purging}
              className="text-graphite-400 hover:text-amber-400 transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 px-2 py-1 rounded-lg hover:bg-amber-950/20"
              title="Privacy-by-Design: Purge biometric image files from disk while preserving anonymized record"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{purging ? 'Purging…' : 'Purge Biometrics'}</span>
            </button>
          ) : (
            <span className="text-graphite-500 italic px-2 py-1 rounded-lg bg-amber-950/20">
              Biometrics scrubbed
            </span>
          )}

          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-graphite-400 hover:text-rose-400 transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 px-2 py-1 rounded-lg hover:bg-rose-950/20"
            title="Delete entire case file"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete Case</span>
          </button>
        </div>
      </div>

      {/* Officer Determination Action Bar */}
      <form onSubmit={handleSubmit} className="p-4 rounded-xl bg-graphite-950/70 border border-graphite-800/80 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-graphite-200 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-graphite-500" />
            Screening officer determination
          </span>
          <span className="text-xs text-graphite-500">
            Recorded by: OFFICER-DEMO-01
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-graphite-400 uppercase tracking-wider block mb-1">
              Officer Action
            </label>
            <select
              value={decision}
              onChange={(e) => setDecision(e.target.value as OfficerDecision)}
              className="w-full bg-graphite-900 border border-graphite-700 rounded-lg px-3 py-2 text-xs text-graphite-200 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all cursor-pointer"
            >
              <option value="CLEARED">CLEARED (Admit Traveler)</option>
              <option value="REQUIRES_INSPECTION">REQUIRES FURTHER INSPECTION (Secondary)</option>
              <option value="ESCALATED">ESCALATED (Supervisor Review)</option>
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="text-[10px] text-graphite-400 uppercase tracking-wider block mb-1">
              Inspection Notes / Justification
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Enter officer notes or document inspection observations..."
                className="flex-1 bg-graphite-900 border border-graphite-700 rounded-lg px-3 py-2 text-xs text-graphite-200 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
              />
              <button
                type="submit"
                disabled={submitting}
                className="btn-brass px-5 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 cursor-pointer shrink-0 focus:outline-none focus:ring-2 focus:ring-brass-500/50"
              >
                <Send className="w-3 h-3" />
                <span>Submit</span>
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
