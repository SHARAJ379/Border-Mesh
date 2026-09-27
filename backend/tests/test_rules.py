from datetime import date
from app.services.rules_engine import DocumentRulesEngine


def _find(checks, check_id):
    return next(c for c in checks if c["id"] == check_id)


def _fails(checks):
    return [c for c in checks if c["status"] == "FAIL"]


def test_document_rules_genuine():
    ocr_data = {
        "fields": {
            "full_name": "ARIHANT KAUL",
            "document_number": "X1234567",
            "country": "UTOPIA",
            "nationality": "UTOPIA"
        }
    }
    mrz_data = {
        "surname": "KAUL",
        "given_names": "ARIHANT",
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101", # Year 2030, in future
        "checksums": [
            {"field": "Document Number Checksum", "valid": True, "check_digit": "7", "calculated_check_digit": "7"},
            {"field": "Date of Birth Checksum", "valid": True, "check_digit": "1", "calculated_check_digit": "1"},
            {"field": "Expiry Date Checksum", "valid": True, "check_digit": "2", "calculated_check_digit": "2"},
            {"field": "Composite Checksum", "valid": True, "check_digit": "0", "calculated_check_digit": "0"}
        ]
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert eval_res["failed_count"] == 0
    assert eval_res["passed_count"] > 0
    assert len(_fails(eval_res["checks"])) == 0

def test_document_rules_expired():
    ocr_data = {"fields": {"document_number": "X1234567"}}
    mrz_data = {
        "surname": "KAUL",
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "900101",
        "expiry_date": "200101", # Expired in 2020
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert any(c["label"] == "Document Expired" for c in eval_res["checks"])
    expired_check = _find(eval_res["checks"], "DOCUMENT_EXPIRATION")
    assert expired_check["status"] == "FAIL"
    assert expired_check["evidence"]["measured_value"] == "2020-01-01"

def test_document_rules_mismatch():
    ocr_data = {"fields": {"document_number": "A9999999", "full_name": "JOHN DOE"}}
    mrz_data = {
        "surname": "DOE",
        "document_number": "B8888888", # Inconsistency between visual and MRZ
        "nationality": "UTO",
        "birth_date": "920510",
        "expiry_date": "300101",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert any("Document Number Inconsistency" in c["label"] for c in eval_res["checks"])
    crosscheck = _find(eval_res["checks"], "DOC_NUMBER_CROSSCHECK")
    assert crosscheck["status"] == "FAIL"
    assert crosscheck["factor"] == "CONSISTENCY"

def test_sex_code_valid():
    ocr_data = {"fields": {"document_number": "X1234567"}}
    mrz_data = {
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101",
        "sex": "M",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    sex_check = _find(eval_res["checks"], "SEX_CODE_FORMAT")
    assert sex_check["status"] == "PASS"
    assert not any(c["label"] == "Malformed Sex/Gender Code" for c in eval_res["checks"])

def test_sex_code_invalid():
    ocr_data = {"fields": {"document_number": "X1234567"}}
    mrz_data = {
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101",
        "sex": "1",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    sex_check = _find(eval_res["checks"], "SEX_CODE_FORMAT")
    assert sex_check["status"] == "FAIL"
    assert any(c["label"] == "Malformed Sex/Gender Code" for c in eval_res["checks"])

def test_document_number_crosscheck_survives_single_ocr_slip():
    """
    The visual-zone text and the MRZ line are two INDEPENDENT OCR passes over
    the same physical document number -- each can misread a different
    character. The old exact-or-substring check had no tolerance for this,
    so a single-character OCR slip in either pass alone (with no actual
    document tampering) would fire a false HIGH-severity "Document Number
    Inconsistency" signal, exactly the same OCR-noise-intolerance bug already
    fixed tonight for the MRZ composite checksum, nationality code, and
    watchlist matching.
    """
    ocr_data = {"fields": {"document_number": "X1B34567"}}  # '2' misread as 'B'
    mrz_data = {
        "surname": "KAUL",
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert not any("Document Number Inconsistency" in c["label"] for c in eval_res["checks"])

def test_document_number_crosscheck_still_catches_real_mismatch():
    """Tolerance is bounded to a single edit -- a genuinely different document
    number must still be flagged."""
    ocr_data = {"fields": {"document_number": "A9999999", "full_name": "JOHN DOE"}}
    mrz_data = {
        "surname": "DOE",
        "document_number": "B8888888",
        "nationality": "UTO",
        "birth_date": "920510",
        "expiry_date": "300101",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert any("Document Number Inconsistency" in c["label"] for c in eval_res["checks"])

def test_document_number_crosscheck_rejects_a_trivially_short_ocr_reading():
    """
    Reproduces a real logic gap found while reviewing RULE 4's OCR-noise
    tolerance: alongside the bounded fuzzy-edit check, it also allows
    outright substring containment (`clean_ocr_no in clean_mrz_no`) with NO
    length floor. A near-degenerate OCR reading of the document number
    (e.g. a single surviving character out of a badly garbled read) is then
    trivially "contained" in almost any longer MRZ document number,
    regardless of how different the two actually are, silently defeating
    the exact cross-check this rule exists to run. A genuinely truncated-
    but-real partial read (the case substring containment is meant to
    tolerate) is always several characters long; a bare single character is
    not a plausible partial read, it's a failed one, and must still be
    flagged.
    """
    ocr_data = {"fields": {"document_number": "7"}}  # OCR essentially failed
    mrz_data = {
        "surname": "KAUL",
        "document_number": "X1234567",  # happens to contain '7', but is a wholly different number
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    assert any("Document Number Inconsistency" in c["label"] for c in eval_res["checks"])

def test_document_number_crosscheck_not_applicable_when_one_source_missing():
    """When only one source extracted a document number, the crosscheck
    can't run -- it must show as NOT_APPLICABLE, not silently absent or a
    false PASS claiming a comparison that never happened."""
    ocr_data = {"fields": {}}
    mrz_data = {
        "surname": "KAUL",
        "document_number": "X1234567",
        "nationality": "UTO",
        "birth_date": "000101",
        "expiry_date": "300101",
        "checksums": []
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, mrz_data)
    crosscheck = _find(eval_res["checks"], "DOC_NUMBER_CROSSCHECK")
    assert crosscheck["status"] == "NOT_APPLICABLE"

def test_aadhaar_document_not_penalized_for_missing_mrz():
    """
    Aadhaar cards are a national ID, not an ICAO 9303 travel document -- they
    have no MRZ by design (a QR code carries the machine-readable payload
    instead). Before document-type awareness, `evaluate()` flagged ANY
    document with no MRZ as "Missing Machine Readable Zone" (HIGH severity),
    which would misclassify every genuine Aadhaar card as suspicious.
    """
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR",
            "document_number": "123456789012",
            "nationality": "INDIA",
            "country": "INDIA",
            "document_type": "AADHAAR"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])
    mrz_check = _find(eval_res["checks"], "MRZ_PRESENCE")
    assert mrz_check["status"] == "NOT_APPLICABLE"

def test_passport_without_mrz_still_flagged():
    """Non-Aadhaar documents missing an MRZ must still be flagged -- the
    Aadhaar exemption must not silently apply to every document type."""
    ocr_data = {"fields": {"full_name": "JOHN DOE", "document_number": "A9999999"}}
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])

def test_pan_document_not_penalized_for_missing_mrz():
    """PAN cards are an Income Tax Department ID, not an ICAO 9303 travel
    document -- like Aadhaar, they must not be flagged for having no MRZ."""
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR SHARMA",
            "document_number": "ABCPK1234F",
            "document_type": "PAN"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])
    mrz_check = _find(eval_res["checks"], "MRZ_PRESENCE")
    assert mrz_check["status"] == "NOT_APPLICABLE"

def test_dl_document_not_penalized_for_missing_mrz():
    """Driving Licences carry no ICAO MRZ either -- same exemption as
    Aadhaar/PAN."""
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR SHARMA",
            "document_number": "MH1220110012345",
            "document_type": "DRIVING_LICENSE"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])

def test_pan_format_validation_passes_for_well_formed_pan_and_decodes_entity_type():
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR SHARMA",
            "document_number": "ABCPK1234F",
            "document_type": "PAN"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    pan_check = _find(eval_res["checks"], "PAN_FORMAT_VALIDATION")
    assert pan_check["status"] == "PASS"
    assert "Individual" in pan_check["explanation"]
    assert not any("PAN" in c["label"] for c in _fails(eval_res["checks"]))

def test_pan_format_validation_fails_for_malformed_structure():
    """A structurally invalid PAN (wrong character classes/length) is a real,
    verifiable format violation -- CBDT's published PAN structure is fixed
    (5 letters, 4 digits, 1 letter), not free text."""
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR SHARMA",
            "document_number": "ABCP1234F",  # only 4 letters before the digits
            "document_type": "PAN"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    pan_check = _find(eval_res["checks"], "PAN_FORMAT_VALIDATION")
    assert pan_check["status"] == "FAIL"
    assert any(c["label"] == "Malformed PAN Structure" for c in eval_res["checks"])

def test_pan_format_validation_flags_unrecognized_entity_letter():
    """The 4th PAN character encodes a documented, enumerable entity type
    (P=Individual, C=Company, etc.) -- a structurally valid PAN whose 4th
    letter isn't one of those codes is suspicious even though the shape is
    otherwise fine."""
    ocr_data = {
        "fields": {
            "full_name": "RAVI KUMAR SHARMA",
            "document_number": "ABCZK1234F",  # 'Z' is not a recognized entity-type code
            "document_type": "PAN"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert any(c["label"] == "Unrecognized PAN Entity-Type Code" for c in eval_res["checks"])

def test_pan_rule_skipped_for_non_pan_documents():
    """A passport document number that happens to be PAN-shaped must not
    trigger PAN-specific validation -- the rule is gated on document_type,
    not on the number's shape alone."""
    ocr_data = {"fields": {"document_number": "ABCPK1234F", "document_type": "PASSPORT"}}
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["id"] == "PAN_FORMAT_VALIDATION" for c in eval_res["checks"])

def test_dl_expiry_uses_ocr_field_when_no_mrz_present():
    """
    A Driving Licence has a genuine printed expiry ("Valid Till") but no
    MRZ -- RULE 2 (DOCUMENT_EXPIRATION) was previously MRZ-only, so an
    expired DL was silently never checked at all. It must be checked the
    same way an expired passport is.
    """
    ocr_data = {
        "fields": {
            "document_number": "MH1220110012345",
            "document_type": "DRIVING_LICENSE",
            "date_of_expiry": "20/03/2020"  # expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert any(c["label"] == "Document Expired" for c in eval_res["checks"])
    expired_check = _find(eval_res["checks"], "DOCUMENT_EXPIRATION")
    assert expired_check["status"] == "FAIL"

def test_dl_valid_expiry_passes():
    ocr_data = {
        "fields": {
            "document_number": "MH1220110012345",
            "document_type": "DRIVING_LICENSE",
            "date_of_expiry": "20/03/2031"  # not yet expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    expired_check = _find(eval_res["checks"], "DOCUMENT_EXPIRATION")
    assert expired_check["status"] == "PASS"
    assert not any(c["label"] == "Document Expired" for c in eval_res["checks"])

def test_voter_id_document_not_penalized_for_missing_mrz():
    """Voter ID (EPIC) cards are an Election Commission of India ID, not an
    ICAO 9303 travel document -- same MRZ exemption as Aadhaar/PAN/DL."""
    ocr_data = {
        "fields": {
            "full_name": "ANJALI NAIR",
            "document_number": "ABC1234567",
            "document_type": "VOTER_ID"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])
    mrz_check = _find(eval_res["checks"], "MRZ_PRESENCE")
    assert mrz_check["status"] == "NOT_APPLICABLE"

def test_voter_id_format_validation_passes_for_well_formed_epic_number():
    ocr_data = {
        "fields": {
            "full_name": "ANJALI NAIR",
            "document_number": "ABC1234567",
            "document_type": "VOTER_ID"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    voter_id_check = _find(eval_res["checks"], "VOTER_ID_FORMAT_VALIDATION")
    assert voter_id_check["status"] == "PASS"
    assert not any("EPIC" in c["label"] for c in _fails(eval_res["checks"]))

def test_voter_id_format_validation_flags_non_standard_structure_as_medium_not_high():
    """
    Unlike PAN's CBDT-enforced format (no legitimate exceptions), EPIC
    numbering has well-documented real-world non-conformance -- older and
    non-standard/duplicate registrations are a known, ECI-acknowledged
    issue. A non-conforming EPIC number is therefore a caution (MEDIUM),
    not a hard structural failure the way a malformed PAN is (HIGH).
    """
    ocr_data = {
        "fields": {
            "full_name": "ANJALI NAIR",
            "document_number": "AB123456789",  # wrong shape: 2 letters + 9 digits
            "document_type": "VOTER_ID"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    voter_id_check = _find(eval_res["checks"], "VOTER_ID_FORMAT_VALIDATION")
    assert voter_id_check["status"] == "FAIL"
    assert voter_id_check["severity"] == "MEDIUM"
    check = next(c for c in eval_res["checks"] if c["label"] == "Non-Standard EPIC Format")
    assert check["severity"] == "MEDIUM"

def test_voter_id_rule_skipped_for_non_voter_id_documents():
    """An EPIC-shaped document number on a passport must not trigger
    Voter-ID-specific validation -- the rule is gated on document_type."""
    ocr_data = {"fields": {"document_number": "ABC1234567", "document_type": "PASSPORT"}}
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["id"] == "VOTER_ID_FORMAT_VALIDATION" for c in eval_res["checks"])

def test_visa_document_not_penalized_for_missing_mrz():
    """A Visa is visually extracted only (no ICAO MRZ modeled) -- same MRZ
    exemption as Aadhaar/PAN/DL/Voter ID."""
    ocr_data = {
        "fields": {
            "full_name": "CARLOS MENDEZ",
            "document_number": "UV1234567",
            "document_type": "VISA"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])
    mrz_check = _find(eval_res["checks"], "MRZ_PRESENCE")
    assert mrz_check["status"] == "NOT_APPLICABLE"

def test_visa_stay_duration_expired_flags_critical():
    """
    Reuses RULE 2 (DOCUMENT_EXPIRATION)'s own date-plausibility pattern
    (parse_ddmmyyyy, compare against today) applied to the visa's own
    'Stay Duration' field rather than a generic document expiry -- an
    overstay-relevant date distinct from the visa's own issue window.
    """
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA",
            "stay_duration_until": "01/01/2020"  # expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    visa_check = _find(eval_res["checks"], "VISA_STAY_DURATION_VALIDATION")
    assert visa_check["status"] == "FAIL"
    assert visa_check["severity"] == "CRITICAL"
    check = next(c for c in eval_res["checks"] if c["label"] == "Visa Stay Duration Expired")
    assert check["severity"] == "CRITICAL"

def test_visa_stay_duration_valid_passes():
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA",
            "stay_duration_until": "30/06/2031"  # not yet expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    visa_check = _find(eval_res["checks"], "VISA_STAY_DURATION_VALIDATION")
    assert visa_check["status"] == "PASS"
    assert not any(c["label"] == "Visa Stay Duration Expired" for c in eval_res["checks"])

def test_visa_stay_duration_missing_pends_visual_confirmation():
    """No stay-duration date extracted -- LOW/pending, not penalized, same
    posture as RULE 2's own missing-expiry branch."""
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    visa_check = _find(eval_res["checks"], "VISA_STAY_DURATION_VALIDATION")
    assert visa_check["status"] == "PASS"
    assert not any(c["label"] == "Visa Stay Duration Expired" for c in eval_res["checks"])

def test_visa_rule_skipped_for_non_visa_documents():
    """A visa-shaped stay_duration_until on a passport must not trigger
    visa-specific validation -- the rule is gated on document_type."""
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "PASSPORT",
            "stay_duration_until": "01/01/2020"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["id"] == "VISA_STAY_DURATION_VALIDATION" for c in eval_res["checks"])


def test_visa_entry_validation_recognized_value_passes():
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA",
            "entry_validation": "Multiple Entry"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    check = _find(eval_res["checks"], "VISA_ENTRY_VALIDATION_CHECK")
    assert check["status"] == "PASS"
    assert not any(c["label"] == "Unrecognized Visa Entry Validation Value" for c in eval_res["checks"])


def test_visa_entry_validation_unrecognized_value_flags_medium():
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA",
            "entry_validation": "PERPETUAL ENTRY"  # not a recognized value
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    check = _find(eval_res["checks"], "VISA_ENTRY_VALIDATION_CHECK")
    assert check["status"] == "FAIL"
    assert check["severity"] == "MEDIUM"
    signal = next(c for c in eval_res["checks"] if c["label"] == "Unrecognized Visa Entry Validation Value")
    assert signal["severity"] == "MEDIUM"


def test_visa_entry_validation_missing_pends_visual_confirmation():
    ocr_data = {
        "fields": {
            "document_number": "UV1234567",
            "document_type": "VISA"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    check = _find(eval_res["checks"], "VISA_ENTRY_VALIDATION_CHECK")
    assert check["status"] == "PASS"
    assert not any(c["label"] == "Unrecognized Visa Entry Validation Value" for c in eval_res["checks"])


def test_permit_not_penalized_for_missing_mrz():
    """A Permit is visually extracted only (no ICAO MRZ modeled) -- same MRZ
    exemption as Aadhaar/PAN/DL/Voter ID/Visa."""
    ocr_data = {
        "fields": {
            "full_name": "TOLA ADEYEMI",
            "document_number": "RP7734210",
            "document_type": "PERMIT"
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert not any(c["label"] == "Missing Machine Readable Zone" for c in eval_res["checks"])
    mrz_check = _find(eval_res["checks"], "MRZ_PRESENCE")
    assert mrz_check["status"] == "NOT_APPLICABLE"


def test_permit_expiry_uses_ocr_field_via_document_expiration_rule():
    """
    A Permit has a genuine printed expiry but no MRZ -- same shape as
    Driving Licence (test_dl_expiry_uses_ocr_field_when_no_mrz_present),
    so it deliberately reuses RULE 2 (DOCUMENT_EXPIRATION) directly rather
    than getting its own PERMIT_EXPIRATION rule, which would double-count
    the same date (see rules_engine.py's comment at RULE 9's end for why).
    """
    ocr_data = {
        "fields": {
            "document_number": "RP7734210",
            "document_type": "PERMIT",
            "date_of_expiry": "01/01/2020"  # expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    assert any(c["label"] == "Document Expired" for c in eval_res["checks"])
    expired_check = _find(eval_res["checks"], "DOCUMENT_EXPIRATION")
    assert expired_check["status"] == "FAIL"
    # And confirms the fix actually prevents double-counting: exactly one
    # DOCUMENT_EXPIRATION entry, no separate PERMIT_EXPIRATION rule at all.
    assert len([c for c in eval_res["checks"] if c["id"] == "DOCUMENT_EXPIRATION"]) == 1
    assert not any(c["id"] == "PERMIT_EXPIRATION" for c in eval_res["checks"])


def test_permit_valid_expiry_passes():
    ocr_data = {
        "fields": {
            "document_number": "RP7734210",
            "document_type": "PERMIT",
            "date_of_expiry": "01/01/2031"  # not yet expired
        }
    }
    eval_res = DocumentRulesEngine.evaluate(ocr_data, None)
    expired_check = _find(eval_res["checks"], "DOCUMENT_EXPIRATION")
    assert expired_check["status"] == "PASS"
    assert not any(c["label"] == "Document Expired" for c in eval_res["checks"])
