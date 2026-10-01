import os
import re
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.api.deps import get_db, get_current_officer
from app.api.routes.screening import MAX_CASE_NUMBER_ATTEMPTS
from app.core.config import settings
from app.core.encryption import encrypt_file_in_place, decrypted_tempfile
from app.models import Case, DocumentAnalysis, RiskCheck, AuditLog, Officer
from app.utils.synthetic_generator import SyntheticDocumentGenerator
from app.services.ocr_service import get_ocr_service, TesseractOCRService
from app.services.mrz_service import MRZService
from app.services.rules_engine import DocumentRulesEngine
from app.services.tamper_service import get_tamper_service
from app.services.face_service import get_face_service
from app.services.watchlist_service import get_watchlist_provider
from app.services.identity_gallery_service import IdentityGalleryService
from app.services.change_detection_service import ChangeDetectionService
from app.services.risk_engine import get_risk_engine
from app.services.policy_service import get_policy
from app.services.audit_service import AuditService
from app.core.security import hash_identifier
from app.core.demo_faces import PERSON_A, PERSON_B

router = APIRouter(prefix="/demo", tags=["demo"])

SCENARIO_CONFIGS = {
    "genuine": {
        "title": "Genuine Document",
        "mode": "genuine",
        "surname": "KAUL",
        "given_names": "ARIHANT",
        "country_code": "UTO",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "X1234567",
        "nationality": "UTOPIAN",
        "dob": "000101",
        "expiry": "300101",
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "mrz_tampering": {
        "title": "MRZ Tampering",
        "mode": "mrz_tampered",
        "surname": "SHARMA",
        "given_names": "PRIYA",
        "country_code": "UTO",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "P8892144",
        "nationality": "UTOPIAN",
        "dob": "950512",
        "expiry": "281115",
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "photo_replacement": {
        "title": "Photo Replacement",
        "mode": "photo_replaced",
        "surname": "DOE",
        "given_names": "JOHN",
        "country_code": "DEM",
        "country_name": "DEMO STATE",
        "doc_number": "D5512398",
        "nationality": "DEMO CITIZEN",
        "dob": "880320",
        "expiry": "290814",
        # Document photo is Person A; the live subject is Person B -- simulates
        # someone presenting a passport with someone else's photo on it.
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman -- live_face_photo (PERSON_B) is a different person entirely, by design
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_B
    },
    "expired": {
        "title": "Expired Document",
        "mode": "expired",
        "surname": "PATEL",
        "given_names": "ROHAN",
        "country_code": "UTO",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "A9938210",
        "nationality": "UTOPIAN",
        "dob": "921010",
        "expiry": "220101", # Expired in 2022
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "multiple_anomalies": {
        "title": "Multiple Anomalies",
        "mode": "multiple_anomalies",
        "surname": "KOROL",
        "given_names": "VIKTOR",
        "country_code": "ATL",
        "country_name": "ATLANTIS FEDERATION",
        "doc_number": "P8892144", # Matches demo watchlist entry
        "nationality": "ATLANTIAN",
        "dob": "850704",
        "expiry": "270420",
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_B  # mismatch, like photo_replacement
    },
    "watchlist_evasion": {
        "title": "Watchlist Evasion Attempt",
        "mode": "genuine",
        "surname": "KOROL",
        "given_names": "VICTOR",  # 'VIKTOR' -> 'VICTOR': one-letter difference from the watchlist name
        "country_code": "ATL",
        "country_name": "ATLANTIS FEDERATION",
        "doc_number": "P8B92144",  # 'P8892144' -> 'P8B92144': one-character difference (8 -> B)
        "nationality": "ATLANTIAN",
        "dob": "850704",
        "expiry": "300420",
        # Every other signal is deliberately clean (valid MRZ, no tamper, face
        # match) so the demo isolates one thing: a document number and name
        # each a single edit away from a real watchlist entry (WL-SIM-2026-081,
        # "VIKTOR KOROL" / "P8892144") still gets caught. An exact-match-only
        # watchlist check -- what this system had before tonight -- would
        # have missed both and cleared this traveler as LOW risk.
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A
    },
    "pan_card": {
        "title": "PAN Card Verification",
        "mode": "genuine",
        "document_type": "PAN",
        "surname": "VERMA",
        "given_names": "ANANYA",
        "father_name": "RAJESH VERMA",
        "country_name": "INDIA",
        # 5th letter 'V' matches the surname's first letter (the documented
        # convention for individual PANs); 4th letter 'P' decodes as
        # Individual -- see rules_engine.py's PAN_ENTITY_TYPES.
        "doc_number": "ABCPV1234F",
        "dob": "920615",
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "driving_license": {
        "title": "Driving Licence — Expired",
        "mode": "expired",
        "document_type": "DRIVING_LICENSE",
        "surname": "REDDY",
        "given_names": "KIRAN",
        "state_code": "KA",
        "state_name": "KARNATAKA",
        "country_name": "INDIA",
        "doc_number": "KA0320110098765",
        "dob": "880210",
        "issue": "110320",
        "expiry": "310320",  # overridden to a fixed past date by generate_driving_license's 'expired' mode
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "voter_id": {
        "title": "Voter ID (EPIC) Verification",
        "mode": "genuine",
        "document_type": "VOTER_ID",
        "surname": "NAIR",
        "given_names": "ANJALI",
        "relation_name": "SURESH NAIR",
        "country_name": "INDIA",
        "doc_number": "MLD1234567",
        "dob": "970422",
        "sex": "FEMALE",
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "visa": {
        "title": "Travel Visa — Stay Duration Expired",
        "mode": "expired",
        "document_type": "VISA",
        "surname": "MENDEZ",
        "given_names": "CARLOS",
        "nationality": "ATLANTIAN",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "UV1234567",
        "dob": "850314",
        "visa_type": "BUSINESS",
        "entry_validation": "MULTIPLE ENTRY",
        "issue": "260101",
        "stay_duration": "260630",  # overridden to a fixed past date by generate_visa's 'expired' mode
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "permit": {
        "title": "Residence Permit — Expired",
        "mode": "expired",
        "document_type": "PERMIT",
        "surname": "ADEYEMI",
        "given_names": "TOLA",
        "nationality": "ATLANTIAN",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "RP7734210",
        "dob": "910304",
        "permit_type": "RESIDENCE PERMIT",
        "issuing_authority": "REPUBLIC OF UTOPIA IMMIGRATION SERVICE",
        "issue": "240101",
        "expiry": "250101",  # overridden to a fixed past date by generate_permit's 'expired' mode
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A  # same person -> MATCH
    },
    "duplicate_identity": {
        "title": "Duplicate Identity Detection",
        "mode": "genuine",
        "surname": "RAO",
        "given_names": "DEEPAK",
        "country_code": "UTO",
        "country_name": "REPUBLIC OF UTOPIA",
        "doc_number": "P9981234",
        "nationality": "UTOPIAN",
        "dob": "910815",
        "expiry": "300101",
        # Same live face as _DUPLICATE_IDENTITY_PRIOR_CONFIG below (PERSON_A)
        # -- a genuinely different, unrelated name and passport number, but
        # the SAME real underlying person. Everything about THIS document
        # is individually clean (valid MRZ, no tamper, a genuine face match
        # on its own document) -- only the cross-case gallery lookup catches it.
        "sex": "F",  # doc_face_photo (PERSON_A) is a woman
        "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A
    }
}

# Seeded automatically before "duplicate_identity" runs (see run_demo_scenario)
# so its gallery lookup has a genuine prior screening -- under a different
# name and passport number, but the same PERSON_A live face -- to match
# against. Not itself a user-selectable scenario key.
_DUPLICATE_IDENTITY_PRIOR_CONFIG = {
    "title": "Duplicate Identity Detection (Prior Screening)",
    "mode": "genuine",
    "surname": "MEHTA",
    "given_names": "SUNIL",
    "country_code": "UTO",
    "country_name": "REPUBLIC OF UTOPIA",
    "doc_number": "P7723456",
    "nationality": "UTOPIAN",
    "dob": "890210",
    "expiry": "300101",
    "sex": "F",  # doc_face_photo (PERSON_A) is a woman
    "doc_face_photo": PERSON_A, "live_face_photo": PERSON_A
}

# Fixed synthetic identity for the "Same-Identity Change Detection" demo
# (run_change_detection_demo below). Not itself a SCENARIO_CONFIGS entry --
# unlike every scenario above, this flow scores nothing and creates no
# Case/DocumentAnalysis row; it generates TWO specimens for one claimed
# identity and reports which specific fields differ between them, so it
# gets its own dedicated request/response shape instead of squeezing into
# the single-document risk-scoring contract every other scenario shares.
_CHANGE_DETECTION_IDENTITY = {
    "surname": "OKAFOR",
    "given_names": "CHIDI",
    "country_code": "UTO",
    "country_name": "REPUBLIC OF UTOPIA",
    "doc_number": "X7741230",
    "nationality": "UTOPIAN",
}


# Case.document_type / DocumentAnalysis.document_type display labels, keyed
# by the SCENARIO_CONFIGS "document_type" tag (which is also what a real
# OCR pass on the rendered specimen tags itself via
# TesseractOCRService._detect_document_type -- see the fields["document_type"]
# assertions in test_api.py's PAN/DL demo scenario tests). Distinct from
# that tag: this is purely the free-text label shown in the UI, matching
# the style of frontend/src/pages/ScreeningPage.tsx's own dropdown options
# ("Passport", "National ID", "Visa").
DOCUMENT_TYPE_LABELS = {
    "PASSPORT": "Passport",
    "PAN": "PAN",
    "DRIVING_LICENSE": "Driving Licence",
    "VOTER_ID": "Voter ID",
    "VISA": "Travel Visa",
    "PERMIT": "Permit",
}

@router.post("/scenario")
def run_demo_scenario(
    scenario_key: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """
    Executes an end-to-end demonstration scenario with 1-click execution.
    Generates appropriate synthetic document, runs all AI modules, computes risk,
    and returns completed case file.
    """
    key = scenario_key.lower().replace(" ", "_")
    if key not in SCENARIO_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario_key}'. Valid: {list(SCENARIO_CONFIGS.keys())}")

    if key == "duplicate_identity":
        # Seed a prior screening under a different identity, same real
        # face, so this scenario's own gallery lookup has something to
        # match -- run and discarded; only the actual scenario's result
        # (below) is returned to the caller. check_duplicate_identity=True
        # on BOTH calls: every other demo scenario also reuses PERSON_A as
        # its live face purely because a hand-drawn avatar isn't detectable
        # as a face at all (see demo_faces.py) -- checking the gallery for
        # those too would make them spuriously "match" each other and every
        # prior run of this very scenario. Scoping the gallery check to only
        # this scenario pair keeps that stock-photo reuse from being
        # mistaken for a real duplicate signal.
        _execute_scenario(_DUPLICATE_IDENTITY_PRIOR_CONFIG, db, actor=current_officer.badge_id, check_duplicate_identity=True)
        return _execute_scenario(SCENARIO_CONFIGS[key], db, actor=current_officer.badge_id, check_duplicate_identity=True)

    return _execute_scenario(SCENARIO_CONFIGS[key], db, actor=current_officer.badge_id)


def _execute_scenario(cfg: Dict[str, Any], db: Session, actor: str = "OFFICER-DEMO-01", check_duplicate_identity: bool = False) -> Dict[str, Any]:
    case_uid = str(uuid.uuid4())

    # Specimen filenames are keyed on case_uid (a full UUID4, already
    # collision-proof) rather than the shorter, human-facing case_number
    # below -- so a case_number collision (see _generate_unique_case_number)
    # never has to redo the already-generated specimen images on retry.
    doc_type = cfg.get("document_type", "PASSPORT")
    doc_filename = f"specimen_{case_uid}.jpg"
    doc_path = os.path.join(settings.UPLOAD_DIR, "documents", doc_filename)

    if doc_type == "PAN":
        SyntheticDocumentGenerator.generate_pan_card(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            father_name=cfg["father_name"],
            doc_number=cfg["doc_number"],
            dob_yymmdd=cfg["dob"],
            face_photo_path=cfg["doc_face_photo"]
        )
    elif doc_type == "DRIVING_LICENSE":
        SyntheticDocumentGenerator.generate_driving_license(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            state_code=cfg["state_code"],
            state_name=cfg["state_name"],
            doc_number=cfg["doc_number"],
            dob_yymmdd=cfg["dob"],
            issue_yymmdd=cfg["issue"],
            expiry_yymmdd=cfg["expiry"],
            face_photo_path=cfg["doc_face_photo"]
        )
    elif doc_type == "VOTER_ID":
        SyntheticDocumentGenerator.generate_voter_id_card(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            relation_name=cfg["relation_name"],
            doc_number=cfg["doc_number"],
            dob_yymmdd=cfg["dob"],
            sex=cfg["sex"],
            face_photo_path=cfg["doc_face_photo"]
        )
    elif doc_type == "VISA":
        SyntheticDocumentGenerator.generate_visa(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            nationality=cfg["nationality"],
            doc_number=cfg["doc_number"],
            dob_yymmdd=cfg["dob"],
            visa_type=cfg["visa_type"],
            entry_validation=cfg["entry_validation"],
            issue_yymmdd=cfg["issue"],
            stay_duration_yymmdd=cfg["stay_duration"],
            face_photo_path=cfg["doc_face_photo"]
        )
    elif doc_type == "PERMIT":
        SyntheticDocumentGenerator.generate_permit(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            nationality=cfg["nationality"],
            doc_number=cfg["doc_number"],
            permit_type=cfg["permit_type"],
            issuing_authority=cfg["issuing_authority"],
            dob_yymmdd=cfg["dob"],
            issue_yymmdd=cfg["issue"],
            expiry_yymmdd=cfg["expiry"],
            face_photo_path=cfg["doc_face_photo"]
        )
    else:
        SyntheticDocumentGenerator.generate_document(
            out_path=doc_path,
            mode=cfg["mode"],
            surname=cfg["surname"],
            given_names=cfg["given_names"],
            country_code=cfg["country_code"],
            country_name=cfg["country_name"],
            doc_number=cfg["doc_number"],
            nationality=cfg["nationality"],
            dob_yymmdd=cfg["dob"],
            expiry_yymmdd=cfg["expiry"],
            # Every scenario's doc_face_photo is PERSON_A (a woman) -- "sex"
            # used to default to generate_document's own "M" regardless,
            # printing SEX/SEXE: M and encoding "M" into the MRZ next to a
            # photo of a woman. Each scenario below now states the sex that
            # actually matches its own doc_face_photo explicitly.
            sex=cfg.get("sex", "F"),
            face_photo_path=cfg["doc_face_photo"]
        )

    # Generate live face file
    live_filename = f"live_{case_uid}.jpg"
    live_path = os.path.join(settings.UPLOAD_DIR, "faces", live_filename)
    SyntheticDocumentGenerator.generate_live_face_image(live_path, face_photo_path=cfg["live_face_photo"])

    # The generator (unaware encryption exists) just wrote both files as
    # plaintext straight to their final resting places -- convert both to
    # ciphertext in place before anything else touches them.
    encrypt_file_in_place(doc_path)
    encrypt_file_in_place(live_path)

    # Create Case (case_number retried on the rare unique-constraint
    # collision -- see screening.py's _create_case_with_unique_number for
    # why this matters; a much larger 16^5 space than the manual-upload
    # flow's 90,000, but not zero).
    case_num = None
    for attempt in range(MAX_CASE_NUMBER_ATTEMPTS):
        case_num = f"BM-2026-{uuid.uuid4().hex[:5].upper()}"
        new_case = Case(
            id=case_uid,
            case_number=case_num,
            document_type=DOCUMENT_TYPE_LABELS.get(doc_type, "Passport"),
            country=cfg["country_name"],
            document_number_hash=hash_identifier(cfg["doc_number"]),
            status="PROCESSING",
            risk_level="LOW",
            risk_score=0.0
        )
        db.add(new_case)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            if attempt == MAX_CASE_NUMBER_ATTEMPTS - 1:
                raise

    AuditService.log(db, "DOCUMENT_UPLOADED", case_uid, actor=actor, metadata={"scenario": cfg["title"], "specimen": doc_filename})

    try:
        # Real wall-clock timing per step -- this used to be a hardcoded
        # processing_time_ms=2100.0 below, which fed a fake-looking-real number
        # into the dashboard's "Average Pipeline Latency" KPI for every demo-
        # generated case (the majority of cases in this database). Measuring it
        # for real here matches what the manual screening flow (screening.py)
        # already does per step.
        step_start = time.perf_counter()

        # Steps 2-5 all re-read the two files persisted above, which are now
        # encrypted at rest -- decrypt each once into a plaintext tempfile
        # and reuse it across every step below (all still within this one
        # function/request), rather than decrypting redundantly per step.
        # Neither the OCR/tamper/face services below nor the synthetic
        # generator above have any idea encryption exists; they only ever
        # see a plain filesystem path, exactly as before.
        with decrypted_tempfile(doc_path) as doc_tmp_path, decrypted_tempfile(live_path) as live_tmp_path:
            # Step 2: OCR
            ocr_svc = get_ocr_service()
            ocr_result = ocr_svc.extract_text(doc_tmp_path)
            AuditService.log(db, "OCR_COMPLETED", case_uid, actor="AI-OCR-ENGINE", metadata={"conf": ocr_result.get("confidence")})

            # Step 3: MRZ & Validation -- prefer the dedicated MRZ-band OCR pass (see
            # TesseractOCRService.extract_mrz_lines / MRZService.parse_pre_isolated_lines)
            # over the general whole-document pass, same as the manual screening flow
            # in screening.py; the general pass misreads the small MRZ font far more.
            #
            # Skipped entirely for Aadhaar/PAN/Driving Licence, exactly like
            # screening.py's own equivalent guard: none of them have an ICAO MRZ
            # by design, so scanning the bottom band for one anyway risks
            # fabricating a fake MRZ from the card's own boilerplate/signature
            # text whose checksums then "fail" against a genuine, unaltered
            # card -- corrupting the MRZ risk factor for every PAN/DL demo
            # scenario. This module had no non-passport demo scenario until the
            # PAN/DL specimens below, so this gap was latent but never
            # exercised until now.
            if ocr_result.get("fields", {}).get("document_type") in TesseractOCRService.NON_MRZ_DOCUMENT_TYPES:
                mrz_data = None
            else:
                mrz_lines = ocr_svc.extract_mrz_lines(doc_tmp_path) if hasattr(ocr_svc, "extract_mrz_lines") else []
                mrz_data = (
                    MRZService.parse_pre_isolated_lines(mrz_lines) if len(mrz_lines) >= 2 else None
                ) or MRZService.extract_mrz_from_lines(ocr_result.get("detected_lines", []))
            validation_data = DocumentRulesEngine.evaluate(ocr_result, mrz_data)
            AuditService.log(db, "MRZ_VALIDATED", case_uid, actor="AI-VALIDATION-ENGINE")

            # Step 4: Tamper Forensics
            tamper_svc = get_tamper_service()
            tamper_result = tamper_svc.analyze(doc_tmp_path, case_uid)
            AuditService.log(db, "TAMPER_ANALYSIS_COMPLETED", case_uid, actor="AI-TAMPER-FORENSICS")

            # Step 5: Face Verification
            face_svc = get_face_service()
            face_result = face_svc.verify(doc_tmp_path, live_tmp_path, case_uid)
            AuditService.log(db, "FACE_VERIFIED", case_uid, actor="AI-FACE-VERIFIER")

        # tamper_svc.analyze() and face_svc.verify() each wrote plaintext
        # artifacts (an ELA heatmap, whichever face crops it managed to
        # extract) directly to their final on-disk paths -- neither knows
        # encryption exists. Convert whatever they actually produced (face
        # crops aren't guaranteed on every code path, e.g. NO_FACE_DETECTED).
        heatmap_path = os.path.join(settings.UPLOAD_DIR, "heatmaps", f"{case_uid}_tamper_heatmap.jpg")
        crops_dir = os.path.join(settings.UPLOAD_DIR, "crops")
        for artifact_path in [
            heatmap_path,
            os.path.join(crops_dir, f"{case_uid}_doc_face.jpg"),
            os.path.join(crops_dir, f"{case_uid}_live_face.jpg"),
        ]:
            if os.path.exists(artifact_path):
                encrypt_file_in_place(artifact_path)

        # Step 6: Watchlist, Duplicate Identity & Risk Engine
        full_name = f"{cfg['surname']} {cfg['given_names']}"
        watchlist_provider = get_watchlist_provider()
        watchlist_match = watchlist_provider.check_watchlist(db, full_name, cfg["doc_number"])
        if watchlist_match:
            AuditService.log(
                db, "WATCHLIST_HIT", case_uid, actor="AI-WATCHLIST-ADAPTER",
                metadata={
                    "watchlist_id": watchlist_match["entry"]["watchlist_id"],
                    "match_field": watchlist_match["match_field"],
                    "category": watchlist_match["entry"]["category"],
                }
            )

        # Cross-Case Duplicate Identity Check -- see screening.py's manual-
        # upload equivalent for the same live_embedding/gallery contract.
        # Gated on check_duplicate_identity: every OTHER demo scenario also
        # reuses PERSON_A as its live face (a hand-drawn avatar isn't
        # detectable as a face at all -- see demo_faces.py), so checking
        # the gallery for those too would flag them as spurious duplicates
        # of each other and of past runs of this scenario itself.
        duplicate_identity_match = None
        if check_duplicate_identity:
            live_embedding = face_result.get("live_embedding")
            if live_embedding:
                duplicate_identity_match = IdentityGalleryService.find_gallery_match(
                    db, embedding=live_embedding, exclude_case_id=case_uid
                )
                IdentityGalleryService.store_gallery_embedding(
                    db,
                    case_id=case_uid,
                    case_number=case_num,
                    full_name=full_name,
                    document_number_hash=hash_identifier(cfg["doc_number"]),
                    embedding=live_embedding
                )

        risk_engine = get_risk_engine(get_policy(db))
        risk_res = risk_engine.calculate(
            mrz_data=mrz_data,
            validation_data=validation_data,
            tamper_data=tamper_result,
            face_data=face_result,
            watchlist_match=watchlist_match,
            duplicate_identity_match=duplicate_identity_match,
            duplicate_identity_checked=check_duplicate_identity and bool(face_result.get("live_embedding")),
        )

        total_processing_ms = (time.perf_counter() - step_start) * 1000.0

        # Finalize Case
        new_case.risk_score = risk_res["risk_score"]
        new_case.risk_level = risk_res["risk_level"]
        new_case.recommendation = risk_res["recommendation"]
        new_case.status = f"{risk_res['risk_level']}_RISK" if risk_res["risk_level"] in ["LOW", "MEDIUM"] else ("CRITICAL" if risk_res["risk_level"] == "CRITICAL" else "REQUIRES_REVIEW")

        # Save DocumentAnalysis
        analysis = DocumentAnalysis(
            case_id=case_uid,
            document_type=DOCUMENT_TYPE_LABELS.get(doc_type, "Passport"),
            document_image_path=doc_path,
            face_image_path=live_path,
            ocr_result=ocr_result,
            mrz_result=mrz_data,
            validation_result=validation_data,
            tamper_result=tamper_result,
            face_result=face_result,
            risk_breakdown=risk_res["breakdown"],
            processing_time_ms=round(total_processing_ms, 1)
        )
        db.add(analysis)

        # Save Checks
        for chk in risk_res["checks"]:
            db.add(RiskCheck(
                case_id=case_uid,
                check_key=chk["id"],
                category=chk["category"],
                factor=chk.get("factor"),
                label=chk["label"],
                status=chk["status"],
                severity=chk.get("severity"),
                confidence=chk.get("confidence", 0.9),
                explanation=chk["explanation"],
                evidence=chk.get("evidence"),
                score_impact=chk.get("score_impact", 0.0),
            ))

        db.commit()
        AuditService.log(db, "RISK_CALCULATED", case_uid, actor="AI-RISK-ENGINE", metadata={"score": new_case.risk_score})

        return {
            "case_id": case_uid,
            "case_number": case_num,
            "scenario": cfg["title"],
            "risk_score": new_case.risk_score,
            "risk_level": new_case.risk_level,
            "recommendation": new_case.recommendation,
            "document_image_url": f"/uploads/documents/{doc_filename}",
            "live_face_url": f"/uploads/faces/{live_filename}"
        }
    except Exception:
        # Any failure past this point (OCR/tamper/face engines, risk
        # calculation, etc. -- e.g. a missing Tesseract binary) used to leave
        # the Case committed above stuck at status="PROCESSING",
        # risk_level="LOW", risk_score=0.0 forever: a zombie row that reads
        # exactly like a genuine cleared case in the Review Queue and Cases
        # Archive. Roll back any uncommitted work from this attempt, then
        # delete the case itself (cascades to its already-committed audit
        # entries -- see the delete-orphan relationships on Case) so a
        # failed demo run leaves no trace instead of a fake result.
        db.rollback()
        zombie_case = db.query(Case).filter(Case.id == case_uid).first()
        if zombie_case:
            db.delete(zombie_case)
            db.commit()
        raise


# Matches the jurisdiction dropdown in frontend/src/pages/ScreeningPage.tsx.
# Falls back to deriving a plausible 3-letter code for any other free-text
# country name, since the generator itself accepts arbitrary strings.
KNOWN_COUNTRY_CODES = {
    "REPUBLIC OF UTOPIA": "UTO",
    "DEMO STATE": "DEM",
    "ATLANTIS FEDERATION": "ATL",
    "INDIA": "IND",
    "UNITED KINGDOM": "GBR",
}


def _country_code_for(country_name: str) -> str:
    known = KNOWN_COUNTRY_CODES.get(country_name.strip().upper())
    if known:
        return known
    letters = re.sub(r'[^A-Z]', '', country_name.upper())
    return (letters + "XXX")[:3] if letters else "UTO"


@router.post("/generate-doc")
def generate_specimen_doc(
    mode: str = Body("genuine", embed=True),
    surname: str = Body("KAUL", embed=True),
    given_names: str = Body("ARIHANT", embed=True),
    doc_number: str = Body("X1234567", embed=True),
    country_name: str = Body("REPUBLIC OF UTOPIA", embed=True),
    _officer: Officer = Depends(get_current_officer),
):
    """Utility to generate a download-ready synthetic document."""
    fname = f"specimen_{uuid.uuid4().hex[:6]}.jpg"
    out_path = os.path.join(settings.UPLOAD_DIR, "documents", fname)
    # country_code/nationality previously defaulted to "UTO"/"UTOPIAN"
    # unconditionally (they were never derived from country_name), so any
    # jurisdiction other than the default rendered an internally
    # inconsistent document -- header said e.g. "ATLANTIS FEDERATION" while
    # the printed NATIONALITY field and MRZ country code both said UTO.
    country_code = _country_code_for(country_name)
    info = SyntheticDocumentGenerator.generate_document(
        out_path=out_path,
        mode=mode,
        surname=surname,
        given_names=given_names,
        doc_number=doc_number,
        country_name=country_name,
        country_code=country_code,
        nationality=f"{country_code} CITIZEN",
        # Without a real embedded face, MTCNN can't detect a face in the
        # hand-drawn avatar fallback at all -- face verification against a
        # New Screening-generated specimen would silently compare two
        # undetected avatar crops via a real face model and present a
        # meaningless similarity score as if it were a genuine result. See
        # app.core.demo_faces for why a real (AI-generated) photo is needed.
        face_photo_path=PERSON_A
    )
    # The generator just wrote a plaintext file straight to its final
    # resting place under UPLOAD_DIR -- convert it in place. The frontend's
    # subsequent fetch(url) is served back as plaintext by the decrypting
    # /uploads route in main.py, exactly as before.
    encrypt_file_in_place(out_path)
    return {
        "filename": fname,
        "url": f"/uploads/documents/{fname}",
        "mode": mode,
        "doc_number": doc_number
    }


@router.post("/change-detection")
def run_change_detection_demo(db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Same-Identity Change Detection demo: generates TWO synthetic specimens
    for one claimed identity -- "Version 1" (the original, genuine
    submission) and "Version 2" (a later resubmission of the SAME claimed
    name, document number, nationality and issuing country, but with date
    of birth, date of expiry, and the portrait photo all altered) -- then
    reports exactly which fields differ between them.

    Version 2 is generated in mode="genuine": its MRZ check digits are
    computed fresh for the new (altered) field values, so it validates
    perfectly on its own -- ICAO checksum validation alone cannot tell it
    apart from a legitimate resubmission. What catches it is comparing it
    against the specific values printed on the earlier submission, which is
    the entire point of this scenario.

    Zero real-identity risk: both specimens are the same synthetic
    fictional "REPUBLIC OF UTOPIA" identity this demo module already uses
    everywhere else, generated fresh on every call.
    """
    comparison_id = str(uuid.uuid4())
    identity = _CHANGE_DETECTION_IDENTITY

    v1_filename = f"specimen_{comparison_id}_v1.jpg"
    v2_filename = f"specimen_{comparison_id}_v2.jpg"
    v1_path = os.path.join(settings.UPLOAD_DIR, "documents", v1_filename)
    v2_path = os.path.join(settings.UPLOAD_DIR, "documents", v2_filename)

    # These specific DOB/expiry pairs (not arbitrary) were each verified
    # against a real Tesseract pass to round-trip through OCR -> MRZ parse
    # -> checksum validation without misreads (see _load_font's own
    # docstring on small-glyph rendering artifacts). A few other plausible-
    # looking YYMMDD pairs tried during development produced a genuine OCR
    # misread of the MRZ padding run around specific digit sequences,
    # corrupting the parsed checksum -- an artifact of this rendering/OCR
    # pipeline, not of the change-detection logic being demonstrated here.
    # 950512/281115 for v2 already appears elsewhere in this module (the
    # "mrz_tampering" scenario's SHARMA identity), so it's proven twice over.
    SyntheticDocumentGenerator.generate_document(
        out_path=v1_path,
        mode="genuine",
        surname=identity["surname"],
        given_names=identity["given_names"],
        country_code=identity["country_code"],
        country_name=identity["country_name"],
        doc_number=identity["doc_number"],
        nationality=identity["nationality"],
        dob_yymmdd="880610",
        expiry_yymmdd="300101",
        face_photo_path=PERSON_A
    )
    SyntheticDocumentGenerator.generate_document(
        out_path=v2_path,
        mode="genuine",
        surname=identity["surname"],
        given_names=identity["given_names"],
        country_code=identity["country_code"],
        country_name=identity["country_name"],
        doc_number=identity["doc_number"],
        nationality=identity["nationality"],
        dob_yymmdd="950512",
        expiry_yymmdd="281115",
        face_photo_path=PERSON_B
    )

    # Both generator calls above wrote plaintext straight to their final
    # resting places under UPLOAD_DIR -- encrypt in place before anything
    # else touches them, matching every other demo/screening flow.
    encrypt_file_in_place(v1_path)
    encrypt_file_in_place(v2_path)

    AuditService.log(
        db, "CHANGE_DETECTION_DEMO_STARTED", None, actor="OFFICER-DEMO-01",
        metadata={"identity": f"{identity['surname']} {identity['given_names']}", "document_number": identity["doc_number"]}
    )

    with decrypted_tempfile(v1_path) as v1_tmp, decrypted_tempfile(v2_path) as v2_tmp:
        ocr_svc = get_ocr_service()
        ocr_v1 = ocr_svc.extract_text(v1_tmp)
        ocr_v2 = ocr_svc.extract_text(v2_tmp)

        # Prefer the dedicated MRZ-band OCR pass over the general whole-
        # document pass, same as every other scenario in this module (see
        # _execute_scenario's own comment) -- the general pass misreads the
        # small MRZ font far more.
        mrz_lines_v1 = ocr_svc.extract_mrz_lines(v1_tmp) if hasattr(ocr_svc, "extract_mrz_lines") else []
        mrz_lines_v2 = ocr_svc.extract_mrz_lines(v2_tmp) if hasattr(ocr_svc, "extract_mrz_lines") else []
        mrz_v1 = (
            MRZService.parse_pre_isolated_lines(mrz_lines_v1) if len(mrz_lines_v1) >= 2 else None
        ) or MRZService.extract_mrz_from_lines(ocr_v1.get("detected_lines", []))
        mrz_v2 = (
            MRZService.parse_pre_isolated_lines(mrz_lines_v2) if len(mrz_lines_v2) >= 2 else None
        ) or MRZService.extract_mrz_from_lines(ocr_v2.get("detected_lines", []))

        if not mrz_v1 or not mrz_v2:
            # Report the failure plainly rather than silently diffing two
            # empty field sets, which would misreport as "no changes
            # detected" -- see CLAUDE.md on not letting an unverifiable
            # result stand in for a real one.
            raise HTTPException(
                status_code=500,
                detail="Could not extract a valid MRZ from one or both generated specimens; change detection requires both submissions to parse successfully."
            )

        face_svc = get_face_service()
        portrait_result = face_svc.compare_document_portraits(v1_tmp, v2_tmp, comparison_id)

    # compare_document_portraits wrote whichever crop(s) it managed to
    # produce as plaintext directly to their final path -- encrypt whatever
    # actually exists (a crop isn't guaranteed on every code path, e.g.
    # NO_FACE_DETECTED on one side).
    crops_dir = os.path.join(settings.UPLOAD_DIR, "crops")
    for artifact_path in [
        os.path.join(crops_dir, f"{comparison_id}_v1_portrait.jpg"),
        os.path.join(crops_dir, f"{comparison_id}_v2_portrait.jpg"),
    ]:
        if os.path.exists(artifact_path):
            encrypt_file_in_place(artifact_path)

    field_diffs = ChangeDetectionService.compare_mrz_identity(mrz_v1, mrz_v2)

    portrait_changed = portrait_result.get("status") == "PORTRAIT_CHANGED"
    field_diffs.append({
        "field": "portrait",
        "label": "Portrait Photo",
        "v1_value": "See image",
        "v2_value": "See image",
        "changed": portrait_changed,
        "severity": "HIGH" if portrait_changed else "LOW",
    })

    changed = [d for d in field_diffs if d["changed"]]

    AuditService.log(
        db, "CHANGE_DETECTION_DEMO_COMPLETED", None, actor="AI-CHANGE-DETECTION",
        metadata={
            "identity": f"{identity['surname']} {identity['given_names']}",
            "changed_fields": [d["field"] for d in changed],
            "changed_field_count": len(changed),
        }
    )

    return {
        "comparison_id": comparison_id,
        "identity": {
            "surname": identity["surname"],
            "given_names": identity["given_names"],
            "document_number": identity["doc_number"],
            "country": identity["country_name"],
        },
        "v1": {
            "label": "Version 1 — Original Submission",
            "document_image_url": f"/uploads/documents/{v1_filename}",
            "mrz_checksum_valid": mrz_v1.get("is_valid", False),
            "ocr_confidence": ocr_v1.get("confidence"),
        },
        "v2": {
            "label": "Version 2 — Resubmission",
            "document_image_url": f"/uploads/documents/{v2_filename}",
            "mrz_checksum_valid": mrz_v2.get("is_valid", False),
            "ocr_confidence": ocr_v2.get("confidence"),
        },
        "portrait_comparison": portrait_result,
        "field_diffs": field_diffs,
        "changed_field_count": len(changed),
        "changed_fields": [d["label"] for d in changed],
    }
