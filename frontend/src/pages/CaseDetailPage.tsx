import React, { useEffect, useState } from 'react';
import { CaseDetail } from '../types';
import { api } from '../services/api';
import { CaseHeader } from '../components/CaseHeader';
import { RiskScore } from '../components/RiskScore';
import { RiskBreakdown } from '../components/RiskBreakdown';
import { OCRResults } from '../components/OCRResults';
import { MRZValidator } from '../components/MRZValidator';
import { TamperHeatmap } from '../components/TamperHeatmap';
import { FaceVerification } from '../components/FaceVerification';
import { RiskReasons } from '../components/RiskReasons';
import { AuditTimeline } from '../components/AuditTimeline';
import { Tabs, TabItem } from '../components/Tabs';
import { ScrollReveal } from '../components/ScrollReveal';
import { downloadCaseReportPdf } from '../lib/pdfExport';
import { buildUploadedDocumentUrl } from '../lib/paths';
import {
  ArrowLeft,
  Loader2,
  RefreshCw,
  Download,
  FileText,
  ShieldCheck,
  Flame,
  ScanFace,
  ListChecks,
  History
} from 'lucide-react';

const DETAIL_TABS: TabItem[] = [
  { id: 'ocr', label: 'OCR', icon: FileText },
  { id: 'mrz', label: 'MRZ', icon: ShieldCheck },
  { id: 'tamper', label: 'Tamper', icon: Flame },
  { id: 'face', label: 'Face', icon: ScanFace },
  { id: 'evidence', label: 'Risk Reasons', icon: ListChecks },
  { id: 'audit', label: 'Audit Trail', icon: History }
];

interface CaseDetailPageProps {
  caseId: string;
  onBack: () => void;
}

export const CaseDetailPage: React.FC<CaseDetailPageProps> = ({ caseId, onBack }) => {
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportingPdf, setExportingPdf] = useState(false);

  useEffect(() => {
    fetchCase();
  }, [caseId]);

  const fetchCase = async () => {
    try {
      setLoading(true);
      const data = await api.getCaseDetail(caseId);
      setCaseData(data);
    } catch (err: any) {
      console.error('Failed to load case detail', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !caseData) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 border border-hairline" />
            <div className="absolute inset-0 border border-accent border-t-transparent border-r-transparent animate-spin" />
          </div>
          <span className="text-[11px] uppercase tracking-[0.06em] text-muted">Loading case file {caseId}&hellip;</span>
        </div>
      </div>
    );
  }

  const analysis = caseData.analyses && caseData.analyses.length > 0 ? caseData.analyses[0] : undefined;

  // The risk engine persists its real per-factor weighted breakdown for any
  // case that ran through the actual screening pipeline. The 20 pre-seeded
  // demo cases never ran that pipeline, so they have no genuine per-signal
  // data — for those (and only those), fall back to a rough client-side
  // estimate rather than showing nothing.
  const riskBreakdown = analysis?.risk_breakdown ?? [
    {
      factor: 'MRZ & Document Validation',
      weight: 0.25,
      raw_risk: analysis?.validation_result?.failed_count ? 70 : 10,
      weighted_contribution: analysis?.validation_result?.failed_count ? 17.5 : 2.5,
    },
    {
      factor: 'Forensic Tamper AI',
      weight: 0.30,
      // `?? 0.1`, not `||` -- a genuinely clean 0.0 tamper_risk reading
      // (possible on seeded demo data, which bypasses
      // _aggregate_tamper_score's own 0.04 floor) is falsy and would
      // otherwise be swallowed into the "no data" fallback, same bug
      // class already fixed once this session in FaceVerification.tsx.
      raw_risk: (analysis?.tamper_result?.tamper_risk ?? 0.1) * 100,
      weighted_contribution: ((analysis?.tamper_result?.tamper_risk ?? 0.1) * 100) * 0.30,
    },
    {
      factor: 'Biometric Face Verification',
      weight: 0.30,
      raw_risk: analysis?.face_result?.status === 'MATCH' ? 12 : 75,
      weighted_contribution: (analysis?.face_result?.status === 'MATCH' ? 12 : 75) * 0.30,
    },
    {
      factor: 'Data Consistency Crosscheck',
      weight: 0.10,
      raw_risk: analysis?.validation_result?.failed_count ? 60 : 0,
      weighted_contribution: (analysis?.validation_result?.failed_count ? 60 : 0) * 0.10,
    },
    {
      factor: 'Simulated Watchlist Adapter',
      weight: 0.05,
      raw_risk: caseData.risk_checks.some(c => c.category === 'WATCHLIST' && c.status === 'FAIL') ? 100 : 0,
      weighted_contribution: caseData.risk_checks.some(c => c.category === 'WATCHLIST' && c.status === 'FAIL') ? 5.0 : 0.0,
    }
  ];

  // Document image URL
  const isPurged = caseData.biometrics_purged || analysis?.document_image_path?.startsWith('[PURGED');
  const docImgUrl = (!isPurged && analysis?.document_image_path)
    ? buildUploadedDocumentUrl(analysis.document_image_path)
    : undefined;

  const handleDownloadPdf = async () => {
    try {
      setExportingPdf(true);
      await downloadCaseReportPdf({ caseData, analysis, riskBreakdown, docImgUrl });
    } catch (err: any) {
      alert(`Failed to generate PDF report: ${err.message}`);
    } finally {
      setExportingPdf(false);
    }
  };

  return (
    <div className="space-y-7 max-w-7xl mx-auto pb-12">
      {/* Navigation and Refresh Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-[11px] uppercase tracking-[0.05em] text-ink-soft hover:text-accent transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.75} />
          <span>Back to Screening Operations</span>
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={handleDownloadPdf}
            disabled={exportingPdf}
            className="btn-secondary px-3 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Download a PDF summary of this case"
          >
            {exportingPdf ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" strokeWidth={1.75} />}
            <span>{exportingPdf ? 'Preparing PDF…' : 'Download PDF'}</span>
          </button>

          <button
            onClick={fetchCase}
            className="btn-secondary px-3 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer"
            title="Refresh case data"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.75} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Case Header & Decision Form */}
      <CaseHeader
        caseData={caseData}
        onDecisionUpdated={(updated) => setCaseData({ ...caseData, ...updated })}
        onDeleted={onBack}
      />

      {/* Top Intelligence Grid: Risk Score Gauge + Explainable Breakdown --
          sized to content, not an even split: the gauge is a compact
          summary, the breakdown is the detailed data. */}
      <ScrollReveal className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4">
          <RiskScore
            score={caseData.risk_score}
            level={caseData.risk_level}
            recommendation={caseData.recommendation}
          />
        </div>

        <div className="lg:col-span-8">
          <RiskBreakdown
            breakdown={riskBreakdown}
            totalScore={caseData.risk_score}
          />
        </div>
      </ScrollReveal>

      {/* Forensics & Deep-Dive Modules: one at a time via tabs */}
      <ScrollReveal>
      <Tabs key={caseId} tabs={DETAIL_TABS} defaultTabId="ocr">
        {(activeTabId) => {
          switch (activeTabId) {
            case 'ocr':
              return <OCRResults data={analysis?.ocr_result} />;
            case 'mrz':
              return (
                <MRZValidator
                  mrz={analysis?.mrz_result}
                  validation={analysis?.validation_result}
                  documentType={analysis?.ocr_result?.fields?.document_type}
                />
              );
            case 'tamper':
              return (
                <TamperHeatmap
                  originalImageUrl={docImgUrl}
                  tamperResult={analysis?.tamper_result}
                />
              );
            case 'face':
              return <FaceVerification faceResult={analysis?.face_result} />;
            case 'evidence':
              return <RiskReasons checks={caseData.risk_checks} />;
            case 'audit':
              return <AuditTimeline logs={caseData.audit_logs} />;
            default:
              return null;
          }
        }}
      </Tabs>
      </ScrollReveal>
    </div>
  );
};
