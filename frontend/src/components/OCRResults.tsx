import React, { useState } from 'react';
import { OCRResult } from '../types';
import { FileText, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { SectionHeading } from './SectionHeading';

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
      <div className="p-5 rounded-xl bg-graphite-900/60 border border-graphite-800/80 text-center text-xs text-graphite-500">
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
    <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur space-y-5 transition-all duration-300 hover:border-graphite-700/60">
      <SectionHeading
        level="h3"
        title="OCR extraction"
        icon={<FileText className="w-4 h-4 text-graphite-500" />}
        action={
          <div className="flex items-center gap-2 flex-wrap">
            {data.fields.document_type && (
              <span className="text-xs font-semibold text-graphite-300 px-2.5 py-1 rounded-lg bg-graphite-800/60 border border-graphite-700">
                {data.fields.document_type}
              </span>
            )}
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-graphite-500">Confidence:</span>
              <span className="text-xs font-semibold text-graphite-200 px-2.5 py-1 rounded-lg bg-graphite-800/60 border border-graphite-700">
                {confPercent}%
              </span>
            </div>
          </div>
        }
      />

      {/* Field Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {fields.map((f, i) => (
          <div key={i} className="p-3 rounded-lg bg-graphite-950/70 border border-graphite-800/80 transition-colors hover:border-graphite-700/60">
            <span className="text-[10px] text-graphite-400 uppercase tracking-wider block">
              {f.label}
            </span>
            <span className="text-xs font-mono font-medium text-graphite-200 truncate block mt-1">
              {f.value}
            </span>
          </div>
        ))}
      </div>

      {/* Raw Text Accordion */}
      <div className="pt-3 border-t border-graphite-800/60">
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="flex items-center justify-between w-full text-xs text-graphite-400 hover:text-graphite-200 transition-colors py-2 cursor-pointer"
        >
          <span>Raw Extracted OCR Buffer ({data.detected_lines?.length ?? 0} lines)</span>
          {showRaw ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showRaw && (
          <div className="mt-3 relative animate-fade-in">
            <pre className="p-4 rounded-lg bg-graphite-950 text-graphite-300 font-mono text-[11px] leading-relaxed overflow-x-auto max-h-56 border border-graphite-800/80 select-all">
              {data.raw_text}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-3 right-3 p-2 rounded-lg bg-graphite-800/80 hover:bg-graphite-700 text-graphite-300 text-xs flex items-center gap-1.5 cursor-pointer transition-colors"
              title="Copy raw text"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
