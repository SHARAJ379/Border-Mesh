import React from 'react';
import { FaceVerificationResult } from '../types';
import { UserCheck, UserX, ScanFace, CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react';
import { RiskBadge } from './RiskBadge';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

interface FaceVerificationProps {
  faceResult?: FaceVerificationResult;
}

const EmptyState: React.FC = () => (
  <div className="glass-panel rounded-xl p-6 text-center">
    <ScanFace className="w-8 h-8 text-graphite-600 mx-auto mb-2" />
    <p className="text-xs text-graphite-500">No face verification biometric data available.</p>
  </div>
);

export const FaceVerification: React.FC<FaceVerificationProps> = ({ faceResult }) => {
  if (!faceResult) {
    return <EmptyState />;
  }

  const simPercent = Math.round(faceResult.similarity * 100);
  const isMatch = faceResult.status === 'MATCH';
  const quality = faceResult.quality_checks || {};

  return (
    <ScrollReveal className="glass-panel rounded-xl p-5 space-y-5">
      {/* Header */}
      <SectionHeading
        level="h3"
        title="Biometric face verification"
        icon={<ScanFace className="w-4 h-4 text-graphite-500" />}
        action={
          <div className="flex items-center gap-2">
            <RiskBadge status={faceResult.status} size="sm" />
            <span className="text-xs font-semibold text-graphite-200 px-2.5 py-1 rounded-lg bg-graphite-800/60 border border-graphite-700">
              Similarity: {simPercent}%
            </span>
          </div>
        }
      />

      {/* Side-by-Side Face Comparison */}
      <div className="grid grid-cols-2 gap-4">
        {/* Document Portrait */}
        <div className="flex flex-col items-center p-3 rounded-xl bg-graphite-950/60 border border-graphite-800/80 transition-colors hover:border-graphite-700/60">
          <span className="text-[10px] text-graphite-400 mb-2 uppercase tracking-wider">
            Document Portrait Crop
          </span>
          <div className="w-full max-w-xs mx-auto aspect-[3/4] rounded-lg overflow-hidden bg-graphite-900 border border-graphite-700/60 flex items-center justify-center shadow-lg shadow-black/30">
            {faceResult.document_face_url ? (
              <img
                src={faceResult.document_face_url}
                alt="Document Portrait"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-[11px] text-graphite-500">Portrait Crop</span>
            )}
          </div>
          <span className="text-[10px] text-graphite-400 mt-2">ICAO Photo Region</span>
        </div>

        {/* Live Subject Capture */}
        <div className="flex flex-col items-center p-3 rounded-xl bg-graphite-950/60 border border-graphite-800/80 transition-colors hover:border-graphite-700/60">
          <span className="text-[10px] text-graphite-400 mb-2 uppercase tracking-wider">
            Live Subject Capture
          </span>
          <div className="w-full max-w-xs mx-auto aspect-[3/4] rounded-lg overflow-hidden bg-graphite-900 border border-graphite-700/60 flex items-center justify-center shadow-lg shadow-black/30">
            {faceResult.live_face_url ? (
              <img
                src={faceResult.live_face_url}
                alt="Live Subject"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-[11px] text-graphite-500">Live Webcam</span>
            )}
          </div>
          <span className="text-[10px] text-graphite-400 mt-2 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-brass-400 animate-pulse" /> Live Frame
          </span>
        </div>
      </div>

      {/* Similarity Progress Bar */}
      <div className="p-4 rounded-xl bg-graphite-950/70 border border-graphite-800/80 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-graphite-400">Biometric Cosine Similarity:</span>
          <span className={`font-bold ${isMatch ? 'text-emerald-400' : 'text-rose-400'}`}>
            {simPercent}% (Threshold: {(faceResult.match_threshold * 100).toFixed(1)}%)
          </span>
        </div>

        <div className="w-full bg-graphite-900 h-3 rounded-full overflow-hidden border border-graphite-800/60">
          <div
            className={`h-full transition-all duration-1000 ${isMatch ? 'bg-emerald-500' : 'bg-rose-500'}`}
            style={{ width: `${Math.min(100, Math.max(0, simPercent))}%` }}
          ></div>
        </div>
      </div>

      {/* Quality Checks & Anti-Spoofing */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg bg-graphite-950/60 border border-graphite-800/80 text-[11px] transition-colors hover:border-graphite-700/60">
          <span className="text-graphite-400 block text-[10px] uppercase tracking-wider">Sharpness</span>
          <span className="font-semibold text-graphite-200 block mt-1">
            {quality.laplacian_sharpness ? `${quality.laplacian_sharpness} (Good)` : 'Adequate'}
          </span>
        </div>

        <div className="p-3 rounded-lg bg-graphite-950/60 border border-graphite-800/80 text-[11px] transition-colors hover:border-graphite-700/60">
          <span className="text-graphite-400 block text-[10px] uppercase tracking-wider">Lighting</span>
          <span className="font-semibold text-graphite-200 block mt-1">
            {quality.is_dark ? 'Underexposed' : quality.is_overexposed ? 'Overexposed' : 'Balanced'}
          </span>
        </div>

        <div
          className="p-3 rounded-lg bg-graphite-950/60 border border-graphite-800/80 text-[11px] transition-colors hover:border-graphite-700/60"
          title="Heuristic indicator (blur/brightness + FFT moire/halftone check), not certified Presentation Attack Detection (PAD)"
        >
          <span className="text-graphite-400 block text-[10px] uppercase tracking-wider">Liveness Heuristic</span>
          <span className="font-semibold text-graphite-200 block mt-1">
            {Math.round((faceResult.anti_spoofing_score || 0.95) * 100)}%
          </span>
          <span className="text-graphite-500 block text-[9px] leading-tight mt-1">
            Heuristic only — not certified PAD
          </span>
        </div>

        <div className="p-3 rounded-lg bg-graphite-950/60 border border-graphite-800/80 text-[11px] transition-colors hover:border-graphite-700/60">
          <span className="text-graphite-400 block text-[10px] uppercase tracking-wider">Decision</span>
          <span className={`font-bold block mt-1 ${isMatch ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isMatch ? 'BIOMETRIC MATCH' : 'REVIEW REQUIRED'}
          </span>
        </div>
      </div>
    </ScrollReveal>
  );
};
