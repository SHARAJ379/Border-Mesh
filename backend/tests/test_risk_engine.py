from datetime import date
from app.services.risk_engine import RiskEngine


def test_risk_engine_low_risk():
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.08, "checks": []}
    face_data = {"similarity": 0.92, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    assert result["risk_level"] == "LOW"
    assert result["risk_score"] < 25.0
    assert "CLEAR FOR ENTRY" in result["recommendation"]
    assert len(result["breakdown"]) == 5
    # Even a clean, low-risk case must show WHY it's clean, not silence --
    # a PASS check for watchlist screening is always emitted regardless of
    # a match.
    assert any(c["id"] == "WATCHLIST_SCREENING" and c["status"] == "PASS" for c in result["checks"])

def test_risk_engine_critical_tampering_and_watchlist():
    engine = RiskEngine()
    validation_data = {
        "passed_count": 1,
        "failed_count": 3,
        "checks": [
            {"id": "MRZ_CHECKSUM", "category": "MRZ", "factor": "MRZ_VALIDATION", "label": "MRZ Checksum Mismatch",
             "status": "FAIL", "severity": "HIGH", "confidence": 0.9, "score_impact": 40.0, "explanation": "Corrupted check digit.", "evidence": None},
            {"id": "DOCUMENT_EXPIRATION", "category": "VALIDATION", "factor": "MRZ_VALIDATION", "label": "Document Expired",
             "status": "FAIL", "severity": "CRITICAL", "confidence": 0.99, "score_impact": 45.0, "explanation": "Document expired.", "evidence": None},
        ]
    }
    tamper_data = {
        "tamper_risk": 0.95,
        "checks": [
            {"id": "TAMPER_PHOTO_BOUNDARY_ANOMALY", "category": "TAMPER", "factor": "TAMPER",
             "label": "Forensic Anomaly (Photo Boundary Anomaly)", "status": "FAIL", "severity": "CRITICAL",
             "confidence": 0.95, "score_impact": 17.1, "explanation": "Photo splicing detected.", "evidence": None},
        ]
    }
    face_data = {
        "similarity": 0.15,
        "status": "REVIEW_REQUIRED",
        "checks": [
            {"id": "FACE_BIOMETRIC_MATCH", "category": "FACE", "factor": "FACE", "label": "Biometric Face Mismatch",
             "status": "FAIL", "severity": "HIGH", "confidence": 0.85, "score_impact": 25.0, "explanation": "Face mismatch.", "evidence": None},
        ]
    }
    watchlist_match = {
        "matched": True,
        "entry": {"watchlist_id": "WL-001", "category": "Demo Flag", "severity": "CRITICAL"},
        "explanation": "Simulated match."
    }

    result = engine.calculate(
        mrz_data={"is_valid": False},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=watchlist_match
    )

    assert result["risk_level"] == "CRITICAL"
    assert result["risk_score"] >= 75.0
    assert "SUPERVISOR ESCALATION" in result["recommendation"]


def test_risk_engine_isolated_critical_signal_floors_to_high():
    """
    An expired document (or any CRITICAL rule violation) is a definitive, legal
    fact -- not a probabilistic risk that an unrelated clean face match or low
    tamper score should be able to dilute into a LOW/MEDIUM weighted average.
    Regression guard for exactly that: otherwise-clean signals plus one
    isolated CRITICAL validation signal must still floor to at least HIGH.
    """
    engine = RiskEngine()
    validation_data = {
        "passed_count": 4,
        "failed_count": 1,
        "checks": [
            {"id": "DOCUMENT_EXPIRATION", "category": "VALIDATION", "factor": "MRZ_VALIDATION", "label": "Document Expired",
             "status": "FAIL", "severity": "CRITICAL", "confidence": 0.99, "score_impact": 28.0,
             "explanation": "Travel document validity expired.", "evidence": None},
        ]
    }
    tamper_data = {"tamper_risk": 0.07, "checks": []}
    face_data = {"similarity": 0.91, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    assert result["critical_floor_applied"] is True
    assert result["risk_level"] in ("HIGH", "CRITICAL")
    assert result["risk_score"] > 49.0


def test_risk_engine_breakdown_reconciles_to_total_when_critical_floor_applies():
    """
    Reproduces a real credibility gap in the "Explainable risk breakdown"
    panel: when an isolated CRITICAL signal (e.g. a CRITICAL tamper verdict,
    which deliberately carries no weighted factor of its own beyond its
    normal tamper contribution) floors the score, the 5 weighted categories
    previously summed to far less than the displayed total with no line
    item accounting for the difference -- in a panel literally named
    "Explainable". The floor must now appear as its own breakdown entry,
    named after the triggering signal, whose contribution makes the
    categories sum back to the total.

    Uses a CRITICAL tamper verdict rather than a duplicate-identity match to
    trigger the floor here -- duplicate-identity no longer floors at all
    (see test_risk_engine_duplicate_identity_match_is_a_high_severity_
    corroborating_signal_not_a_floor below for why: a 26% 1:N false-accept
    rate at gallery scale, measured by scripts/evaluate_gallery_scale_far.py,
    means it isn't the near-certain violation CRITICAL implies).
    """
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {
        "tamper_risk": 0.91,
        "risk_level": "CRITICAL",
        "checks": [
            {"id": "TAMPER_PHOTO_BOUNDARY_ANOMALY", "category": "TAMPER", "factor": "TAMPER",
             "label": "Forensic Anomaly (Photo Boundary Anomaly)", "status": "FAIL", "severity": "CRITICAL",
             "confidence": 0.95, "score_impact": 17.1, "explanation": "Photo splicing detected.", "evidence": None},
        ]
    }
    face_data = {"similarity": 0.97, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    assert result["critical_floor_applied"] is True
    floor_entry = next(b for b in result["breakdown"] if b["factor"] == "Critical Signal Floor")
    assert floor_entry["weight"] is None
    assert floor_entry["raw_risk"] is None

    reconciled_total = round(sum(b["weighted_contribution"] for b in result["breakdown"]), 1)
    assert reconciled_total == result["risk_score"]


def test_risk_engine_breakdown_reconciles_to_total_with_a_duplicate_identity_contribution():
    """
    Same "Explainable" reconciliation requirement as the critical-floor
    case above, but for duplicate-identity's own flat unweighted addition
    (see risk_engine.py's comment at the duplicate-identity block): its own
    "Cross-Case Duplicate Identity" breakdown row must make the 5 weighted
    categories sum back to the total, the same way the floor row does.
    """
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.1, "checks": []}
    face_data = {"similarity": 0.97, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match={"case_number": "BM-2026-F0E17", "similarity": 1.0}
    )

    assert result["critical_floor_applied"] is False
    identity_entry = next(b for b in result["breakdown"] if b["factor"] == "Cross-Case Duplicate Identity")
    assert identity_entry["weight"] is None
    assert identity_entry["raw_risk"] is None
    assert identity_entry["weighted_contribution"] == 30.0
    assert any(
        c["category"] == "IDENTITY" and "Duplicate Identity" in c["label"] for c in result["checks"]
    )

    reconciled_total = round(sum(b["weighted_contribution"] for b in result["breakdown"]), 1)
    assert reconciled_total == result["risk_score"]


def test_risk_engine_breakdown_has_no_floor_entry_when_floor_not_applied():
    """A clean/low-risk result must not grow a phantom breakdown row."""
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.08, "checks": []}
    face_data = {"similarity": 0.92, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    assert result["critical_floor_applied"] is False
    assert all(b["factor"] != "Critical Signal Floor" for b in result["breakdown"])
    reconciled_total = round(sum(b["weighted_contribution"] for b in result["breakdown"]), 1)
    assert reconciled_total == result["risk_score"]


def test_risk_engine_critical_tamper_verdict_floors_score():
    """
    A tamper_risk that crosses into the tamper service's own CRITICAL tier
    (>=0.85) represents a highly-confident forgery finding -- it must be able
    to floor the overall risk the same way an expired document does, even if
    face verification and validation are otherwise clean. Regression guard for
    the earlier gap where tamper signal severity was capped at HIGH and could
    never trigger the critical-floor override.
    """
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {
        "tamper_risk": 0.91,
        "risk_level": "CRITICAL",
        "checks": [
            {"id": "TAMPER_PHOTO_BOUNDARY_ANOMALY", "category": "TAMPER", "factor": "TAMPER",
             "label": "Forensic Anomaly (Photo Boundary Anomaly)", "status": "FAIL", "severity": "CRITICAL",
             "confidence": 0.95, "score_impact": 17.1, "explanation": "Photo splicing detected.", "evidence": None},
        ]
    }
    face_data = {"similarity": 0.9, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    assert result["critical_floor_applied"] is True
    assert result["risk_level"] in ("HIGH", "CRITICAL")


def _yymmdd(d: date) -> str:
    return d.strftime("%y%m%d")


def test_risk_engine_discounts_face_weight_for_large_age_gap():
    """
    A document that was very likely issued to the holder as a minor, long
    enough ago that ordinary facial aging plausibly explains a mediocre
    (but not clearly-mismatched) similarity score, should have its face
    module weight discounted rather than penalized as if it were a same-age
    photo -- see risk_engine.estimate_face_age_gap.
    """
    engine = RiskEngine()
    today = date.today()
    # DOB ~11 years ago, expiry ~1 year ago -> estimated 5-year-validity
    # minor's passport, issued ~6 years ago while the holder was ~5 --
    # a large, minor-at-issue gap.
    mrz_data = {
        "is_valid": True,
        "birth_date": _yymmdd(today.replace(year=today.year - 11)),
        "expiry_date": _yymmdd(today.replace(year=today.year - 1)),
    }
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.60, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data=mrz_data,
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    face_entry = next(b for b in result["breakdown"] if b["factor"] == "Biometric Face Verification")
    assert face_entry["weight"] < engine.w_face

    age_gap_checks = [c for c in result["checks"] if c["category"] == "FACE" and "Age-Gap" in c["label"]]
    assert len(age_gap_checks) == 1
    assert age_gap_checks[0]["status"] == "INFO"
    assert "gap since likely document" in age_gap_checks[0]["explanation"]
    # Purely informational -- discounting the face weight already reduces
    # its contribution, so the note itself must not ALSO add risk score.
    assert age_gap_checks[0]["score_impact"] == 0.0


def test_risk_engine_does_not_discount_face_weight_for_a_genuine_mismatch():
    """
    Reproduces a real gap: the age-gap discount fired regardless of the
    face module's own verdict, so a GENUINE mismatch (REVIEW_REQUIRED) on
    an old document got its weight cut exactly like a merely-uncertain
    MATCH would -- softening the one signal that actually caught an
    impersonator, rather than a case where the system is uncertain solely
    because of aging. The aging rationale (documented on the discount
    itself) only supports discounting a borderline SIMILARITY SCORE,
    never a case where face verification already returned an affirmative
    mismatch/no-face verdict.

    Concrete before/after, same MRZ age-gap setup as
    test_risk_engine_discounts_face_weight_for_large_age_gap (effective
    gap ~9.6 years -> the 50% discount tier), with an otherwise clean,
    moderate-tamper, single-consistency-flag case chosen so the total
    composite score straddles the real HIGH/MEDIUM boundary (default
    threshold_medium=49):
      - undiscounted: 21.0 (tamper) + 25.5 (face, undiscounted 0.30 * 85)
        + 3.0 (consistency) = 49.5 -> HIGH ("SECONDARY INSPECTION")
      - buggy discount applied: 21.0 + 12.75 (0.15 * 85) + 3.0 = 36.75
        -> MEDIUM ("ROUTINE VERIFICATION") -- a real impersonation case
        silently downgraded out of secondary inspection.
    """
    engine = RiskEngine()
    today = date.today()
    mrz_data = {
        "is_valid": True,
        "birth_date": _yymmdd(today.replace(year=today.year - 11)),
        "expiry_date": _yymmdd(today.replace(year=today.year - 1)),
    }
    validation_data = {
        "passed_count": 4, "failed_count": 1,
        "checks": [
            {"id": "DOC_NUMBER_CROSSCHECK", "category": "VALIDATION", "factor": "CONSISTENCY",
             "label": "Document Number Inconsistency", "status": "FAIL", "severity": "HIGH", "confidence": 0.95,
             "score_impact": 30.0, "explanation": "Mismatch.", "evidence": None},
        ]
    }
    tamper_data = {"tamper_risk": 0.70, "checks": []}
    face_data = {"similarity": 0.15, "status": "REVIEW_REQUIRED", "checks": []}

    result = engine.calculate(
        mrz_data=mrz_data,
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    face_entry = next(b for b in result["breakdown"] if b["factor"] == "Biometric Face Verification")
    assert face_entry["weight"] == engine.w_face  # undiscounted -- this is a real mismatch, not aging uncertainty
    assert not [c for c in result["checks"] if c["category"] == "FACE" and "Age-Gap" in c["label"]]

    assert result["risk_score"] == 49.5
    assert result["risk_level"] == "HIGH"
    assert "SECONDARY INSPECTION" in result["recommendation"]


def test_risk_engine_no_age_gap_discount_for_recent_adult_document():
    """Regression guard: a normal, recently-issued adult document must not
    trigger any face-weight discount or explanatory signal."""
    engine = RiskEngine()
    today = date.today()
    mrz_data = {
        "is_valid": True,
        "birth_date": _yymmdd(today.replace(year=today.year - 40)),
        "expiry_date": _yymmdd(today.replace(year=today.year + 9)),
    }
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.90, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data=mrz_data,
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None
    )

    face_entry = next(b for b in result["breakdown"] if b["factor"] == "Biometric Face Verification")
    assert face_entry["weight"] == engine.w_face
    assert not [c for c in result["checks"] if c["category"] == "FACE" and "Age-Gap" in c["label"]]


def test_risk_engine_missing_mrz_dates_never_discounts_face_weight():
    """Regression guard: absent/unparseable MRZ dates (the common case in
    existing tests and for documents with no MRZ) must never trigger a
    discount -- only a genuinely computed gap may."""
    engine = RiskEngine()
    face_data = {"similarity": 0.90, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},  # no birth_date/expiry_date at all
        validation_data={"passed_count": 5, "failed_count": 0, "checks": []},
        tamper_data={"tamper_risk": 0.05, "checks": []},
        face_data=face_data,
        watchlist_match=None
    )
    face_entry = next(b for b in result["breakdown"] if b["factor"] == "Biometric Face Verification")
    assert face_entry["weight"] == engine.w_face


def test_risk_engine_duplicate_identity_match_is_a_high_severity_corroborating_signal_not_a_floor():
    """
    A cross-case duplicate-identity gallery hit (see identity_gallery_service.py)
    is modeled as a HIGH-severity check under the "IDENTITY" category, added
    as a real +30 flat contribution to the score -- deliberately NOT the
    CRITICAL-floors-to-HIGH treatment this used to get. scripts/
    evaluate_gallery_scale_far.py measured the REAL 1:N false-accept rate at
    gallery scale (1,200 identities): 26.0% at this same threshold -- a
    1-in-4 false-positive rate at usable recall isn't the near-certain rule
    violation CRITICAL severity implies (an expired document, a watchlist
    hit), so it must not automatically force the outcome to HIGH regardless
    of how clean every other signal is. It still needs to materially move
    the score, or the signal would be silently inert whenever nothing else
    already crosses the floor.
    """
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.95, "status": "MATCH", "checks": []}
    duplicate_identity_match = {
        "case_id": "prior-case-uuid",
        "case_number": "BM-2026-PRIOR",
        "full_name": "SUNIL MEHTA",
        "similarity": 0.97
    }

    result_without = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match=None
    )
    result_with = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match=duplicate_identity_match
    )

    identity_checks = [c for c in result_with["checks"] if c["category"] == "IDENTITY"]
    assert len(identity_checks) == 1
    assert identity_checks[0]["status"] == "FAIL"
    assert identity_checks[0]["severity"] == "HIGH"
    assert "BM-2026-PRIOR" in identity_checks[0]["label"]
    assert result_with["critical_floor_applied"] is False
    # A real, material effect on the score -- not silently inert -- but not
    # an automatic override of an otherwise-clean case either.
    assert result_with["risk_score"] == round(result_without["risk_score"] + 30.0, 1)


def test_risk_engine_no_duplicate_identity_match_emits_no_identity_signal_when_not_checked():
    """When the gallery search never ran at all (no live embedding to search
    with), IDENTITY must stay silent -- not a PASS claiming a check that
    didn't happen."""
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.95, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match=None
    )

    assert not any(c["category"] == "IDENTITY" for c in result["checks"])
    assert result["risk_level"] == "LOW"


def test_risk_engine_duplicate_identity_checked_but_clean_emits_a_pass_check():
    """
    Principle: show why a clean result is clean, not just silence. When the
    gallery search DID run (a live embedding existed) and found no match,
    that's real evidentiary information -- distinct from the check never
    having run at all.
    """
    engine = RiskEngine()
    validation_data = {"passed_count": 5, "failed_count": 0, "checks": []}
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.95, "status": "MATCH", "checks": []}

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match=None,
        duplicate_identity_checked=True,
    )

    identity_checks = [c for c in result["checks"] if c["category"] == "IDENTITY"]
    assert len(identity_checks) == 1
    assert identity_checks[0]["status"] == "PASS"


# --- Edge cases: a document that fails nothing, a document that fails
# everything, and a tie in severity between two independent signals -------

def test_risk_engine_zero_failures_still_produces_a_populated_checks_list():
    """
    A document that fails zero checks must still show ITS OWN evidence for
    why it's clean -- an empty checks list would be indistinguishable from
    "nothing was ever checked." Every category (MRZ/VALIDATION passes,
    tamper passes, face match, watchlist clean, identity clean) should
    contribute at least one PASS check.
    """
    engine = RiskEngine()
    validation_data = {
        "passed_count": 9, "failed_count": 0,
        "checks": [
            {"id": "MRZ_DOCUMENT_NUMBER_CHECKSUM", "category": "MRZ", "factor": "MRZ_VALIDATION",
             "label": "Document Number Checksum", "status": "PASS", "severity": None, "confidence": 0.99,
             "score_impact": 0.0, "explanation": "Matches.", "evidence": None},
            {"id": "DOC_NUMBER_CROSSCHECK", "category": "VALIDATION", "factor": "CONSISTENCY",
             "label": "Document Number Crosscheck", "status": "PASS", "severity": None, "confidence": 0.95,
             "score_impact": 0.0, "explanation": "Matches.", "evidence": None},
        ]
    }
    tamper_data = {
        "tamper_risk": 0.0,
        "checks": [
            {"id": "TAMPER_ELA", "category": "TAMPER", "factor": "TAMPER", "label": "Error Level Analysis",
             "status": "PASS", "severity": None, "confidence": 0.9, "score_impact": 0.0,
             "explanation": "Clean.", "evidence": None},
        ]
    }
    face_data = {
        "similarity": 1.0, "status": "MATCH",
        "checks": [
            {"id": "FACE_BIOMETRIC_MATCH", "category": "FACE", "factor": "FACE", "label": "Biometric Face Match",
             "status": "PASS", "severity": None, "confidence": 0.95, "score_impact": 0.0,
             "explanation": "Matches.", "evidence": None},
        ]
    }

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=None,
        duplicate_identity_match=None,
        duplicate_identity_checked=True,
    )

    assert result["risk_level"] == "LOW"
    assert result["risk_score"] == 0.0
    assert not any(c["status"] == "FAIL" for c in result["checks"])
    # A real, populated evidentiary trail -- not an empty list.
    assert len(result["checks"]) >= 6
    categories_present = {c["category"] for c in result["checks"]}
    assert {"MRZ", "VALIDATION", "TAMPER", "FACE", "WATCHLIST", "IDENTITY"} <= categories_present


def test_risk_engine_every_check_failing_reaches_critical():
    """The opposite edge case: every module fails at once."""
    engine = RiskEngine()
    validation_data = {
        "passed_count": 0, "failed_count": 2,
        "checks": [
            {"id": "DOCUMENT_EXPIRATION", "category": "VALIDATION", "factor": "MRZ_VALIDATION",
             "label": "Document Expired", "status": "FAIL", "severity": "CRITICAL", "confidence": 0.99,
             "score_impact": 28.0, "explanation": "Expired.", "evidence": None},
            {"id": "DOC_NUMBER_CROSSCHECK", "category": "VALIDATION", "factor": "CONSISTENCY",
             "label": "Document Number Inconsistency", "status": "FAIL", "severity": "HIGH", "confidence": 0.95,
             "score_impact": 22.0, "explanation": "Mismatch.", "evidence": None},
        ]
    }
    tamper_data = {
        "tamper_risk": 0.95, "risk_level": "CRITICAL",
        "checks": [
            {"id": "TAMPER_ELA", "category": "TAMPER", "factor": "TAMPER", "label": "Error Level Analysis",
             "status": "FAIL", "severity": "CRITICAL", "confidence": 0.9, "score_impact": 16.2,
             "explanation": "Recompression detected.", "evidence": None},
        ]
    }
    face_data = {
        "similarity": 0.10, "status": "REVIEW_REQUIRED",
        "checks": [
            {"id": "FACE_BIOMETRIC_MATCH", "category": "FACE", "factor": "FACE", "label": "Biometric Face Mismatch",
             "status": "FAIL", "severity": "HIGH", "confidence": 0.9, "score_impact": 25.0,
             "explanation": "Mismatch.", "evidence": None},
        ]
    }
    watchlist_match = {
        "matched": True,
        "entry": {"watchlist_id": "WL-002", "category": "Travel Alert", "severity": "CRITICAL"},
        "explanation": "Simulated match.",
    }

    result = engine.calculate(
        mrz_data={"is_valid": False},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=watchlist_match,
        duplicate_identity_match={"case_number": "BM-2026-DUP", "similarity": 0.9},
        duplicate_identity_checked=True,
    )

    assert result["risk_level"] == "CRITICAL"
    assert result["risk_score"] >= engine.threshold_high
    assert not any(c["status"] == "PASS" for c in result["checks"])


def test_risk_engine_ties_in_severity_are_all_retained_not_collapsed():
    """
    Two independent CRITICAL signals from different modules (an expired
    document AND a watchlist hit) must both survive into the checks list --
    a tie in severity must never cause one to be silently dropped in favor
    of the other, since each is independent evidence an officer needs to
    see.
    """
    engine = RiskEngine()
    validation_data = {
        "passed_count": 4, "failed_count": 1,
        "checks": [
            {"id": "DOCUMENT_EXPIRATION", "category": "VALIDATION", "factor": "MRZ_VALIDATION",
             "label": "Document Expired", "status": "FAIL", "severity": "CRITICAL", "confidence": 0.99,
             "score_impact": 28.0, "explanation": "Expired.", "evidence": None},
        ]
    }
    tamper_data = {"tamper_risk": 0.05, "checks": []}
    face_data = {"similarity": 0.95, "status": "MATCH", "checks": []}
    watchlist_match = {
        "matched": True,
        "entry": {"watchlist_id": "WL-003", "category": "Travel Alert", "severity": "CRITICAL"},
        "explanation": "Simulated match.",
    }

    result = engine.calculate(
        mrz_data={"is_valid": True},
        validation_data=validation_data,
        tamper_data=tamper_data,
        face_data=face_data,
        watchlist_match=watchlist_match,
    )

    critical_checks = [c for c in result["checks"] if c["severity"] == "CRITICAL"]
    assert len(critical_checks) == 2
    assert {c["category"] for c in critical_checks} == {"VALIDATION", "WATCHLIST"}
    assert result["critical_floor_applied"] is True
