import React from 'react';
import { MRZResult, ValidationResult } from '../types';
import { Binary, CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-react';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

interface MRZValidatorProps {
  mrz?: MRZResult;
  validation?: ValidationResult;
  // The OCR-detected document type tag (analysis.ocr_result.fields.
  // document_type -- "AADHAAR", "PAN", "DRIVING_LICENSE", "VOTER_ID",
  // "VISA", "PASSPORT"), not the officer's upload-form document-type
  // selection: that's a user-entered label that can be wrong/mismatched,
  // while this is what the OCR pass actually identified the document as,
  // the same signal the backend's own NON_MRZ_DOCUMENT_TYPES gate
  // already keys off to decide whether to even attempt MRZ extraction.
  documentType?: string;
}

// Kept in sync with (but intentionally not imported from) DocumentRulesEngine
// .NON_MRZ_DOCUMENT_TYPES / TesseractOCRService.NON_MRZ_DOCUMENT_TYPES on the
// backend, matching this codebase's existing style of duplicating this exact
// tuple independently at each of its call sites rather than sharing one
// constant across the Python backend and this TypeScript frontend.
const NON_MRZ_DOCUMENT_TYPES = new Set(['AADHAAR', 'PAN', 'DRIVING_LICENSE', 'VOTER_ID', 'VISA']);

const EmptyState: React.FC<{ variant: 'expected' | 'missing' }> = ({ variant }) => (
  <div className="glass-panel rounded-xl p-6 text-center">
    <div className={`flex items-center justify-center gap-2 mb-2 text-sm font-semibold ${variant === 'expected' ? 'text-graphite-400' : 'text-amber-400'}`}>
      {variant === 'expected' ? <Info className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
      <span>MRZ extraction</span>
    </div>
    <p className="text-xs text-graphite-500">
      {variant === 'expected'
        ? 'Not applicable for this document type — no ICAO 9303 Machine Readable Zone by design.'
        : 'No Machine Readable Zone (MRZ) detected or parsed.'}
    </p>
  </div>
);

export const MRZValidator: React.FC<MRZValidatorProps> = ({ mrz, validation, documentType }) => {
  if (!mrz) {
    // Absent by design for a document type that never carries an ICAO 9303
    // MRZ -- not a failure, so it must not read as one. Defaults to the
    // warning state when documentType is unknown/undefined rather than
    // assuming inapplicability, since a genuinely MRZ-bearing document
    // (passport) with no detected MRZ is a real, worth-flagging problem.
    const isExpectedToBeAbsent = documentType ? NON_MRZ_DOCUMENT_TYPES.has(documentType.toUpperCase()) : false;

    return <EmptyState variant={isExpectedToBeAbsent ? 'expected' : 'missing'} />;
  }

  return (
    <ScrollReveal className="glass-panel rounded-xl p-5 space-y-5">
      <SectionHeading
        level="h3"
        title="ICAO 9303 MRZ validation"
        icon={<Binary className="w-4 h-4 text-graphite-500" />}
        action={
          <span
            className={`text-xs font-semibold px-3 py-1 rounded-full border ${
              mrz.is_valid
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40'
                : 'bg-rose-950/60 text-rose-300 border-rose-500/40'
            }`}
          >
            {mrz.is_valid ? 'All checksums valid' : 'Checksum mismatch'}
          </span>
        }
      />

      {/* Raw MRZ Lines Display */}
      <div className="p-4 rounded-lg bg-graphite-950/60 border border-graphite-800/80 space-y-2">
        <span className="text-[10px] text-graphite-400 block mb-1">
          Format: {mrz.format} (2 lines x 44 chars)
        </span>
        <div className="font-mono text-xs sm:text-sm tracking-widest text-graphite-200 break-all select-all font-semibold p-2 bg-graphite-900/50 rounded border border-graphite-800/60">
          {mrz.line1}
        </div>
        <div className="font-mono text-xs sm:text-sm tracking-widest text-graphite-200 break-all select-all font-semibold p-2 bg-graphite-900/50 rounded border border-graphite-800/60">
          {mrz.line2}
        </div>
      </div>

      {/* Checksums Matrix */}
      <div>
        <h4 className="text-xs font-medium text-graphite-400 mb-3">
          ICAO 9303 7-3-1 checksum matrix
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {mrz.checksums.map((cs, idx) => {
            const isValid = cs.valid;
            return (
              <div
                key={idx}
                className={`p-3 rounded-lg border flex items-center justify-between transition-colors ${
                  isValid
                    ? 'bg-graphite-950/60 border-graphite-800/80 text-graphite-200 hover:border-emerald-500/30'
                    : 'bg-rose-950/40 border-rose-500/40 text-rose-200 hover:border-rose-500/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  {isValid ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  )}
                  <div>
                    <span className="text-xs font-medium block">
                      {cs.field}
                    </span>
                    <span className="text-[10px] font-mono text-graphite-400">
                      Found: '{cs.check_digit}' | Calc: '{cs.calculated_check_digit}'
                    </span>
                  </div>
                </div>

                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    isValid
                      ? 'bg-emerald-950/80 text-emerald-300'
                      : 'bg-rose-950/80 text-rose-300'
                  }`}
                >
                  {isValid ? 'MATCH' : 'FAIL'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Document Rules Engine Summary if available */}
      {validation && (
        <div className="pt-3 border-t border-graphite-800/60 animate-fade-in">
          <div className="flex items-center justify-between text-xs text-graphite-400 mb-3">
            <span>Rules Engine Consistency:</span>
            <span>
              <strong className="text-emerald-400">{validation.passed_count} Passed</strong> /{' '}
              <strong className={validation.failed_count > 0 ? 'text-rose-400' : 'text-graphite-400'}>
                {validation.failed_count} Failed
              </strong>
            </span>
          </div>

          <div className="space-y-2">
            {validation.rules_detail.map((rule, idx) => (
              <div
                key={idx}
                className={`text-[11px] p-2.5 rounded-lg flex items-center justify-between transition-colors ${
                  rule.passed
                    ? 'bg-graphite-950/50 text-graphite-400 hover:bg-graphite-950/80'
                    : 'bg-rose-950/40 border border-rose-900/60 text-rose-300 hover:bg-rose-950/50'
                }`}
              >
                <span>{rule.explanation}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${rule.passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {rule.passed ? 'PASS' : 'FAIL'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </ScrollReveal>
  );
};
