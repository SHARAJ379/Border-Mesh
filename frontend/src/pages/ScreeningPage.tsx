import React, { useState, useRef } from 'react';
import { api } from '../services/api';
import { ProcessingPipeline, PipelineStage } from '../components/ProcessingPipeline';
import { SectionHeading } from '../components/SectionHeading';
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

      {/* Specimen Generator -- a test/judging shortcut, not the primary task,
          so it's a plain utility row rather than another bordered card. */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 pb-5 border-b border-graphite-800/60 animate-fade-in">
        <span className="flex items-center gap-1.5 text-xs text-graphite-500 shrink-0">
          <Sparkles className="w-3.5 h-3.5" />
          Specimen generator
        </span>

        <div className="flex flex-wrap items-center gap-2 flex-1">
          <button
            type="button"
            onClick={() => handleGenerateSpecimen('genuine')}
            disabled={generatingSpecimen || isProcessing}
            className="px-3 py-1.5 rounded-lg border border-graphite-800/80 hover:border-emerald-500/50 hover:text-emerald-300 hover:bg-emerald-950/20 text-xs text-graphite-300 transition-all duration-200 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Generate genuine demo
          </button>

          <div className="flex rounded-lg overflow-hidden border border-graphite-800/80 bg-graphite-950/60">
            <select
              value={tamperOption}
              onChange={(e) => setTamperOption(e.target.value)}
              disabled={generatingSpecimen || isProcessing}
              className="bg-transparent text-graphite-300 px-3 py-1.5 text-xs focus:outline-none focus:border-brass-500 min-w-0 border-r border-graphite-800/60 cursor-pointer"
            >
              <option value="photo_replaced" className="bg-graphite-900">Photo replacement</option>
              <option value="mrz_tampered" className="bg-graphite-900">MRZ checksum corruption</option>
              <option value="altered_text" className="bg-graphite-900">Altered date/text</option>
              <option value="expired" className="bg-graphite-900">Expired document</option>
              <option value="stamp_manipulated" className="bg-graphite-900">Pasted stamp patch</option>
              <option value="brightness_manipulated" className="bg-graphite-900">Brightness hotspot</option>
              <option value="multiple_anomalies" className="bg-graphite-900">Multiple anomalies</option>
            </select>

            <button
              type="button"
              onClick={() => handleGenerateSpecimen(tamperOption)}
              disabled={generatingSpecimen || isProcessing}
              className="px-3 py-1.5 text-graphite-300 hover:text-rose-300 hover:bg-rose-950/20 text-xs transition-all duration-200 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shrink-0 whitespace-nowrap"
              title="Generate tampered demo"
            >
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              Generate
            </button>
          </div>
        </div>
      </div>

      {/* Two primary inputs, side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Document Upload Area */}
        <div className="p-5 rounded-xl bg-graphite-900/90 border border-graphite-800/80 space-y-4 transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading level="h3" title="Document specimen" icon={<FileText className="w-4 h-4 text-brass-400" />} />

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
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
              isDraggingDoc
                ? 'border-brass-400 bg-brass-950/30'
                : docPreview
                ? 'border-brass-500/50 bg-graphite-950/80'
                : 'border-graphite-700 hover:border-brass-400/50 bg-graphite-950/40 hover:bg-graphite-950/60'
            }`}
          >
            {docPreview ? (
              <div className="space-y-3">
                <img
                  src={docPreview}
                  alt="Document Preview"
                  className="max-h-52 mx-auto rounded-lg border border-graphite-800/80 object-contain shadow-lg shadow-black/30"
                />
                <span className="text-xs text-brass-300 block">
                  Click to replace document image
                </span>
              </div>
            ) : (
              <div className="space-y-2 py-4">
                <UploadCloud className="w-8 h-8 text-graphite-500 mx-auto" />
                <p className="text-sm text-graphite-300 font-medium">
                  Drop travel document here or click to browse
                </p>
                <p className="text-xs text-graphite-500">
                  JPG, JPEG, PNG — normalized up to 1600px
                </p>
              </div>
            )}
          </div>

          {docError && (
            <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs animate-fade-in">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span className="flex-1">{docError}</span>
              <button type="button" onClick={() => setDocError(null)} className="shrink-0 cursor-pointer hover:text-rose-100">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Document Metadata Form */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-graphite-500 block mb-1">
                Document type
              </label>
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="w-full bg-graphite-950/80 border border-graphite-800/80 rounded-lg px-3 py-2 text-xs text-graphite-200 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
              >
                <option value="Passport">Passport (TD3)</option>
                <option value="National ID">National ID (TD1)</option>
                <option value="Visa">Travel Visa</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-graphite-500 block mb-1">
                Issuing jurisdiction
              </label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full bg-graphite-950/80 border border-graphite-800/80 rounded-lg px-3 py-2 text-xs text-graphite-200 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition-all"
              >
                <option value="REPUBLIC OF UTOPIA">Republic of Utopia (UTO)</option>
                <option value="DEMO STATE">Demo State (DEM)</option>
                <option value="ATLANTIS FEDERATION">Atlantis Federation (ATL)</option>
                <option value="INDIA">India (IND)</option>
                <option value="UNITED KINGDOM">United Kingdom (GBR)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Live Face Capture: Webcam in browser or File upload */}
        <div className="p-5 rounded-xl bg-graphite-900/90 border border-graphite-800/80 space-y-4 transition-all duration-300 hover:border-graphite-700/60">
          <SectionHeading
            level="h3"
            title="Live traveler face capture"
            icon={<Camera className="w-4 h-4 text-brass-400" />}
            action={
              <span className="text-xs text-graphite-500">
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

          {/* In-Browser Webcam Viewport if active */}
          {showWebcam ? (
            <div className="p-3 rounded-xl bg-graphite-950/60 border border-brass-500/50 space-y-3 animate-fade-in">
              <div className="relative rounded-lg overflow-hidden bg-black aspect-[4/3] max-h-64 mx-auto flex items-center justify-center">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover mirror"
                />
                {/* Facial positioning reticle */}
                <div className="absolute inset-0 border-2 border-brass-400/40 rounded-full m-8 pointer-events-none flex items-center justify-center">
                  <span className="text-[10px] text-brass-300 bg-black/60 px-2 py-0.5 rounded">
                    Align face in frame
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={captureWebcamSnapshot}
                  className="px-4 py-1.5 rounded-lg bg-brass-600 hover:bg-brass-500 active:bg-brass-700 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-md shadow-brass-950/40 transition-all duration-200"
                >
                  <Camera className="w-3.5 h-3.5" />
                  <span>Snap photo</span>
                </button>

                <button
                  type="button"
                  onClick={stopWebcam}
                  className="px-3 py-1.5 rounded-lg bg-graphite-800/80 hover:bg-graphite-700 text-graphite-300 text-xs cursor-pointer transition-all duration-200"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              {liveFacePreview ? (
                <div className="w-20 h-20 rounded-lg overflow-hidden bg-graphite-950 border border-graphite-700/60 shrink-0">
                  <img src={liveFacePreview} alt="Live face" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="w-20 h-20 rounded-lg bg-graphite-950 border border-dashed border-graphite-800/60 flex items-center justify-center shrink-0">
                  <Camera className="w-6 h-6 text-graphite-500" />
                </div>
              )}

              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={startWebcam}
                    className="px-3 py-1.5 rounded-lg bg-graphite-950/80 border border-graphite-700/60 hover:border-brass-500/50 hover:text-brass-300 hover:bg-graphite-900/60 text-xs text-graphite-300 font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer"
                  >
                    <Video className="w-3.5 h-3.5" />
                    <span>Capture from webcam</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => faceInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-graphite-950/80 border border-graphite-700/60 hover:border-graphite-500 hover:bg-graphite-900/60 text-xs text-graphite-300 transition-all duration-200 cursor-pointer"
                  >
                    {liveFacePreview ? 'Replace photo' : 'Upload file'}
                  </button>
                </div>
                <p className="text-xs text-graphite-500">
                  Take a live camera picture or upload an image to test document portrait comparison.
                </p>
                {faceError && (
                  <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs animate-fade-in">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span className="flex-1">{faceError}</span>
                    <button type="button" onClick={() => setFaceError(null)} className="shrink-0 cursor-pointer hover:text-rose-100">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {pipelineError && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-sm animate-fade-in">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1">{pipelineError}</span>
          <button type="button" onClick={() => setPipelineError(null)} className="shrink-0 cursor-pointer hover:text-rose-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Action Button */}
      <button
        onClick={handleStartScreening}
        disabled={!docFile || isProcessing}
        className="w-full bg-brass-600 hover:bg-brass-500 active:bg-brass-700 text-white font-semibold text-sm py-3.5 rounded-xl shadow-lg shadow-brass-950/40 transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brass-500/50"
      >
        <Play className="w-4 h-4 fill-current" />
        <span>Run full AI screening pipeline</span>
      </button>

      {/* Pipeline progress -- full width so the left-to-right flow has room */}
      <div className="p-5 rounded-xl bg-graphite-900/90 border border-graphite-800/80 transition-all duration-300 hover:border-graphite-700/60">
        <ProcessingPipeline
          stages={stages}
          title={isProcessing ? 'Active screening in-flight' : 'Screening pipeline'}
        />
      </div>
    </div>
  );
};
