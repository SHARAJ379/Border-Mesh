from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.api.deps import get_db, get_current_officer
from app.models import Case, DocumentAnalysis, RiskCheck, AuditLog, Officer
from app.schemas import DashboardStatsOut, CaseOut
from app.services.policy_service import get_policy

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# (start action, end action, display label) -- both the manual screening flow
# (screening.py) and the 1-click demo scenarios (demo.py) log the same action
# names at the same pipeline boundaries, so a single query covers every case.
LATENCY_STEP_SEQUENCE = [
    ("DOCUMENT_UPLOADED", "OCR_COMPLETED", "OCR Extraction"),
    ("OCR_COMPLETED", "MRZ_VALIDATED", "MRZ Checksums"),
    ("MRZ_VALIDATED", "TAMPER_ANALYSIS_COMPLETED", "Tamper AI (ELA)"),
    ("TAMPER_ANALYSIS_COMPLETED", "FACE_VERIFIED", "Face Verification"),
    ("FACE_VERIFIED", "RISK_CALCULATED", "Risk Engine"),
]


def _compute_latency_breakdown(db: Session):
    """
    Real per-module latency, averaged across every case's own audit trail
    timestamps -- replaces a previous hardcoded, never-measured array. Each
    entry's average is computed only from cases where both boundary actions
    were actually logged, so a case that failed partway through doesn't
    silently corrupt other modules' averages with a missing endpoint.
    """
    relevant_actions = {a for pair in LATENCY_STEP_SEQUENCE for a in pair[:2]}
    rows = (
        db.query(AuditLog.case_id, AuditLog.action, AuditLog.timestamp)
        .filter(AuditLog.action.in_(relevant_actions))
        .all()
    )
    by_case: dict = {}
    for case_id, action, ts in rows:
        by_case.setdefault(case_id, {})[action] = ts

    # scripts/seed_cases.py backfills demo history by writing all of a case's
    # audit entries in one tight loop with no real work between them, so
    # their timestamps land only microseconds apart -- not a real
    # measurement. Rather than guess a minimum-plausible-duration cutoff
    # (real steps can legitimately be a few milliseconds too -- risk
    # aggregation is pure arithmetic), use a precise structural signal
    # instead: the seed script is the only writer that never logs
    # FACE_VERIFIED, so its absence identifies a backfilled case exactly.
    breakdown = []
    for start_action, end_action, label in LATENCY_STEP_SEQUENCE:
        samples = []
        for actions in by_case.values():
            if "FACE_VERIFIED" not in actions:
                continue
            if start_action in actions and end_action in actions:
                delta_ms = (actions[end_action] - actions[start_action]).total_seconds() * 1000.0
                if delta_ms >= 0:
                    samples.append(delta_ms)
        avg_ms = sum(samples) / len(samples) if samples else 0.0
        breakdown.append({"module": label, "time_ms": round(avg_ms, 1), "sample_count": len(samples)})
    return breakdown

@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """Computes real-time metrics, risk distributions, and operational queue stats."""
    total_screened = db.query(Case).count()
    
    high_risk = db.query(Case).filter(Case.risk_level == "HIGH").count()
    critical = db.query(Case).filter(Case.risk_level == "CRITICAL").count()
    cleared = db.query(Case).filter(Case.officer_decision == "CLEARED").count()
    
    # "Requiring review" means "not clearly LOW risk" -- this must track the
    # live, officer-editable threshold_low policy (Settings page), the same
    # cutoff risk_engine.py itself uses to classify LOW vs MEDIUM, rather
    # than a hardcoded value that silently drifts out of sync the moment an
    # officer changes the policy.
    requiring_review = db.query(Case).filter(
        Case.officer_decision == "PENDING",
        Case.risk_score >= get_policy(db).threshold_low
    ).count()

    # Risk Distribution
    risk_dist = {
        "LOW": db.query(Case).filter(Case.risk_level == "LOW").count(),
        "MEDIUM": db.query(Case).filter(Case.risk_level == "MEDIUM").count(),
        "HIGH": high_risk,
        "CRITICAL": critical
    }

    # Document Types
    doc_type_counts = {}
    doc_types = db.query(Case.document_type, func.count(Case.id)).group_by(Case.document_type).all()
    for dt, count in doc_types:
        doc_type_counts[dt or "Passport"] = count

    # Average processing time
    avg_time = db.query(func.avg(DocumentAnalysis.processing_time_ms)).scalar() or 0.0

    latency_breakdown = _compute_latency_breakdown(db)

    # Top risk reasons -- only FAIL-status checks are a "reason a document
    # was flagged"; once PASS/INFO/NOT_APPLICABLE rows also live in this
    # table (see RiskCheck), counting them here would bury real risk
    # reasons under "MRZ Composite Checksum" appearing on every clean case.
    top_checks = (
        db.query(RiskCheck.label, func.count(RiskCheck.id).label("count"))
        .filter(RiskCheck.status == "FAIL")
        .group_by(RiskCheck.label)
        .order_by(desc("count"))
        .limit(6)
        .all()
    )
    top_risk_reasons = [{"reason": s[0], "count": s[1]} for s in top_checks]

    # Recent cases
    recent_cases = db.query(Case).order_by(desc(Case.created_at)).limit(10).all()

    return {
        "documents_screened": total_screened,
        "high_risk_cases": high_risk,
        "critical_cases": critical,
        "cases_requiring_review": requiring_review,
        "cleared_cases": cleared,
        "avg_processing_time_ms": round(float(avg_time), 1),
        "risk_distribution": risk_dist,
        "latency_breakdown": latency_breakdown,
        "document_types": doc_type_counts,
        "top_risk_reasons": top_risk_reasons,
        "recent_cases": recent_cases
    }
