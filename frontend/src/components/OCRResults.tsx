import React, { useState } from 'react';
import { OCRResult } from '../types';
import { FileText, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

// Per UIDAI convention (and this app's own DPDP-dashboard-documented
// identifier-hashing control): mask a displayed Aadhaar number to only its
// last 4 digits, grouped 4-4-4 with "X" placeholders (e.g. "XXXX XXXX
// 2529") -- display-layer only. The backend independently hashes the full,
// unmasked number for storage (see screening.py's document_number_hash);
// this never touches that value, only how it's rendered here.
function maskAadhaarNumber(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (digits.length <= 4) return value; // too short to usefully mask
  const last4 = digits.slice(-4);
  const maskedCount = digits.length - 4;
  const maskedGroups: string[] = [];
  for (let i = 0; i < maskedCount; i += 4) {
    maskedGroups.push('X'.repeat(Math.min(4, maskedCount - i)));
  }
  return [...maskedGroups, last4].join(' ');
}

interface OCRResultsProps {
  data?: OCRResult;
}

export const OCRResults: React.FC<OCRResultsProps> = ({ data }) => {
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!data) {
    return (
      <div className="border border-hairline p-5 text-center text-[11px] text-muted">
        No OCR extraction data recorded.
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(data.raw_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isAadhaar = data.fields.document_type === 'AADHAAR';
  const documentNumberDisplay =
    isAadhaar && data.fields.document_number
      ? maskAadhaarNumber(data.fields.document_number)
      : data.fields.document_number || '—';

  const fields = [
    { label: 'Full Name', value: data.fields.full_name || '—' },
    { label: 'Document Number', value: documentNumberDisplay },
    { label: 'Nationality', value: data.fields.nationality || '—' },
    { label: 'Country of Issue', value: data.fields.country || '—' },
    { label: 'Date of Birth', value: data.fields.date_of_birth || '—' },
    { label: 'Date of Expiry', value: data.fields.date_of_expiry || '—' },
    { label: 'Sex', value: data.fields.sex || '—' },
  ];

  const confPercent = Math.round(data.confidence * 100);

  return (
    <ScrollReveal className="border border-hairline p-5 space-y-5">
      <SectionHeading
        level="h3"
        title="OCR extraction"
        icon={<FileText className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <div className="flex items-center gap-4 flex-wrap text-[11px]">
            {data.fields.document_type && (
              <span className="label-eyebrow">{data.fields.document_type}</span>
            )}
            <span className="figure text-ink font-bold">Confidence: {confPercent}%</span>
          </div>
        }
      />

      {/* Field grid -- hairline rows, not bordered tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 border-t border-b border-hairline divide-x divide-hairline">
        {fields.map((f, i) => (
          <div key={i} className="p-3">
            <span className="label-eyebrow block">
              {f.label}
            </span>
            <span className="figure text-[12px] text-ink truncate block mt-1">
              {f.value}
            </span>
          </div>
        ))}
      </div>

      {/* Raw text accordion */}
      <div>
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="flex items-center justify-between w-full text-[11px] uppercase tracking-[0.06em] text-ink-soft hover:text-ink transition-colors py-1 cursor-pointer"
        >
          <span>Raw Extracted OCR Buffer ({data.detected_lines?.length ?? 0} lines)</span>
          {showRaw ? <ChevronUp className="w-3.5 h-3.5" strokeWidth={1.75} /> : <ChevronDown className="w-3.5 h-3.5" strokeWidth={1.75} />}
        </button>

        {showRaw && (
          <div className="mt-3 relative animate-fade-in">
            <pre className="p-4 border border-hairline text-ink-soft text-[11px] leading-relaxed overflow-x-auto max-h-56 select-all">
              {data.raw_text}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-3 right-3 btn-secondary p-2 text-[11px] flex items-center gap-1.5 cursor-pointer"
              title="Copy raw text"
            >
              {copied ? <Check className="w-3.5 h-3.5" strokeWidth={1.75} /> : <Copy className="w-3.5 h-3.5" strokeWidth={1.75} />}
              <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        )}
      </div>
    </ScrollReveal>
  );
};
