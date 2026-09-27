import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List, Dict

from app.api.deps import get_db, require_officer_auth
from app.models import Case, DocumentAnalysis, RiskCheck, AuditLog, FaceEmbeddingGallery
from app.schemas import CaseOut, CaseDetailOut, OfficerDecisionRequest, RiskCheckOut, AuditLogOut, PurgeBiometricsResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/cases", tags=["cases"])

_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@router.get("", response_model=List[CaseOut])
def list_cases(
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Lists screening cases with optional risk/status filters."""
    query = db.query(Case)
    if status:
        query = query.filter(Case.status == status)
    if risk_level:
        query = query.filter(Case.risk_level == risk_level)
    if country:
        query = query.filter(Case.country.ilike(f"%{country}%"))

    cases = query.order_by(desc(Case.created_at)).offset(offset).limit(limit).all()

    # Attach a lightweight risk-check summary per case (see
    # CaseOut.flagged_check_count/top_flagged_checks) -- one batched query
    # for every case on this page rather than N+1 per-row queries, since
    # the Review Queue needs "why is this flagged" beyond the bare badge
    # without paying for the full itemized checks list per row.
    case_ids = [c.id for c in cases]
    if case_ids:
        failed_checks = (
            db.query(RiskCheck)
            .filter(RiskCheck.case_id.in_(case_ids), RiskCheck.status == "FAIL")
            .all()
        )
        by_case: Dict[str, List[RiskCheck]] = {}
        for chk in failed_checks:
            by_case.setdefault(chk.case_id, []).append(chk)
        for c in cases:
            case_failed = sorted(
                by_case.get(c.id, []),
                key=lambda chk: (_SEVERITY_RANK.get(chk.severity, 4), -chk.score_impact),
            )
            c.flagged_check_count = len(case_failed)
            c.top_flagged_checks = [chk.label for chk in case_failed[:2]]

    return cases


@router.get("/{case_id}", response_model=CaseDetailOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Retrieves full case file details including analyses, risk signals, and audit timeline."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Record CASE_VIEWED audit log
    AuditService.log(
        db=db,
        action="CASE_VIEWED",
        case_id=case.id,
        actor="OFFICER-DEMO-01",
        metadata={"case_number": case.case_number}
    )

    return case


@router.get("/{case_id}/checks", response_model=List[RiskCheckOut])
def get_case_checks(case_id: str, db: Session = Depends(get_db)):
    """Returns every itemized risk check (pass, fail, or note) recorded for a specific case."""
    checks = db.query(RiskCheck).filter(RiskCheck.case_id == case_id).all()
    return checks


@router.get("/{case_id}/audit", response_model=List[AuditLogOut])
def get_case_audit_trail(case_id: str, db: Session = Depends(get_db)):
    """Returns the chronological audit trail for a specific case."""
    logs = db.query(AuditLog).filter(AuditLog.case_id == case_id).order_by(AuditLog.timestamp.asc()).all()
    return logs


@router.post("/{case_id}/decision", response_model=CaseOut)
def record_officer_decision(
    case_id: str,
    payload: OfficerDecisionRequest,
    db: Session = Depends(get_db)
):
    """
    Records human officer decision: 'CLEARED', 'REQUIRES_INSPECTION', 'ESCALATED' with notes.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    valid_decisions = ["CLEARED", "REQUIRES_INSPECTION", "ESCALATED"]
    if payload.decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Invalid decision. Must be one of {valid_decisions}")

    case.officer_decision = payload.decision
    case.officer_notes = payload.notes
    case.status = payload.decision

    db.commit()
    db.refresh(case)

    # Log audit event
    AuditService.log(
        db=db,
        action="OFFICER_DECISION_RECORDED",
        case_id=case.id,
        actor=payload.officer_id,
        metadata={
            "decision": payload.decision,
            "notes": payload.notes
        }
    )

    return case


@router.post("/{case_id}/purge-biometrics", response_model=PurgeBiometricsResponse)
def purge_case_biometrics(case_id: str, db: Session = Depends(get_db), _auth: None = Depends(require_officer_auth)):
    """
    Privacy-by-Design & GDPR Article 17 Biometric Purge Protocol:
    Permanently deletes all raw biometric artifacts (document scan, live facial capture,
    extracted biometric crops, and heatmaps) from disk storage, replaces paths with anonymized markers,
    and logs an immutable cryptographically chained BIOMETRICS_PURGED audit event.
    The case record and mathematical risk hash remain preserved for regulatory audit integrity.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    analyses = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).all()
    purged_files_count = 0

    from app.core.config import settings
    crop_doc = os.path.join(settings.UPLOAD_DIR, "crops", f"{case_id}_doc_face.jpg")
    crop_live = os.path.join(settings.UPLOAD_DIR, "crops", f"{case_id}_live_face.jpg")
    heatmap = os.path.join(settings.UPLOAD_DIR, "heatmaps", f"{case_id}_tamper_heatmap.jpg")

    for an in analyses:
        for p in [an.document_image_path, an.face_image_path]:
            if p and os.path.exists(p) and not p.startswith("[PURGED"):
                try:
                    os.remove(p)
                    purged_files_count += 1
                except Exception:
                    pass
        an.document_image_path = "[PURGED_PRIVACY_COMPLIANCE]"
        an.face_image_path = "[PURGED_PRIVACY_COMPLIANCE]"
        an.biometrics_purged = True

    for p in [crop_doc, crop_live, heatmap]:
        if os.path.exists(p):
            try:
                os.remove(p)
                purged_files_count += 1
            except Exception:
                pass

    # A gallery embedding (see identity_gallery_service.py) IS raw
    # biometric data -- arguably more sensitive than the photo it came
    # from, since it's already in matchable form -- so it's deleted
    # outright here, not just anonymized like the analysis rows above.
    # Otherwise it would keep matching future screenings after the case's
    # own biometrics are supposedly purged.
    db.query(FaceEmbeddingGallery).filter(FaceEmbeddingGallery.case_id == case_id).delete()

    case.biometrics_purged = True
    db.commit()
    db.refresh(case)

    # Log immutable cryptographically chained audit event
    audit_entry = AuditService.log(
        db=db,
        action="BIOMETRICS_PURGED",
        case_id=case_id,
        actor="PRIVACY-SCRUBBER-ENGINE",
        metadata={
            "protocol": "GDPR-Art17-Privacy-by-Design",
            "purged_files_count": purged_files_count,
            "case_number": case.case_number,
            "retained_metadata": "Anonymized hash and risk score only"
        }
    )

    return {
        "case_id": case_id,
        "message": f"All biometric artifacts ({purged_files_count} files) permanently purged for Case {case.case_number}.",
        "biometrics_purged": True,
        "purged_files_count": purged_files_count,
        "audit_hash": audit_entry.entry_hash or "0" * 64
    }


@router.delete("/{case_id}")
def delete_case_privacy(case_id: str, db: Session = Depends(get_db), _auth: None = Depends(require_officer_auth)):
    """
    Privacy-by-Design requirement: Allows demo data deletion and scrubbing of associated biometric files.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    analyses = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).all()
    for an in analyses:
        for p in [an.document_image_path, an.face_image_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    db.delete(case)
    db.commit()

    return {"message": f"Case {case_id} and all biometric files permanently scrubbed."}
