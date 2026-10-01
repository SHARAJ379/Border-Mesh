import re
from typing import Dict, Any, List, Optional, Tuple

class MRZService:
    """
    ICAO 9303 compliant Machine Readable Zone (MRZ) parser and validator.
    Supports TD3 (2x44 chars, standard passports), TD1 (3x30 chars), and TD2 (2x36 chars).
    Calculates exact check digits using the 7-3-1 weight system.
    """

    # ICAO 9303 character values: 0-9 = 0-9, A-Z = 10-35, < = 0
    CHAR_VALUES: Dict[str, int] = {
        **{str(i): i for i in range(10)},
        **{chr(c): c - 55 for c in range(ord('A'), ord('Z') + 1)},
        '<': 0
    }
    WEIGHTS = [7, 3, 1]

    @classmethod
    def compute_check_digit(cls, data: str) -> str:
        """Computes the ICAO 9303 check digit for a given alphanumeric string."""
        total = 0
        for i, ch in enumerate(data.upper()):
            val = cls.CHAR_VALUES.get(ch, 0)
            weight = cls.WEIGHTS[i % 3]
            total += val * weight
        return str(total % 10)

    @classmethod
    def clean_mrz_line(cls, line: str) -> str:
        """Sanitizes line by normalizing OCR misrecognitions for filler '<' and uppercase."""
        # Common OCR errors for '<'
        for ch in ['«', '»', '‹', '›', '{', '}', '[', ']', '(', ')']:
            line = line.replace(ch, '<')
        
        # In trailing filler zone, lowercase c, e, o often misread for <
        line = re.sub(r'[ceo]{2,}', lambda m: '<' * len(m.group(0)), line)
        line = re.sub(r'[^A-Za-z0-9<]', '', line).upper()
        return line

    @classmethod
    def normalize_digits(cls, text: str) -> str:
        """Corrects common OCR letter substitutions in strictly numeric MRZ fields."""
        subs = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8', '<': '0'}
        res = []
        for ch in text.upper():
            res.append(subs.get(ch, ch))
        return "".join(res)

    @classmethod
    def normalize_letters(cls, text: str) -> str:
        """
        The mirror image of normalize_digits, for strictly alphabetic MRZ
        fields (country, nationality -- ICAO 3166-1 alpha-3 codes). Any digit
        appearing here is necessarily OCR noise, since these fields can never
        legitimately contain one; correct it back to its most visually
        similar letter rather than let it flow through and fail a downstream
        alpha-format check on an otherwise genuine document.
        """
        subs = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'}
        return "".join(subs.get(ch, ch) for ch in text.upper())

    @classmethod
    def _reconstruct_length(cls, s: str, target_len: int) -> str:
        """
        Pads a short OCR'd MRZ line to target_len characters.

        OCR reliably reads distinct/real characters but often undercounts a long
        run of a single repeated glyph -- in practice, a string of consecutive
        '<' filler characters gets merged/undercounted, even though the real
        content immediately before AND after that run (e.g. the trailing
        composite check digit) is read correctly. Blindly right-padding in that
        case pushes the trailing real character out of its fixed ICAO 9303
        position, corrupting checksum validation.

        If a run of '<' exists anywhere in the string, the missing characters
        are inserted into that run (preserving whatever comes after it);
        otherwise falls back to plain right-padding.
        """
        if len(s) >= target_len:
            return s[:target_len]
        deficit = target_len - len(s)
        runs = list(re.finditer(r'<+', s))
        if runs:
            start, end = runs[-1].span()
            return s[:start] + ('<' * (end - start + deficit)) + s[end:]
        return s.ljust(target_len, '<')

    @classmethod
    def parse_td3(cls, line1: str, line2: str) -> Dict[str, Any]:
        """
        Parses TD3 format (Passport, 2 lines of 44 characters).
        Line 1:
          P<[Country 3][Surname]<<[Given Names]...
        Line 2:
          [Doc# 9][Doc# CD 1][Nationality 3][DOB 6][DOB CD 1][Sex 1][Expiry 6][Expiry CD 1][Optional 15][Composite CD 1]
        """
        line1 = cls._reconstruct_length(cls.clean_mrz_line(line1), 44)
        line2 = cls._reconstruct_length(cls.clean_mrz_line(line2), 44)

        doc_type = line1[0:2].replace('<', '')
        country = cls.normalize_letters(line1[2:5].replace('<', ''))
        
        name_section = line1[5:]
        name_parts = name_section.split('<<')
        surname = name_parts[0].replace('<', ' ').strip()
        given_names = ""
        if len(name_parts) > 1:
            given_names = name_parts[1].replace('<', ' ').strip()

        # Line 2 fields
        doc_number_raw = line2[0:9]
        doc_number = doc_number_raw.replace('<', '')
        doc_number_cd = cls.normalize_digits(line2[9])
        
        nationality = cls.normalize_letters(line2[10:13].replace('<', ''))
        
        dob_raw = cls.normalize_digits(line2[13:19])
        dob_cd = cls.normalize_digits(line2[19])

        # A garbled sex character is preserved as-is (uppercased), not
        # silently defaulted to 'M' -- defaulting it would make Rule 7
        # (SEX_CODE_FORMAT, rules_engine.py -- added specifically to catch a
        # malformed sex/gender code) permanently unable to detect one from
        # real OCR'd data, since it would never see anything but a value
        # already valid by construction. '<' filler is the one case ICAO
        # 9303 itself defines as meaningful here: unspecified ('X').
        sex = 'X' if line2[20] == '<' else line2[20].upper()

        expiry_raw = cls.normalize_digits(line2[21:27])
        expiry_cd = cls.normalize_digits(line2[27])

        optional_raw = line2[28:43]
        optional_data = optional_raw.replace('<', '')
        
        composite_cd = cls.normalize_digits(line2[43])

        # Calculate actual checksums
        calc_doc_cd = cls.compute_check_digit(doc_number_raw)
        calc_dob_cd = cls.compute_check_digit(dob_raw)
        calc_expiry_cd = cls.compute_check_digit(expiry_raw)
        
        # Composite string according to ICAO Doc 9303-4 (TD3):
        # Doc Number (9) + check (1) + DOB (6) + check (1) + Expiry (6) + check (1) + Optional Data (15)
        #
        # Built from the already-normalized field values above rather than raw
        # line2 slices: an OCR digit/letter confusion in the DOB or expiry
        # field (e.g. '0' misread as 'O') is exactly what normalize_digits
        # corrects for the individual field checksums, which is why those
        # pass -- but computing the composite from the raw, un-normalized
        # slice re-introduces the same corruption ('O' and '0' have different
        # ICAO character values), spuriously failing composite validation on
        # an entirely genuine document. doc_number_raw itself is intentionally
        # NOT normalized -- document numbers legitimately contain letters.
        #
        # optional_data is NOT normalized the way dob_raw/expiry_raw are:
        # unlike those, which ICAO 9303 mandates are strictly numeric,
        # optional data is issuer-defined and genuinely varies -- confirmed
        # against real MIDV-2020 scans, where Greek passports leave it blank
        # filler (occasionally with one literal trailing digit) while
        # Azerbaijani passports pack a real alphanumeric personal-ID code
        # into it (e.g. "KEK2K556"). Blindly normalizing it as if it were
        # numeric (an earlier version of this fix did exactly that) corrects
        # Greece's OCR noise but corrupts Azerbaijan's genuine letters
        # (S->5, O->0, etc.), breaking composite validation on entirely
        # unmodified documents -- verified directly: it dropped 61/100
        # genuine Azerbaijani ground-truth records from valid to invalid.
        #
        # Instead, try BOTH interpretations and accept either: this still
        # tolerates the confirmed real OCR-noise case (Greece) without
        # assuming every issuer's optional field is numeric. The tradeoff is
        # a real one, not a free lunch -- accepting two candidate checksums
        # instead of one roughly doubles the chance a genuinely corrupted
        # composite coincidentally validates (~1/10 -> ~1/5 for a
        # single-digit checksum) -- but the alternative (blanket normalize)
        # was measurably worse: a strictly higher false-invalid rate on
        # real, unmodified documents. Both individual field checksums
        # (doc number, DOB, expiry) are UNCHANGED and still each single-
        # candidate, so this tradeoff is scoped to the composite only.
        composite_data_raw = doc_number_raw + doc_number_cd + dob_raw + dob_cd + expiry_raw + expiry_cd + optional_raw
        composite_data_normalized = (
            doc_number_raw + doc_number_cd + dob_raw + dob_cd + expiry_raw + expiry_cd
            + cls.normalize_digits(optional_raw)
        )
        calc_composite_cd = cls.compute_check_digit(composite_data_raw)
        calc_composite_cd_normalized = cls.compute_check_digit(composite_data_normalized)

        checksums = [
            {
                "field": "Document Number Checksum",
                "value": doc_number_raw,
                "check_digit": doc_number_cd,
                "calculated_check_digit": calc_doc_cd,
                "valid": doc_number_cd == calc_doc_cd
            },
            {
                "field": "Date of Birth Checksum",
                "value": dob_raw,
                "check_digit": dob_cd,
                "calculated_check_digit": calc_dob_cd,
                "valid": dob_cd == calc_dob_cd
            },
            {
                "field": "Expiry Date Checksum",
                "value": expiry_raw,
                "check_digit": expiry_cd,
                "calculated_check_digit": calc_expiry_cd,
                "valid": expiry_cd == calc_expiry_cd
            },
            {
                "field": "Composite Checksum",
                "value": "Composite Checksum Payload",
                "check_digit": composite_cd,
                "calculated_check_digit": calc_composite_cd,
                "valid": composite_cd in (calc_composite_cd, calc_composite_cd_normalized)
            }
        ]

        all_valid = all(cs["valid"] for cs in checksums)

        return {
            "format": "TD3",
            "line1": line1,
            "line2": line2,
            "document_type": doc_type or "P",
            "country": country,
            "surname": surname,
            "given_names": given_names,
            "document_number": doc_number,
            "nationality": nationality,
            "birth_date": dob_raw,
            "sex": sex,
            "expiry_date": expiry_raw,
            "optional_data": optional_data,
            "checksums": checksums,
            "is_valid": all_valid
        }

    @classmethod
    def parse_td1(cls, line1: str, line2: str, line3: str) -> Dict[str, Any]:
        """
        Parses TD1 format (national ID cards, 3 lines of 30 characters).
        Line 1: [Doc type 2][Country 3][Doc# 9][Doc# CD 1][Optional 15]
        Line 2: [DOB 6][DOB CD 1][Sex 1][Expiry 6][Expiry CD 1][Nationality 3][Optional 11][Composite CD 1]
        Line 3: [Surname]<<[Given Names]...
        """
        line1 = cls._reconstruct_length(cls.clean_mrz_line(line1), 30)
        line2 = cls._reconstruct_length(cls.clean_mrz_line(line2), 30)
        line3 = cls._reconstruct_length(cls.clean_mrz_line(line3), 30)

        doc_type = line1[0:2].replace('<', '')
        country = cls.normalize_letters(line1[2:5].replace('<', ''))

        doc_number_raw = line1[5:14]
        doc_number = doc_number_raw.replace('<', '')
        doc_number_cd = cls.normalize_digits(line1[14])
        optional1_raw = line1[15:30]

        dob_raw = cls.normalize_digits(line2[0:6])
        dob_cd = cls.normalize_digits(line2[6])

        # See parse_td3's comment: preserve a garbled sex character as-is
        # rather than defaulting it to 'M', so Rule 7 (SEX_CODE_FORMAT) can
        # actually see and flag it.
        sex = 'X' if line2[7] == '<' else line2[7].upper()

        expiry_raw = cls.normalize_digits(line2[8:14])
        expiry_cd = cls.normalize_digits(line2[14])

        nationality = cls.normalize_letters(line2[15:18].replace('<', ''))
        optional2_raw = line2[18:29]
        composite_cd = cls.normalize_digits(line2[29])

        name_parts = line3.split('<<')
        surname = name_parts[0].replace('<', ' ').strip()
        given_names = ""
        if len(name_parts) > 1:
            given_names = name_parts[1].replace('<', ' ').strip()

        calc_doc_cd = cls.compute_check_digit(doc_number_raw)
        calc_dob_cd = cls.compute_check_digit(dob_raw)
        calc_expiry_cd = cls.compute_check_digit(expiry_raw)

        # Composite payload per ICAO 9303-5: line1's doc-number-through-
        # optional-data-1 span, plus line2's DOB+CD, expiry+CD, and
        # optional-data-2 spans -- built from the same already-normalized
        # field values as the individual checksums above, for the same
        # reason as TD3's composite (see parse_td3): computing it from raw,
        # un-normalized slices would re-fail on ordinary OCR digit/letter
        # noise the individual field checks already tolerate. The optional
        # spans use TD3's "try both raw and digit-normalized, accept either"
        # approach (see parse_td3's comment) rather than blanket-normalizing
        # them -- optional data is issuer-defined and not guaranteed numeric.
        composite_data_raw = (
            doc_number_raw + doc_number_cd + optional1_raw
            + dob_raw + dob_cd + expiry_raw + expiry_cd + optional2_raw
        )
        composite_data_normalized = (
            doc_number_raw + doc_number_cd + cls.normalize_digits(optional1_raw)
            + dob_raw + dob_cd + expiry_raw + expiry_cd + cls.normalize_digits(optional2_raw)
        )
        calc_composite_cd = cls.compute_check_digit(composite_data_raw)
        calc_composite_cd_normalized = cls.compute_check_digit(composite_data_normalized)

        checksums = [
            {
                "field": "Document Number Checksum",
                "value": doc_number_raw,
                "check_digit": doc_number_cd,
                "calculated_check_digit": calc_doc_cd,
                "valid": doc_number_cd == calc_doc_cd
            },
            {
                "field": "Date of Birth Checksum",
                "value": dob_raw,
                "check_digit": dob_cd,
                "calculated_check_digit": calc_dob_cd,
                "valid": dob_cd == calc_dob_cd
            },
            {
                "field": "Expiry Date Checksum",
                "value": expiry_raw,
                "check_digit": expiry_cd,
                "calculated_check_digit": calc_expiry_cd,
                "valid": expiry_cd == calc_expiry_cd
            },
            {
                "field": "Composite Checksum",
                "value": "Composite Checksum Payload",
                "check_digit": composite_cd,
                "calculated_check_digit": calc_composite_cd,
                "valid": composite_cd in (calc_composite_cd, calc_composite_cd_normalized)
            }
        ]
        all_valid = all(cs["valid"] for cs in checksums)

        return {
            "format": "TD1",
            "line1": line1,
            "line2": line2,
            "line3": line3,
            "document_type": doc_type or "I",
            "country": country,
            "surname": surname,
            "given_names": given_names,
            "document_number": doc_number,
            "nationality": nationality,
            "birth_date": dob_raw,
            "sex": sex,
            "expiry_date": expiry_raw,
            "optional_data": (optional1_raw + optional2_raw).replace('<', ''),
            "checksums": checksums,
            "is_valid": all_valid
        }

    @classmethod
    def parse_td2(cls, line1: str, line2: str) -> Dict[str, Any]:
        """
        Parses TD2 format (visas and some ID cards, 2 lines of 36 characters).
        Line 1: [Doc type 2][Country 3][Surname]<<[Given Names]...
        Line 2: [Doc# 9][Doc# CD 1][Nationality 3][DOB 6][DOB CD 1][Sex 1][Expiry 6][Expiry CD 1][Optional 7][Composite CD 1]
        """
        line1 = cls._reconstruct_length(cls.clean_mrz_line(line1), 36)
        line2 = cls._reconstruct_length(cls.clean_mrz_line(line2), 36)

        doc_type = line1[0:2].replace('<', '')
        country = cls.normalize_letters(line1[2:5].replace('<', ''))

        name_parts = line1[5:].split('<<')
        surname = name_parts[0].replace('<', ' ').strip()
        given_names = ""
        if len(name_parts) > 1:
            given_names = name_parts[1].replace('<', ' ').strip()

        doc_number_raw = line2[0:9]
        doc_number = doc_number_raw.replace('<', '')
        doc_number_cd = cls.normalize_digits(line2[9])

        nationality = cls.normalize_letters(line2[10:13].replace('<', ''))

        dob_raw = cls.normalize_digits(line2[13:19])
        dob_cd = cls.normalize_digits(line2[19])

        # See parse_td3's comment: preserve a garbled sex character as-is
        # rather than defaulting it to 'M', so Rule 7 (SEX_CODE_FORMAT) can
        # actually see and flag it.
        sex = 'X' if line2[20] == '<' else line2[20].upper()

        expiry_raw = cls.normalize_digits(line2[21:27])
        expiry_cd = cls.normalize_digits(line2[27])

        optional_raw = line2[28:35]
        optional_data = optional_raw.replace('<', '')

        composite_cd = cls.normalize_digits(line2[35])

        calc_doc_cd = cls.compute_check_digit(doc_number_raw)
        calc_dob_cd = cls.compute_check_digit(dob_raw)
        calc_expiry_cd = cls.compute_check_digit(expiry_raw)

        # optional_data uses TD3's "try both raw and digit-normalized,
        # accept either" approach -- see parse_td3's comment.
        composite_data_raw = doc_number_raw + doc_number_cd + dob_raw + dob_cd + expiry_raw + expiry_cd + optional_raw
        composite_data_normalized = (
            doc_number_raw + doc_number_cd + dob_raw + dob_cd + expiry_raw + expiry_cd
            + cls.normalize_digits(optional_raw)
        )
        calc_composite_cd = cls.compute_check_digit(composite_data_raw)
        calc_composite_cd_normalized = cls.compute_check_digit(composite_data_normalized)

        checksums = [
            {
                "field": "Document Number Checksum",
                "value": doc_number_raw,
                "check_digit": doc_number_cd,
                "calculated_check_digit": calc_doc_cd,
                "valid": doc_number_cd == calc_doc_cd
            },
            {
                "field": "Date of Birth Checksum",
                "value": dob_raw,
                "check_digit": dob_cd,
                "calculated_check_digit": calc_dob_cd,
                "valid": dob_cd == calc_dob_cd
            },
            {
                "field": "Expiry Date Checksum",
                "value": expiry_raw,
                "check_digit": expiry_cd,
                "calculated_check_digit": calc_expiry_cd,
                "valid": expiry_cd == calc_expiry_cd
            },
            {
                "field": "Composite Checksum",
                "value": "Composite Checksum Payload",
                "check_digit": composite_cd,
                "calculated_check_digit": calc_composite_cd,
                "valid": composite_cd in (calc_composite_cd, calc_composite_cd_normalized)
            }
        ]
        all_valid = all(cs["valid"] for cs in checksums)

        return {
            "format": "TD2",
            "line1": line1,
            "line2": line2,
            "document_type": doc_type or "I",
            "country": country,
            "surname": surname,
            "given_names": given_names,
            "document_number": doc_number,
            "nationality": nationality,
            "birth_date": dob_raw,
            "sex": sex,
            "expiry_date": expiry_raw,
            "optional_data": optional_data,
            "checksums": checksums,
            "is_valid": all_valid
        }

    @classmethod
    def _dispatch_by_line_shape(cls, lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Chooses between TD1 and TD3 by how many MRZ-shaped lines were
        found. Line COUNT reliably tells TD1 (always 3 lines) apart from
        the 2-line formats -- but TD2 and TD3 are NOT auto-detected apart
        from each other here, for a structural reason discovered while
        building this:

        TD2 and TD3 share an IDENTICAL line2 prefix layout (document
        number, nationality, DOB, sex, expiry all sit at the same
        offsets) and differ only in the optional-data field's length (7
        vs 15 chars) immediately before the final composite check digit.
        Whenever that optional field ends in '<' filler -- true for a
        blank optional field, and true for the overwhelming majority of
        real documents that only partially use it -- a genuine TD2 line
        ALSO parses as a checksum-valid TD3, because appending extra
        zero-value filler at the very tail of a checksum payload can
        never change its weighted sum. So a checksum-based tiebreak
        between the two is not actually a tiebreak: it silently prefers
        whichever was tried first, almost regardless of which one is
        real. (Raw OCR length doesn't help either -- a dedicated MRZ-band
        pass routinely undercounts a long run of trailing '<' filler, see
        _reconstruct_length, so a genuine TD3 line just as routinely OCRs
        under 40 characters. A real production case hit exactly this: a
        genuine TD3 line2 read at 39 characters was misrouted into
        parse_td2's offsets by an earlier length-cutoff version of this
        function, corrupting every checksum on an entirely genuine
        document.)

        TD3 (passports) is this system's overwhelmingly dominant
        real-world case, so ambiguous 2-line input defaults to it.
        parse_td2 is still fully implemented and correct for a caller
        that already knows its input is TD2 (e.g. a dedicated visa/ID-
        card scanning path) -- it's just not blindly auto-selected here.
        """
        if len(lines) >= 3:
            return cls.parse_td1(lines[0], lines[1], lines[2])
        if len(lines) >= 2:
            return cls.parse_td3(lines[0], lines[1])
        return None

    @classmethod
    def extract_mrz_from_lines(cls, text_lines: List[str]) -> Optional[Dict[str, Any]]:
        """Scans extracted OCR text lines to find candidate MRZ lines and parses them."""
        cleaned = [cls.clean_mrz_line(l) for l in text_lines if l]

        def is_mrz_shaped(line: str, min_len: int) -> bool:
            return len(line) >= min_len and '<' in line

        # TD1's 3-line shape is checked first since it's the one signal that
        # can't be confused with the 2-line formats -- a genuine TD1 triplet
        # must not be mistaken for a TD2/TD3 pair drawn from just its first
        # two lines.
        for i in range(len(cleaned) - 2):
            l1, l2, l3 = cleaned[i], cleaned[i + 1], cleaned[i + 2]
            if all(is_mrz_shaped(l, 25) for l in (l1, l2, l3)):
                return cls.parse_td1(l1, l2, l3)

        # Look for a 2-line pair (TD3, or TD2 -- see _dispatch_by_line_shape's
        # docstring for why the two aren't auto-distinguished). Requiring the
        # first line to start with a document-code-like prefix (or at least
        # contain '<') keeps this from matching arbitrary prose that happens
        # to contain a stray '<'.
        for i in range(len(cleaned) - 1):
            l1, l2 = cleaned[i], cleaned[i + 1]
            if is_mrz_shaped(l1, 30) and is_mrz_shaped(l2, 30) and (l1.startswith('P') or '<' in l1):
                return cls._dispatch_by_line_shape([l1, l2])

        # Fallback: look for lines containing multiple '<<'
        mrz_candidates = [l for l in cleaned if l.count('<') >= 4 and len(l) >= 30]
        if len(mrz_candidates) >= 2:
            return cls._dispatch_by_line_shape(mrz_candidates[:3])

        return None

    @classmethod
    def parse_pre_isolated_lines(cls, text_lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parses lines that a caller has already isolated as the MRZ band (e.g. a
        dedicated MRZ-region OCR pass -- see TesseractOCRService.extract_mrz_lines),
        skipping extract_mrz_from_lines' whole-document scanning heuristic.

        That heuristic requires ~40-character lines to avoid false-positives when
        scanning arbitrary prose text, but a cropped, upscaled, restricted-charset
        MRZ pass often doesn't capture a long run of near-invisible trailing '<'
        filler even when every character it did read is correct -- parse_td3
        right-pads short-but-accurate lines to 44 chars, so no length gate is
        needed once the lines are already known to be the MRZ. Line count alone
        (2 vs 3) tells the caller's isolated band apart as TD1 vs a 2-line format.
        """
        cleaned = [cls.clean_mrz_line(l) for l in text_lines if l]
        return cls._dispatch_by_line_shape(cleaned)
