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
import { EvidenceList } from '../components/EvidenceList';
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
  History,
  ChevronRight
} from 'lucide-react';

const DETAIL_TABS: TabItem[] = [
  { id: 'ocr', label: 'OCR', icon: FileText },
  { id: 'mrz', label: 'MRZ', icon: ShieldCheck },
  { id: 'tamper', label: 'Tamper', icon: Flame },
  { id: 'face', label: 'Face', icon: ScanFace },
  { id: 'evidence', label: 'Evidence', icon: ListChecks },
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
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 border-2 border-graphite-800 rounded-full" />
            <div className="absolute inset-0 border-2 border-brass-400 border-t-transparent border-r-transparent rounded-full animate-spin" />
          </div>
          <span className="text-xs text-graphite-400 font-medium tracking-wide">Loading case file {caseId}…</span>
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
      top_signals: analysis?.mrz_result?.is_valid ? ['Checksums Verified'] : ['MRZ Discrepancy']
    },
    {
      factor: 'Forensic Tamper AI',
      weight: 0.30,
      raw_risk: (analysis?.tamper_result?.tamper_risk || 0.1) * 100,
      weighted_contribution: ((analysis?.tamper_result?.tamper_risk || 0.1) * 100) * 0.30,
      top_signals: analysis?.tamper_result?.signals?.map(s => s.type) || ['Authentic Texture']
    },
    {
      factor: 'Biometric Face Verification',
      weight: 0.30,
      raw_risk: analysis?.face_result?.status === 'MATCH' ? 12 : 75,
      weighted_contribution: (analysis?.face_result?.status === 'MATCH' ? 12 : 75) * 0.30,
      top_signals: [analysis?.face_result?.status || 'Face Evaluated']
    },
    {
      factor: 'Data Consistency Crosscheck',
      weight: 0.10,
      raw_risk: analysis?.validation_result?.failed_count ? 60 : 0,
      weighted_contribution: (analysis?.validation_result?.failed_count ? 60 : 0) * 0.10,
      top_signals: []
    },
    {
      factor: 'Simulated Watchlist Adapter',
      weight: 0.05,
      raw_risk: caseData.risk_signals.some(s => s.module === 'WATCHLIST') ? 100 : 0,
      weighted_contribution: caseData.risk_signals.some(s => s.module === 'WATCHLIST') ? 5.0 : 0.0,
      top_signals: []
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
          className="flex items-center gap-2 text-xs text-graphite-400 hover:text-brass-400 transition-colors cursor-pointer px-2 py-1.5 rounded-lg hover:bg-graphite-900/50"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Screening Operations</span>
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadPdf}
            disabled={exportingPdf}
            className="glass-panel px-3 py-1.5 rounded-lg text-graphite-400 hover:text-graphite-200 text-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brass-500/50"
            title="Download a PDF summary of this case"
          >
            {exportingPdf ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            <span>{exportingPdf ? 'Preparing PDF…' : 'Download PDF'}</span>
          </button>

          <button
            onClick={fetchCase}
            className="glass-panel px-3 py-1.5 rounded-lg text-graphite-400 hover:text-graphite-200 text-xs flex items-center gap-1.5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-brass-500/50"
            title="Refresh case data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
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
              return <EvidenceList signals={caseData.risk_signals} />;
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
