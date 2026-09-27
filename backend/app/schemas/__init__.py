from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict

# --- Audit Schemas ---
class AuditLogBase(BaseModel):
    action: str
    actor: str = "OFFICER-DEMO-01"
    metadata_json: Optional[Dict[str, Any]] = None

class AuditLogCreate(AuditLogBase):
    case_id: Optional[str] = None

class AuditLogOut(AuditLogBase):
    id: str
    case_id: Optional[str] = None
    timestamp: datetime
    previous_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChainVerificationOut(BaseModel):
    valid: bool
    total_records: int
    head_hash: Optional[str] = None
    genesis_hash: str
    verified_at: datetime
    compromised_id: Optional[str] = None
    reason: Optional[str] = None


class BlockchainAnchorOut(BaseModel):
    id: str
    head_hash: str
    total_records_at_anchor: int
    network: str
    chain_id: int
    tx_hash: str
    block_number: Optional[int] = None
    explorer_url: str
    anchored_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseAnchorProofOut(BaseModel):
    """
    Response for the public, unauthenticated case-anchor-proof endpoint --
    deliberately minimal. Must never carry anything beyond proof that a
    case's audit trail was (or wasn't) anchored: no risk score, name,
    document number, or any other case field. See
    AuditService.get_case_anchor_proof.
    """
    case_number: str
    case_found: bool
    chain_valid: bool
    anchored: bool
    anchor: Optional[BlockchainAnchorOut] = None
    message: str


class PurgeBiometricsResponse(BaseModel):
    case_id: str
    message: str
    biometrics_purged: bool
    purged_files_count: int
    audit_hash: str


# --- Risk Check Schemas (the itemized "risk reasons" model) ---
class MatchEvidenceOut(BaseModel):
    """How a fuzzy/phonetic string-matching check judged two tokens
    equivalent -- exposed so an officer can see WHY it matched, not just
    that it did."""
    method: str  # EXACT, EDIT_DISTANCE, SOUNDEX, METAPHONE
    query_token: str
    matched_token: str
    edit_distance: Optional[int] = None

class RiskCheckEvidenceOut(BaseModel):
    measured_value: Optional[Union[float, int, str, bool]] = None
    threshold_value: Optional[Union[float, int, str, bool]] = None
    unit: Optional[str] = None
    region: Optional[List[int]] = None  # [x, y, w, h] in the source image's own pixel coordinates
    region_source: Optional[str] = None  # "document" | "live_capture"
    match: Optional[List[MatchEvidenceOut]] = None

class RiskCheckOut(BaseModel):
    id: Optional[str] = None
    case_id: Optional[str] = None
    check_key: Optional[str] = None
    category: str  # OCR, MRZ, VALIDATION, TAMPER, FACE, WATCHLIST, IDENTITY
    factor: Optional[str] = None  # RiskFactorKey -- which weighted breakdown row this rolls into
    label: str
    status: str  # PASS, FAIL, INFO, NOT_APPLICABLE
    severity: Optional[str] = None  # LOW, MEDIUM, HIGH, CRITICAL -- only set when status == FAIL
    confidence: float
    explanation: str
    evidence: Optional[RiskCheckEvidenceOut] = None
    score_impact: float = 0.0

    model_config = ConfigDict(from_attributes=True)


# Note: the old OCRFieldItem/OCRResultOut/MRZChecksumDetail/MRZResultOut/
# RuleValidationItem/ValidationResultOut/TamperSignalItem/TamperResultOut/
# FaceVerificationOut/RiskEngineResult schemas were never actually wired as
# a response_model anywhere (confirmed by search) -- DocumentAnalysisOut's
# ocr_result/mrz_result/validation_result/tamper_result/face_result fields
# below have always been the loosely-typed Dict[str, Any] passthrough that
# actually serves the frontend. Removed as dead schema clutter rather than
# updated to match the new checks-based shape, since updating dead code
# only to keep it dead isn't worth the surface area.


# --- Full Risk Breakdown ---
class RiskFactorBreakdown(BaseModel):
    factor: str
    # None for either of the two synthetic flat-adjustment rows
    # risk_engine.py can add alongside the 5 weighted factors: "Critical
    # Signal Floor" (a CRITICAL-severity signal -- an expired document, a
    # watchlist hit, a CRITICAL tamper verdict -- forces the score up
    # regardless of the weighted math) and "Cross-Case Duplicate Identity"
    # (a gallery match, HIGH severity, added as a flat unweighted point
    # amount rather than a floor -- see risk_engine.py for why). Neither row
    # has a proportional weight or raw-risk percentage of its own, only a
    # flat point adjustment (see weighted_contribution).
    weight: Optional[float] = None
    raw_risk: Optional[float] = None
    weighted_contribution: float
    # top_signals: List[str] -- REMOVED. Superseded by RiskCheckOut.factor:
    # the frontend groups the full checks list by factor key directly
    # instead of re-matching a truncated name list back to it by string
    # equality.


# --- Case Schemas ---
class CaseBase(BaseModel):
    document_type: str = "Passport"
    country: str = "Unknown"

class CaseCreate(CaseBase):
    case_number: Optional[str] = None

class OfficerDecisionRequest(BaseModel):
    decision: str # CLEARED, REQUIRES_INSPECTION, ESCALATED
    notes: Optional[str] = None
    officer_id: str = "OFFICER-DEMO-01"

class DocumentAnalysisOut(BaseModel):
    id: str
    document_type: str
    document_image_path: Optional[str] = None
    face_image_path: Optional[str] = None
    biometrics_purged: bool = False
    ocr_result: Optional[Dict[str, Any]] = None
    mrz_result: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    tamper_result: Optional[Dict[str, Any]] = None
    face_result: Optional[Dict[str, Any]] = None
    risk_breakdown: Optional[List[RiskFactorBreakdown]] = None
    processing_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)

class CaseOut(BaseModel):
    id: str
    case_number: str
    created_at: datetime
    updated_at: datetime
    document_type: str
    document_number_hash: Optional[str] = None
    country: str
    risk_score: float
    risk_level: str
    recommendation: str
    status: str
    officer_decision: str
    officer_notes: Optional[str] = None
    biometrics_purged: bool = False
    # Lightweight risk-check summary for list views (Review Queue) that
    # can't afford the full itemized checks list per row -- computed
    # server-side in cases.py's list_cases. Full detail lives in
    # CaseDetailOut.risk_checks.
    flagged_check_count: int = 0
    top_flagged_checks: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class CaseDetailOut(CaseOut):
    analyses: List[DocumentAnalysisOut] = []
    risk_checks: List[RiskCheckOut] = []
    audit_logs: List[AuditLogOut] = []


# --- Dashboard Stats Schemas ---
class DashboardStatsOut(BaseModel):
    documents_screened: int
    high_risk_cases: int
    critical_cases: int
    cases_requiring_review: int
    cleared_cases: int
    avg_processing_time_ms: float
    risk_distribution: Dict[str, int] # {"LOW": 12, "MEDIUM": 5, "HIGH": 4, "CRITICAL": 2}
    latency_breakdown: List[Dict[str, Any]] # [{"module": "OCR Extraction", "time_ms": 512.3, "sample_count": 41}, ...]
    document_types: Dict[str, int]
    top_risk_reasons: List[Dict[str, Any]]
    recent_cases: List[CaseOut]
