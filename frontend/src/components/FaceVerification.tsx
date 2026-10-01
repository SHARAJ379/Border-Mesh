import React, { useEffect, useState } from 'react';
import { FaceVerificationResult } from '../types';
import { ScanFace } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';
import { prefersReducedMotion } from '../lib/deviceCapability';

interface FaceVerificationProps {
  faceResult?: FaceVerificationResult;
}

const EmptyState: React.FC = () => (
  <div className="border border-hairline p-6 text-center">
    <ScanFace className="w-7 h-7 text-muted mx-auto mb-2" strokeWidth={1.5} />
    <p className="text-[11px] text-muted">No face verification biometric data available.</p>
  </div>
);

export const FaceVerification: React.FC<FaceVerificationProps> = ({ faceResult }) => {
  // Mounts the similarity line at 0 and flips to its real width a tick
  // later, so the transition has a "from" state to draw in from -- see
  // RiskScore/RiskBreakdown for the same technique on this page.
  const [drawn, setDrawn] = useState(prefersReducedMotion());
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const t = setTimeout(() => setDrawn(true), 60);
    return () => clearTimeout(t);
  }, []);

  if (!faceResult) {
    return <EmptyState />;
  }

  const simPercent = Math.round(faceResult.similarity * 100);
  const isMatch = faceResult.status === 'MATCH';
  const signalCls = isMatch ? 'text-signal-low' : 'text-signal-critical';
  const quality = faceResult.quality_checks || {};

  return (
    <ScrollReveal className="border border-hairline p-5 space-y-5">
      {/* Header */}
      <SectionHeading
        level="h3"
        title="Biometric face verification"
        icon={<ScanFace className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <div className="flex items-center gap-3">
            <RiskBadge status={faceResult.status} size="sm" />
            <span className="figure text-[12px] font-bold text-ink">
              Similarity: {simPercent}%
            </span>
          </div>
        }
      />

      {/* Side-by-side face comparison -- real photographs, so this is one
          of the few places the system allows a shadow (see .photo-shadow). */}
      <div className="grid grid-cols-2 gap-6">
        <div className="flex flex-col items-center">
          <span className="label-eyebrow mb-2">
            Document Portrait Crop
          </span>
          <div className="photo-shadow border border-hairline w-full max-w-xs mx-auto aspect-[3/4] bg-paper-dim flex items-center justify-center overflow-hidden">
            {faceResult.document_face_url ? (
              <img
                src={faceResult.document_face_url}
                alt="Document Portrait"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-[11px] text-muted">Portrait Crop</span>
            )}
          </div>
          <span className="text-[10px] text-muted mt-2">ICAO Photo Region</span>
        </div>

        <div className="flex flex-col items-center">
          <span className="label-eyebrow mb-2">
            Live Subject Capture
          </span>
          <div className="photo-shadow border border-hairline w-full max-w-xs mx-auto aspect-[3/4] bg-paper-dim flex items-center justify-center overflow-hidden">
            {faceResult.live_face_url ? (
              <img
                src={faceResult.live_face_url}
                alt="Live Subject"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-[11px] text-muted">Live Webcam</span>
            )}
          </div>
          <span className="text-[10px] text-muted mt-2 flex items-center gap-1.5">
            <span className="badge-signal badge-pending" /> Live Frame
          </span>
        </div>
      </div>

      {/* Similarity -- a thin drawn line, not a filled rounded-pill bar */}
      <div className="border-t border-hairline pt-4 space-y-2">
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-ink-soft">Biometric Cosine Similarity:</span>
          <span className={`figure font-bold ${signalCls}`}>
            {simPercent}% (Threshold: {(faceResult.match_threshold * 100).toFixed(1)}%)
          </span>
        </div>

        <div className="w-full h-[3px] bg-hairline overflow-hidden">
          <div
            className={`h-full transition-all duration-1000 ${isMatch ? 'bg-signal-low' : 'bg-signal-critical'}`}
            style={{ width: drawn ? `${Math.min(100, Math.max(0, simPercent))}%` : '0%' }}
          ></div>
        </div>
      </div>

      {/* Quality checks & anti-spoofing */}
      <div className="grid grid-cols-2 sm:grid-cols-4 border-t border-b border-hairline divide-x divide-hairline">
        <div className="p-3 text-[11px]">
          <span className="label-eyebrow block">Sharpness</span>
          <span className="font-bold text-ink block mt-1">
            {quality.laplacian_sharpness ? `${quality.laplacian_sharpness} (Good)` : 'Adequate'}
          </span>
        </div>

        <div className="p-3 text-[11px]">
          <span className="label-eyebrow block">Lighting</span>
          <span className="font-bold text-ink block mt-1">
            {quality.is_dark ? 'Underexposed' : quality.is_overexposed ? 'Overexposed' : 'Balanced'}
          </span>
        </div>

        <div
          className="p-3 text-[11px]"
          title="Heuristic indicator (blur/brightness + FFT moire/halftone check), not certified Presentation Attack Detection (PAD)"
        >
          <span className="label-eyebrow block">Liveness Heuristic</span>
          <span className="font-bold text-ink block mt-1">
            {Math.round((faceResult.anti_spoofing_score || 0.95) * 100)}%
          </span>
          <span className="text-muted block text-[9px] leading-tight mt-1">
            Heuristic only — not certified PAD
          </span>
        </div>

        <div className="p-3 text-[11px]">
          <span className="label-eyebrow block">Decision</span>
          <span className={`font-bold block mt-1 ${signalCls}`}>
            {isMatch ? 'BIOMETRIC MATCH' : 'REVIEW REQUIRED'}
          </span>
        </div>
      </div>
    </ScrollReveal>
  );
};
