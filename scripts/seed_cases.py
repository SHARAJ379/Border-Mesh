import os
import sys
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.core.database import SessionLocal, Base, engine
from app.core.encryption import encrypt_file_in_place
from app.models import Case, DocumentAnalysis, AuditLog
from app.services.audit_service import AuditService
from app.core.security import hash_identifier
from app.utils.synthetic_generator import SyntheticDocumentGenerator

# Each profile carries its own `doc_type` (Passport / National ID / Visa --
# matching the dropdown in frontend/src/pages/ScreeningPage.tsx) and explicit
# `officer_decision` so the Review Queue and Cases Archive tables show a
# realistic mix on first load, instead of every seeded row landing on
# Passport/PENDING and looking like duplicate entries during a demo.
SYNTHETIC_PROFILES = [
    # Low Risk (Genuine) -- mostly already cleared, one still pending review
    # so the queue isn't purely medium/high risk either.
    {"surname": "KAUL", "given": "ARIHANT", "country": "REPUBLIC OF UTOPIA", "code": "UTO", "doc_no": "X1234567", "dob": "000101", "exp": "300101", "sex": "M", "scenario": "genuine", "risk": 12.0, "level": "LOW", "status": "CLEARED", "doc_type": "Passport", "officer_decision": "CLEARED"},
    {"surname": "SHARMA", "given": "PRIYA", "country": "INDIA", "code": "IND", "doc_no": "Z9876543", "dob": "960412", "exp": "291020", "sex": "F", "scenario": "genuine", "risk": 8.5, "level": "LOW", "status": "CLEARED", "doc_type": "National ID", "officer_decision": "CLEARED"},
    {"surname": "SMITH", "given": "EMMA", "country": "UNITED KINGDOM", "code": "GBR", "doc_no": "G5544332", "dob": "940822", "exp": "310515", "sex": "F", "scenario": "genuine", "risk": 14.2, "level": "LOW", "status": "CLEARED", "doc_type": "Passport", "officer_decision": "CLEARED"},
    {"surname": "CHEN", "given": "WEI", "country": "SINGAPORE", "code": "SGP", "doc_no": "E1122334", "dob": "910214", "exp": "320409", "sex": "M", "scenario": "genuine", "risk": 10.0, "level": "LOW", "status": "CLEARED", "doc_type": "Visa", "officer_decision": "CLEARED"},
    {"surname": "GARCIA", "given": "CARLOS", "country": "SPAIN", "code": "ESP", "doc_no": "S4455667", "dob": "891130", "exp": "280718", "sex": "M", "scenario": "genuine", "risk": 15.0, "level": "LOW", "status": "CLEARED", "doc_type": "Passport", "officer_decision": "CLEARED"},
    {"surname": "DUBOIS", "given": "CLAIRE", "country": "FRANCE", "code": "FRA", "doc_no": "F7788990", "dob": "970319", "exp": "301201", "sex": "F", "scenario": "genuine", "risk": 9.5, "level": "LOW", "status": "CLEARED", "doc_type": "National ID", "officer_decision": "CLEARED"},
    {"surname": "MUELLER", "given": "LUKAS", "country": "GERMANY", "code": "DEU", "doc_no": "C3322119", "dob": "930605", "exp": "290325", "sex": "M", "scenario": "genuine", "risk": 11.8, "level": "LOW", "status": "CLEARED", "doc_type": "Passport", "officer_decision": "CLEARED"},
    {"surname": "OKAFOR", "given": "CHIDI", "country": "NIGERIA", "code": "NGA", "doc_no": "N4412897", "dob": "990617", "exp": "310730", "sex": "M", "scenario": "genuine", "risk": 17.5, "level": "LOW", "status": "REQUIRES_REVIEW", "doc_type": "Visa", "officer_decision": "PENDING"},

    # Medium Risk (Sub-optimal photo / OCR anomaly / minor inconsistency)
    {"surname": "TANAKA", "given": "KENJI", "country": "JAPAN", "code": "JPN", "doc_no": "J8877665", "dob": "850915", "exp": "280110", "sex": "M", "scenario": "genuine", "risk": 34.0, "level": "MEDIUM", "status": "REQUIRES_REVIEW", "doc_type": "Passport", "officer_decision": "PENDING"},
    {"surname": "SILVA", "given": "LUCIA", "country": "BRAZIL", "code": "BRA", "doc_no": "B6655443", "dob": "981204", "exp": "270819", "sex": "F", "scenario": "genuine", "risk": 41.5, "level": "MEDIUM", "status": "REQUIRES_REVIEW", "doc_type": "National ID", "officer_decision": "PENDING"},
    {"surname": "KOWALSKI", "given": "PIOTR", "country": "POLAND", "code": "POL", "doc_no": "P2233445", "dob": "900518", "exp": "281112", "sex": "M", "scenario": "genuine", "risk": 29.0, "level": "MEDIUM", "status": "REQUIRES_REVIEW", "doc_type": "Visa", "officer_decision": "REQUIRES_INSPECTION"},
    {"surname": "AHMED", "given": "TARIQ", "country": "UAE", "code": "ARE", "doc_no": "U5566778", "dob": "920725", "exp": "290930", "sex": "M", "scenario": "genuine", "risk": 38.0, "level": "MEDIUM", "status": "REQUIRES_REVIEW", "doc_type": "Passport", "officer_decision": "PENDING"},
    {"surname": "NAKAMURA", "given": "YUKI", "country": "JAPAN", "code": "JPN", "doc_no": "J2231987", "dob": "940812", "exp": "300214", "sex": "F", "scenario": "genuine", "risk": 45.0, "level": "MEDIUM", "status": "CLEARED", "doc_type": "National ID", "officer_decision": "CLEARED"},
    {"surname": "OYELARAN", "given": "ADAEZE", "country": "NIGERIA", "code": "NGA", "doc_no": "N8834521", "dob": "930221", "exp": "290604", "sex": "F", "scenario": "genuine", "risk": 31.5, "level": "MEDIUM", "status": "REQUIRES_REVIEW", "doc_type": "Visa", "officer_decision": "PENDING"},

    # High Risk (MRZ checksum mismatch / altered expiry / photo replaced)
    {"surname": "SHARMA", "given": "PRIYA", "country": "REPUBLIC OF UTOPIA", "code": "UTO", "doc_no": "P8892144", "dob": "950512", "exp": "281115", "sex": "F", "scenario": "mrz_tampered", "risk": 64.5, "level": "HIGH", "status": "REQUIRES_REVIEW", "doc_type": "Passport", "officer_decision": "PENDING"},
    {"surname": "DOE", "given": "JOHN", "country": "DEMO STATE", "code": "DEM", "doc_no": "D5512398", "dob": "880320", "exp": "290814", "sex": "M", "scenario": "photo_replaced", "risk": 72.0, "level": "HIGH", "status": "REQUIRES_REVIEW", "doc_type": "National ID", "officer_decision": "REQUIRES_INSPECTION"},
    {"surname": "ROSSI", "given": "MARCO", "country": "ITALY", "code": "ITA", "doc_no": "I9988771", "dob": "870114", "exp": "290520", "sex": "M", "scenario": "altered_text", "risk": 58.0, "level": "HIGH", "status": "REQUIRES_REVIEW", "doc_type": "Visa", "officer_decision": "PENDING"},
    {"surname": "IVANOV", "given": "ALEXEI", "country": "BULGARIA", "code": "BGR", "doc_no": "N3344556", "dob": "841129", "exp": "280614", "sex": "M", "scenario": "mrz_tampered", "risk": 68.0, "level": "HIGH", "status": "REQUIRES_REVIEW", "doc_type": "Passport", "officer_decision": "REQUIRES_INSPECTION"},
    {"surname": "MENDOZA", "given": "SOFIA", "country": "MEXICO", "code": "MEX", "doc_no": "M6612378", "dob": "911005", "exp": "270228", "sex": "F", "scenario": "altered_text", "risk": 61.0, "level": "HIGH", "status": "REQUIRES_REVIEW", "doc_type": "National ID", "officer_decision": "PENDING"},

    # Critical Risk (Expired documents / Watchlist alerts / Multi-signal tampering)
    {"surname": "PATEL", "given": "ROHAN", "country": "REPUBLIC OF UTOPIA", "code": "UTO", "doc_no": "A9938210", "dob": "921010", "exp": "220101", "sex": "M", "scenario": "expired", "risk": 78.5, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "Passport", "officer_decision": "ESCALATED"},
    {"surname": "KOROL", "given": "VIKTOR", "country": "ATLANTIS FEDERATION", "code": "ATL", "doc_no": "P8892144", "dob": "850704", "exp": "270420", "sex": "M", "scenario": "multiple_anomalies", "risk": 91.0, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "Passport", "officer_decision": "ESCALATED"},
    {"surname": "ROSTOVA", "given": "ELENA", "country": "DEMO STATE", "code": "DEM", "doc_no": "A9938210", "dob": "900909", "exp": "280315", "sex": "F", "scenario": "multiple_anomalies", "risk": 88.0, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "National ID", "officer_decision": "ESCALATED"},
    {"surname": "VANCE", "given": "MARCUS", "country": "REPUBLIC OF UTOPIA", "code": "UTO", "doc_no": "M7744112", "dob": "830412", "exp": "260901", "sex": "M", "scenario": "multiple_anomalies", "risk": 84.5, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "Visa", "officer_decision": "ESCALATED"},
    {"surname": "HANSEN", "given": "ERIK", "country": "DENMARK", "code": "DNK", "doc_no": "D1199228", "dob": "890228", "exp": "210510", "sex": "M", "scenario": "expired", "risk": 76.0, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "Passport", "officer_decision": "ESCALATED"},
    {"surname": "OSEI", "given": "KWAME", "country": "GHANA", "code": "GHA", "doc_no": "G7723451", "dob": "870519", "exp": "220901", "sex": "M", "scenario": "expired", "risk": 81.0, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "National ID", "officer_decision": "PENDING"},
    {"surname": "KARIMOVA", "given": "DILNOZA", "country": "UZBEKISTAN", "code": "UZB", "doc_no": "U9981223", "dob": "950128", "exp": "260817", "sex": "F", "scenario": "multiple_anomalies", "risk": 86.5, "level": "CRITICAL", "status": "ESCALATED", "doc_type": "Visa", "officer_decision": "ESCALATED"},
]

def seed_initial_cases(db=None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        now = datetime.utcnow()
        for idx, p in enumerate(SYNTHETIC_PROFILES):
            case_uid = str(uuid.uuid4())
            case_num = f"BM-2026-{10020 + idx}"
            created_time = now - timedelta(hours=random.randint(1, 72), minutes=random.randint(5, 50))

            doc_fname = f"seed_{case_num}.jpg"
            doc_path = os.path.join(settings.UPLOAD_DIR, "documents", doc_fname)
            
            # Generate specimen image
            SyntheticDocumentGenerator.generate_document(
                out_path=doc_path,
                mode=p["scenario"],
                surname=p["surname"],
                given_names=p["given"],
                country_code=p["code"],
                country_name=p["country"],
                doc_number=p["doc_no"],
                nationality=f"{p['code']} CITIZEN",
                dob_yymmdd=p["dob"],
                expiry_yymmdd=p["exp"],
                sex=p["sex"]
            )
            # generate_document() (unaware encryption exists, same as every
            # other caller of it -- screening.py, demo.py) just wrote a
            # plaintext JPEG straight to doc_path. Every other seeded-case
            # write site in this app converts to ciphertext immediately
            # after generation; this one didn't, which left every startup-
            # seeded case's document image as a plaintext file under
            # UPLOAD_DIR and made it un-fetchable through main.py's
            # decrypt-on-read /uploads route (InvalidToken trying to
            # Fernet-decrypt a plain JPEG) -- see
            # backend/tests/test_seed_cases.py's own regression test for
            # this exact bug.
            encrypt_file_in_place(doc_path)

            # Recommendations
            rec_map = {
                "LOW": "CLEAR FOR ENTRY — Routine processing permitted",
                "MEDIUM": "ROUTINE VERIFICATION — Officer visual confirmation recommended",
                "HIGH": "SECONDARY INSPECTION — Multiple document risk indicators detected",
                "CRITICAL": "SUPERVISOR ESCALATION — Significant anomalies requiring physical document review"
            }

            c = Case(
                id=case_uid,
                case_number=case_num,
                created_at=created_time,
                updated_at=created_time,
                document_type=p["doc_type"],
                document_number_hash=hash_identifier(p["doc_no"]),
                country=p["country"],
                risk_score=p["risk"],
                risk_level=p["level"],
                recommendation=rec_map[p["level"]],
                status=p["status"],
                officer_decision=p["officer_decision"],
                officer_notes="Synthetic demonstration case generated for SIH 2026." if p["level"] != "LOW" else "Verified genuine document."
            )
            db.add(c)

            # DocumentAnalysis record
            da = DocumentAnalysis(
                case_id=case_uid,
                document_type=p["doc_type"],
                document_image_path=doc_path,
                processing_time_ms=round(random.uniform(1800, 3200), 1),
                ocr_result={
                    "raw_text": f"{p['doc_type'].upper()} {p['country']}\n{p['surname']} {p['given']}\nDOC NO: {p['doc_no']}\nDOB: {p['dob']}\nEXPIRY: {p['exp']}",
                    "fields": {
                        "full_name": f"{p['surname']} {p['given']}",
                        "document_number": p["doc_no"],
                        "country": p["country"],
                        "nationality": p["code"],
                        "sex": p["sex"]
                    },
                    "confidence": 0.95 if p["level"] == "LOW" else 0.82
                },
                mrz_result={
                    "format": "TD3",
                    "line1": f"P<{p['code']}{p['surname']}<<{p['given']}".ljust(44, '<')[:44],
                    "line2": f"{p['doc_no'].ljust(9, '<')}8{p['code']}{p['dob']}1{p['sex']}{p['exp']}2<<<<<<<<<<<<<<02",
                    "document_number": p["doc_no"],
                    "is_valid": p["scenario"] not in ["mrz_tampered", "multiple_anomalies"]
                },
                validation_result={
                    "passed_count": 5 if p["level"] == "LOW" else 3,
                    "failed_count": 0 if p["level"] == "LOW" else 2,
                    "rules_detail": [
                        {"rule": "MRZ_CHECKSUM", "passed": p["scenario"] != "mrz_tampered", "severity": "HIGH", "explanation": "MRZ check digit validation.", "confidence": 0.99},
                        {"rule": "DOCUMENT_EXPIRATION", "passed": p["scenario"] != "expired", "severity": "CRITICAL", "explanation": "Validity period check.", "confidence": 0.99}
                    ]
                },
                tamper_result={
                    "tamper_risk": round(p["risk"] / 100.0, 2),
                    "risk_level": p["level"],
                    "signals": [
                        {"type": "compression_anomaly", "confidence": 0.85, "explanation": "Recompression artifact."}
                    ] if p["level"] in ["HIGH", "CRITICAL"] else []
                },
                face_result={
                    "similarity": 0.88 if p["scenario"] != "photo_replaced" else 0.42,
                    "status": "MATCH" if p["scenario"] != "photo_replaced" else "REVIEW_REQUIRED"
                }
            )
            db.add(da)

            # Audit logs
            AuditService.log(db, "DOCUMENT_UPLOADED", case_uid, actor="OFFICER-DEMO-01", metadata={"specimen": doc_fname})
            AuditService.log(db, "OCR_COMPLETED", case_uid, actor="AI-OCR-ENGINE")
            AuditService.log(db, "MRZ_VALIDATED", case_uid, actor="AI-VALIDATION-ENGINE")
            AuditService.log(db, "TAMPER_ANALYSIS_COMPLETED", case_uid, actor="AI-TAMPER-FORENSICS")
            AuditService.log(db, "RISK_CALCULATED", case_uid, actor="AI-RISK-ENGINE", metadata={"score": p["risk"]})

        db.commit()
        print(f"Successfully seeded {len(SYNTHETIC_PROFILES)} synthetic demonstration cases.")
    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_initial_cases()
