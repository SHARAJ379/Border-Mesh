import os
import time
import random
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db, get_current_officer
from app.core.config import settings
from app.core.security import validate_image_upload, sanitize_filename, hash_identifier
from app.core.encryption import write_encrypted_file, encrypt_file_in_place, decrypted_tempfile
from app.models import Case, DocumentAnalysis, RiskCheck, AuditLog, Officer
from app.services.ocr_service import get_ocr_service, TesseractOCRService
from app.services.mrz_service import MRZService
from app.services.rules_engine import DocumentRulesEngine
from app.services.tamper_service import get_tamper_service
from app.services.face_service import get_face_service
from app.services.watchlist_service import get_watchlist_provider
from app.services.identity_gallery_service import IdentityGalleryService
from app.services.risk_engine import get_risk_engine
from app.services.policy_service import get_policy
from app.services.audit_service import AuditService
from app.core.demo_faces import PERSON_A

router = APIRouter(prefix="/screening", tags=["screening"])

# 90,000 possible values (10000-99999) means a collision on case_number's
# unique DB constraint is a real, non-negligible possibility as cases
# accumulate (birthday-paradox growth, not a one-in-90000 flat chance) --
# without a retry, that raised an unhandled IntegrityError straight through
# to the client as an opaque 500 instead of just trying a new number.
MAX_CASE_NUMBER_ATTEMPTS = 5


def _create_case_with_unique_number(db: Session, **case_fields) -> Case:
    """Creates and commits a new Case, retrying with a fresh random
    case_number on a unique-constraint collision."""
    for attempt in range(MAX_CASE_NUMBER_ATTEMPTS):
        case_num = f"BM-2026-{random.randint(10000, 99999)}"
        new_case = Case(case_number=case_num, **case_fields)
        db.add(new_case)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == MAX_CASE_NUMBER_ATTEMPTS - 1:
                raise
            continue
        db.refresh(new_case)
        return new_case
    raise RuntimeError("unreachable")  # loop always returns or raises above


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("Passport"),
    country: str = Form("Unknown"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """
    Step 1 of Screening Pipeline:
    Uploads document image, creates new case record, and records initial audit log.
    """
    contents = await file.read()
    validate_image_upload(file.filename, len(contents), contents)

    # Generate secure filename
    filename = sanitize_filename(file.filename)
    save_path = os.path.join(settings.UPLOAD_DIR, "documents", filename)
    # Encrypted at rest (see app.core.encryption) -- every later re-read of
    # this same path (OCR, tamper, face steps) decrypts it back into a
    # plaintext tempfile first, so this is the only place raw upload bytes
    # ever touch the filesystem.
    write_encrypted_file(save_path, contents)

    # Create Case in DB (case_number e.g. BM-2026-10482, retried on collision)
    new_case = _create_case_with_unique_number(
        db,
        document_type=document_type,
        country=country,
        status="PROCESSING",
        risk_level="LOW",
        risk_score=0.0
    )

    # Create DocumentAnalysis record
    analysis = DocumentAnalysis(
        case_id=new_case.id,
        document_type=document_type,
        document_image_path=save_path
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Audit Trail
    AuditService.log(
        db=db,
        action="DOCUMENT_UPLOADED",
        case_id=new_case.id,
        actor=current_officer.badge_id,
        metadata={
            "filename": file.filename,
            "file_size": len(contents),
            "document_type": document_type
        }
    )

    return {
        "case_id": new_case.id,
        "case_number": new_case.case_number,
        "document_image_url": f"/uploads/documents/{filename}",
        "document_type": document_type,
        "status": new_case.status
    }


@router.post("/{case_id}/ocr")
def process_ocr(case_id: str, db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Step 2: Preprocesses image and runs OCR extraction.
    """
    t0 = time.time()
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
    if not analysis or not analysis.document_image_path:
        raise HTTPException(status_code=404, detail="Document analysis record not found.")

    ocr_svc = get_ocr_service()
    # Decrypts the stored document once into a plaintext tempfile and hands
    # that path to the OCR service, completely unaware encryption exists --
    # reused for both calls below, deleted when this block exits.
    with decrypted_tempfile(analysis.document_image_path) as doc_tmp_path:
        ocr_result = ocr_svc.extract_text(doc_tmp_path)

        # Dedicated MRZ-band OCR pass (crop/upscale/binarize + restricted charset),
        # much more reliable for the small monospace MRZ font than the general
        # whole-document text pass above. Falls back gracefully if unavailable
        # (e.g. MockOCRService, which has no extract_mrz_lines method).
        #
        # Skipped entirely for Aadhaar/PAN/Driving Licence: none of them have an
        # ICAO MRZ by design, so this crops the bottom ~30% of the page looking
        # for one anyway. A real e-Aadhaar PDF/screenshot has a dense English
        # disclaimer paragraph in exactly that band -- observed live to garble
        # into text that still passes the "looks MRZ-shaped" heuristic (long
        # enough, contains '<'), which the MRZ parser then "validates" as a
        # forged passport MRZ with every checksum failing. Running this pass on
        # a document that structurally can't have an MRZ only manufactures false
        # positives.
        if hasattr(ocr_svc, "extract_mrz_lines") and ocr_result.get("fields", {}).get("document_type") not in TesseractOCRService.NON_MRZ_DOCUMENT_TYPES:
            ocr_result["mrz_lines"] = ocr_svc.extract_mrz_lines(doc_tmp_path)
        else:
            ocr_result["mrz_lines"] = []

    elapsed_ms = (time.time() - t0) * 1000.0
    analysis.ocr_result = ocr_result
    analysis.processing_time_ms += elapsed_ms
    db.commit()

    AuditService.log(
        db=db,
        action="OCR_COMPLETED",
        case_id=case_id,
        actor="AI-OCR-ENGINE",
        metadata={"confidence": ocr_result.get("confidence"), "elapsed_ms": round(elapsed_ms, 1)}
    )

    return {
        "case_id": case_id,
        "ocr_result": ocr_result,
        "elapsed_ms": round(elapsed_ms, 1)
    }


@router.post("/{case_id}/validate")
def process_mrz_and_validation(case_id: str, db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Step 3: MRZ Parsing & Document Rules Engine Validation.
    """
    t0 = time.time()
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
    case = db.query(Case).filter(Case.id == case_id).first()
    if not analysis or not case:
        raise HTTPException(status_code=404, detail="Case record not found.")

    ocr_result = analysis.ocr_result or {}
    detected_lines = ocr_result.get("detected_lines", [])
    mrz_lines = ocr_result.get("mrz_lines", [])

    # Aadhaar/PAN/Driving Licence cards have no ICAO MRZ by design -- never
    # attempt to find one, regardless of what either OCR pass turns up. Both
    # MRZ scanners key off a generic "long line containing '<'" shape
    # heuristic, and a real e-Aadhaar page's English disclaimer paragraph
    # (or its QR/signature block) has been observed live to garble into text
    # that satisfies it, producing a fabricated MRZ whose checksums then
    # "fail" against a real, unaltered card. Guarding at this single point
    # (rather than only at the dedicated-pass call site) closes that off no
    # matter which pass -- or any future one -- would have produced the
    # false match.
    if ocr_result.get("fields", {}).get("document_type") in TesseractOCRService.NON_MRZ_DOCUMENT_TYPES:
        mrz_data = None
    else:
        # Prefer the dedicated MRZ-band OCR pass (crop/upscale/restricted-charset --
        # see TesseractOCRService.extract_mrz_lines) over lines from the general
        # whole-document pass, which is tuned for prose text and misreads the MRZ's
        # small monospace font far more often. Lines from the dedicated pass are
        # already isolated, so parse them directly rather than re-scanning.
        mrz_data = (
            MRZService.parse_pre_isolated_lines(mrz_lines)
            if len(mrz_lines) >= 2
            else None
        ) or MRZService.extract_mrz_from_lines(detected_lines)

    # Evaluate Document Rules -- case.country at this point is still
    # whatever the officer selected at upload (the block below is the only
    # place it's ever overwritten, and that happens after this call), so
    # this is the correct "declared" value to cross-check the document
    # against (see RULE 10 in rules_engine.py).
    validation_data = DocumentRulesEngine.evaluate(ocr_result, mrz_data, declared_country=case.country)

    elapsed_ms = (time.time() - t0) * 1000.0
    analysis.mrz_result = mrz_data
    analysis.validation_result = validation_data
    analysis.processing_time_ms += elapsed_ms

    # Update Case country/fields if MRZ found
    if mrz_data:
        if mrz_data.get("country") and case.country in ["Unknown", ""]:
            case.country = mrz_data["country"]
        if mrz_data.get("document_number"):
            case.document_number_hash = hash_identifier(mrz_data["document_number"])
    elif ocr_result.get("fields", {}).get("document_number"):
        case.document_number_hash = hash_identifier(ocr_result["fields"]["document_number"])

    db.commit()

    AuditService.log(
        db=db,
        action="MRZ_VALIDATED",
        case_id=case_id,
        actor="AI-VALIDATION-ENGINE",
        metadata={
            "has_mrz": bool(mrz_data),
            "is_valid": mrz_data.get("is_valid", False) if mrz_data else False,
            "rules_passed": validation_data.get("passed_count", 0),
            "rules_failed": validation_data.get("failed_count", 0)
        }
    )

    return {
        "case_id": case_id,
        "mrz_result": mrz_data,
        "validation_result": validation_data,
        "elapsed_ms": round(elapsed_ms, 1)
    }


@router.post("/{case_id}/tamper")
def process_tamper_analysis(case_id: str, db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Step 4: Forensic Tamper AI (ELA, edge splicing, portrait seam, texture anomalies).
    """
    t0 = time.time()
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
    if not analysis or not analysis.document_image_path:
        raise HTTPException(status_code=404, detail="Document analysis record not found.")

    tamper_svc = get_tamper_service()
    doc_type = (analysis.ocr_result or {}).get("fields", {}).get("document_type")
    with decrypted_tempfile(analysis.document_image_path) as doc_tmp_path:
        tamper_result = tamper_svc.analyze(doc_tmp_path, case_id, document_type=doc_type)

    # tamper_svc.analyze() writes its ELA heatmap directly to this path as
    # plaintext (it has no idea encryption exists) -- encrypt it in place
    # immediately, the same treatment as the source document above.
    heatmap_path = os.path.join(settings.UPLOAD_DIR, "heatmaps", f"{case_id}_tamper_heatmap.jpg")
    if os.path.exists(heatmap_path):
        encrypt_file_in_place(heatmap_path)

    elapsed_ms = (time.time() - t0) * 1000.0
    analysis.tamper_result = tamper_result
    analysis.processing_time_ms += elapsed_ms
    db.commit()

    AuditService.log(
        db=db,
        action="TAMPER_ANALYSIS_COMPLETED",
        case_id=case_id,
        actor="AI-TAMPER-FORENSICS",
        metadata={
            "tamper_risk": tamper_result.get("tamper_risk"),
            "risk_level": tamper_result.get("risk_level"),
            "signals_count": len(tamper_result.get("signals", []))
        }
    )

    return {
        "case_id": case_id,
        "tamper_result": tamper_result,
        "elapsed_ms": round(elapsed_ms, 1)
    }


@router.post("/{case_id}/face")
async def process_face_verification(
    case_id: str,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _officer: Officer = Depends(get_current_officer),
):
    """
    Step 5: Biometric Face Verification between document portrait and live capture.
    """
    t0 = time.time()
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
    if not analysis or not analysis.document_image_path:
        raise HTTPException(status_code=404, detail="Document analysis record not found.")

    live_face_path = None
    if file:
        contents = await file.read()
        validate_image_upload(file.filename, len(contents), contents)
        fname = sanitize_filename(file.filename)
        live_face_path = os.path.join(settings.UPLOAD_DIR, "faces", fname)
        write_encrypted_file(live_face_path, contents)
    else:
        # No custom live image uploaded: auto-simulate a capture. Without a
        # real embedded face here, MTCNN can't detect a face in the
        # hand-drawn avatar fallback at all -- comparing it against the
        # document photo (also a real face since the fix in
        # generate_specimen_doc) would silently produce a meaningless
        # similarity score. Use the same demo person as the document photo
        # so the default (nothing customized) is a genuine MATCH rather
        # than an undetectable non-comparison.
        live_face_path = os.path.join(settings.UPLOAD_DIR, "faces", f"{case_id}_live.jpg")
        from app.utils.synthetic_generator import SyntheticDocumentGenerator
        SyntheticDocumentGenerator.generate_live_face_image(live_face_path, face_photo_path=PERSON_A)
        # The generator (unaware encryption exists) just wrote a plaintext
        # file straight to its final resting place -- convert it in place.
        encrypt_file_in_place(live_face_path)

    analysis.face_image_path = live_face_path

    face_svc = get_face_service()
    with decrypted_tempfile(analysis.document_image_path) as doc_tmp_path, \
         decrypted_tempfile(live_face_path) as live_tmp_path:
        face_result = face_svc.verify(doc_tmp_path, live_tmp_path, case_id)

    # face_svc.verify() writes whichever face crops it managed to extract
    # directly to these paths as plaintext -- encrypt in place whatever it
    # actually produced (not every code path inside it creates both, e.g.
    # NO_FACE_DETECTED/MULTIPLE_FACES branches).
    crops_dir = os.path.join(settings.UPLOAD_DIR, "crops")
    for crop_path in [
        os.path.join(crops_dir, f"{case_id}_doc_face.jpg"),
        os.path.join(crops_dir, f"{case_id}_live_face.jpg"),
    ]:
        if os.path.exists(crop_path):
            encrypt_file_in_place(crop_path)

    elapsed_ms = (time.time() - t0) * 1000.0
    analysis.face_result = face_result
    analysis.processing_time_ms += elapsed_ms
    db.commit()

    AuditService.log(
        db=db,
        action="FACE_VERIFIED",
        case_id=case_id,
        actor="AI-FACE-VERIFIER",
        metadata={
            "similarity": face_result.get("similarity"),
            "status": face_result.get("status")
        }
    )

    return {
        "case_id": case_id,
        "face_result": face_result,
        "elapsed_ms": round(elapsed_ms, 1)
    }


@router.post("/{case_id}/risk")
def process_risk_aggregation(case_id: str, db: Session = Depends(get_db), _officer: Officer = Depends(get_current_officer)):
    """
    Step 6: Central Risk Engine Aggregation & Case File Finalization.
    """
    t0 = time.time()
    case = db.query(Case).filter(Case.id == case_id).first()
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.case_id == case_id).first()
    if not case or not analysis:
        raise HTTPException(status_code=404, detail="Case record not found.")

    # 1. Watchlist Query
    watchlist_provider = get_watchlist_provider()
    mrz_data = analysis.mrz_result or {}
    ocr_data = analysis.ocr_result or {}
    
    full_name = None
    if mrz_data.get("surname"):
        full_name = f"{mrz_data.get('surname')} {mrz_data.get('given_names', '')}".strip()
    elif ocr_data.get("fields", {}).get("full_name"):
        full_name = ocr_data["fields"]["full_name"]

    doc_no = mrz_data.get("document_number") or ocr_data.get("fields", {}).get("document_number")
    watchlist_match = watchlist_provider.check_watchlist(db, full_name, doc_no)
    if watchlist_match:
        # A dedicated audit action, not just RISK_CALCULATED's rolled-up
        # metadata below -- an investigator scanning the audit trail for
        # every watchlist hit across all cases must not have to open each
        # RISK_CALCULATED entry individually and check whether a watchlist
        # signal happened to be among its inputs.
        AuditService.log(
            db=db,
            action="WATCHLIST_HIT",
            case_id=case_id,
            actor="AI-WATCHLIST-ADAPTER",
            metadata={
                "watchlist_id": watchlist_match["entry"]["watchlist_id"],
                "match_field": watchlist_match["match_field"],
                "category": watchlist_match["entry"]["category"],
            }
        )

    # 2. Cross-Case Duplicate Identity Check
    #
    # face_result's live_embedding (see face_service.py) is only present
    # when a live face was actually detected and embedded -- absent for
    # NO_FACE_DETECTED/MULTIPLE_FACES, which already carry their own
    # signals and have nothing to search the gallery with anyway.
    face_result = analysis.face_result or {}
    live_embedding = face_result.get("live_embedding")
    duplicate_identity_match = None
    if live_embedding:
        duplicate_identity_match = IdentityGalleryService.find_gallery_match(
            db, embedding=live_embedding, exclude_case_id=case_id
        )
        IdentityGalleryService.store_gallery_embedding(
            db,
            case_id=case_id,
            case_number=case.case_number,
            full_name=full_name,
            document_number_hash=case.document_number_hash,
            embedding=live_embedding
        )

    # 3. Risk Engine Evaluation
    risk_engine = get_risk_engine(get_policy(db))
    risk_res = risk_engine.calculate(
        mrz_data=analysis.mrz_result,
        validation_data=analysis.validation_result or {},
        tamper_data=analysis.tamper_result or {},
        face_data=analysis.face_result,
        watchlist_match=watchlist_match,
        duplicate_identity_match=duplicate_identity_match,
        duplicate_identity_checked=bool(live_embedding),
    )

    # 4. Update Case
    case.risk_score = risk_res["risk_score"]
    case.risk_level = risk_res["risk_level"]
    case.recommendation = risk_res["recommendation"]
    case.status = f"{risk_res['risk_level']}_RISK" if risk_res["risk_level"] in ["LOW", "MEDIUM"] else ("CRITICAL" if risk_res["risk_level"] == "CRITICAL" else "REQUIRES_REVIEW")
    analysis.risk_breakdown = risk_res["breakdown"]

    # Clear existing checks if re-evaluating, then insert new ones
    db.query(RiskCheck).filter(RiskCheck.case_id == case_id).delete()
    for chk in risk_res["checks"]:
        db.add(RiskCheck(
            case_id=case_id,
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

    elapsed_ms = (time.time() - t0) * 1000.0
    analysis.processing_time_ms += elapsed_ms
    db.commit()
    db.refresh(case)

    AuditService.log(
        db=db,
        action="RISK_CALCULATED",
        case_id=case_id,
        actor="AI-RISK-ENGINE",
        metadata={
            "risk_score": case.risk_score,
            "risk_level": case.risk_level,
            "recommendation": case.recommendation
        }
    )

    return {
        "case_id": case_id,
        "risk_score": case.risk_score,
        "risk_level": case.risk_level,
        "recommendation": case.recommendation,
        "critical_floor_applied": risk_res.get("critical_floor_applied", False),
        "breakdown": risk_res["breakdown"],
        "checks": risk_res["checks"],
        "elapsed_ms": round(elapsed_ms, 1)
    }
