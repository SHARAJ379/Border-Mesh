import contextlib
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.api.deps import get_current_officer
from app.models import Officer

# Starlette's TestClient only runs the app's lifespan (startup/shutdown --
# here, Base.metadata.create_all plus initial seeding) when entered as a
# context manager; a bare `TestClient(app)` never triggers it, leaving every
# DB-backed endpoint below failing with "no such table". Enter it once for
# the whole module so all tests keep sharing state/order as originally
# written, and close it after the last test.
_client_cm = TestClient(app)
client = _client_cm.__enter__()

# Every route now requires a real logged-in Officer (see
# app.api.deps.get_current_officer) -- overriding the dependency itself,
# rather than performing a real login handshake in every single test,
# keeps this whole suite's existing call sites unchanged: FastAPI's
# dependency_overrides machinery swaps in this fixed officer for every
# request through `client`, with zero per-request auth bookkeeping needed.
# The handful of tests that specifically verify auth REJECTION (below) pop
# this override for the duration of their negative assertions, via
# `_no_officer_auth()`.
_TEST_OFFICER = Officer(
    id="test-officer-id", badge_id="OFFICER-DEMO-01", full_name="Test Officer",
    password_hash="unused-under-the-override", is_active=True,
)
app.dependency_overrides[get_current_officer] = lambda: _TEST_OFFICER

# No longer a real header (the override above authenticates every request
# regardless) -- kept as an empty dict purely so the many pre-existing
# `headers=OFFICER_AUTH_HEADERS` call sites below don't all need editing;
# an empty headers dict is a no-op.
OFFICER_AUTH_HEADERS = {}


@contextlib.contextmanager
def _no_officer_auth():
    """Temporarily removes the auth override so a request actually exercises
    get_current_officer's real rejection path (missing/invalid token), then
    restores it -- every other test in this module expects to be
    auto-authenticated."""
    app.dependency_overrides.pop(get_current_officer, None)
    try:
        yield
    finally:
        app.dependency_overrides[get_current_officer] = lambda: _TEST_OFFICER


def teardown_module(module):
    _client_cm.__exit__(None, None, None)
    # `app` is a module-level singleton shared with every other test file
    # that imports it (test_auth.py in particular) -- an override left in
    # place here would silently auto-authenticate requests those other
    # modules deliberately expect to be rejected.
    app.dependency_overrides.pop(get_current_officer, None)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ai_engines" in data
    assert data["ai_engines"]["mrz_validator"] == "ONLINE"

def test_dashboard_stats_endpoint():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "documents_screened" in data
    assert data["documents_screened"] >= 0
    assert "risk_distribution" in data

def test_dashboard_latency_breakdown_reflects_real_audit_timestamps():
    """
    latency_breakdown used to not exist -- the "Component Processing
    Latency" chart on the Analytics page was a hardcoded array
    (Normalization: 140ms, OCR: 520ms, ...) never measured from anything.
    Every case's audit trail already timestamps each pipeline step
    (DOCUMENT_UPLOADED, OCR_COMPLETED, MRZ_VALIDATED, ...), so the per-module
    average can be computed for real from those deltas. Run an actual
    scenario and confirm each module's reported time is a genuine
    measurement (backed by at least one real sample), not a placeholder.
    """
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200

    stats = client.get("/api/dashboard/stats").json()
    breakdown = {b["module"]: b for b in stats["latency_breakdown"]}
    assert "OCR Extraction" in breakdown
    assert "Risk Engine" in breakdown
    for module in breakdown.values():
        assert module["sample_count"] >= 1
        assert module["time_ms"] > 0

def test_cases_list_endpoint():
    response = client.get("/api/cases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_demo_scenario_execution():
    response = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert response.status_code == 200
    data = response.json()
    assert "case_id" in data
    assert "case_number" in data
    assert data["risk_level"] == "LOW"

    # Fetch case detail
    case_res = client.get(f"/api/cases/{data['case_id']}")
    assert case_res.status_code == 200
    detail = case_res.json()
    assert detail["case_number"] == data["case_number"]
    assert len(detail["analyses"]) > 0

    # The risk engine's real per-factor breakdown must be persisted on the
    # analysis record, not just returned transiently by the risk step.
    breakdown = detail["analyses"][0]["risk_breakdown"]
    assert breakdown is not None
    assert len(breakdown) == 5
    factor_names = {b["factor"] for b in breakdown}
    assert "Forensic Tamper AI" in factor_names
    assert "Biometric Face Verification" in factor_names
    for factor in breakdown:
        assert "weight" in factor
        assert "raw_risk" in factor
        assert "weighted_contribution" in factor

def test_pan_card_demo_scenario_runs_clean_through_the_full_pipeline():
    """
    A genuine PAN card has no MRZ by design. Before demo.py's MRZ-band OCR
    pass was gated the same way screening.py's already is, this scenario
    would have had its bottom band scanned for an MRZ anyway, fabricating
    one from the card's own boilerplate/signature text whose checksums then
    "fail" -- corrupting the MRZ risk factor and misclassifying a clean PAN
    as HIGH/CRITICAL. It must come back LOW, with the new PAN structural
    check passing and decoding the entity-type letter.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "pan_card"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    assert detail["document_type"] == "PAN"
    analysis = detail["analyses"][0]
    assert analysis["ocr_result"]["fields"]["document_type"] == "PAN"
    assert analysis["mrz_result"] is None

    pan_rule = [r for r in analysis["validation_result"]["checks"] if r["id"] == "PAN_FORMAT_VALIDATION"][0]
    assert pan_rule["status"] == "PASS"
    assert "Individual" in pan_rule["explanation"]

def test_driving_license_expired_demo_scenario_is_flagged_critical():
    """
    A Driving Licence has no MRZ either, but it DOES have a genuine printed
    expiry -- this is the actual value of last session's RULE 2
    generalization (previously MRZ-only): an expired DL must be caught the
    same way an expired passport already is. "Document Expired" is a
    CRITICAL-severity signal, which risk_engine.py's hard-stop floor
    guarantees classifies at least HIGH regardless of how clean every other
    factor is (same floor an expired passport gets -- see
    test_policy_change_actually_changes_a_real_screening_result's use of
    the "expired" passport scenario).
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "driving_license"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    assert detail["document_type"] == "Driving Licence"
    analysis = detail["analyses"][0]
    assert analysis["mrz_result"] is None

    expiry_rule = [r for r in analysis["validation_result"]["checks"] if r["id"] == "DOCUMENT_EXPIRATION"][0]
    assert expiry_rule["status"] == "FAIL"
    assert any(c["label"] == "Document Expired" for c in detail["risk_checks"])

def test_voter_id_demo_scenario_runs_clean_through_the_full_pipeline():
    """
    A genuine Voter ID (EPIC) card has no MRZ by design, same as PAN/DL --
    the MRZ-band OCR pass must be gated for it too, or a fabricated
    "failed" MRZ checksum would corrupt an otherwise-clean case. It must
    come back LOW, with the new EPIC structural check passing.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "voter_id"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    assert detail["document_type"] == "Voter ID"
    analysis = detail["analyses"][0]
    assert analysis["ocr_result"]["fields"]["document_type"] == "VOTER_ID"
    assert analysis["mrz_result"] is None

    voter_id_rule = [r for r in analysis["validation_result"]["checks"] if r["id"] == "VOTER_ID_FORMAT_VALIDATION"][0]
    assert voter_id_rule["status"] == "PASS"


def test_visa_stay_duration_expired_demo_scenario_is_flagged_critical():
    """
    A Visa has no ICAO MRZ modeled (extract-only, same posture as
    Aadhaar's document number -- no fabricated checksum). Its 'Stay
    Duration' field is the actual value of the new
    VISA_STAY_DURATION_VALIDATION rule: an overstayed visa must be caught
    the same way an expired passport/DL already is, via the same
    CRITICAL-floors-to-at-least-HIGH mechanism.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "visa"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    assert detail["document_type"] == "Travel Visa"
    analysis = detail["analyses"][0]
    assert analysis["ocr_result"]["fields"]["document_type"] == "VISA"
    assert analysis["mrz_result"] is None

    visa_rule = [r for r in analysis["validation_result"]["checks"] if r["id"] == "VISA_STAY_DURATION_VALIDATION"][0]
    assert visa_rule["status"] == "FAIL"
    assert any(c["label"] == "Visa Stay Duration Expired" for c in detail["risk_checks"])


def test_permit_expired_demo_scenario_is_flagged_critical():
    """
    A Permit has no ICAO MRZ modeled either (extract-only, same posture as
    Visa/Aadhaar). Its printed expiry hooks into the existing generic
    DOCUMENT_EXPIRATION rule (rules_engine.py) the same way a Driving
    Licence's does -- not a dedicated PERMIT_EXPIRATION rule, which would
    double-count the same date. An expired permit must still be caught the
    same way an expired passport/DL already is, via the same
    CRITICAL-floors-to-at-least-HIGH mechanism.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "permit"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    assert detail["document_type"] == "Permit"
    analysis = detail["analyses"][0]
    assert analysis["ocr_result"]["fields"]["document_type"] == "PERMIT"
    assert analysis["mrz_result"] is None

    expiry_rule = [r for r in analysis["validation_result"]["checks"] if r["id"] == "DOCUMENT_EXPIRATION"][0]
    assert expiry_rule["status"] == "FAIL"
    assert any(c["label"] == "Document Expired" for c in detail["risk_checks"])


def test_duplicate_identity_demo_scenario_flags_a_high_severity_corroborating_signal():
    """
    Two entirely different fabricated identities (different name, different
    passport number) but the SAME underlying live face photo (PERSON_A) --
    both documents are otherwise clean (valid MRZ, no tamper, a genuine
    face match on their own document). The elevated risk here comes
    entirely from the cross-case duplicate-identity gallery hit: this real
    person was already screened once under a different name.

    HIGH severity, not CRITICAL, and no automatic floor to HIGH/CRITICAL --
    scripts/evaluate_gallery_scale_far.py measured a 26% real 1:N
    false-accept rate for this gallery match at scale, so it's modeled as a
    material but non-overriding corroborating signal (see risk_engine.py's
    duplicate-identity comment), not a near-certain rule violation the way
    an expired document or watchlist hit is.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "duplicate_identity"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] != "LOW"

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    identity_signals = [c for c in detail["risk_checks"] if c["category"] == "IDENTITY"]
    assert len(identity_signals) == 1
    assert identity_signals[0]["severity"] == "HIGH"
    assert "Possible Duplicate Identity" in identity_signals[0]["label"]

    analysis = detail["analyses"][0]
    assert analysis["face_result"]["status"] == "MATCH"  # clean on its own document
    assert analysis["risk_breakdown"] is not None
    identity_entry = next(b for b in analysis["risk_breakdown"] if b["factor"] == "Cross-Case Duplicate Identity")
    assert identity_entry["weighted_contribution"] == 30.0

def test_demo_scenario_failure_does_not_leave_a_zombie_case():
    """
    The Case row is committed to the DB before the OCR/tamper/face/risk
    pipeline runs (see app.api.routes.demo.run_demo_scenario). Before the
    try/except around that pipeline, any failure there -- a missing
    Tesseract binary, a model load error, anything -- left that case
    permanently stuck at status="PROCESSING", risk_level="LOW",
    risk_score=0.0: a zombie that reads exactly like a genuine cleared case
    in the Review Queue and Cases Archive. A failed run must clean up after
    itself instead.

    Asserts a BEFORE/AFTER delta, not an absolute global count: this suite
    shares one persistent DB across the whole session (no per-test
    isolation), and several other tests (e.g.
    test_aadhaar_document_never_gets_a_fabricated_mrz,
    test_upload_survives_a_random_case_number_collision,
    test_uploaded_document_is_encrypted_on_disk_and_served_decrypted) call
    only /api/screening/upload and deliberately stop there to test a single
    pipeline step in isolation, legitimately leaving their own case at
    status="PROCESSING" forever. A prior version of this assertion
    (`count == 0`) was a real test bug, not a product bug: it failed
    whenever any of those ran first in the same session, even though this
    scenario's own failure was cleaned up correctly.
    """
    from app.core.database import SessionLocal
    from app.models import Case

    db = SessionLocal()
    try:
        before = db.query(Case).filter(Case.status == "PROCESSING").count()
    finally:
        db.close()

    with patch("app.api.routes.demo.get_ocr_service", side_effect=RuntimeError("Simulated OCR engine failure")):
        with pytest.raises(RuntimeError):
            client.post("/api/demo/scenario", json={"scenario_key": "genuine"})

    db = SessionLocal()
    try:
        after = db.query(Case).filter(Case.status == "PROCESSING").count()
        assert after == before, "A failed demo scenario left a PROCESSING zombie case behind"
    finally:
        db.close()

def test_watchlist_evasion_scenario_still_flags_near_miss():
    """
    The 'watchlist_evasion' demo scenario is a document with a valid MRZ, a
    matching face, and no tamper signals -- everything about it looks clean
    except that the name and document number are each a single character
    away from a real watchlist entry (WL-SIM-2026-081). An exact-match-only
    watchlist check (what this system had before the fuzzy-matching fix)
    would have missed both and cleared this as LOW risk; the fuzzy check
    must still catch it and floor the outcome to at least HIGH, since a
    CRITICAL-severity watchlist hit is a hard-stop regardless of how clean
    every other signal is.
    """
    response = client.post("/api/demo/scenario", json={"scenario_key": "watchlist_evasion"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")

    detail = client.get(f"/api/cases/{data['case_id']}").json()
    analysis = detail["analyses"][0]
    assert analysis["mrz_result"]["is_valid"] is True
    assert analysis["face_result"]["status"] == "MATCH"
    assert analysis["tamper_result"]["risk_level"] in ("LOW", "MEDIUM")

    breakdown = analysis["risk_breakdown"]
    watchlist_factor = next(b for b in breakdown if b["factor"] == "Simulated Watchlist Adapter")
    assert watchlist_factor["raw_risk"] == 100.0

    # A watchlist hit gets its own dedicated audit action -- not just folded
    # into RISK_CALCULATED's metadata -- so an investigator can find every
    # watchlist hit across all cases without opening each risk-calculation
    # entry individually to check whether one happened to be among its inputs.
    audit_logs = client.get(f"/api/audit?case_id={data['case_id']}&action=WATCHLIST_HIT").json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["metadata_json"]["watchlist_id"] == "WL-SIM-2026-081"

def test_get_policy_settings_returns_defaults():
    response = client.get("/api/settings/policy")
    assert response.status_code == 200
    data = response.json()
    total = (data["weight_mrz"] + data["weight_tamper"] + data["weight_face"]
             + data["weight_consistency"] + data["weight_watchlist"])
    assert abs(total - 1.0) < 0.01

def test_update_policy_rejects_weights_not_summing_to_100():
    bad_policy = {
        "weight_mrz": 0.5, "weight_tamper": 0.5, "weight_face": 0.5,
        "weight_consistency": 0.1, "weight_watchlist": 0.05,
        "threshold_low": 24, "threshold_medium": 49, "threshold_high": 74
    }
    response = client.post("/api/settings/policy", json=bad_policy, headers=OFFICER_AUTH_HEADERS)
    assert response.status_code == 400
    assert "100%" in response.json()["detail"]

def test_update_policy_rejects_non_ascending_thresholds():
    bad_policy = {
        "weight_mrz": 0.25, "weight_tamper": 0.30, "weight_face": 0.30,
        "weight_consistency": 0.10, "weight_watchlist": 0.05,
        "threshold_low": 50, "threshold_medium": 30, "threshold_high": 74
    }
    response = client.post("/api/settings/policy", json=bad_policy, headers=OFFICER_AUTH_HEADERS)
    assert response.status_code == 400

def test_policy_change_actually_changes_a_real_screening_result():
    """
    This is the entire point of the fix: the Settings page's sliders used to
    update local React state only -- "Apply Policy Configuration" was
    entirely cosmetic and never reached the risk engine. Changing a weight
    here must change a real demo scenario's computed risk breakdown.
    """
    # Push MRZ weight to its max and zero out everything else the
    # "expired" scenario doesn't otherwise trigger, so the MRZ factor's
    # contribution to the total score is unmistakable.
    new_policy = {
        "weight_mrz": 0.70, "weight_tamper": 0.10, "weight_face": 0.10,
        "weight_consistency": 0.05, "weight_watchlist": 0.05,
        "threshold_low": 24, "threshold_medium": 49, "threshold_high": 74
    }
    update_res = client.post("/api/settings/policy", json=new_policy, headers=OFFICER_AUTH_HEADERS)
    assert update_res.status_code == 200
    assert update_res.json()["weight_mrz"] == 0.70

    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "expired"})
    assert demo_res.status_code == 200
    detail = client.get(f"/api/cases/{demo_res.json()['case_id']}").json()
    breakdown = detail["analyses"][0]["risk_breakdown"]
    mrz_factor = next(b for b in breakdown if b["factor"] == "MRZ & Document Validation")
    assert mrz_factor["weight"] == 0.70

    # Restore defaults so later tests in this module aren't affected.
    client.post("/api/settings/policy", json={
        "weight_mrz": 0.25, "weight_tamper": 0.30, "weight_face": 0.30,
        "weight_consistency": 0.10, "weight_watchlist": 0.05,
        "threshold_low": 24, "threshold_medium": 49, "threshold_high": 74
    }, headers=OFFICER_AUTH_HEADERS)

def test_dashboard_requiring_review_kpi_respects_the_configured_low_threshold():
    """
    The dashboard's "cases requiring review" KPI hardcoded a `risk_score >=
    25.0` cutoff, completely decoupled from the officer-editable
    threshold_low policy (Settings page / policy_service.py) that actually
    defines the real LOW/MEDIUM boundary used everywhere else (risk_engine.py
    classifies risk_level from this same threshold_low). After an officer
    raises threshold_low well above a pending case's score, that case is
    unambiguously LOW risk under the now-configured policy and must stop
    being counted as "requiring review" -- otherwise the KPI silently stops
    reflecting the policy an officer just configured.
    """
    from app.core.database import SessionLocal
    from app.models import Case

    import uuid
    db = SessionLocal()
    try:
        probe_case = Case(
            case_number=f"BM-2026-RVW{uuid.uuid4().hex[:5].upper()}",
            document_type="Passport",
            country="Unknown",
            status="PROCESSING",
            risk_level="LOW",
            risk_score=30.0,
            officer_decision="PENDING",
        )
        db.add(probe_case)
        db.commit()
        probe_case_id = probe_case.id
    finally:
        db.close()

    try:
        # The probe case (score 30, PENDING) straddles both threshold
        # values tried below, so each one exercises a real change in its
        # membership -- but the assertion itself doesn't hardcode any
        # specific count: it independently recomputes "how many PENDING
        # cases have risk_score >= <the live threshold_low>" directly via
        # the DB (the correct formula) and checks the dashboard endpoint's
        # own reported count matches it EXACTLY, at two different
        # threshold_low values. The old hardcoded `>= 25.0` could only ever
        # coincidentally match this independently-computed expectation;
        # tying the KPI to the live policy makes it match at any threshold.
        for threshold_low in (10, 60):
            policy = {
                "weight_mrz": 0.25, "weight_tamper": 0.30, "weight_face": 0.30,
                "weight_consistency": 0.10, "weight_watchlist": 0.05,
                "threshold_low": threshold_low,
                "threshold_medium": threshold_low + 15,
                "threshold_high": threshold_low + 30,
            }
            update_res = client.post("/api/settings/policy", json=policy, headers=OFFICER_AUTH_HEADERS)
            assert update_res.status_code == 200

            stats = client.get("/api/dashboard/stats").json()

            db2 = SessionLocal()
            try:
                expected = (
                    db2.query(Case)
                    .filter(Case.officer_decision == "PENDING", Case.risk_score >= threshold_low)
                    .count()
                )
            finally:
                db2.close()

            assert stats["cases_requiring_review"] == expected
    finally:
        client.post("/api/settings/policy", json={
            "weight_mrz": 0.25, "weight_tamper": 0.30, "weight_face": 0.30,
            "weight_consistency": 0.10, "weight_watchlist": 0.05,
            "threshold_low": 24, "threshold_medium": 49, "threshold_high": 74
        }, headers=OFFICER_AUTH_HEADERS)
        db2 = SessionLocal()
        try:
            db2.query(Case).filter(Case.id == probe_case_id).delete()
            db2.commit()
        finally:
            db2.close()

def test_officer_decision_recording():
    # Fetch first case
    cases_res = client.get("/api/cases?limit=1")
    cases = cases_res.json()
    case_id = cases[0]["id"]

    decision_payload = {
        "decision": "REQUIRES_INSPECTION",
        "notes": "Test officer inspection note for SIH verification.",
        "officer_id": "OFFICER-TEST-99"
    }
    dec_res = client.post(f"/api/cases/{case_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    updated_case = dec_res.json()
    assert updated_case["officer_decision"] == "REQUIRES_INSPECTION"

    # Verify audit log contains entry
    audit_res = client.get(f"/api/cases/{case_id}/audit")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any(log["action"] == "OFFICER_DECISION_RECORDED" for log in logs)

def test_central_audit_and_chain_verification():
    # 1. Test centralized audit list
    res = client.get("/api/audit?limit=10")
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    # Verify hash presence on blocks
    assert "entry_hash" in logs[0]
    assert "previous_hash" in logs[0]

    # 2. Test live cryptographic chain verification
    verify_res = client.get("/api/audit/verify")
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["valid"] is True
    assert vdata["total_records"] > 0
    assert len(vdata["head_hash"]) == 64

    # 3. Test audit stats
    stats_res = client.get("/api/audit/stats")
    assert stats_res.status_code == 200
    sdata = stats_res.json()
    assert sdata["total_blocks"] > 0
    assert len(sdata["head_hash"]) == 64

def test_chain_verification_detects_a_block_tampered_and_self_resigned():
    """
    Reproduces a real gap found while reviewing the audit chain: verify_chain
    recomputed each block's hash from that SAME block's own stored fields
    (including its own previous_hash) and compared the result to itself --
    which only proves a block is internally self-consistent, never that it
    is the block the NEXT entry's previous_hash actually points to. Anyone
    with DB write access can edit one block's content and recompute just
    that block's own entry_hash (pure SHA-256 over public fields, no secret
    key involved) without touching any other row, and the chain reported
    "valid" regardless -- defeating the entire point of a hash chain.

    This tampers one real block's action field, re-signs ONLY that block's
    own entry_hash (self-consistent, exactly what a real attacker who knows
    the hash algorithm would do), and confirms verification must catch it by
    noticing the next block's previous_hash no longer matches this block's
    (new) entry_hash.
    """
    from app.core.database import SessionLocal
    from app.models import AuditLog
    from app.services.audit_service import AuditService

    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    db = SessionLocal()
    try:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.case_id == case_id)
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
            .all()
        )
        # Need a block with both a predecessor and a successor so the broken
        # forward-linkage check has something to actually catch.
        assert len(logs) >= 3
        target = logs[1]
        original_action = target.action
        original_entry_hash = target.entry_hash

        tampered_action = target.action + "_TAMPERED"
        ts_str = target.timestamp.isoformat()
        meta_str = AuditService.canonical_json(target.metadata_json)
        resigned_hash = AuditService.compute_hash(
            previous_hash=target.previous_hash or ("0" * 64),
            case_id=target.case_id,
            action=tampered_action,
            actor=target.actor,
            timestamp_str=ts_str,
            metadata_str=meta_str,
        )
        target.action = tampered_action
        target.entry_hash = resigned_hash
        db.commit()

        try:
            verify_res = client.get("/api/audit/verify")
            assert verify_res.status_code == 200
            vdata = verify_res.json()
            assert vdata["valid"] is False
            assert vdata["compromised_id"] is not None
        finally:
            # This is a shared, persistent ledger (this whole suite reuses
            # one sqlite DB, and a broken hash chain has global, cascading
            # effects on every later chain check) -- restore the block to
            # its original, correctly-chained state so this test doesn't
            # leave the ledger permanently invalid for every test/run after it.
            target.action = original_action
            target.entry_hash = original_entry_hash
            db.commit()
    finally:
        db.close()


class _FakeAnchorService:
    """Stands in for Web3BlockchainAnchorService so this API-level test never
    touches a real network -- the mandatory "mock the chain call for CI"
    half of this feature's test plan. The real-network half is a manual,
    one-off run against a live testnet, never part of the automated suite.

    Generates a fresh tx_hash per call (a real anchor service always would
    too, since it's a new transaction every time) rather than a fixed
    constant -- this test module reuses one persistent on-disk SQLite DB
    across separate pytest invocations (see the module-level TestClient
    setup), and BlockchainAnchor.tx_hash is UNIQUE, so a hardcoded value
    would collide with a leftover row from a prior run of this same test."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.anchored_hashes = []

    def anchor(self, head_hash):
        if self._error:
            raise self._error
        self.anchored_hashes.append(head_hash)
        if self._result:
            return self._result
        tx_hash = "0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32]
        return {
            "tx_hash": tx_hash,
            "network": "Ethereum Sepolia",
            "chain_id": 11155111,
            "block_number": 999,
            "explorer_url": f"https://sepolia.etherscan.io/tx/{tx_hash}",
        }


def test_anchor_audit_chain_rejects_unauthenticated_requests(monkeypatch):
    """Triggers a real (though free) testnet transaction -- gated the same
    way as case deletion/biometric purge so a bare, credential-free request
    can't fire it."""
    fake = _FakeAnchorService()
    monkeypatch.setattr("app.api.routes.audit.get_blockchain_anchor_service", lambda: fake)

    with _no_officer_auth():
        no_auth_res = client.post("/api/audit/anchor")
        assert no_auth_res.status_code == 401

        wrong_auth_res = client.post("/api/audit/anchor", headers={"Authorization": "Bearer definitely-not-a-real-token"})
        assert wrong_auth_res.status_code == 401

    assert fake.anchored_hashes == []  # rejected requests must never reach the chain call


def test_anchor_audit_chain_publishes_the_real_head_hash_and_persists_a_record(monkeypatch):
    fake = _FakeAnchorService()
    monkeypatch.setattr("app.api.routes.audit.get_blockchain_anchor_service", lambda: fake)

    verify_before = client.get("/api/audit/verify").json()
    expected_head_hash = verify_before["head_hash"]

    res = client.post("/api/audit/anchor")
    assert res.status_code == 200
    data = res.json()

    # The exact hash sent to the chain must be the ledger's real, current
    # head hash -- not a stale or hardcoded value.
    assert fake.anchored_hashes == [expected_head_hash]
    assert data["head_hash"] == expected_head_hash
    assert data["network"] == "Ethereum Sepolia"
    assert data["chain_id"] == 11155111
    assert data["explorer_url"] == f"https://sepolia.etherscan.io/tx/{data['tx_hash']}"
    assert data["total_records_at_anchor"] == verify_before["total_records"]

    anchors = client.get("/api/audit/anchors").json()
    assert any(a["id"] == data["id"] for a in anchors)


def test_anchor_audit_chain_surfaces_configuration_error_as_503(monkeypatch):
    from app.services.blockchain_anchor_service import AnchorConfigurationError

    fake = _FakeAnchorService(error=AnchorConfigurationError("ANCHOR_PRIVATE_KEY is not configured"))
    monkeypatch.setattr("app.api.routes.audit.get_blockchain_anchor_service", lambda: fake)

    res = client.post("/api/audit/anchor", headers=OFFICER_AUTH_HEADERS)
    assert res.status_code == 503


def test_anchor_audit_chain_surfaces_network_failure_as_502(monkeypatch):
    fake = _FakeAnchorService(error=ConnectionError("could not reach RPC endpoint"))
    monkeypatch.setattr("app.api.routes.audit.get_blockchain_anchor_service", lambda: fake)

    res = client.post("/api/audit/anchor", headers=OFFICER_AUTH_HEADERS)
    assert res.status_code == 502


def test_case_anchor_proof_returns_not_found_for_unknown_case_number():
    res = client.get("/api/audit/anchor-proof/BM-2026-NOPE1")
    assert res.status_code == 200
    data = res.json()
    assert data["case_found"] is False
    assert data["anchored"] is False
    assert data["anchor"] is None


def test_case_anchor_proof_reports_not_yet_anchored_when_no_covering_anchor_exists():
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    case_id = demo_res.json()["case_id"]
    case_number = client.get(f"/api/cases/{case_id}").json()["case_number"]

    res = client.get(f"/api/audit/anchor-proof/{case_number}")
    assert res.status_code == 200
    data = res.json()
    assert data["case_found"] is True
    assert data["chain_valid"] is True
    assert data["anchored"] is False
    assert data["anchor"] is None


def test_case_anchor_proof_reports_anchored_when_a_covering_anchor_exists(monkeypatch):
    fake = _FakeAnchorService()
    monkeypatch.setattr("app.api.routes.audit.get_blockchain_anchor_service", lambda: fake)

    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    case_id = demo_res.json()["case_id"]
    case_number = client.get(f"/api/cases/{case_id}").json()["case_number"]

    anchor_res = client.post("/api/audit/anchor", headers=OFFICER_AUTH_HEADERS)
    assert anchor_res.status_code == 200

    res = client.get(f"/api/audit/anchor-proof/{case_number}")
    assert res.status_code == 200
    data = res.json()
    assert data["case_found"] is True
    assert data["anchored"] is True
    assert data["anchor"]["tx_hash"] == anchor_res.json()["tx_hash"]
    assert data["anchor"]["explorer_url"] == anchor_res.json()["explorer_url"]
    assert data["anchor"]["network"] == "Ethereum Sepolia"


def test_case_anchor_proof_requires_no_authentication():
    """The whole point of this endpoint is a public, no-login verification
    page -- a bare, credential-free request must succeed."""
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    case_id = demo_res.json()["case_id"]
    case_number = client.get(f"/api/cases/{case_id}").json()["case_number"]

    res = client.get(f"/api/audit/anchor-proof/{case_number}")
    assert res.status_code == 200


def test_case_anchor_proof_never_leaks_sensitive_case_data():
    """
    This endpoint is public and unauthenticated by design -- it must prove
    ONLY that a case's audit trail was anchored, never surface the case's
    risk score, name, or document number. This is the one thing that must
    never regress here.
    """
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    case_id = demo_res.json()["case_id"]
    detail = client.get(f"/api/cases/{case_id}").json()
    case_number = detail["case_number"]

    res = client.get(f"/api/audit/anchor-proof/{case_number}")
    assert res.status_code == 200
    raw_body = res.text

    # "genuine" scenario's identity -- see demo.py's SCENARIO_CONFIGS.
    assert "KAUL" not in raw_body
    assert "ARIHANT" not in raw_body
    assert "X1234567" not in raw_body  # doc_number
    assert str(detail["document_number_hash"]) not in raw_body

    forbidden_keys = {
        "risk_score", "risk_level", "full_name", "document_number",
        "document_number_hash", "officer_notes", "recommendation",
        "status", "country", "officer_decision"
    }
    assert forbidden_keys.isdisjoint(res.json().keys())


def test_public_verification_page_is_served_standalone_with_no_auth():
    """
    The standalone verification page (app/static/verify/index.html) must be
    reachable with a bare, credential-free request -- it's the whole point
    of a no-login public page -- and must actually call the anchor-proof
    endpoint rather than some other path.
    """
    res = client.get("/verify/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "/api/audit/anchor-proof/" in res.text


def test_biometrics_purge_protocol():
    # Execute a demo scenario to create fresh case
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    # Trigger biometrics purge (requires officer auth -- see
    # test_purge_biometrics_rejects_unauthenticated_requests for the
    # rejection path)
    purge_res = client.post(f"/api/cases/{case_id}/purge-biometrics", headers=OFFICER_AUTH_HEADERS)
    assert purge_res.status_code == 200
    pdata = purge_res.json()
    assert pdata["biometrics_purged"] is True
    assert pdata["case_id"] == case_id
    assert len(pdata["audit_hash"]) == 64

    # Verify case reflects purged biometrics
    case_res = client.get(f"/api/cases/{case_id}")
    assert case_res.status_code == 200
    cdata = case_res.json()
    assert cdata["biometrics_purged"] is True
    assert cdata["analyses"][0]["biometrics_purged"] is True
    assert cdata["analyses"][0]["document_image_path"] == "[PURGED_PRIVACY_COMPLIANCE]"

def test_biometrics_purge_deletes_the_face_embedding_gallery_entry():
    """
    A stored gallery embedding IS raw biometric data -- arguably more
    sensitive than the photo it came from, since it's already in matchable
    form -- so the purge protocol must delete it outright, not just leave
    it sitting in the gallery where it could still match a future
    screening after the case's own biometrics are supposedly gone.
    """
    from app.core.database import SessionLocal
    from app.models import FaceEmbeddingGallery

    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "duplicate_identity"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    db = SessionLocal()
    try:
        assert db.query(FaceEmbeddingGallery).filter(FaceEmbeddingGallery.case_id == case_id).count() == 1
    finally:
        db.close()

    purge_res = client.post(f"/api/cases/{case_id}/purge-biometrics", headers=OFFICER_AUTH_HEADERS)
    assert purge_res.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(FaceEmbeddingGallery).filter(FaceEmbeddingGallery.case_id == case_id).count() == 0
    finally:
        db.close()


def test_delete_case_cascades_to_the_face_embedding_gallery_entry():
    from app.core.database import SessionLocal
    from app.models import FaceEmbeddingGallery

    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "duplicate_identity"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    db = SessionLocal()
    try:
        assert db.query(FaceEmbeddingGallery).filter(FaceEmbeddingGallery.case_id == case_id).count() == 1
    finally:
        db.close()

    delete_res = client.delete(f"/api/cases/{case_id}", headers=OFFICER_AUTH_HEADERS)
    assert delete_res.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(FaceEmbeddingGallery).filter(FaceEmbeddingGallery.case_id == case_id).count() == 0
    finally:
        db.close()


def test_purge_biometrics_rejects_unauthenticated_requests():
    """
    Biometric purge is an irreversible, privacy-critical action (permanently
    deletes the document scan, live face capture, and biometric crops from
    disk). Before this fix it had no auth check at all -- any request, with
    no credential whatsoever, could trigger it. A request with no (or a
    wrong) X-API-Key must be rejected, and the case's biometrics must be
    left untouched.
    """
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    with _no_officer_auth():
        no_auth_res = client.post(f"/api/cases/{case_id}/purge-biometrics")
        assert no_auth_res.status_code == 401

        wrong_auth_res = client.post(
            f"/api/cases/{case_id}/purge-biometrics",
            headers={"Authorization": "Bearer definitely-not-a-real-token"},
        )
        assert wrong_auth_res.status_code == 401

    # Confirm the rejected requests didn't actually purge anything.
    case_res = client.get(f"/api/cases/{case_id}")
    assert case_res.json()["biometrics_purged"] is False

    # A real logged-in officer must still be able to perform the action --
    # this isn't rejecting everything indiscriminately.
    ok_res = client.post(f"/api/cases/{case_id}/purge-biometrics")
    assert ok_res.status_code == 200

def test_delete_case_rejects_unauthenticated_requests():
    """
    Case deletion is permanent and unrecoverable. Before this fix it had no
    auth check at all. A request with no (or an invalid) session must be
    rejected, and the case must still exist afterward.
    """
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    with _no_officer_auth():
        no_auth_res = client.delete(f"/api/cases/{case_id}")
        assert no_auth_res.status_code == 401

        wrong_auth_res = client.delete(
            f"/api/cases/{case_id}", headers={"Authorization": "Bearer definitely-not-a-real-token"}
        )
        assert wrong_auth_res.status_code == 401

    # Confirm the case still exists.
    case_res = client.get(f"/api/cases/{case_id}")
    assert case_res.status_code == 200

    # A real logged-in officer must still be able to perform the action.
    ok_res = client.delete(f"/api/cases/{case_id}")
    assert ok_res.status_code == 200
    assert client.get(f"/api/cases/{case_id}").status_code == 404

def test_update_policy_rejects_unauthenticated_requests():
    """
    The risk engine's live weights/thresholds directly control every case's
    LOW/MEDIUM/HIGH/CRITICAL classification (risk_engine.py reads them
    straight off the policy row) -- before this fix, POST /settings/policy
    had no auth check at all, unlike the case-deletion and biometric-purge
    routes, which already require officer auth for comparable-severity
    actions. A request with no (or a wrong) X-API-Key must be rejected, and
    the stored policy must be left untouched.
    """
    from app.core.database import SessionLocal
    from app.services.policy_service import get_policy

    db = SessionLocal()
    try:
        before = get_policy(db)
        before_threshold_low = before.threshold_low
    finally:
        db.close()

    hostile_policy = {
        "weight_mrz": 0.05, "weight_tamper": 0.05, "weight_face": 0.05,
        "weight_consistency": 0.05, "weight_watchlist": 0.80,
        "threshold_low": 99, "threshold_medium": 99.5, "threshold_high": 99.9
    }

    with _no_officer_auth():
        no_auth_res = client.post("/api/settings/policy", json=hostile_policy)
        assert no_auth_res.status_code == 401

        wrong_auth_res = client.post(
            "/api/settings/policy",
            json=hostile_policy,
            headers={"Authorization": "Bearer definitely-not-a-real-token"},
        )
        assert wrong_auth_res.status_code == 401

    # Confirm the rejected requests didn't actually change the live policy.
    db = SessionLocal()
    try:
        after = get_policy(db)
        assert after.threshold_low == before_threshold_low
    finally:
        db.close()

    # The correct key must still be able to perform the action -- this
    # isn't rejecting everything indiscriminately.
    ok_res = client.post("/api/settings/policy", json=hostile_policy, headers=OFFICER_AUTH_HEADERS)
    assert ok_res.status_code == 200

    # Restore defaults so later tests in this module aren't affected.
    client.post("/api/settings/policy", json={
        "weight_mrz": 0.25, "weight_tamper": 0.30, "weight_face": 0.30,
        "weight_consistency": 0.10, "weight_watchlist": 0.05,
        "threshold_low": 24, "threshold_medium": 49, "threshold_high": 74
    }, headers=OFFICER_AUTH_HEADERS)

def test_cors_does_not_reflect_arbitrary_origins():
    """
    ALLOWED_ORIGINS previously included a bare "*" alongside explicit
    origins, with allow_credentials=True on the CORS middleware. Starlette's
    documented behavior in that combination is to reflect whatever Origin
    header the request actually sent instead of a literal "*" -- verified
    against the real running server with a fake origin before this was
    fixed, which made the explicit allowlist meaningless. Locks in that an
    arbitrary origin no longer gets echoed back.
    """
    response = client.get("/api/health", headers={"Origin": "http://evil.example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"

def test_update_policy_service_rejects_bad_weights_even_bypassing_the_route():
    """
    The weights-sum-to-100% check used to live only in the API route, not in
    update_policy() itself -- so any other future caller of the service
    function would silently write an inconsistent policy row with no error.
    Calling the service directly (bypassing the route's own validation
    entirely) must still reject a bad payload and must not mutate the
    stored policy.
    """
    from app.core.database import SessionLocal
    from app.services.policy_service import get_policy, update_policy, PolicyValidationError

    db = SessionLocal()
    try:
        before = get_policy(db)
        before_weights = (
            before.weight_mrz, before.weight_tamper, before.weight_face,
            before.weight_consistency, before.weight_watchlist
        )

        with pytest.raises(PolicyValidationError):
            update_policy(
                db,
                weight_mrz=0.9, weight_tamper=0.9, weight_face=0.9,
                weight_consistency=0.1, weight_watchlist=0.05,
                threshold_low=before.threshold_low,
                threshold_medium=before.threshold_medium,
                threshold_high=before.threshold_high,
            )

        db.rollback()
        after = get_policy(db)
        after_weights = (
            after.weight_mrz, after.weight_tamper, after.weight_face,
            after.weight_consistency, after.weight_watchlist
        )
        assert after_weights == before_weights
    finally:
        db.close()

def test_face_result_reports_its_own_real_match_threshold():
    """
    The frontend used to hardcode "Threshold: 70.0%" in two places (the
    case-detail Face tab and the PDF report) while the actual verification
    threshold in face_service.py was 0.72 -- a real, judge-visible
    discrepancy found while double-checking these exact numbers. The API
    must report the real threshold it actually used, so the UI can display
    it instead of a value someone has to remember to keep in sync by hand.
    """
    demo_res = client.post("/api/demo/scenario", json={"scenario_key": "genuine"})
    assert demo_res.status_code == 200
    case_id = demo_res.json()["case_id"]

    detail = client.get(f"/api/cases/{case_id}").json()
    face_result = detail["analyses"][0]["face_result"]
    assert face_result["match_threshold"] == pytest.approx(0.72)
    is_match = face_result["similarity"] >= face_result["match_threshold"]
    assert (face_result["status"] == "MATCH") == is_match

def test_aadhaar_document_never_gets_a_fabricated_mrz(tmp_path):
    """
    Reproduces a real failure found by running an actual e-Aadhaar
    screenshot through the live app: both MRZ scanners key off a generic
    "long line containing '<'" shape heuristic, and a real Aadhaar page's
    English disclaimer paragraph (or QR/signature block) garbled into text
    that satisfied it -- producing a fabricated MRZ whose checksums then
    "failed" against a genuine, unaltered card, flagging it as forged.

    Exercises the actual /ocr and /validate routes (not just the service
    functions directly), injecting a document whose OCR result claims to be
    Aadhaar but whose raw lines are deliberately MRZ-shaped noise -- the
    exact bug shape -- and asserts no MRZ data or MRZ signal ever surfaces.
    """
    from PIL import Image
    from app.core.database import SessionLocal
    from app.models import DocumentAnalysis

    img_path = tmp_path / "aadhaar.jpg"
    Image.new("RGB", (100, 100), "white").save(img_path)

    upload_resp = client.post(
        "/api/screening/upload",
        files={"file": ("aadhaar.jpg", open(img_path, "rb"), "image/jpeg")},
        data={"document_type": "Aadhaar", "country": "India"},
    )
    assert upload_resp.status_code == 200
    case_id = upload_resp.json()["case_id"]

    # Simulate the real failure directly: OCR correctly identified this as
    # Aadhaar, but MRZ-shaped noise (mirroring the garbled disclaimer text
    # observed live) is present in both the dedicated MRZ-band pass output
    # and the general whole-document line list.
    fake_mrz_line_1 = "BIRTHITSHOULDBEUSEDONLYWITHVERIF<ONLI"
    fake_mrz_line_2 = "AUTHENTICATIONORSCANNINGOFQRCODEO<<<<"
    db = SessionLocal()
    try:
        analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
        analysis.ocr_result = {
            "raw_text": "Government of India\nRavi Kumar\n" + fake_mrz_line_1 + "\n" + fake_mrz_line_2,
            "fields": {
                "full_name": "Ravi Kumar",
                "document_number": "123456789012",
                "nationality": "INDIA",
                "country": "INDIA",
                "date_of_birth": "01/01/2000",
                "date_of_issue": None,
                "date_of_expiry": None,
                "sex": "M",
                "document_type": "AADHAAR",
            },
            "confidence": 0.9,
            "detected_lines": ["Government of India", "Ravi Kumar", fake_mrz_line_1, fake_mrz_line_2],
            "mrz_lines": [fake_mrz_line_1, fake_mrz_line_2],
        }
        db.commit()
    finally:
        db.close()

    validate_resp = client.post(f"/api/screening/{case_id}/validate")
    assert validate_resp.status_code == 200
    body = validate_resp.json()
    assert body["mrz_result"] is None
    assert not any(
        "MRZ" in c["label"] or "Document Number Inconsistency" in c["label"]
        for c in body["validation_result"]["checks"] if c["status"] == "FAIL"
    )

def test_upload_survives_a_random_case_number_collision(tmp_path, monkeypatch):
    """
    case_number is `f"BM-2026-{random.randint(10000, 99999)}"` with a unique
    DB constraint and, before this fix, no collision handling -- only 90,000
    possible values, so a collision is a real (if individually unlikely)
    possibility as cases accumulate, and previously produced an unhandled
    IntegrityError -> 500 instead of a working upload. Forces a collision
    deterministically by making random.randint always return the same
    value as an existing case's number, and confirms upload still succeeds
    (with a genuinely different, non-colliding case number) rather than
    failing outright.
    """
    import random
    from PIL import Image
    from app.core.database import SessionLocal
    from app.models import Case

    colliding_number_suffix = 54321
    db = SessionLocal()
    try:
        # Idempotent setup: this suite reuses one persistent DB across runs,
        # so a leftover row from a previous run of this same test would
        # otherwise collide with this fixture insert itself.
        db.query(Case).filter(Case.case_number == f"BM-2026-{colliding_number_suffix}").delete()
        db.commit()

        pre_existing = Case(
            case_number=f"BM-2026-{colliding_number_suffix}",
            document_type="Passport",
            country="Unknown",
            status="PROCESSING",
            risk_level="LOW",
            risk_score=0.0,
        )
        db.add(pre_existing)
        db.commit()
    finally:
        db.close()

    call_count = {"n": 0}
    real_randint = random.randint

    def rigged_randint(a, b):
        # First call collides with the pre-existing case; every call after
        # that behaves normally so a retry can actually succeed.
        call_count["n"] += 1
        if call_count["n"] == 1:
            return colliding_number_suffix
        return real_randint(a, b)

    monkeypatch.setattr(random, "randint", rigged_randint)

    img_path = tmp_path / "collision.jpg"
    Image.new("RGB", (100, 100), "white").save(img_path)

    upload_resp = client.post(
        "/api/screening/upload",
        files={"file": ("collision.jpg", open(img_path, "rb"), "image/jpeg")},
        data={"document_type": "Passport", "country": "Unknown"},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["case_number"] != f"BM-2026-{colliding_number_suffix}"
    assert call_count["n"] >= 2


def test_uploaded_document_is_encrypted_on_disk_and_served_decrypted(tmp_path):
    """
    End-to-end check of the encryption-at-rest path through the REAL HTTP
    routes (upload -> GET the returned document_image_url), not just the
    encryption module's own unit tests (test_encryption.py) or a service
    called directly. This is the one thing those tests can't catch: that
    the actual on-disk file under UPLOAD_DIR is ciphertext, and that the
    decrypt-then-stream /uploads route (main.py, replacing the old raw
    StaticFiles mount) actually hands back the original bytes over a real
    request.
    """
    import os
    from PIL import Image

    img_path = tmp_path / "encryption_check.jpg"
    Image.new("RGB", (64, 64), "white").save(img_path)
    with open(img_path, "rb") as f:
        original_bytes = f.read()

    upload_resp = client.post(
        "/api/screening/upload",
        files={"file": ("encryption_check.jpg", open(img_path, "rb"), "image/jpeg")},
        data={"document_type": "Passport", "country": "Unknown"},
    )
    assert upload_resp.status_code == 200
    document_image_url = upload_resp.json()["document_image_url"]

    # The file on disk must NOT be the plaintext JPEG that was uploaded --
    # this is what "encrypted at rest" actually means, checked against the
    # real file the real route wrote, not a mock.
    on_disk_path = os.path.join(settings.UPLOAD_DIR, document_image_url.removeprefix("/uploads/"))
    with open(on_disk_path, "rb") as f:
        on_disk_bytes = f.read()
    assert on_disk_bytes != original_bytes
    assert not on_disk_bytes.startswith(b"\xff\xd8")  # not a plaintext JPEG

    # But fetching it back through the real decrypt-then-stream route must
    # reproduce the exact original bytes -- the whole point of encrypting
    # transparently is that nothing else in the app needs to change.
    fetch_resp = client.get(document_image_url)
    assert fetch_resp.status_code == 200
    assert fetch_resp.content == original_bytes
    assert fetch_resp.headers["content-type"] == "image/jpeg"


def test_uploads_route_rejects_path_traversal():
    """The decrypt-then-stream /uploads route re-implements the
    path-containment check StaticFiles used to provide for free -- confirm
    a "../" segment attempting to escape UPLOAD_DIR is rejected, not
    silently resolved and decrypted."""
    resp = client.get("/uploads/../../app/main.py")
    assert resp.status_code == 404


def test_uploads_route_404s_for_a_nonexistent_file():
    resp = client.get("/uploads/documents/does-not-exist.jpg")
    assert resp.status_code == 404


def test_change_detection_demo_flags_exactly_the_fields_that_were_altered():
    """
    Same-Identity Change Detection demo (app.api.routes.demo.run_change_
    detection_demo): generates two specimens for ONE claimed identity --
    same surname, given names, document number, nationality and issuing
    country in both -- but Version 2 has a different date of birth, date of
    expiry, and portrait photo. Both are generated in mode="genuine", so
    each specimen's own MRZ checksum is independently valid; only comparing
    the two catches the altered fields. This must flag precisely the three
    altered fields as changed and everything else as unchanged -- a diff
    that flagged everything (or nothing) would be useless regardless of
    whether it happened to include the real changes.
    """
    response = client.post("/api/demo/change-detection", json={})
    assert response.status_code == 200
    data = response.json()

    assert data["identity"]["surname"] == "OKAFOR"
    assert data["identity"]["given_names"] == "CHIDI"

    # Both submissions must independently pass MRZ checksum validation --
    # the whole point of this scenario is that checksum validation alone
    # can't tell them apart.
    assert data["v1"]["mrz_checksum_valid"] is True
    assert data["v2"]["mrz_checksum_valid"] is True

    diffs = {d["field"]: d for d in data["field_diffs"]}
    for unchanged_field in ["document_number", "surname", "given_names", "nationality", "country"]:
        assert diffs[unchanged_field]["changed"] is False, f"{unchanged_field} should be unchanged"

    for changed_field in ["birth_date", "expiry_date"]:
        assert diffs[changed_field]["changed"] is True, f"{changed_field} should be flagged as changed"
        assert diffs[changed_field]["v1_value"] != diffs[changed_field]["v2_value"]
        assert diffs[changed_field]["severity"] == "HIGH"

    assert diffs["portrait"]["changed"] is True
    assert data["portrait_comparison"]["status"] == "PORTRAIT_CHANGED"
    assert data["portrait_comparison"]["v1_portrait_url"]
    assert data["portrait_comparison"]["v2_portrait_url"]

    assert set(data["changed_fields"]) == {"Date of Birth", "Date of Expiry", "Portrait Photo"}
    assert data["changed_field_count"] == 3

    # Both rendered specimen images must actually be fetchable (decrypted
    # transparently through /uploads, same as every other demo artifact).
    for version in ["v1", "v2"]:
        img_resp = client.get(data[version]["document_image_url"])
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"] == "image/jpeg"


def test_dpdp_compliance_status_reflects_real_backend_state():
    """
    The DPDP compliance dashboard (app.api.routes.compliance) is a pure
    read-only view over state that already exists elsewhere -- no new write
    path, no new data model. Every number it returns must be independently
    reproducible by querying the same tables directly, not something the
    endpoint computes differently or fabricates. This also deliberately
    does NOT assert audit_chain.valid is True: earlier tests in this same
    module (test_case_deletion_requires_officer_auth and friends) delete
    cases via DELETE /api/cases/{id}, which -- per KNOWN_LIMITATIONS.md #12
    -- permanently breaks /api/audit/verify for the whole ledger with no
    repair path. The endpoint reporting that honestly (whatever the current
    real value is) is the correct behavior, not something to paper over by
    asserting a specific value here.
    """
    from app.core.database import SessionLocal
    from app.models import Case, AuditLog
    from app.services.audit_service import AuditService

    res = client.get("/api/compliance/dpdp-status")
    assert res.status_code == 200
    data = res.json()

    db = SessionLocal()
    try:
        real_total_cases = db.query(Case).count()
        real_hashed_cases = db.query(Case).filter(Case.document_number_hash.isnot(None)).count()
        real_purged_cases = db.query(Case).filter(Case.biometrics_purged.is_(True)).count()
        real_purge_events = db.query(AuditLog).filter(AuditLog.action == "BIOMETRICS_PURGED").count()
        real_chain = AuditService.verify_chain(db)
    finally:
        db.close()

    assert data["identifier_hashing"]["total_cases"] == real_total_cases
    assert data["identifier_hashing"]["cases_with_hashed_identifier"] == real_hashed_cases

    assert data["biometric_purge"]["cases_purged"] == real_purged_cases
    assert data["biometric_purge"]["total_cases"] == real_total_cases
    assert data["biometric_purge"]["audit_events_logged"] == real_purge_events

    assert data["audit_chain"]["valid"] == real_chain["valid"]
    assert data["audit_chain"]["total_records"] == real_chain["total_records"]
    assert data["audit_chain"]["reason"] == real_chain["reason"]

    # Structural/static facts -- not numbers, but must not be silently empty.
    assert "Fernet" in data["encryption"]["algorithm"]
    assert isinstance(data["encryption"]["using_default_demo_key"], bool)
    assert "SHA-256" in data["identifier_hashing"]["algorithm"]
    assert len(data["access_control"]["authentication_required_for"]) > 0
    assert len(data["known_gaps"]) > 0
    assert any("audit" in gap["gap"].lower() for gap in data["known_gaps"])

