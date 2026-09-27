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
  <div className="border border-hairline p-6 text-center">
    <div className={`flex items-center justify-center gap-2 mb-2 text-[13px] font-bold ${variant === 'expected' ? 'text-muted' : 'text-signal-medium'}`}>
      {variant === 'expected' ? <Info className="w-4 h-4" strokeWidth={1.75} /> : <AlertTriangle className="w-4 h-4" strokeWidth={1.75} />}
      <span>MRZ extraction</span>
    </div>
    <p className="text-[11px] text-muted">
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
    <ScrollReveal className="border border-hairline p-5 space-y-5">
      <SectionHeading
        level="h3"
        title="ICAO 9303 MRZ validation"
        icon={<Binary className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <span className={`badge-signal ${mrz.is_valid ? 'badge-low' : 'badge-critical'}`}>
            {mrz.is_valid ? 'All checksums valid' : 'Checksum mismatch'}
          </span>
        }
      />

      {/* Raw MRZ lines */}
      <div className="border-t border-b border-hairline py-3 space-y-2">
        <span className="label-eyebrow block mb-1">
          Format: {mrz.format} (2 lines x 44 chars)
        </span>
        <div className="figure text-[13px] sm:text-[14px] tracking-[0.15em] text-ink break-all select-all font-bold py-2 border-b border-hairline">
          {mrz.line1}
        </div>
        <div className="figure text-[13px] sm:text-[14px] tracking-[0.15em] text-ink break-all select-all font-bold py-2">
          {mrz.line2}
        </div>
      </div>

      {/* Checksums matrix */}
      <div>
        <h4 className="label-eyebrow mb-3">
          ICAO 9303 7-3-1 checksum matrix
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
          {mrz.checksums.map((cs, idx) => {
            const isValid = cs.valid;
            return (
              <div
                key={idx}
                className="rule-row"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {isValid ? (
                    <CheckCircle2 className="w-4 h-4 text-signal-low shrink-0" strokeWidth={1.75} />
                  ) : (
                    <XCircle className="w-4 h-4 text-signal-critical shrink-0" strokeWidth={1.75} />
                  )}
                  <div className="min-w-0">
                    <span className="text-[12px] font-bold text-ink block">
                      {cs.field}
                    </span>
                    <span className="text-[10px] figure text-muted">
                      Found: '{cs.check_digit}' | Calc: '{cs.calculated_check_digit}'
                    </span>
                  </div>
                </div>

                <span className={`badge-signal shrink-0 ${isValid ? 'badge-low' : 'badge-critical'}`}>
                  {isValid ? 'MATCH' : 'FAIL'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Document rules engine summary, if available */}
      {validation && (
        <div className="pt-3 border-t border-hairline animate-fade-in">
          <div className="flex items-center justify-between text-[11px] text-muted mb-3">
            <span>Rules Engine Consistency:</span>
            <span className="figure">
              <strong className="text-signal-low">{validation.passed_count} Passed</strong> /{' '}
              <strong className={validation.failed_count > 0 ? 'text-signal-critical' : 'text-muted'}>
                {validation.failed_count} Failed
              </strong>
            </span>
          </div>

          <div>
            {validation.checks.map((check, idx) => (
              <div
                key={idx}
                className="text-[11px] py-2 border-t border-hairline flex items-center justify-between gap-3"
              >
                <span className={check.status === 'FAIL' ? 'text-signal-critical' : 'text-ink-soft'}>{check.explanation}</span>
                <span className={`badge-signal shrink-0 ${
                  check.status === 'FAIL' ? 'badge-critical' : check.status === 'NOT_APPLICABLE' ? 'badge-neutral' : 'badge-low'
                }`}>
                  {check.status === 'NOT_APPLICABLE' ? 'N/A' : check.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </ScrollReveal>
  );
};
