from datetime import datetime, date
from typing import Dict, Any, List, Optional
import re

from app.utils.text_similarity import fuzzy_equal
from app.services.risk_types import RiskCheckStatus, RiskFactorKey, make_check, make_evidence

class DocumentRulesEngine:
    """
    Configurable rules engine validating document consistency and integrity.
    Validates cross-field matching (visual OCR vs MRZ), expiration, checksums, and date boundaries.
    Generates a unified list of itemized risk checks (RiskCheckResult shape,
    see app.services.risk_types) -- one entry per rule evaluated, whether it
    passed, failed, or didn't apply, each carrying its own structured
    evidence (the value measured vs. the threshold/expected value it was
    judged against).
    """

    # Document types with no ICAO 9303 Machine Readable Zone by design --
    # kept in sync with (but intentionally not imported from)
    # TesseractOCRService.NON_MRZ_DOCUMENT_TYPES in ocr_service.py, matching
    # this codebase's existing style of duplicating the "AADHAAR" check
    # independently at each of its call sites rather than sharing one
    # constant across the OCR and rules-engine modules.
    NON_MRZ_DOCUMENT_TYPES = ("AADHAAR", "PAN", "DRIVING_LICENSE", "VOTER_ID", "VISA", "PERMIT")

    # Enumerated values a Visa's "Entry Validation" field plausibly holds --
    # not an exhaustive real-world standard (none is published the way
    # ICAO 9303's MRZ format is), but a genuine, checkable set of the values
    # this project's own visa specimens can carry (see ocr_service.py's
    # parse_visa_fields / synthetic_generator.py's generate_visa). An
    # unrecognized value is a caution (MEDIUM), not a hard failure -- a real
    # visa could plausibly use wording this table doesn't happen to list.
    VISA_ENTRY_VALIDATION_VALUES = {
        "SINGLE ENTRY", "DOUBLE ENTRY", "MULTIPLE ENTRY", "TRANSIT"
    }

    # CBDT's published PAN entity-type codes (the 4th of the 5 leading
    # letters). Only the well-established, commonly-cited codes are listed
    # here -- an unrecognized letter is flagged as suspicious (MEDIUM, not a
    # hard failure) rather than assumed exhaustive, since a rarer real code
    # this table is missing would otherwise be misclassified as fabricated.
    PAN_ENTITY_TYPES = {
        "P": "Individual",
        "C": "Company",
        "H": "Hindu Undivided Family (HUF)",
        "F": "Firm",
        "A": "Association of Persons (AOP)",
        "T": "Trust",
        "B": "Body of Individuals (BOI)",
        "L": "Local Authority",
        "J": "Artificial Juridical Person",
        "G": "Government",
    }

    # Maps each option in the manual "New Screening" flow's Issuing
    # Jurisdiction dropdown (frontend/src/pages/ScreeningPage.tsx) to its
    # ICAO 3-letter country code, for RULE 10 below -- a document's MRZ
    # carries only the code, not the full name. Intentionally duplicated
    # from app.api.routes.demo's KNOWN_COUNTRY_CODES (same convention this
    # file already uses for NON_MRZ_DOCUMENT_TYPES above) rather than
    # imported, since a service module importing from an API route module
    # would be a backwards dependency.
    JURISDICTION_COUNTRY_CODES = {
        "REPUBLIC OF UTOPIA": "UTO",
        "DEMO STATE": "DEM",
        "ATLANTIS FEDERATION": "ATL",
        "INDIA": "IND",
        "UNITED KINGDOM": "GBR",
    }

    @classmethod
    def parse_ddmmyyyy(cls, value: Optional[str]) -> Optional[date]:
        """
        Parses the DD/MM/YYYY date string TesseractOCRService._extract_date
        produces for document types with no MRZ (e.g. a Driving Licence's
        printed "Valid Till" field) -- distinct from parse_yymmdd, which
        parses the MRZ's own 6-digit YYMMDD format.
        """
        if not value:
            return None
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', value)
        if not m:
            return None
        dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            return None
        try:
            return date(yyyy, mm, dd)
        except ValueError:
            return None

    @classmethod
    def parse_yymmdd(cls, yymmdd: str) -> Optional[date]:
        """Parses ICAO YYMMDD date string."""
        if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
            return None
        yy = int(yymmdd[:2])
        mm = int(yymmdd[2:4])
        dd = int(yymmdd[4:6])
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            return None
        # Heuristic: 00-40 -> 2000-2040, 41-99 -> 1941-1999
        century = 2000 if yy <= 45 else 1900
        try:
            return date(century + yy, mm, dd)
        except ValueError:
            return None

    @classmethod
    def evaluate(
        cls, ocr_data: Dict[str, Any], mrz_data: Optional[Dict[str, Any]],
        declared_country: Optional[str] = None,
    ) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []

        def add(
            id: str, label: str, passed_or_status, severity: Optional[str],
            explanation: str, confidence: float,
            evidence: Optional[Dict[str, Any]] = None, score_impact: float = 0.0,
            category: str = "VALIDATION", factor: str = RiskFactorKey.MRZ_VALIDATION,
        ):
            if passed_or_status is True:
                status = RiskCheckStatus.PASS
            elif passed_or_status is False:
                status = RiskCheckStatus.FAIL
            else:
                status = passed_or_status  # NOT_APPLICABLE passed through directly
            checks.append(make_check(
                id=id, category=category, factor=factor, label=label, status=status,
                severity=severity if status == RiskCheckStatus.FAIL else None,
                confidence=confidence, explanation=explanation, evidence=evidence,
                score_impact=score_impact,
            ))

        today = date.today()
        fields = ocr_data.get("fields", {})

        # RULE 1: MRZ Checksum Validation
        if mrz_data and mrz_data.get("checksums"):
            for cs in mrz_data["checksums"]:
                field_name = cs["field"]
                is_valid = cs["valid"]
                check_id = f"MRZ_{field_name.upper().replace(' ', '_')}"
                evidence = make_evidence(
                    measured_value=cs["check_digit"], threshold_value=cs["calculated_check_digit"],
                    unit="check_digit",
                )
                if is_valid:
                    add(check_id, field_name, True, None,
                        f"{field_name} matches calculated check digit ({cs['check_digit']}).",
                        0.99, evidence=evidence, category="MRZ")
                else:
                    add(check_id, f"MRZ Checksum Mismatch ({field_name})", False, "HIGH",
                        f"ICAO 9303 check digit verification failed for {field_name}: found "
                        f"'{cs['check_digit']}', expected '{cs['calculated_check_digit']}'. "
                        f"Potential character alteration.",
                        0.99, evidence=evidence, score_impact=18.0, category="MRZ")
        elif fields.get("document_type") in cls.NON_MRZ_DOCUMENT_TYPES:
            # Aadhaar/PAN/Driving Licence are national IDs, not ICAO 9303
            # travel documents -- none of them carry an MRZ by design, so a
            # missing MRZ here is expected, not a red flag.
            add("MRZ_PRESENCE", "MRZ Presence", RiskCheckStatus.NOT_APPLICABLE, None,
                "Not applicable — this document type does not carry an ICAO Machine Readable Zone by design.",
                0.95, category="MRZ")
        elif not mrz_data:
            add("MRZ_PRESENCE", "Missing Machine Readable Zone", False, "HIGH",
                "Standard travel documents must contain a readable 2-line or 3-line MRZ zone.",
                0.92, score_impact=20.0, category="MRZ")

        # RULE 1b: PAN Structural Format Validation
        #
        # Unlike an MRZ check digit, PAN's own final check character is
        # generated by an algorithm CBDT/NSDL/UTIITSL has never published --
        # there is no authoritative way to recompute it independently, and
        # claiming to validate it would be presenting an unverified guess as
        # a real checksum. What IS publicly documented and genuinely
        # checkable: the fixed 10-character structure itself, and the 4th
        # letter's entity-type encoding.
        if fields.get("document_type") == "PAN":
            pan_number = fields.get("document_number") or ""
            evidence = make_evidence(measured_value=pan_number, threshold_value="AAAAA9999A", unit="pan_format")
            if not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', pan_number):
                add("PAN_FORMAT_VALIDATION", "Malformed PAN Structure", False, "HIGH",
                    f"'{pan_number}' does not match the required PAN structure (5 letters, 4 digits, 1 letter). "
                    f"Permanent Account Number does not conform to the CBDT-published 10-character format.",
                    0.97, evidence=evidence, score_impact=20.0)
            else:
                entity_letter = pan_number[3]
                entity_type = cls.PAN_ENTITY_TYPES.get(entity_letter)
                if entity_type:
                    add("PAN_FORMAT_VALIDATION", "PAN Format Validation", True, None,
                        f"Well-formed PAN; 4th character '{entity_letter}' indicates entity type {entity_type}.",
                        0.97, evidence=evidence)
                else:
                    entity_evidence = make_evidence(
                        measured_value=entity_letter,
                        threshold_value=", ".join(sorted(cls.PAN_ENTITY_TYPES)),
                        unit="pan_entity_code",
                    )
                    add("PAN_FORMAT_VALIDATION", "Unrecognized PAN Entity-Type Code", False, "MEDIUM",
                        f"PAN structure is well-formed, but 4th character '{entity_letter}' is not a "
                        f"recognized entity-type code.",
                        0.70, evidence=entity_evidence, score_impact=8.0)

        # RULE 1c: Voter ID (EPIC) Structural Format Validation
        #
        # The Election Commission of India's current EPIC format (3 letters,
        # 7 digits) is publicly documented, so it's genuinely checkable --
        # but unlike PAN's CBDT-enforced format, EPIC numbering has
        # well-documented real-world non-conformance. A mismatch is
        # therefore a caution (MEDIUM), not a hard structural failure.
        if fields.get("document_type") == "VOTER_ID":
            voter_id_number = fields.get("document_number") or ""
            evidence = make_evidence(measured_value=voter_id_number, threshold_value="AAA9999999", unit="epic_format")
            if re.fullmatch(r'[A-Z]{3}[0-9]{7}', voter_id_number):
                add("VOTER_ID_FORMAT_VALIDATION", "Voter ID Format Validation", True, None,
                    f"'{voter_id_number}' matches the ECI's standard EPIC format (3 letters, 7 digits).",
                    0.90, evidence=evidence)
            else:
                add("VOTER_ID_FORMAT_VALIDATION", "Non-Standard EPIC Format", False, "MEDIUM",
                    f"'{voter_id_number}' does not match the ECI's standard EPIC format (3 letters, 7 digits). "
                    f"Older or non-standard registrations are known to legitimately deviate, so this is a "
                    f"caution rather than a hard failure.",
                    0.65, evidence=evidence, score_impact=8.0)

        # RULE 2: Expiration Check
        expiry_date = None
        if mrz_data and mrz_data.get("expiry_date"):
            expiry_date = cls.parse_yymmdd(mrz_data["expiry_date"])
        elif fields.get("date_of_expiry"):
            expiry_date = cls.parse_ddmmyyyy(fields["date_of_expiry"])

        if expiry_date:
            evidence = make_evidence(
                measured_value=expiry_date.strftime('%Y-%m-%d'),
                threshold_value=today.strftime('%Y-%m-%d'),
                unit="expiry_date_vs_today",
            )
            if expiry_date < today:
                add("DOCUMENT_EXPIRATION", "Document Expired", False, "CRITICAL",
                    f"Travel document validity expired on {expiry_date.strftime('%Y-%m-%d')} "
                    f"(current date: {today.strftime('%Y-%m-%d')}). Document is invalid for travel.",
                    0.99, evidence=evidence, score_impact=28.0)
            else:
                add("DOCUMENT_EXPIRATION", "Document Expiration Check", True, None,
                    f"Document is valid until {expiry_date.strftime('%Y-%m-%d')}.",
                    0.99, evidence=evidence)
        else:
            add("DOCUMENT_EXPIRATION", "Document Expiration Check", True, None,
                "Expiry date verified or pending visual confirmation.", 0.85)

        # RULE 3: DOB Plausibility & Impossible Date
        dob_date = None
        if mrz_data and mrz_data.get("birth_date"):
            dob_date = cls.parse_yymmdd(mrz_data["birth_date"])
            if dob_date is None:
                add("IMPOSSIBLE_DATE", "Impossible Date in MRZ", False, "HIGH",
                    f"Birth date contains non-existent calendar date values: '{mrz_data.get('birth_date')}'.",
                    0.98, evidence=make_evidence(measured_value=mrz_data.get('birth_date'), unit="birth_date_raw"),
                    score_impact=15.0)
            elif dob_date > today:
                add("FUTURE_BIRTH_DATE", "Future Date of Birth", False, "CRITICAL",
                    f"Holder's recorded birth date ({dob_date.strftime('%Y-%m-%d')}) is after current calendar date.",
                    0.99,
                    evidence=make_evidence(measured_value=dob_date.strftime('%Y-%m-%d'),
                                            threshold_value=today.strftime('%Y-%m-%d'), unit="dob_vs_today"),
                    score_impact=25.0)
            else:
                add("BIRTH_DATE_PLAUSIBILITY", "Birth Date Plausibility", True, None,
                    f"Valid birth date ({dob_date.strftime('%Y-%m-%d')}).", 0.99)

        # RULE 4: Visual Zone vs MRZ Document Number Inconsistency -- a
        # genuine CROSS-SOURCE consistency check (two independent OCR passes
        # over the same physical number), unlike every other rule here,
        # which validates a single source's own well-formedness. Tagged
        # factor=CONSISTENCY, not MRZ_VALIDATION, so it contributes to the
        # score exactly once, via the Consistency factor -- see
        # risk_engine.py's own comment on why this must not also be summed
        # into MRZ_VALIDATION's raw risk.
        ocr_doc_no = fields.get("document_number")
        mrz_doc_no = mrz_data.get("document_number") if mrz_data else None

        if ocr_doc_no and mrz_doc_no:
            clean_ocr_no = re.sub(r'[^A-Za-z0-9]', '', ocr_doc_no).upper()
            clean_mrz_no = re.sub(r'[^A-Za-z0-9]', '', mrz_doc_no).upper()

            MIN_SUBSTRING_MATCH_LENGTH = 5
            shorter_len = min(len(clean_ocr_no), len(clean_mrz_no))
            is_consistent = (
                clean_ocr_no == clean_mrz_no
                or (
                    shorter_len >= MIN_SUBSTRING_MATCH_LENGTH
                    and (clean_ocr_no in clean_mrz_no or clean_mrz_no in clean_ocr_no)
                )
                or fuzzy_equal(clean_ocr_no, clean_mrz_no)
            )
            evidence = make_evidence(measured_value=ocr_doc_no, threshold_value=mrz_doc_no, unit="document_number")
            if not is_consistent:
                add("DOC_NUMBER_CROSSCHECK", "Document Number Inconsistency", False, "HIGH",
                    f"Visual inspection zone displays '{ocr_doc_no}' but machine-readable zone records "
                    f"'{mrz_doc_no}'.",
                    0.95, evidence=evidence, score_impact=22.0,
                    factor=RiskFactorKey.CONSISTENCY)
            else:
                add("DOC_NUMBER_CROSSCHECK", "Document Number Crosscheck", True, None,
                    "Visual document number matches MRZ document number.",
                    0.95, evidence=evidence, factor=RiskFactorKey.CONSISTENCY)
        else:
            add("DOC_NUMBER_CROSSCHECK", "Document Number Crosscheck", RiskCheckStatus.NOT_APPLICABLE, None,
                "Visual-vs-MRZ document number crosscheck requires both sources; at least one was not "
                "extracted, so the crosscheck did not run.",
                0.5, factor=RiskFactorKey.CONSISTENCY)

        # RULE 5: Required Fields Presence
        missing_fields = []
        if not (fields.get("full_name") or (mrz_data and mrz_data.get("surname"))):
            missing_fields.append("Full Name")
        if not (ocr_doc_no or mrz_doc_no):
            missing_fields.append("Document Number")

        if missing_fields:
            add("REQUIRED_FIELDS_PRESENCE", "Missing Mandatory Identity Fields", False, "MEDIUM",
                f"Failed to detect {', '.join(missing_fields)} in visual or machine-readable zones.",
                0.90, evidence=make_evidence(measured_value=", ".join(missing_fields),
                                              threshold_value="Full Name, Document Number", unit="required_fields"),
                score_impact=10.0)
        else:
            add("REQUIRED_FIELDS_PRESENCE", "Required Fields Presence", True, None,
                "All mandatory identity fields detected.", 0.95)

        # RULE 6: Nationality Code Format (ISO 3166-1 alpha-3 in MRZ)
        if mrz_data and mrz_data.get("nationality"):
            nat = mrz_data["nationality"]
            evidence = make_evidence(measured_value=nat, threshold_value="3-letter ISO alpha code", unit="nationality_code")
            if len(nat) == 3 and nat.isalpha():
                add("NATIONALITY_CODE_FORMAT", "Nationality Code Format", True, None,
                    f"Valid 3-letter ICAO country/nationality code: '{nat}'.", 0.98, evidence=evidence)
            else:
                add("NATIONALITY_CODE_FORMAT", "Malformed Nationality Code", False, "MEDIUM",
                    f"MRZ nationality '{nat}' violates ICAO 3-letter alpha format.",
                    0.95, evidence=evidence, score_impact=8.0)

        # RULE 7: Sex/Gender Code Validation (ICAO 9303 -- must be M, F, or X)
        if mrz_data and mrz_data.get("sex"):
            sex = mrz_data["sex"].upper()
            evidence = make_evidence(measured_value=sex, threshold_value="M, F, or X", unit="sex_code")
            if sex in ("M", "F", "X"):
                add("SEX_CODE_FORMAT", "Sex/Gender Code Format", True, None,
                    f"Valid ICAO sex/gender code: '{sex}'.", 0.98, evidence=evidence)
            else:
                add("SEX_CODE_FORMAT", "Malformed Sex/Gender Code", False, "MEDIUM",
                    f"MRZ sex/gender code '{sex}' violates ICAO 9303 format (expected M/F/X).",
                    0.90, evidence=evidence, score_impact=6.0)

        # RULE 8: Visa Stay Duration Validity
        if fields.get("document_type") == "VISA":
            stay_until = cls.parse_ddmmyyyy(fields.get("stay_duration_until"))
            if stay_until:
                evidence = make_evidence(measured_value=stay_until.strftime('%Y-%m-%d'),
                                          threshold_value=today.strftime('%Y-%m-%d'), unit="stay_until_vs_today")
                if stay_until < today:
                    add("VISA_STAY_DURATION_VALIDATION", "Visa Stay Duration Expired", False, "CRITICAL",
                        f"Authorized stay duration on this visa expired on {stay_until.strftime('%Y-%m-%d')} "
                        f"(current date: {today.strftime('%Y-%m-%d')}). Holder is not authorized for "
                        f"continued presence.",
                        0.97, evidence=evidence, score_impact=24.0)
                else:
                    add("VISA_STAY_DURATION_VALIDATION", "Visa Stay Duration Validation", True, None,
                        f"Authorized stay is valid until {stay_until.strftime('%Y-%m-%d')}.",
                        0.97, evidence=evidence)
            else:
                add("VISA_STAY_DURATION_VALIDATION", "Visa Stay Duration Validation", True, None,
                    "Stay duration verified or pending visual confirmation.", 0.80)

        # RULE 9: Visa Entry Validation Field Check
        if fields.get("document_type") == "VISA":
            entry_validation = (fields.get("entry_validation") or "").strip().upper()
            if not entry_validation:
                add("VISA_ENTRY_VALIDATION_CHECK", "Visa Entry Validation Check", True, None,
                    "Entry validation field verified or pending visual confirmation.", 0.75)
            elif entry_validation in cls.VISA_ENTRY_VALIDATION_VALUES:
                add("VISA_ENTRY_VALIDATION_CHECK", "Visa Entry Validation Check", True, None,
                    f"Entry validation '{entry_validation}' is a recognized visa entry type.",
                    0.90, evidence=make_evidence(measured_value=entry_validation,
                                                  threshold_value=", ".join(sorted(cls.VISA_ENTRY_VALIDATION_VALUES)),
                                                  unit="visa_entry_type"))
            else:
                add("VISA_ENTRY_VALIDATION_CHECK", "Unrecognized Visa Entry Validation Value", False, "MEDIUM",
                    f"Visa's printed entry validation field ('{entry_validation}') does not match any "
                    f"recognized entry type ({', '.join(sorted(cls.VISA_ENTRY_VALIDATION_VALUES))}).",
                    0.60, evidence=make_evidence(measured_value=entry_validation,
                                                  threshold_value=", ".join(sorted(cls.VISA_ENTRY_VALIDATION_VALUES)),
                                                  unit="visa_entry_type"),
                    score_impact=8.0)

        # RULE 10: Declared Jurisdiction vs. Document's Own Country --
        # catches a case where the officer selects one issuing jurisdiction
        # at upload (ScreeningPage.tsx's "Issuing jurisdiction" dropdown,
        # stored as Case.country) but the document actually presented is
        # printed for a different country entirely. This used to go
        # completely unchecked: Case.country was only ever overwritten by
        # the MRZ's own country when it was still "Unknown" (see
        # screening.py), never compared against what the officer actually
        # declared. A genuine cross-source consistency check, like RULE 4
        # above -- factor=CONSISTENCY, not MRZ_VALIDATION, for the same
        # reason (see that rule's own comment).
        declared = (declared_country or "").strip().upper()
        if declared and declared != "UNKNOWN":
            document_country_name = (fields.get("country") or "").strip().upper()
            document_country_code = ((mrz_data or {}).get("country") or "").strip().upper()
            declared_code = cls.JURISDICTION_COUNTRY_CODES.get(declared)

            # Prefer comparing full names (the visual "Country of Issue"
            # field, populated for every document type including the ones
            # with no MRZ) -- fall back to comparing ICAO codes only when
            # the visual field wasn't extracted but an MRZ was.
            if document_country_name:
                is_consistent = document_country_name == declared
                compared_against = document_country_name
            elif document_country_code and declared_code:
                is_consistent = document_country_code == declared_code
                compared_against = document_country_code
            else:
                is_consistent = None
                compared_against = None

            if is_consistent is None:
                add("JURISDICTION_COUNTRY_CROSSCHECK", "Declared Jurisdiction Crosscheck",
                    RiskCheckStatus.NOT_APPLICABLE, None,
                    "Officer-declared issuing jurisdiction could not be cross-checked against the document's "
                    "own printed country or MRZ issuing-state code -- neither was extracted.",
                    0.5, factor=RiskFactorKey.CONSISTENCY)
            elif not is_consistent:
                evidence = make_evidence(measured_value=compared_against, threshold_value=declared, unit="issuing_country")
                add("JURISDICTION_COUNTRY_CROSSCHECK", "Declared Jurisdiction Does Not Match Document", False, "HIGH",
                    f"Officer selected '{declared_country}' as the issuing jurisdiction at intake, but the "
                    f"document itself is printed for '{compared_against}'. Either a data-entry error or a "
                    f"document presented under an inconsistent claimed origin -- requires officer verification.",
                    0.85, evidence=evidence, score_impact=15.0, factor=RiskFactorKey.CONSISTENCY)
            else:
                evidence = make_evidence(measured_value=compared_against, threshold_value=declared, unit="issuing_country")
                add("JURISDICTION_COUNTRY_CROSSCHECK", "Declared Jurisdiction Crosscheck", True, None,
                    f"Officer-declared issuing jurisdiction ('{declared_country}') matches the document's own "
                    f"printed/MRZ country.",
                    0.90, evidence=evidence, factor=RiskFactorKey.CONSISTENCY)

        # Permit deliberately has NO dedicated expiration rule here, unlike
        # Visa's stay-duration check above -- a Permit has only one temporal
        # concept (its own validity), the same shape as Driving Licence,
        # which already reuses RULE 2 (DOCUMENT_EXPIRATION) directly rather
        # than getting its own PERMIT_EXPIRATION rule, which would
        # double-count the same date.

        passed_count = sum(1 for c in checks if c["status"] == RiskCheckStatus.PASS)
        failed_count = sum(1 for c in checks if c["status"] == RiskCheckStatus.FAIL)

        return {
            "passed_count": passed_count,
            "failed_count": failed_count,
            "checks": checks,
        }
