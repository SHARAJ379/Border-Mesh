import React from 'react';
import { CaseDetail, DocumentAnalysis, RiskFactorContribution, RiskLevel } from '../types';

interface CaseReportPrintableProps {
  caseData: CaseDetail;
  analysis?: DocumentAnalysis;
  riskBreakdown: RiskFactorContribution[];
  docImgUrl?: string;
}

const RISK_THEME: Record<RiskLevel, { bg: string; border: string; text: string }> = {
  LOW: { bg: '#ECFDF5', border: '#10B981', text: '#047857' },
  MEDIUM: { bg: '#FFFBEB', border: '#F59E0B', text: '#92400E' },
  HIGH: { bg: '#FFF7ED', border: '#F97316', text: '#9A3412' },
  CRITICAL: { bg: '#FEF2F2', border: '#EF4444', text: '#991B1B' }
};

const SectionTitle: React.FC<{ index: string; title: string }> = ({ index, title }) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      borderBottom: '1px solid #E2E8F0',
      paddingBottom: 6,
      marginBottom: 12
    }}
  >
    <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94A3B8' }}>{index}</span>
    <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#0F172A', margin: 0 }}>
      {title}
    </h2>
  </div>
);

const Field: React.FC<{ label: string; value?: string }> = ({ label, value }) => (
  <div style={{ minWidth: 0 }}>
    <div style={{ fontSize: 9, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
    <div style={{ fontSize: 12, color: '#0F172A', fontWeight: 600, marginTop: 2, wordBreak: 'break-word' }}>{value || '—'}</div>
  </div>
);

export const CaseReportPrintable: React.FC<CaseReportPrintableProps> = ({
  caseData,
  analysis,
  riskBreakdown,
  docImgUrl
}) => {
  const theme = RISK_THEME[caseData.risk_level] || RISK_THEME.MEDIUM;
  const mrz = analysis?.mrz_result;
  const ocr = analysis?.ocr_result;
  const tamper = analysis?.tamper_result;
  const face = analysis?.face_result;
  const generatedAt = new Date().toLocaleString();
  const screenedAt = new Date(caseData.created_at).toLocaleString();

  return (
    <div
      style={{
        width: 794,
        background: '#FFFFFF',
        color: '#1E293B',
        fontFamily: "'Helvetica Neue', Arial, sans-serif",
        padding: 30
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#0B0F19',
          borderRadius: 8,
          padding: '18px 24px',
          marginBottom: 18
        }}
      >
        <div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#FFFFFF', letterSpacing: '0.02em' }}>
            BORDER<span style={{ color: '#22D3EE' }}>MESH</span>
          </div>
          <div style={{ fontSize: 10, color: '#94A3B8', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>
            AI Identity Screening — Case Report
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#FFFFFF', fontFamily: 'monospace' }}>{caseData.case_number}</div>
          <div style={{ fontSize: 9, color: '#64748B', marginTop: 2 }}>Generated {generatedAt}</div>
        </div>
      </div>

      {/* Case meta */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          padding: '14px 0',
          borderBottom: '1px solid #E2E8F0',
          marginBottom: 18
        }}
      >
        <Field label="Jurisdiction" value={caseData.country} />
        <Field label="Document Type" value={caseData.document_type} />
        <Field label="Screened At" value={screenedAt} />
        <Field label="Officer Decision" value={caseData.officer_decision?.replace(/_/g, ' ')} />
      </div>

      {/* Overall risk */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          background: theme.bg,
          border: `1px solid ${theme.border}`,
          borderRadius: 8,
          padding: '18px 22px',
          marginBottom: 18
        }}
      >
        <div style={{ textAlign: 'center', minWidth: 80 }}>
          <div style={{ fontSize: 34, fontWeight: 800, color: theme.text, fontFamily: 'monospace', lineHeight: 1 }}>
            {caseData.risk_score.toFixed(1)}
          </div>
          <div style={{ fontSize: 9, color: theme.text, opacity: 0.7 }}>/ 100</div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: theme.text, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            {caseData.risk_level} Risk
          </div>
          <div style={{ fontSize: 12, color: theme.text, marginTop: 4 }}>{caseData.recommendation}</div>
        </div>
      </div>

      {/* Document image + face verification */}
      <div style={{ marginBottom: 18 }}>
        <SectionTitle index="01" title="Document &amp; Biometric Evidence" />
        <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 16 }}>
          <div>
            <div style={{ fontSize: 9, color: '#94A3B8', textTransform: 'uppercase', marginBottom: 6 }}>
              Submitted Document
            </div>
            <div
              style={{
                border: '1px solid #E2E8F0',
                borderRadius: 6,
                overflow: 'hidden',
                background: '#F8FAFC',
                height: 180,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {docImgUrl ? (
                <img src={docImgUrl} crossOrigin="anonymous" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
              ) : (
                <span style={{ fontSize: 11, color: '#94A3B8' }}>No document image (purged or unavailable)</span>
              )}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: '#94A3B8', textTransform: 'uppercase', marginBottom: 6 }}>
              Face Match — {face?.status?.replace(/_/g, ' ') || 'Not evaluated'}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    border: '1px solid #E2E8F0',
                    borderRadius: 6,
                    overflow: 'hidden',
                    background: '#F8FAFC',
                    height: 100,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {face?.document_face_url ? (
                    <img src={face.document_face_url} crossOrigin="anonymous" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <span style={{ fontSize: 9, color: '#94A3B8' }}>Portrait</span>
                  )}
                </div>
                <div style={{ fontSize: 8, color: '#94A3B8', marginTop: 3 }}>Document</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    border: '1px solid #E2E8F0',
                    borderRadius: 6,
                    overflow: 'hidden',
                    background: '#F8FAFC',
                    height: 100,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {face?.live_face_url ? (
                    <img src={face.live_face_url} crossOrigin="anonymous" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <span style={{ fontSize: 9, color: '#94A3B8' }}>Live Capture</span>
                  )}
                </div>
                <div style={{ fontSize: 8, color: '#94A3B8', marginTop: 3 }}>Live Capture</div>
              </div>
            </div>
            {face && (
              <div style={{ marginTop: 8, fontSize: 11, textAlign: 'center', fontWeight: 700, color: face.status === 'MATCH' ? '#047857' : '#B91C1C' }}>
                {Math.round(face.similarity * 100)}% Similarity (Threshold {Math.round(face.match_threshold * 100)}%)
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tamper analysis */}
      <div style={{ marginBottom: 18 }}>
        <SectionTitle index="02" title="Forensic Tamper Analysis" />
        {tamper ? (
          <>
            {(() => {
              const flaggedChecks = (tamper.checks || []).filter((c) => c.status === 'FAIL');
              return (
                <>
                  <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
                    <Field label="Tamper Risk" value={`${Math.round(tamper.tamper_risk * 100)}%`} />
                    <Field label="Risk Level" value={tamper.risk_level} />
                    <Field label="Checks Flagged" value={String(flaggedChecks.length)} />
                  </div>
                  {flaggedChecks.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {flaggedChecks.slice(0, 4).map((c, i) => (
                        <div
                          key={i}
                          style={{
                            fontSize: 10.5,
                            padding: '6px 10px',
                            border: '1px solid #FED7AA',
                            background: '#FFF7ED',
                            borderRadius: 5,
                            color: '#9A3412'
                          }}
                        >
                          <strong>{c.label}</strong> — {Math.round(c.confidence * 100)}% confidence. {c.explanation}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: '#047857' }}>No significant image manipulation detected.</div>
                  )}
                </>
              );
            })()}
          </>
        ) : (
          <div style={{ fontSize: 11, color: '#94A3B8' }}>No tamper forensic analysis conducted.</div>
        )}
      </div>

      {/* MRZ / OCR */}
      <div style={{ marginBottom: 18 }}>
        <SectionTitle index="03" title="Document Data &amp; MRZ Validation" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 10 }}>
          <Field label="Full Name" value={ocr?.fields.full_name || `${mrz?.surname || ''} ${mrz?.given_names || ''}`.trim()} />
          <Field label="Document Number" value={ocr?.fields.document_number || mrz?.document_number} />
          <Field label="Nationality" value={ocr?.fields.nationality || mrz?.nationality} />
          <Field label="Date of Birth" value={ocr?.fields.date_of_birth || mrz?.birth_date} />
          <Field label="Date of Expiry" value={ocr?.fields.date_of_expiry || mrz?.expiry_date} />
          <Field label="MRZ Checksum" value={mrz ? (mrz.is_valid ? 'All Valid' : 'Mismatch Detected') : 'Not Available'} />
        </div>
      </div>

      {/* Risk breakdown */}
      <div style={{ marginBottom: 18 }}>
        <SectionTitle index="04" title="Explainable Risk Breakdown" />
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10.5 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: '#94A3B8', textTransform: 'uppercase', fontSize: 9 }}>
              <th style={{ paddingBottom: 6, fontWeight: 600 }}>Factor</th>
              <th style={{ paddingBottom: 6, fontWeight: 600 }}>Weight</th>
              <th style={{ paddingBottom: 6, fontWeight: 600 }}>Raw Risk</th>
              <th style={{ paddingBottom: 6, fontWeight: 600, textAlign: 'right' }}>Contribution</th>
            </tr>
          </thead>
          <tbody>
            {riskBreakdown.map((item, i) => (
              <tr key={i} style={{ borderTop: '1px solid #F1F5F9' }}>
                <td style={{ padding: '6px 0', color: '#0F172A', fontWeight: 500 }}>{item.factor}</td>
                <td style={{ padding: '6px 0', color: '#64748B' }}>{item.weight !== null ? `${Math.round(item.weight * 100)}%` : '—'}</td>
                <td style={{ padding: '6px 0', color: '#64748B' }}>{item.raw_risk !== null ? `${Math.round(item.raw_risk)}%` : '—'}</td>
                <td style={{ padding: '6px 0', color: '#0F172A', fontWeight: 700, textAlign: 'right' }}>
                  {item.weighted_contribution >= 0 ? '+' : ''}{item.weighted_contribution.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: 12, display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#94A3B8' }}>
        <span>BorderMesh — Prototype system. Simulated watchlist, no real law-enforcement data.</span>
        <span>AI decision-support only — final determination rests with the screening officer.</span>
      </div>
    </div>
  );
};
