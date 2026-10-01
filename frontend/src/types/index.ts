export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type CaseStatus = 'PROCESSING' | 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK' | 'CRITICAL' | 'CLEARED' | 'REQUIRES_REVIEW' | 'ESCALATED';
export type OfficerDecision = 'PENDING' | 'CLEARED' | 'REQUIRES_INSPECTION' | 'ESCALATED';

export interface AuditLog {
  id: string;
  case_id?: string;
  action: string;
  actor: string;
  timestamp: string;
  metadata_json?: Record<string, any>;
  previous_hash?: string;
  entry_hash?: string;
}

export interface ChainVerificationResult {
  valid: boolean;
  total_records: number;
  head_hash?: string;
  genesis_hash: string;
  verified_at: string;
  compromised_id?: string;
  reason?: string;
}

export interface BlockchainAnchor {
  id: string;
  head_hash: string;
  total_records_at_anchor: number;
  network: string;
  chain_id: number;
  tx_hash: string;
  block_number?: number;
  explorer_url: string;
  anchored_by: string;
  created_at: string;
}

export type RiskCheckStatus = 'PASS' | 'FAIL' | 'INFO' | 'NOT_APPLICABLE';
export type RiskFactorKey = 'MRZ_VALIDATION' | 'TAMPER' | 'FACE' | 'CONSISTENCY' | 'WATCHLIST' | 'IDENTITY';

export interface MatchEvidence {
  method: 'EXACT' | 'EDIT_DISTANCE' | 'SOUNDEX' | 'METAPHONE';
  query_token: string;
  matched_token: string;
  edit_distance?: number | null;
}

export interface RiskCheckEvidence {
  measured_value?: number | string | boolean | null;
  threshold_value?: number | string | boolean | null;
  unit?: string | null;
  /** [x, y, w, h] in the source image's own pixel coordinates. */
  region?: number[] | null;
  region_source?: 'document' | 'live_capture' | null;
  match?: MatchEvidence[] | null;
}

/**
 * One itemized entry in the "risk reasons" model -- a check that ran and
 * what it found, whether it passed, failed, or is a non-blocking note.
 * Renamed from the old RiskSignal, which only ever carried FAILURES; this
 * now covers PASS/FAIL/INFO/NOT_APPLICABLE, so a clean case's evidentiary
 * trail is "23 checks ran, all passed" rather than an empty list.
 */
export interface RiskCheck {
  id?: string;
  case_id?: string;
  check_key?: string;
  category: string; // OCR, MRZ, VALIDATION, TAMPER, FACE, WATCHLIST, IDENTITY
  factor?: RiskFactorKey | null;
  label: string;
  status: RiskCheckStatus;
  severity?: RiskLevel | null;
  confidence: number;
  explanation: string;
  evidence?: RiskCheckEvidence | null;
  score_impact: number;
}

export interface MRZChecksum {
  field: string;
  value: string;
  check_digit: string;
  calculated_check_digit: string;
  valid: boolean;
}

export interface MRZResult {
  format: string;
  line1: string;
  line2: string;
  line3?: string;
  document_type: string;
  country: string;
  surname: string;
  given_names: string;
  document_number: string;
  nationality: string;
  birth_date: string;
  sex: string;
  expiry_date: string;
  optional_data?: string;
  checksums: MRZChecksum[];
  is_valid: boolean;
}

export interface OCRResult {
  raw_text: string;
  fields: {
    full_name?: string;
    document_number?: string;
    country?: string;
    nationality?: string;
    date_of_birth?: string;
    date_of_issue?: string;
    date_of_expiry?: string;
    sex?: string;
    document_type?: string;
  };
  confidence: number;
  detected_lines: string[];
}

export interface TamperResult {
  tamper_risk: number;
  risk_level: RiskLevel;
  checks: RiskCheck[];
  heatmap_url?: string;
}

export interface FaceVerificationResult {
  similarity: number;
  status: 'MATCH' | 'REVIEW_REQUIRED' | 'NO_FACE_DETECTED' | 'MULTIPLE_FACES';
  document_face_url?: string;
  live_face_url?: string;
  quality_checks: Record<string, any>;
  anti_spoofing_score: number;
  match_threshold: number;
  checks?: RiskCheck[];
}

export interface ValidationResult {
  passed_count: number;
  failed_count: number;
  checks: RiskCheck[];
}

export interface RiskFactorContribution {
  factor: string;
  // null for the synthetic "Critical Signal Floor" row the backend adds when
  // a CRITICAL signal (e.g. a duplicate-identity match) forces the score up
  // regardless of the weighted math -- that row is a flat point adjustment,
  // not a proportional weighted category, so it has no weight/raw-risk %.
  weight: number | null;
  raw_risk: number | null;
  weighted_contribution: number;
}

export interface RiskEngineResult {
  risk_score: number;
  risk_level: RiskLevel;
  recommendation: string;
  breakdown: RiskFactorContribution[];
  checks: RiskCheck[];
  elapsed_ms?: number;
}

export interface DocumentAnalysis {
  id: string;
  document_type: string;
  document_image_path?: string;
  face_image_path?: string;
  biometrics_purged?: boolean;
  ocr_result?: OCRResult;
  mrz_result?: MRZResult;
  validation_result?: ValidationResult;
  tamper_result?: TamperResult;
  face_result?: FaceVerificationResult;
  risk_breakdown?: RiskFactorContribution[];
  processing_time_ms: number;
}

export interface CaseItem {
  id: string;
  case_number: string;
  created_at: string;
  updated_at: string;
  document_type: string;
  document_number_hash?: string;
  country: string;
  risk_score: number;
  risk_level: RiskLevel;
  recommendation: string;
  status: CaseStatus;
  officer_decision: OfficerDecision;
  officer_notes?: string;
  biometrics_purged?: boolean;
  /** Lightweight risk-check summary for list views -- see CaseDetail.risk_checks for the full itemized list. */
  flagged_check_count?: number;
  top_flagged_checks?: string[];
}

export interface CaseDetail extends CaseItem {
  analyses: DocumentAnalysis[];
  risk_checks: RiskCheck[];
  audit_logs: AuditLog[];
}

export interface PolicySettings {
  weight_mrz: number;
  weight_tamper: number;
  weight_face: number;
  weight_consistency: number;
  weight_watchlist: number;
  threshold_low: number;
  threshold_medium: number;
  threshold_high: number;
}

export interface DashboardStats {
  documents_screened: number;
  high_risk_cases: number;
  critical_cases: number;
  cases_requiring_review: number;
  cleared_cases: number;
  avg_processing_time_ms: number;
  risk_distribution: Record<RiskLevel, number>;
  latency_breakdown: Array<{ module: string; time_ms: number; sample_count: number }>;
  document_types: Record<string, number>;
  top_risk_reasons: Array<{ reason: string; count: number }>;
  recent_cases: CaseItem[];
}

export interface FieldDiff {
  field: string;
  label: string;
  v1_value: string | null;
  v2_value: string | null;
  changed: boolean;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface PortraitComparisonResult {
  similarity: number;
  status: 'SAME_PORTRAIT' | 'PORTRAIT_CHANGED' | 'NO_FACE_DETECTED';
  v1_portrait_url: string | null;
  v2_portrait_url: string | null;
  match_threshold: number;
  issue?: string;
}

export interface ChangeDetectionResult {
  comparison_id: string;
  identity: {
    surname: string;
    given_names: string;
    document_number: string;
    country: string;
  };
  v1: {
    label: string;
    document_image_url: string;
    mrz_checksum_valid: boolean;
    ocr_confidence: number;
  };
  v2: {
    label: string;
    document_image_url: string;
    mrz_checksum_valid: boolean;
    ocr_confidence: number;
  };
  portrait_comparison: PortraitComparisonResult;
  field_diffs: FieldDiff[];
  changed_field_count: number;
  changed_fields: string[];
}

export interface DpdpComplianceStatus {
  generated_at: string;
  encryption: {
    algorithm: string;
    applies_to: string[];
    using_default_demo_key: boolean;
  };
  identifier_hashing: {
    algorithm: string;
    field: string;
    total_cases: number;
    cases_with_hashed_identifier: number;
  };
  biometric_purge: {
    endpoint: string;
    total_cases: number;
    cases_purged: number;
    audit_events_logged: number;
  };
  audit_chain: {
    valid: boolean;
    total_records: number;
    reason: string;
  };
  access_control: {
    mechanism: string;
    authentication_required_for: string[];
    public_without_login: string[];
  };
  known_gaps: Array<{ control: string; gap: string }>;
}
