from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_officer
from app.core.config import settings
from app.models import Case, AuditLog, Officer
from app.services.audit_service import AuditService

router = APIRouter(prefix="/compliance", tags=["compliance"])

# The default demo key baked into config.py -- compared against below so the
# dashboard can honestly report whether a deployment is still running on the
# out-of-the-box key (a real, if unremarkable, security-posture fact) without
# ever exposing the key's actual value.
_DEFAULT_DEMO_ENCRYPTION_KEY = "GIdlRJ4jkqQin6vgx8uDRtGQ2EXnGhbd_jIXGEjS848="

# Every entry here names a control this app genuinely has code for (see the
# docstring of dpdp_compliance_status below). This is deliberately NOT a
# generic list of every DPDP Act obligation -- principles with no
# corresponding implementation (consent management, a Data Principal rights
# portal, breach notification to the Data Protection Board, cross-border
# transfer safeguards, Significant Data Fiduciary obligations) are omitted
# rather than claimed, and are called out explicitly on the frontend instead.


@router.get("/dpdp-status")
def dpdp_compliance_status(db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Read-only status view mapping this app's ALREADY-IMPLEMENTED privacy/
    security controls to the DPDP Act 2023 principles they actually serve --
    no new write path, no new data model, every figure below is a live
    query or a direct call into the same service the rest of the app already
    uses (AuditService.verify_chain, the same function /api/audit/verify
    calls). This is a presentation layer over existing state, not a new
    compliance engine, and it is not a legal certification of compliance --
    see the frontend's own disclaimer.
    """
    total_cases = db.query(Case).count()
    hashed_cases = db.query(Case).filter(Case.document_number_hash.isnot(None)).count()
    purged_cases = db.query(Case).filter(Case.biometrics_purged.is_(True)).count()
    purge_events = db.query(AuditLog).filter(AuditLog.action == "BIOMETRICS_PURGED").count()
    chain = AuditService.verify_chain(db)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "encryption": {
            "algorithm": "Fernet (AES-128-CBC + HMAC-SHA256, authenticated)",
            "applies_to": [
                "document scans",
                "live face captures",
                "extracted face crops",
                "tamper-analysis heatmaps",
                "cross-case face embeddings",
            ],
            "using_default_demo_key": settings.BIOMETRIC_ENCRYPTION_KEY == _DEFAULT_DEMO_ENCRYPTION_KEY,
        },
        "identifier_hashing": {
            "algorithm": "SHA-256",
            "field": "document_number_hash",
            "total_cases": total_cases,
            "cases_with_hashed_identifier": hashed_cases,
        },
        "biometric_purge": {
            "endpoint": "POST /api/cases/{case_id}/purge-biometrics",
            "total_cases": total_cases,
            "cases_purged": purged_cases,
            "audit_events_logged": purge_events,
        },
        "audit_chain": {
            "valid": chain["valid"],
            "total_records": chain["total_records"],
            "reason": chain["reason"],
        },
        "access_control": {
            "mechanism": "Per-officer login (JWT bearer token, see /api/auth/login)",
            "authentication_required_for": [
                "every case-data route (list, detail, checks, audit trail)",
                "the /uploads image-serving route",
                "every screening-pipeline step and demo scenario",
                "case deletion",
                "biometric purge",
                "policy settings update",
                "blockchain anchoring",
            ],
            "public_without_login": [
                "GET /api/audit/anchor-proof/{case_number} (the standalone /verify page)",
                "GET /api/audit/anchors (already public on-chain once anchored)",
                "GET /api/health",
            ],
        },
        "known_gaps": [
            {
                "control": "Case deletion",
                "gap": (
                    "Deleting a case removes its audit_logs rows via cascade with no "
                    "chain-repair step, permanently breaking /api/audit/verify for the "
                    "whole ledger from that point forward -- the only recovery is "
                    "truncating the audit log (see KNOWN_LIMITATIONS.md #12)."
                ),
            },
        ],
    }
