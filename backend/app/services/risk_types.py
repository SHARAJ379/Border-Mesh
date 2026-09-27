"""
Shared vocabulary for the itemized "risk reasons" model every check-
producing module (rules_engine, tamper_service, face_service,
watchlist_service, risk_engine) builds its entries with.

Every risk-relevant finding in this app -- pass, fail, or a non-blocking
note -- is one of these, whether or not it ends up moving the score. This
replaces the old split where only FAILURES became a "signal" (module/
signal/severity/confidence/explanation/score_impact) and passing checks
either lived nowhere or were confined to one module's own result blob
(e.g. rules_engine's rules_detail, never reaching the unified risk view).

A plain dict, not a dataclass/pydantic model: every producer already
builds plain dicts (matching this codebase's existing style in
rules_engine.py/tamper_service.py/face_service.py), and the dicts flow
straight into app.schemas.RiskCheckOut for API serialization -- a second
in-process model here would just be a redundant translation step.
"""
from typing import Any, Dict, List, Optional, Union


class RiskCheckStatus:
    PASS = "PASS"
    FAIL = "FAIL"
    # Non-blocking annotation attached to context, not a verdict of its own
    # (e.g. the age-gap face-weight discount note). Never contributes score.
    INFO = "INFO"
    # The check does not apply to this document/case at all (e.g. an MRZ
    # rule on an Aadhaar card) -- distinct from PASS, which means "this WAS
    # verified and found clean." Conflating the two overstates what was
    # actually checked.
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RiskFactorKey:
    MRZ_VALIDATION = "MRZ_VALIDATION"
    TAMPER = "TAMPER"
    FACE = "FACE"
    CONSISTENCY = "CONSISTENCY"
    WATCHLIST = "WATCHLIST"
    IDENTITY = "IDENTITY"


def make_evidence(
    measured_value: Optional[Union[float, int, str, bool]] = None,
    threshold_value: Optional[Union[float, int, str, bool]] = None,
    unit: Optional[str] = None,
    region: Optional[List[int]] = None,
    region_source: Optional[str] = None,
    match: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Builds a RiskCheckEvidence dict, or None when every field is empty --
    callers that have no structured evidence for a given check (a pure
    presence/format check with nothing numeric to cite) should pass no
    evidence rather than an all-None placeholder."""
    if measured_value is None and threshold_value is None and region is None and match is None:
        return None
    return {
        "measured_value": measured_value,
        "threshold_value": threshold_value,
        "unit": unit,
        "region": region,
        "region_source": region_source,
        "match": match,
    }


def make_check(
    id: str,
    category: str,
    factor: str,
    label: str,
    status: str,
    confidence: float,
    explanation: str,
    severity: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
    score_impact: float = 0.0,
) -> Dict[str, Any]:
    """The one place a RiskCheckResult dict gets constructed, so every
    producer emits an identically-shaped entry regardless of which module
    it came from."""
    return {
        "id": id,
        "category": category,
        "factor": factor,
        "label": label,
        "status": status,
        "severity": severity,
        "confidence": confidence,
        "explanation": explanation,
        "evidence": evidence,
        "score_impact": score_impact if status == RiskCheckStatus.FAIL else 0.0,
    }
