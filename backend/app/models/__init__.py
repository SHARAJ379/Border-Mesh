import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, ForeignKey, Integer, Boolean, LargeBinary
from sqlalchemy.orm import relationship

from app.core.database import Base

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_number = Column(String(32), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    document_type = Column(String(64), default="Passport")
    document_number_hash = Column(String(64), index=True, nullable=True)
    country = Column(String(64), default="Unknown")
    
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(32), default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    recommendation = Column(String(128), default="CLEAR FOR ENTRY")
    status = Column(String(32), default="PROCESSING") # PROCESSING, LOW_RISK, MEDIUM_RISK, HIGH_RISK, CRITICAL, CLEARED, REQUIRES_REVIEW, ESCALATED
    
    officer_decision = Column(String(64), default="PENDING") # PENDING, CLEARED, REQUIRES_INSPECTION, ESCALATED
    officer_notes = Column(Text, nullable=True)
    biometrics_purged = Column(Boolean, default=False)

    # Relationships
    analyses = relationship("DocumentAnalysis", back_populates="case", cascade="all, delete-orphan")
    risk_checks = relationship("RiskCheck", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case", cascade="all, delete-orphan")
    gallery_entries = relationship("FaceEmbeddingGallery", back_populates="case", cascade="all, delete-orphan")


class DocumentAnalysis(Base):
    __tablename__ = "document_analysis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    document_type = Column(String(64), default="Passport")
    document_image_path = Column(String(255), nullable=True)
    face_image_path = Column(String(255), nullable=True)
    biometrics_purged = Column(Boolean, default=False)
    
    ocr_result = Column(JSON, nullable=True)
    mrz_result = Column(JSON, nullable=True)
    validation_result = Column(JSON, nullable=True)
    tamper_result = Column(JSON, nullable=True)
    face_result = Column(JSON, nullable=True)
    risk_breakdown = Column(JSON, nullable=True)
    
    processing_time_ms = Column(Float, default=0.0)

    case = relationship("Case", back_populates="analyses")


class RiskCheck(Base):
    """
    One itemized entry in the "risk reasons" model -- a single check that
    ran (a rule, a forensic heuristic, a biometric comparison, a watchlist
    query) and what it found, whether it passed, failed, or is a non-
    blocking note. Renamed from the old RiskSignal, which only ever stored
    FAILURES -- this table now holds every check regardless of outcome
    (status PASS/FAIL/INFO/NOT_APPLICABLE), so a clean case's evidentiary
    trail is "23 checks ran, all passed" rather than an empty table.
    """
    __tablename__ = "risk_checks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    # Stable machine key (e.g. "TAMPER_CNN_PORTRAIT_REGION") -- survives
    # re-runs of the same case, used for correlation/testing, never shown
    # raw in the UI (that's `label`).
    check_key = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)  # OCR, MRZ, VALIDATION, TAMPER, FACE, WATCHLIST, IDENTITY
    factor = Column(String(64), nullable=True)      # RiskFactorKey -- which weighted breakdown row this rolls into
    label = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="FAIL")  # PASS, FAIL, INFO, NOT_APPLICABLE
    severity = Column(String(32), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL -- only set when status == FAIL
    confidence = Column(Float, default=0.95)
    explanation = Column(Text, nullable=False)
    # The structured, non-prose half of this check's evidence (measured
    # value vs. threshold, unit, an optional region/region_source bounding
    # box, an optional fuzzy-match detail) -- see app.services.risk_types.
    evidence = Column(JSON, nullable=True)
    score_impact = Column(Float, default=0.0)

    case = relationship("Case", back_populates="risk_checks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    
    action = Column(String(128), nullable=False) # DOCUMENT_UPLOADED, OCR_COMPLETED, MRZ_VALIDATED, TAMPER_ANALYSIS_COMPLETED, FACE_VERIFIED, WATCHLIST_HIT, RISK_CALCULATED, CASE_VIEWED, OFFICER_DECISION_RECORDED, BIOMETRICS_PURGED
    actor = Column(String(128), default="OFFICER-DEMO-01")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    metadata_json = Column(JSON, nullable=True)

    previous_hash = Column(String(64), nullable=True) # SHA-256 hash of previous block (Blockchain Chain-of-Custody)
    entry_hash = Column(String(64), nullable=True)    # SHA-256 hash of current block

    case = relationship("Case", back_populates="audit_logs")


class BlockchainAnchor(Base):
    """
    On-demand, best-effort anchoring of the audit ledger's head hash (see
    AuditService -- the head hash already commits to the FULL chain history
    by construction, since each entry_hash embeds the previous one, so
    anchoring it is equivalent to anchoring a Merkle root) to a public
    blockchain testnet. This lets an independent verifier confirm a specific
    hash value existed at a specific, un-forgeable block time, without
    trusting this application's own database at all.

    Deliberately isolated from AuditService.log()/verify_chain(): this table
    and the service that writes to it (app.services.blockchain_anchor_service)
    are never called from that hot path, so a testnet RPC outage or an empty
    faucet wallet cannot affect the core, already-working local hash-chain
    audit trail.
    """
    __tablename__ = "blockchain_anchors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    head_hash = Column(String(64), nullable=False)
    total_records_at_anchor = Column(Integer, nullable=False)
    network = Column(String(64), nullable=False)  # e.g. "Ethereum Sepolia"
    chain_id = Column(Integer, nullable=False)
    tx_hash = Column(String(66), nullable=False, unique=True)
    block_number = Column(Integer, nullable=True)
    explorer_url = Column(String(255), nullable=False)
    anchored_by = Column(String(128), default="OFFICER-DEMO-01")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FaceEmbeddingGallery(Base):
    """
    Best-effort 1:N cross-case face-embedding gallery for duplicate-identity
    detection (see identity_gallery_service.py) -- built from each
    screening's LIVE facial capture (the actual physically-present person),
    not the document photo, since the question this answers is "has this
    real person been screened before under a different claimed identity."

    Denormalizes case_number/full_name/document_number_hash rather than
    joining back to Case/DocumentAnalysis on every 1:N lookup -- this table
    exists purely to be scanned on every new screening, and these are
    exactly the values a matched signal needs to display.

    Deleted (not anonymized) on both the biometric purge endpoint and full
    case deletion -- a stored embedding IS raw biometric data, arguably
    more sensitive than the photo it was derived from since it's already
    in matchable form, so it gets the same privacy-by-design treatment as
    every other biometric artifact in this app.
    """
    __tablename__ = "face_embedding_gallery"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    case_number = Column(String(32), nullable=False)
    full_name = Column(String(255), nullable=True)
    document_number_hash = Column(String(64), nullable=True)
    # Encrypted at rest (see app.core.encryption.encrypt_embedding/
    # decrypt_embedding, and identity_gallery_service.py, which is the only
    # code that ever reads/writes this column): a Fernet-encrypted JSON blob
    # of the 512-d L2-normalized VGGFace2 embedding, not the raw floats.
    # Was a plaintext JSON column -- this app has no migration tooling
    # (Base.metadata.create_all only creates missing tables), so an already-
    # populated DB volume needs recreating, not just upgrading, after this
    # change.
    embedding = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    case = relationship("Case", back_populates="gallery_entries")


class WatchlistEntry(Base):
    """
    DB-backed watchlist records, queried by WatchlistProvider on every
    screening's risk step (see app.services.watchlist_service). Replaces
    what used to be a hardcoded Python list baked into the provider class
    itself -- entries can now be added/removed/audited as real rows
    without a code change and redeploy, the same way every other piece of
    case data in this app lives in the DB rather than in source.

    This does NOT make the underlying data any less simulated: every
    seeded row (see scripts/seed_cases.py) is still fictional, and this
    table is not connected to, and has no path to become, any real
    government or law-enforcement watchlist -- see LABEL below and the
    DPDP compliance dashboard's own disclosure. What changes is only the
    storage/management model, not the data's authenticity.
    """
    __tablename__ = "watchlist_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    watchlist_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    document_number = Column(String(64), nullable=False, index=True)
    category = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    severity = Column(String(32), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Officer(Base):
    """
    Real per-officer account -- replaces the single shared OFFICER_API_KEY
    that used to gate the 4 most sensitive actions (and nothing else). Every
    authenticated request now resolves to a specific Officer row (see
    app.api.deps.get_current_officer), so AuditLog.actor can record who
    actually did something instead of a hardcoded "OFFICER-DEMO-01"
    string, and every data-reading route can require real login rather
    than being open to any unauthenticated request.

    `badge_id` doubles as the login username and the audit-trail actor
    value -- there is no separate internal ID vs. display-name split,
    matching how every pre-existing audit entry already recorded a human-
    readable actor string.
    """
    __tablename__ = "officers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    badge_id = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PolicySettings(Base):
    """
    Single-row table (id is always 1) holding the live-editable risk engine
    policy -- the Settings page used to let an officer drag these same
    weights/thresholds and click "Apply", but nothing was ever persisted or
    read back by the risk engine. Defaults to app.core.config.settings'
    static values the first time it's read; from then on, the risk engine
    reads its weights and thresholds from here instead.
    """
    __tablename__ = "policy_settings"

    id = Column(Integer, primary_key=True, default=1)
    weight_mrz = Column(Float, nullable=False)
    weight_tamper = Column(Float, nullable=False)
    weight_face = Column(Float, nullable=False)
    weight_consistency = Column(Float, nullable=False)
    weight_watchlist = Column(Float, nullable=False)
    threshold_low = Column(Float, nullable=False)
    threshold_medium = Column(Float, nullable=False)
    threshold_high = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
