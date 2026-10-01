import React, { useState, useRef } from 'react';
import { api } from '../services/api';
import { ProcessingPipeline, PipelineStage } from '../components/ProcessingPipeline';
import { SectionHeading } from '../components/SectionHeading';
import { ScrollReveal } from '../components/ScrollReveal';
import { validateImageFile } from '../utils/fileValidation';
import {
  UploadCloud,
  FileText,
  Camera,
  Play,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Layers,
  X,
  RefreshCw,
  Video,
  SlidersHorizontal,
  Flame
} from 'lucide-react';

interface ScreeningPageProps {
  onScreeningComplete: (caseId: string) => void;
}

const INITIAL_STAGES: PipelineStage[] = [
  { id: '1', name: 'Ingestion', status: 'pending' },
  { id: '2', name: 'OCR extraction', status: 'pending' },
  { id: '3', name: 'MRZ & rules', status: 'pending' },
  { id: '4', name: 'Tamper AI', status: 'pending' },
  { id: '5', name: 'Face verification', status: 'pending' },
  { id: '6', name: 'Risk engine', status: 'pending' },
  { id: '7', name: 'Case file', status: 'pending' },
];

export const ScreeningPage: React.FC<ScreeningPageProps> = ({ onScreeningComplete }) => {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [liveFaceFile, setLiveFaceFile] = useState<File | null>(null);
  const [liveFacePreview, setLiveFacePreview] = useState<string | null>(null);
  const [faceError, setFaceError] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const [documentType, setDocumentType] = useState('Passport');
  const [country, setCountry] = useState('REPUBLIC OF UTOPIA');

  const [isProcessing, setIsProcessing] = useState(false);
  const [stages, setStages] = useState<PipelineStage[]>(INITIAL_STAGES);

  // Tampering options
  const [tamperOption, setTamperOption] = useState('photo_replaced');
  const [generatingSpecimen, setGeneratingSpecimen] = useState(false);

  // Live Webcam state
  const [showWebcam, setShowWebcam] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  const [isDraggingDoc, setIsDraggingDoc] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const faceInputRef = useRef<HTMLInputElement>(null);

  // Validates the file's actual content (magic bytes), not just its
  // extension or declared MIME type, before it ever reaches the pipeline --
  // see utils/fileValidation.ts for why that distinction matters here.
  const trySetDocFile = async (file: File) => {
    const result = await validateImageFile(file);
    if (!result.valid) {
      setDocError(result.reason || 'That file could not be used as a document image.');
      return;
    }
    setDocError(null);
    setDocFile(file);
    setDocPreview(URL.createObjectURL(file));
  };

  const trySetFaceFile = async (file: File) => {
    const result = await validateImageFile(file);
    if (!result.valid) {
      setFaceError(result.reason || 'That file could not be used as a face photo.');
      return;
    }
    setFaceError(null);
    setLiveFaceFile(file);
    setLiveFacePreview(URL.createObjectURL(file));
  };

  const handleDocChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same (or a corrected) file
    if (file) trySetDocFile(file);
  };

  const handleDocDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingDoc(false);
    const file = e.dataTransfer.files?.[0];
    if (file) trySetDocFile(file);
  };

  const handleFaceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) trySetFaceFile(file);
  };

  // Webcam Controls
  const startWebcam = async () => {
    try {
      setShowWebcam(true);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      });
      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err: any) {
      alert(`Webcam access error: ${err.message || 'Camera unavailable. Please upload a photo or use auto-simulation.'}`);
      setShowWebcam(false);
    }
  };

  const stopWebcam = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    setShowWebcam(false);
  };

  const captureWebcamSnapshot = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], 'live_webcam_capture.jpg', { type: 'image/jpeg' });
        setLiveFaceFile(file);
        setLiveFacePreview(URL.createObjectURL(file));
      }
      stopWebcam();
    }, 'image/jpeg', 0.95);
  };

  const updateStage = (index: number, status: PipelineStage['status'], latency?: number, detail?: string) => {
    setStages((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], status, latencyMs: latency, detail };
      return next;
    });
  };

  // Generate synthetic specimen directly
  const handleGenerateSpecimen = async (mode: string) => {
    try {
      setGeneratingSpecimen(true);
      const res = await api.generateSpecimenDoc({
        mode,
        surname: mode === 'photo_replaced' ? 'DOE' : 'KAUL',
        given_names: mode === 'photo_replaced' ? 'JOHN' : 'ARIHANT',
        doc_number: mode === 'mrz_tampered' ? 'P8892144' : 'X1234567',
        country_name: country
      });

      // Fetch the generated specimen blob so it can be screened as a real File upload
      const imgRes = await fetch(res.url);
      const blob = await imgRes.blob();
      const file = new File([blob], res.filename, { type: 'image/jpeg' });

      setDocFile(file);
      setDocPreview(res.url);
      setDocError(null);
    } catch (err: any) {
      setPipelineError(`Specimen generator error: ${err.message}`);
    } finally {
      setGeneratingSpecimen(false);
    }
  };

  // Run full staged screening pipeline
  const handleStartScreening = async () => {
    if (!docFile) {
      setDocError('Please upload or generate a document first.');
      return;
    }

    // Tracks which stage was in-flight so a failure can mark that exact
    // node red instead of leaving it spinning forever -- see
    // ProcessingPipeline's 'error' status.
    let currentStage = 0;

    try {
      setPipelineError(null);
      setIsProcessing(true);
      setStages(INITIAL_STAGES.map((s) => ({ ...s, status: 'pending', latencyMs: undefined })));

      // Step 1: Upload
      currentStage = 0;
      updateStage(0, 'running');
      const t0 = performance.now();
      const uploadRes = await api.uploadScreeningDocument(docFile, documentType, country);
      const caseId = uploadRes.case_id;
      updateStage(0, 'completed', performance.now() - t0, `Case #${uploadRes.case_number} registered`);

      // Step 2: OCR
      currentStage = 1;
      updateStage(1, 'running');
      const t1 = performance.now();
      const ocrRes = await api.runStepOCR(caseId);
      updateStage(1, 'completed', performance.now() - t1, `Extracted ${ocrRes.ocr_result.detected_lines?.length || 0} text lines`);

      // Step 3: MRZ & Rules
      currentStage = 2;
      updateStage(2, 'running');
      const t2 = performance.now();
      const valRes = await api.runStepValidate(caseId);
      const mrzValid = valRes.mrz_result?.is_valid;
      updateStage(2, 'completed', performance.now() - t2, mrzValid ? 'Checksums verified' : 'Checksum discrepancy');

      // Step 4: Tamper AI
      currentStage = 3;
      updateStage(3, 'running');
      const t3 = performance.now();
      const tamperRes = await api.runStepTamper(caseId);
      const risk = tamperRes.tamper_result.risk_level;
      updateStage(3, 'completed', performance.now() - t3, `${risk} tamper risk`);

      // Step 5: Face Verification
      currentStage = 4;
      updateStage(4, 'running');
      const t4 = performance.now();
      const faceRes = await api.runStepFace(caseId, liveFaceFile || undefined);
      updateStage(4, 'completed', performance.now() - t4, `${Math.round(faceRes.face_result.similarity * 100)}% match (${faceRes.face_result.status})`);

      // Step 6: Risk Aggregation
      currentStage = 5;
      updateStage(5, 'running');
      const t5 = performance.now();
      const riskRes = await api.runStepRisk(caseId);
      updateStage(5, 'completed', performance.now() - t5, `${Math.round(riskRes.risk_score)}/100 (${riskRes.risk_level})`);

      // Step 7: Finalize & Navigate
      currentStage = 6;
      updateStage(6, 'running');
      await new Promise((r) => setTimeout(r, 600));
      updateStage(6, 'completed', 100, 'Ready for officer inspection');

      // Transition to Case File
      setTimeout(() => {
        onScreeningComplete(caseId);
      }, 900);
    } catch (err: any) {
      updateStage(currentStage, 'error', undefined, err.message || 'Failed');
      setPipelineError(err.message || 'The screening pipeline failed unexpectedly.');
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-7 max-w-5xl mx-auto">
      <SectionHeading
        title="Document screening"
        description="Upload a physical document or generate a controlled forensic test specimen for AI inspection."
      />

      {/* Specimen generator -- a test/judging shortcut, not the primary task,
          so it's a plain utility row. */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 pb-5 border-b border-hairline animate-fade-in">
        <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.06em] text-muted shrink-0">
          <Sparkles className="w-3.5 h-3.5" strokeWidth={1.75} />
          Specimen generator
        </span>

        <div className="flex flex-wrap items-center gap-3 flex-1">
          <button
            type="button"
            onClick={() => handleGenerateSpecimen('genuine')}
            disabled={generatingSpecimen || isProcessing}
            className="btn-secondary px-3 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} />
            Generate genuine demo
          </button>

          <div className="flex items-center border border-ink">
            <select
              value={tamperOption}
              onChange={(e) => setTamperOption(e.target.value)}
              disabled={generatingSpecimen || isProcessing}
              className="bg-transparent text-ink px-3 py-1.5 text-[11px] focus:outline-none min-w-0 border-r border-hairline cursor-pointer"
              style={{ colorScheme: 'dark' }}
            >
              {/* The closed select picks up text-ink via inheritance, but a
                  native <option>'s own popup list doesn't reliably inherit
                  color/background from its parent <select> in Chromium --
                  it falls back to a washed-out system default, nearly
                  unreadable against this app's dark theme. Each option
                  needs its own explicit bg/text color, not inheritance. */}
              <option value="photo_replaced" className="bg-paper-dim text-ink">Photo replacement</option>
              <option value="mrz_tampered" className="bg-paper-dim text-ink">MRZ checksum corruption</option>
              <option value="altered_text" className="bg-paper-dim text-ink">Altered date/text</option>
              <option value="expired" className="bg-paper-dim text-ink">Expired document</option>
              <option value="stamp_manipulated" className="bg-paper-dim text-ink">Pasted stamp patch</option>
              <option value="brightness_manipulated" className="bg-paper-dim text-ink">Brightness hotspot</option>
              <option value="multiple_anomalies" className="bg-paper-dim text-ink">Multiple anomalies</option>
            </select>

            <button
              type="button"
              onClick={() => handleGenerateSpecimen(tamperOption)}
              disabled={generatingSpecimen || isProcessing}
              className="px-3 py-1.5 text-ink hover:text-signal-high text-[11px] transition-colors duration-200 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shrink-0 whitespace-nowrap"
              title="Generate tampered demo"
            >
              <Flame className="w-3.5 h-3.5" strokeWidth={1.75} />
              Generate
            </button>
          </div>
        </div>
      </div>

      {/* Two primary inputs, side by side */}
      <ScrollReveal className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Document Upload Area */}
        <div className="border border-hairline p-5 space-y-4">
          <SectionHeading level="h3" title="Document specimen" icon={<FileText className="w-4 h-4 text-accent" strokeWidth={1.75} />} />

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleDocChange}
            accept="image/jpeg,image/png,image/jpg"
            className="hidden"
            data-testid="doc-file-input"
          />

          <div
            data-testid="doc-dropzone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDraggingDoc(true); }}
            onDragLeave={() => setIsDraggingDoc(false)}
            onDrop={handleDocDrop}
            className={`border p-6 text-center cursor-pointer transition-colors ${
              isDraggingDoc ? 'border-accent bg-paper-dim' : 'border-hairline hover:border-ink'
            }`}
          >
            {docPreview ? (
              <div className="space-y-3">
                <img
                  src={docPreview}
                  alt="Document Preview"
                  className="photo-shadow max-h-52 mx-auto border border-hairline object-contain"
                />
                <span className="text-[11px] text-accent block">
                  Click to replace document image
                </span>
              </div>
            ) : (
              <div className="space-y-2 py-4">
                <UploadCloud className="w-7 h-7 text-muted mx-auto" strokeWidth={1.5} />
                <p className="text-[13px] text-ink font-bold">
                  Drop travel document here or click to browse
                </p>
                <p className="text-[11px] text-muted">
                  JPG, JPEG, PNG — normalized up to 1600px
                </p>
              </div>
            )}
          </div>

          {docError && (
            <div className="flex items-start gap-2 py-2 strip text-signal-critical animate-fade-in">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" strokeWidth={1.75} />
              <span className="flex-1">{docError}</span>
              <button type="button" onClick={() => setDocError(null)} className="shrink-0 cursor-pointer hover:opacity-70">
                <X className="w-3.5 h-3.5" strokeWidth={1.75} />
              </button>
            </div>
          )}

          {/* Document metadata */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label-eyebrow block mb-1.5">
                Document type
              </label>
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="field w-full cursor-pointer"
                style={{ colorScheme: 'dark' }}
              >
                <option value="Passport" className="bg-paper-dim text-ink">Passport (TD3)</option>
                <option value="National ID" className="bg-paper-dim text-ink">National ID (TD1)</option>
                <option value="Visa" className="bg-paper-dim text-ink">Travel Visa</option>
                <option value="Permit" className="bg-paper-dim text-ink">Permit (Residence/Work/Entry/Transit)</option>
              </select>
            </div>

            <div>
              <label className="label-eyebrow block mb-1.5">
                Issuing jurisdiction
              </label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="field w-full cursor-pointer"
                style={{ colorScheme: 'dark' }}
              >
                <option value="REPUBLIC OF UTOPIA" className="bg-paper-dim text-ink">Republic of Utopia (UTO)</option>
                <option value="DEMO STATE" className="bg-paper-dim text-ink">Demo State (DEM)</option>
                <option value="ATLANTIS FEDERATION" className="bg-paper-dim text-ink">Atlantis Federation (ATL)</option>
                <option value="INDIA" className="bg-paper-dim text-ink">India (IND)</option>
                <option value="UNITED KINGDOM" className="bg-paper-dim text-ink">United Kingdom (GBR)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Live Face Capture: Webcam in browser or File upload */}
        <div className="border border-hairline p-5 space-y-4">
          <SectionHeading
            level="h3"
            title="Live traveler face capture"
            icon={<Camera className="w-4 h-4 text-accent" strokeWidth={1.75} />}
            action={
              <span className="label-eyebrow">
                {liveFacePreview ? 'Loaded' : 'Auto-simulated if empty'}
              </span>
            }
          />

          <input
            type="file"
            ref={faceInputRef}
            onChange={handleFaceChange}
            accept="image/jpeg,image/png,image/jpg"
            className="hidden"
          />

          {/* In-browser webcam viewport, if active -- a real live photo, so
              it gets the same corner-registration-mark framing as the
              document image, not a rounded video card. */}
          {showWebcam ? (
            <div className="border border-hairline p-3 space-y-3 animate-fade-in">
              <div className="photo-shadow relative border border-hairline aspect-[4/3] max-h-64 mx-auto flex items-center justify-center overflow-hidden">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover mirror"
                />
                <div className="absolute inset-6 border border-accent pointer-events-none flex items-end justify-center pb-2">
                  <span className="text-[10px] uppercase tracking-[0.06em] text-accent bg-paper/80 px-2 py-0.5">
                    Align face in frame
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={captureWebcamSnapshot}
                  className="btn-primary px-4 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer"
                >
                  <Camera className="w-3.5 h-3.5" strokeWidth={1.75} />
                  <span>Snap photo</span>
                </button>

                <button
                  type="button"
                  onClick={stopWebcam}
                  className="btn-secondary px-3 py-1.5 text-[11px] cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              {liveFacePreview ? (
                <div className="photo-shadow w-20 h-20 border border-hairline shrink-0 overflow-hidden">
                  <img src={liveFacePreview} alt="Live face" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="w-20 h-20 border border-hairline flex items-center justify-center shrink-0">
                  <Camera className="w-5 h-5 text-muted" strokeWidth={1.5} />
                </div>
              )}

              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={startWebcam}
                    className="btn-secondary px-3 py-1.5 text-[11px] flex items-center gap-1.5 cursor-pointer"
                  >
                    <Video className="w-3.5 h-3.5" strokeWidth={1.75} />
                    <span>Capture from webcam</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => faceInputRef.current?.click()}
                    className="btn-secondary px-3 py-1.5 text-[11px] cursor-pointer"
                  >
                    {liveFacePreview ? 'Replace photo' : 'Upload file'}
                  </button>
                </div>
                <p className="text-[11px] text-muted">
                  Take a live camera picture or upload an image to test document portrait comparison.
                </p>
                {faceError && (
                  <div className="flex items-start gap-2 py-2 strip text-signal-critical animate-fade-in">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" strokeWidth={1.75} />
                    <span className="flex-1">{faceError}</span>
                    <button type="button" onClick={() => setFaceError(null)} className="shrink-0 cursor-pointer hover:opacity-70">
                      <X className="w-3.5 h-3.5" strokeWidth={1.75} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </ScrollReveal>

      {pipelineError && (
        <div className="flex items-start gap-2 py-3 strip text-[13px] text-signal-critical animate-fade-in">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.75} />
          <span className="flex-1">{pipelineError}</span>
          <button type="button" onClick={() => setPipelineError(null)} className="shrink-0 cursor-pointer hover:opacity-70">
            <X className="w-4 h-4" strokeWidth={1.75} />
          </button>
        </div>
      )}

      {/* Action button */}
      <button
        onClick={handleStartScreening}
        disabled={!docFile || isProcessing}
        className="btn-primary w-full text-[13px] py-3.5 flex items-center justify-center gap-2 cursor-pointer"
      >
        <Play className="w-4 h-4 fill-current" strokeWidth={1.75} />
        <span>Run full AI screening pipeline</span>
      </button>

      {/* Pipeline progress -- full width so the left-to-right flow has room */}
      <ScrollReveal className="border border-hairline p-5">
        <ProcessingPipeline
          stages={stages}
          title={isProcessing ? 'Active screening in-flight' : 'Screening pipeline'}
        />
      </ScrollReveal>
    </div>
  );
};
