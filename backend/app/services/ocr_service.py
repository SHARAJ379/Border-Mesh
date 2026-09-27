import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.utils.text_similarity import levenshtein

class BaseOCRService(ABC):
    @abstractmethod
    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """Extracts text, parsed fields, and confidence from document image."""
        pass

class TesseractOCRService(BaseOCRService):
    def __init__(self):
        # Point to configured tesseract binary if available
        if os.path.exists(settings.TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

    @staticmethod
    def _estimate_skew_angle(gray: np.ndarray) -> float:
        """
        Estimates a document photo's rotation from the minimum-area bounding
        box of its dark (text/print) pixels -- reliable on a mostly-text
        document since printed lines dominate the foreground's orientation.

        cv2.minAreaRect's angle is relative to whichever of the box's two
        sides it reports first, which flips depending on the box's own
        aspect ratio: when the box's reported width is its SHORT side
        (w < h), the angle is 90 degrees off from the rotation that would
        make on-page text run horizontal. Verified empirically against known
        rotations rather than assumed, since this convention has changed
        across OpenCV versions.

        Returns 0.0 when there isn't enough foreground to estimate
        confidently, or when the estimate is implausibly large (more likely
        a bad fit on sparse/non-text content than a real extreme tilt).
        """
        inverted = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = cv2.findNonZero(thresh)
        if coords is None or len(coords) < 100:
            return 0.0

        (w, h), angle = cv2.minAreaRect(coords)[1:]
        correction = angle + 90 if w < h else angle

        if abs(correction) > 20:
            return 0.0
        return correction

    @staticmethod
    def _deskew(gray: np.ndarray) -> np.ndarray:
        """
        Rotates a document photo so printed text lines run horizontal.

        A photographed (rather than flatbed-scanned) document is rarely
        perfectly axis-aligned. That matters twice over here: a tilted MRZ
        line is measurably harder for Tesseract to read character-perfectly
        even when it's otherwise sharp -- and a single misread character
        fails an MRZ checksum outright -- and extract_mrz_lines crops a
        FIXED bottom fraction of the image to isolate the MRZ band, which a
        several-degree rotation can shift enough to clip or unevenly split
        across that fixed boundary.
        """
        angle = TesseractOCRService._estimate_skew_angle(gray)
        if abs(angle) < 0.3:
            return gray  # not worth the interpolation cost/risk on a near-straight image

        h, w = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        OpenCV image preprocessing pipeline:
        1. Read image
        2. Resize / normalize resolution (e.g. 1500px width minimum)
        3. Convert to grayscale
        4. Deskew (correct rotation from an off-angle photo)
        5. CLAHE contrast enhancement
        6. Denoise
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Unable to read image at {image_path}")

        h, w = img.shape[:2]
        target_w = max(w, 1600)
        scale = target_w / w
        target_h = int(h * scale)
        resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = self._deskew(gray)

        # Contrast Limited Adaptive Histogram Equalization
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Subtle Gaussian blur to reduce high-frequency noise
        denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
        return denoised

    def extract_mrz_lines(self, image_path: str) -> List[str]:
        """
        Dedicated MRZ-band OCR pass, separate from general document-field OCR.

        The general pass is tuned for mixed-case prose text across the whole
        document and struggles with the MRZ's small monospace OCR-B font --
        misreading '<' fillers, confusing O/0, etc. This crops just the bottom
        band where ICAO 9303 places the MRZ, upscales it heavily, binarizes it,
        and constrains Tesseract to the MRZ character set (A-Z0-9<) with a
        single-uniform-block page segmentation mode, which is the standard
        technique for reliable MRZ OCR.
        """
        img = cv2.imread(image_path)
        if img is None:
            return []

        # Deskew the FULL image before cropping -- the crop below takes a
        # fixed bottom fraction, and an off-angle photo shifts the MRZ band
        # unevenly (one end down, the other up) relative to that fixed line,
        # which correcting only after cropping can't undo.
        full_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        full_gray = self._deskew(full_gray)

        h, w = full_gray.shape[:2]
        # ICAO 9303 places the MRZ in the bottom portion of the bio-data page;
        # crop generously (bottom 30%) so TD1's 3 lines fit with margin
        # (TD3/TD2's 2 lines fit comfortably within the same crop).
        band_gray = full_gray[int(h * 0.70):h, 0:w]
        if band_gray.size == 0:
            return []

        # Upscale substantially -- small monospace glyphs need real pixel height
        # for Tesseract to resolve them reliably.
        bh, bw = band_gray.shape[:2]
        scale = max(1.0, 2200 / bw)
        upscaled = cv2.resize(
            band_gray, (int(bw * scale), int(bh * scale)), interpolation=cv2.INTER_CUBIC
        )

        # Otsu binarization: MRZ print is high-contrast dark-on-light, so a
        # global threshold is robust and avoids adaptive-threshold noise on
        # otherwise-blank background.
        _, binarized = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Generous white padding: without it, Tesseract can silently drop the
        # last character of a line (observed with `--psm 6` when the trailing
        # glyph sits close to the image edge -- font rendering differences
        # between environments shift exactly how close). Padding plus `--psm 4`
        # (assume a single column of text, appropriate for MRZ's left-aligned
        # block) eliminated this in testing; `--psm 6` did not.
        padded = cv2.copyMakeBorder(binarized, 20, 20, 20, 60, cv2.BORDER_CONSTANT, value=255)

        mrz_config = (
            "--psm 4 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        )
        try:
            raw = pytesseract.image_to_string(padded, config=mrz_config)
        except Exception:
            # Mirrors extract_text's own except block: a missing/misconfigured
            # Tesseract binary (TesseractNotFoundError) or any other engine
            # failure must degrade, not crash the screening request. Returning
            # [] here is indistinguishable to the caller from "no MRZ band
            # detected," which rules_engine.py's RULE 1 already treats as a
            # HIGH-severity "Missing Machine Readable Zone" signal for
            # documents expected to carry one -- routing the case to review
            # instead of failing the request outright.
            return []

        candidates = [
            re.sub(r'[^A-Z0-9<]', '', line.upper())
            for line in raw.splitlines()
        ]
        # MRZ lines are long (44 chars for TD3) and filler-heavy; keep only
        # lines that plausibly are MRZ rather than OCR noise.
        return [line for line in candidates if len(line) >= 20 and '<' in line]

    @staticmethod
    def _value_after_label(lines: List[str], keyword_pattern: str) -> Optional[str]:
        """
        Our synthetic documents render every field as a label line immediately
        followed by its value line (see SyntheticDocumentGenerator: label at
        y, value at y+18). Anchoring on the label's distinctive French half
        (e.g. "NOM", "NAISSANCE") and reading the line below it survives
        Tesseract garbling the English half of the label -- which regexing
        over the whole raw-text blob for the value itself cannot, since a
        mangled label often still contains real letters that a value-shaped
        pattern can accidentally match.
        """
        pattern = re.compile(keyword_pattern, re.IGNORECASE)
        for i, line in enumerate(lines):
            if pattern.search(line) and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None

    @staticmethod
    def _line_matches_label_words(line: str, label_words: List[str]) -> bool:
        """
        True if every word in `label_words` (already uppercase) shows up
        somewhere in `line`, either exactly or as a plausible single-word
        OCR misread -- reproduces a real failure found on an actual
        photographed Driving Licence: Tesseract read the genuine printed
        "VALID TILL" label as "VAUD TILL" (VALID -> VAUD is edit-distance 2:
        L misread as U, the I dropped entirely), which an exact literal-
        label match never catches. The edit-distance budget scales with
        word length (2 for 5+ letters, 1 otherwise) so short label words
        like "TILL"/"FROM" still need a near-exact match while longer ones
        tolerate the kind of multi-character slip observed here.
        """
        line_words = re.findall(r'[A-Z0-9]+', line.upper())
        for label_word in label_words:
            threshold = 2 if len(label_word) >= 5 else 1
            if not any(
                w == label_word or levenshtein(w, label_word) <= threshold
                for w in line_words
            ):
                return False
        return True

    @classmethod
    def _value_after_fuzzy_label(cls, lines: List[str], label_words: List[str]) -> Optional[str]:
        """Fallback for _value_after_label when the label itself may be
        OCR-garbled -- see _line_matches_label_words."""
        for i, line in enumerate(lines):
            if cls._line_matches_label_words(line, label_words) and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None

    @staticmethod
    def _extract_date(value_line: Optional[str]) -> Optional[str]:
        """
        Parses a date from a single labeled value line with a separator-
        tolerant pattern (day/month/year each 1-2 digits, 0-2 arbitrary
        non-digit separator characters between them) rather than requiring
        exact DD/MM/YYYY -- Tesseract sometimes drops a separator entirely
        (e.g. "01/01/2000" -> "0101/2000"), which a strict pattern misses.
        """
        if not value_line:
            return None
        m = re.search(r'(\d{1,2})\D{0,2}(\d{1,2})\D{0,2}(\d{4})', value_line)
        if not m:
            return None
        # Reproduces a real failure: this pattern's lenient, separator-
        # optional groups will assemble a "date" out of ANY bare 6-8 digit
        # run, including ones that aren't a date at all (observed live: a
        # 6-digit PIN code "560039" on an Aadhaar card parsed as day=05,
        # month=06, year=0039). A plausible human date's year must fall in
        # a sane range -- rejecting an implausible one here is a much
        # narrower fix than tightening the separator tolerance itself,
        # which was added deliberately to survive a different real OCR
        # failure (a dropped separator character).
        year = int(m.group(3))
        if not (1900 <= year <= 2099):
            return None
        return f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"

    # Markers that only appear on an Indian Aadhaar card, never on the
    # project's ICAO-style bilingual passport specimens -- used to route
    # extraction to the right label set rather than assuming one document
    # type. Checked against the raw OCR blob (pre line-splitting) so a
    # marker split across Tesseract's line breaks still matches.
    AADHAAR_MARKERS = (
        "AADHAAR", "UIDAI", "UNIQUE IDENTIFICATION AUTHORITY", "ENROLMENT"
    )

    # PAN cards are issued by the Income Tax Department, not UIDAI -- these
    # markers are distinct from Aadhaar's and from each other's, so checked
    # in a fixed order (PAN and DL both say "GOVT. OF INDIA" / state
    # boilerplate, but only one of the two ever also carries its own
    # document-specific marker) below in _detect_document_type.
    PAN_MARKERS = (
        "INCOME TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER"
    )

    # Driving Licences are issued per-state (Transport Department / RTO),
    # not centrally like PAN/Aadhaar -- "DRIVING LICENCE"/"DRIVING LICENSE"
    # itself is the one marker guaranteed present regardless of issuing
    # state.
    DL_MARKERS = (
        "DRIVING LICENCE", "DRIVING LICENSE", "TRANSPORT DEPARTMENT"
    )

    # Voter ID (EPIC) cards are issued centrally by the Election Commission
    # of India, not per-state like a Driving Licence -- "ELECTION COMMISSION
    # OF INDIA" is present regardless of issuing state, mirroring how
    # Aadhaar/PAN each have one central-issuer marker.
    VOTER_ID_MARKERS = (
        "ELECTION COMMISSION OF INDIA", "ELECTORS PHOTO IDENTITY CARD", "EPIC NO"
    )

    # Visa specimens are issued by this project's own fictional "Republic of
    # Utopia" (matching the passport specimen's own fictional issuer),
    # rather than modeled on any one real country's visa design -- there is
    # no single real template a visa could be validated against the way
    # Aadhaar/PAN/DL/EPIC each have one real national issuer and spec.
    # Deliberately NOT a bare "VISA" substring: generate_document's own
    # 'stamp_manipulated'/'multiple_anomalies' tamper modes draw a simulated
    # pasted stamp reading "VISA EXEMPTION [SIMULATED PATCH]" directly onto
    # a PASSPORT specimen, which a bare "VISA" marker would misroute to the
    # visa field parser instead of the passport one.
    VISA_MARKERS = (
        "ENTRY VISA", "BUREAU OF IMMIGRATION"
    )

    # Residence/work/entry/transit permits -- like Visa, issued by this
    # project's own fictional "Republic of Utopia" rather than modeled on
    # any one real country's permit design, since there's no single real
    # template to validate a generic permit against. Deliberately two-word
    # phrases (never a bare "PERMIT" substring): a bare substring would
    # false-positive on unrelated printed text that happens to mention a
    # permit in passing, the same reasoning VISA_MARKERS already applies
    # against a bare "VISA" substring.
    PERMIT_MARKERS = (
        "RESIDENCE PERMIT", "WORK PERMIT", "ENTRY PERMIT", "TRANSIT PERMIT"
    )

    @classmethod
    def _detect_document_type(cls, raw_text: str) -> str:
        """
        Aadhaar/PAN/Driving Licence cards carry none of the ICAO 9303
        furniture (MRZ, French/English bilingual field labels, passport-
        style document number) the passport field parser is anchored on --
        so field extraction must know up front which label set applies.
        Checked in a fixed, most-specific-first order since a real card can
        carry more than one issuer's boilerplate line (e.g. both a PAN and a
        DL mention "GOVT. OF INDIA" / state government text). Defaults to
        the existing passport-style path when no marker matches, preserving
        current behavior for the project's own demo specimens.
        """
        upper = raw_text.upper()
        if any(marker in upper for marker in cls.AADHAAR_MARKERS):
            return "AADHAAR"
        if any(marker in upper for marker in cls.PAN_MARKERS):
            return "PAN"
        if any(marker in upper for marker in cls.DL_MARKERS):
            return "DRIVING_LICENSE"
        if any(marker in upper for marker in cls.VOTER_ID_MARKERS):
            return "VOTER_ID"
        if any(marker in upper for marker in cls.VISA_MARKERS):
            return "VISA"
        if any(marker in upper for marker in cls.PERMIT_MARKERS):
            return "PERMIT"
        return "PASSPORT"

    # Document types with no ICAO 9303 Machine Readable Zone by design --
    # shared with screening.py (which skips the MRZ-band OCR pass for these)
    # and rules_engine.py (which treats a missing MRZ as expected, not a
    # HIGH-severity "Missing Machine Readable Zone" signal, for these). A
    # visa/permit is extract-only here (no MRZ format is modeled for
    # either), same as the other three.
    NON_MRZ_DOCUMENT_TYPES = ("AADHAAR", "PAN", "DRIVING_LICENSE", "VOTER_ID", "VISA", "PERMIT")

    @staticmethod
    def _extract_aadhaar_number(raw_text: str) -> Optional[str]:
        r"""
        The printed Aadhaar (UID) is always exactly 12 digits, conventionally
        grouped as 4-4-4 with spaces -- distinct from the Enrolment Number
        (a slash-separated tracking ID also printed on the card, e.g.
        "4050/00286/01675") which must NOT be mistaken for the identity
        number itself. The space between groups is treated as optional at
        each boundary independently (`\s?`, not a mandatory `\s`) rather
        than requiring the whole group to be either fully spaced or fully
        bare -- observed live against real Tesseract output, which dropped
        only ONE of the two group separators ("1234 5678 9012" ->
        "12345678 9012"), a case a same-either-way regex misses. The `\s?`
        gap still can't match the enrolment ID's "/" separators, so it
        can't accidentally bridge digits out of that field.

        Also distinct from the 16-digit VID (Virtual ID) many modern
        Aadhaar cards print alongside the UID, conventionally grouped
        4-4-4-4 the same way -- a real silent-wrongness bug: a version of
        this regex that only checked the single character immediately
        after a candidate 12-digit run wasn't a bare digit let a VID's
        OWN 4th group boundary (a space, not a digit) satisfy that check,
        silently returning the VID's first 12 digits as this person's
        Aadhaar number. Matching the FULL surrounding digit-and-single-
        space cluster first, then requiring it to total exactly 12 digits
        once spaces are stripped, rejects any longer (or shorter) run as a
        whole rather than letting a same-length WINDOW inside it match --
        a 16-digit VID cluster is checked and rejected as one unit, and
        `finditer` then keeps searching past it for a genuinely separate
        12-digit cluster elsewhere on the card.
        """
        for m in re.finditer(r'(?<![\d/])\d(?:\s?\d){8,19}(?![\d/])', raw_text):
            digits = re.sub(r'\s', '', m.group(0))
            if len(digits) == 12:
                return digits
        return None

    def parse_aadhaar_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from an Aadhaar card. Unlike the
        passport path's fixed label-above-value layout, Aadhaar printouts
        vary in field placement, so each field uses whichever keyword
        pattern is most reliable for it individually rather than one
        uniform strategy.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": "INDIA",
            "country": "INDIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,  # Aadhaar has no expiry
            "sex": None
        }

        fields["document_number"] = self._extract_aadhaar_number(raw_text)

        # DOB is most often printed on the SAME line as its label
        # ("DOB: 01/01/1990"), unlike the passport path's fixed
        # label-above-value layout -- try the label's own line first, and
        # only fall back to the line below it if that line has no date of
        # its own (a label-only line, value printed underneath).
        #
        # Keeps scanning past a matching label line that yields no real
        # date rather than committing to it -- reproduces a real failure:
        # a genuine Aadhaar card's own disclaimer text ("...not of
        # citizenship or date of birth (DOB)...") mentions the word "DOB"
        # well before the holder's own labeled DOB field, and the old code
        # locked onto that first incidental mention (and its unrelated
        # next line) instead of continuing to look for a line that
        # actually parses as a date.
        dob_label_pattern = r'\b(DOB|DATE OF BIRTH)\b'
        dob_line = None
        for i, line in enumerate(lines):
            if not re.search(dob_label_pattern, line, re.IGNORECASE):
                continue
            candidate = line if self._extract_date(line) else (
                lines[i + 1] if i + 1 < len(lines) else None
            )
            if self._extract_date(candidate):
                dob_line = candidate
                break
        fields["date_of_birth"] = self._extract_date(dob_line)

        gender_match = re.search(r'\b(MALE|FEMALE|TRANSGENDER)\b', raw_text, re.IGNORECASE)
        if gender_match:
            gender = gender_match.group(1).upper()
            fields["sex"] = "M" if gender == "MALE" else ("F" if gender == "FEMALE" else "X")

        # Name isn't behind a consistent label on Aadhaar printouts -- fall
        # back to the same name-shaped-line heuristic as the passport path's
        # fallback, extended with Aadhaar's own institutional boilerplate so
        # header text ("Government of India", "Unique Identification
        # Authority of India") isn't mistaken for the holder's name.
        #
        # Window widened from the original 10 lines, and a real name (a
        # space-separated multi-word run) is now required: reproduces a
        # real failure on an actual Aadhaar photo where a single OCR-
        # garbled token from unrelated boilerplate text ("cendaiead.")
        # fullmatched this same letters-only pattern and won purely
        # because it appeared earlier in the scan than the real name.
        # NOTE this does not catch every real-world case -- a multi-word
        # garbled fragment that also dodges the boilerplate keyword
        # exclusion below (e.g. "Unique" OCR'd as "Unaque") can still win;
        # that residual gap needs fuzzy/approximate keyword matching or a
        # different extraction strategy entirely, out of scope here.
        for line in lines[:15]:
            clean_l = line.strip()
            if (
                len(clean_l) > 4
                and " " in clean_l
                and re.fullmatch(r"[A-Za-z.'\- ]+", clean_l)
                and not re.search(r'\b(DOB|DATE OF BIRTH|MALE|FEMALE|TRANSGENDER)\b', clean_l, re.IGNORECASE)
                # Individual words, not multi-word phrases: real Tesseract
                # output on a live test dropped the space between
                # "Government" and "of" ("Governmentof India"), which
                # silently defeated a "GOVERNMENT OF INDIA" phrase-substring
                # check while leaving "GOVERNMENT" itself intact as a
                # substring of the merged word.
                and not any(k in clean_l.upper() for k in [
                    "GOVERNMENT", "UNIQUE", "IDENTIFICATION", "AUTHORITY",
                    "AADHAAR", "ENROLMENT", "UIDAI"
                ])
                # Closes the "multi-word garbled fragment" gap the single-
                # token fix above explicitly left open: a real Aadhaar
                # prints the holder's name in Hindi (Devanagari) directly
                # above the English name, and this OCR pass runs English-
                # only (no `-l` flag on GENERAL_OCR_CONFIG), so that line
                # comes back as garbled Latin-letter noise -- observed live
                # as "weddseah Ja hMA so Hsod". That noise is letters-only,
                # multi-word, and dodges the boilerplate exclusion above,
                # but unlike a real printed name (always either Title Case
                # or ALL CAPS, consistently) it has no coherent internal
                # capitalization pattern. `str.istitle()`/`str.isupper()`
                # already encode exactly that real-world convention
                # correctly, including for apostrophes/hyphens (e.g.
                # "O'Brien") and single-letter middle initials -- no need
                # to hand-roll the same check with a regex.
                and (clean_l.istitle() or clean_l.isupper())
            ):
                fields["full_name"] = clean_l
                break

        return fields

    @staticmethod
    def _extract_pan_number(raw_text: str) -> Optional[str]:
        """
        A PAN is always exactly 5 letters, 4 digits, then 1 letter (10
        characters total, e.g. "ABCPK1234F") -- CBDT's published structural
        format. Word boundaries on both sides keep this from matching a
        10-character substring embedded inside a longer alphanumeric token
        (a reference number, a barcode string, etc.).
        """
        m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', raw_text.upper())
        return m.group(1) if m else None

    def parse_pan_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from a PAN card. Real PAN cards print
        "Name", "Father's Name", and "Date of Birth" as their own label
        lines with the value directly beneath -- the same label-above-value
        layout the passport path's `_value_after_label` already assumes, so
        it's reused here rather than duplicated.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": "INDIA",
            "country": "INDIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,  # PAN has no expiry -- it's a lifetime identifier
            "sex": None
        }

        fields["document_number"] = self._extract_pan_number(raw_text)

        # A plain \bNAME\b search would also match "Father's Name" -- which
        # PAN cards print as its own separate label line -- and, since
        # _value_after_label returns on the first match, silently take the
        # holder's father's name instead of their own the moment the "Name"
        # label line itself is missed by OCR. Explicitly skip any line
        # mentioning "FATHER" rather than relying on label ordering alone.
        for i, line in enumerate(lines):
            if (
                re.search(r'\bNAME\b', line, re.IGNORECASE)
                and 'FATHER' not in line.upper()
                and i + 1 < len(lines)
            ):
                fields["full_name"] = lines[i + 1].strip()
                break

        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF BIRTH\b'))

        return fields

    @staticmethod
    def _extract_dl_number(raw_text: str) -> Optional[str]:
        r"""
        The nationwide standardized ("Sarathi") Driving Licence number is a
        2-letter state code, a 2-digit RTO code, a 4-digit issue year, and a
        7-digit serial -- 15 characters total. Real printouts commonly space
        or dash-separate each of those groups (e.g. "MH-12 2011-0012345");
        each boundary is treated as an independently optional separator
        (matching the Aadhaar number extractor's own `\s?`-per-boundary
        approach) rather than requiring one consistent style throughout, and
        the matched groups are re-joined bare so the returned number is
        always the normalized 15-char form.
        """
        m = re.search(r'\b([A-Z]{2})[\s-]?(\d{2})[\s-]?(\d{4})[\s-]?(\d{7})\b', raw_text.upper())
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}" if m else None

    def parse_dl_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from an Indian Driving Licence. Unlike
        Aadhaar/PAN, a DL carries a genuine printed expiry ("Valid Till") --
        populating date_of_expiry here is what lets the rules engine's
        existing expiration check (previously MRZ-only) apply to DLs too.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": "INDIA",
            "country": "INDIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
            "sex": None
        }

        fields["document_number"] = self._extract_dl_number(raw_text)
        fields["full_name"] = self._value_after_label(lines, r"\bNAME\b")
        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF BIRTH\b'))
        fields["date_of_issue"] = self._extract_date(
            self._value_after_label(lines, r'\bVALID FROM\b')
            or self._value_after_fuzzy_label(lines, ["VALID", "FROM"])
        )
        fields["date_of_expiry"] = self._extract_date(
            self._value_after_label(lines, r'\bVALID TILL\b')
            or self._value_after_fuzzy_label(lines, ["VALID", "TILL"])
        )

        return fields

    @staticmethod
    def _extract_voter_id_number(raw_text: str) -> Optional[str]:
        """
        The Election Commission of India's current EPIC number format is 3
        letters followed by 7 digits (10 characters total) -- distinct from
        PAN's 5-letters/4-digits/1-letter shape and Aadhaar's 12 bare
        digits, so word boundaries on both sides are enough to avoid
        cross-matching either of those on a document that happens to also
        carry one nearby (e.g. a reference number). Unlike PAN's 4th-letter
        entity-type code, the 3 letters here have no publicly documented
        decodable meaning -- they are not decoded or otherwise interpreted.
        """
        m = re.search(r'\b([A-Z]{3}[0-9]{7})\b', raw_text.upper())
        return m.group(1) if m else None

    def parse_voter_id_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from an Indian Voter ID (EPIC) card. Like
        PAN, a Voter ID has no genuine expiry -- it's a lifetime identifier.
        Real cards print the elector's name alongside a relation name
        (Father's/Husband's/Mother's Name, depending on the elector) as two
        separate label-above-value blocks; the relation-name line must be
        excluded the same way PAN's parser excludes "Father's Name" from
        matching \bNAME\b, since _value_after_label returns on first match.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": "INDIA",
            "country": "INDIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,  # Voter ID has no expiry -- it's a lifetime identifier
            "sex": None
        }

        fields["document_number"] = self._extract_voter_id_number(raw_text)

        for i, line in enumerate(lines):
            if (
                re.search(r'\bNAME\b', line, re.IGNORECASE)
                and not any(k in line.upper() for k in ["FATHER", "HUSBAND", "MOTHER"])
                and i + 1 < len(lines)
            ):
                fields["full_name"] = lines[i + 1].strip()
                break

        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF BIRTH\b'))

        gender_match = re.search(r'\b(MALE|FEMALE|THIRD GENDER)\b', raw_text, re.IGNORECASE)
        if gender_match:
            gender = gender_match.group(1).upper()
            fields["sex"] = "M" if gender == "MALE" else ("F" if gender == "FEMALE" else "X")

        return fields

    def parse_visa_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from a Visa specimen. Like Aadhaar/PAN/
        DL/Voter ID, this is a plain label-above-value layout, so the
        existing _value_after_label helper covers every field directly --
        no dedicated regex extractor for the visa number is needed (unlike
        PAN/DL/EPIC, there is no publicly documented visa-numbering
        structure to check the shape of, or to fall back on when a label
        line is OCR-garbled).

        Visa Number is extract-only: no checksum or structural format is
        invented for it, the same honest posture as Aadhaar's document
        number (Aadhaar has no format-validation rule in rules_engine.py
        either).

        'Stay Duration' is modeled as a printed validity date (the date
        until which the holder may remain), not a duration-in-days count --
        this is what lets DocumentRulesEngine's new VISA_STAY_DURATION_
        VALIDATION rule reuse RULE 2's own date-plausibility pattern
        directly, the same way a DL's 'Valid Till' does for
        DOCUMENT_EXPIRATION. It is intentionally a separate field from
        date_of_expiry (left None here) rather than reusing that key: a
        real visa's own validity window (when it can be used to enter) and
        the permitted duration of a given stay are genuinely distinct
        concepts, and populating date_of_expiry here would silently double
        up with RULE 2's own generic expiry check instead of exercising the
        dedicated visa rule.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": None,
            "country": "REPUBLIC OF UTOPIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
            "sex": None,
            "visa_type": None,
            "entry_validation": None,
            "stay_duration_until": None
        }

        # Reproduces a real failure found by rendering an actual specimen
        # through real Tesseract: the small label-font "R" in "VISA NUMBER"
        # was misread as "VISA NUMBEF" (an exact-match label search returns
        # None entirely on this single-character slip) -- the same class of
        # failure DL's "VALID TILL"/"VAUD TILL" fix addressed, and the same
        # fuzzy-label fallback fixes it here.
        fields["document_number"] = (
            self._value_after_label(lines, r'\bVISA NUMBER\b')
            or self._value_after_fuzzy_label(lines, ["VISA", "NUMBER"])
        )
        fields["full_name"] = self._value_after_label(lines, r'\bFULL NAME\b')
        fields["nationality"] = self._value_after_label(lines, r'\bNATIONALITY\b')
        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF BIRTH\b'))
        fields["visa_type"] = self._value_after_label(lines, r'\bVISA TYPE\b')
        fields["entry_validation"] = self._value_after_label(lines, r'\bENTRY VALIDATION\b')
        fields["date_of_issue"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF ISSUE\b'))
        fields["stay_duration_until"] = self._extract_date(self._value_after_label(lines, r'\bSTAY DURATION\b'))

        return fields

    def parse_permit_fields(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts structured fields from a residence/work/entry/transit
        Permit specimen. Like Visa, a plain label-above-value layout, so
        the existing _value_after_label helper covers every field. Permit
        Number is extract-only, the same honest posture as Visa Number /
        Aadhaar's document number: no checksum or structural format is
        invented for it since no single real issuing authority's format
        exists to check against.
        """
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": None,
            "country": "REPUBLIC OF UTOPIA",
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
            "sex": None,
            "permit_type": None,
            "issuing_authority": None
        }

        fields["document_number"] = (
            self._value_after_label(lines, r'\bPERMIT NUMBER\b')
            or self._value_after_fuzzy_label(lines, ["PERMIT", "NUMBER"])
        )
        fields["full_name"] = self._value_after_label(lines, r'\bFULL NAME\b')
        fields["nationality"] = self._value_after_label(lines, r'\bNATIONALITY\b')
        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF BIRTH\b'))
        fields["permit_type"] = self._value_after_label(lines, r'\bPERMIT TYPE\b')
        fields["issuing_authority"] = self._value_after_label(lines, r'\bISSUING AUTHORITY\b')
        fields["date_of_issue"] = self._extract_date(self._value_after_label(lines, r'\bDATE OF ISSUE\b'))
        fields["date_of_expiry"] = self._extract_date(
            self._value_after_label(lines, r'\bDATE OF EXPIRY\b')
            or self._value_after_fuzzy_label(lines, ["DATE", "OF", "EXPIRY"])
        )

        return fields

    def parse_fields_from_text(self, raw_text: str, lines: List[str]) -> Dict[str, Any]:
        """Extracts structured document fields, anchored on each field's own label line."""
        fields: Dict[str, Any] = {
            "full_name": None,
            "document_number": None,
            "nationality": None,
            "country": None,
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
            "sex": None
        }

        # Search for document numbers (letters followed by 7-8 digits, e.g. A1234567, X12345678, P1234567)
        doc_no_match = re.search(r'\b([A-Z]{1,2}\d{7,8})\b', raw_text)
        if doc_no_match:
            fields["document_number"] = doc_no_match.group(1)

        fields["date_of_birth"] = self._extract_date(self._value_after_label(lines, r'\bNAISSANCE\b'))
        # No leading \b: the apostrophe in "D'EXPIRATION" is frequently
        # dropped by OCR, fusing it into "DEXPIRATION" with no word boundary
        # before EXPIRATION itself -- only require the trailing boundary.
        fields["date_of_expiry"] = self._extract_date(self._value_after_label(lines, r'EXPIRATION\b'))

        fields["country"] = self._value_after_label(lines, r'\bPAYS\b')
        fields["nationality"] = self._value_after_label(lines, r'\bNATIONALITE\b')

        sex_value = self._value_after_label(lines, r'\bSEXE\b')
        if sex_value and sex_value[:1].upper() in ("M", "F", "X"):
            fields["sex"] = sex_value[:1].upper()

        surname = self._value_after_label(lines, r'\bNOM\b')
        given_names = self._value_after_label(lines, r'\bPRENOM')
        if surname and given_names:
            fields["full_name"] = f"{surname} {given_names}"
        elif surname or given_names:
            fields["full_name"] = surname or given_names
        else:
            # Fallback for documents that don't follow our label-above-value
            # layout: scan upper case lines before the MRZ.
            for line in lines[:8]:
                clean_l = line.strip()
                if len(clean_l) > 4 and clean_l.isupper() and not any(k in clean_l for k in ["PASSPORT", "REPUBLIC", "DEMO", "TRAVEL", "DOCUMENT"]):
                    fields["full_name"] = clean_l
                    break

        return fields

    # Forces single-column page segmentation rather than Tesseract's default
    # fully-automatic layout analysis (PSM 3). Reproduces a real failure
    # found by running an actual photographed Aadhaar card (not a synthetic
    # specimen) through this pipeline: PSM 3's automatic segmentation
    # produced near-total garbage on that real, denser, mixed-script/
    # QR-code layout (Tesseract's own OSD reported near-zero orientation/
    # script confidence), while this same PSM (already used by
    # extract_mrz_lines, for the same underlying reason) recovered the
    # document almost completely. Confirmed byte-for-byte identical output
    # to the old default on every synthetic specimen this project generates
    # (passport, PAN, driving licence, voter ID) -- this is a real-document
    # robustness fix, not a synthetic-path behavior change.
    GENERAL_OCR_CONFIG = "--psm 4"

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        try:
            preprocessed = self.preprocess_image(image_path)

            # Use PyTesseract with both text and layout analysis
            ocr_data = pytesseract.image_to_data(
                preprocessed, output_type=pytesseract.Output.DICT, config=self.GENERAL_OCR_CONFIG
            )
            raw_text = pytesseract.image_to_string(preprocessed, config=self.GENERAL_OCR_CONFIG)

            # Compute average confidence over non-empty words
            confs = [float(c) for c in ocr_data.get("conf", []) if str(c).replace("-1", "").strip()]
            avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.88
            avg_conf = max(0.40, min(0.99, round(avg_conf, 2)))

            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            document_type = self._detect_document_type(raw_text)
            if document_type == "AADHAAR":
                fields = self.parse_aadhaar_fields(raw_text, lines)
            elif document_type == "PAN":
                fields = self.parse_pan_fields(raw_text, lines)
            elif document_type == "DRIVING_LICENSE":
                fields = self.parse_dl_fields(raw_text, lines)
            elif document_type == "VOTER_ID":
                fields = self.parse_voter_id_fields(raw_text, lines)
            elif document_type == "VISA":
                fields = self.parse_visa_fields(raw_text, lines)
            elif document_type == "PERMIT":
                fields = self.parse_permit_fields(raw_text, lines)
            else:
                fields = self.parse_fields_from_text(raw_text, lines)
            fields["document_type"] = document_type

            return {
                "raw_text": raw_text.strip(),
                "fields": fields,
                "confidence": avg_conf,
                "detected_lines": lines
            }
        except Exception as e:
            # Fallback if tesseract fails or has binary issue
            return {
                "raw_text": f"Error running Tesseract engine: {str(e)}",
                "fields": {
                    "full_name": None,
                    "document_number": None,
                    "nationality": "UNKNOWN",
                    "country": "UNKNOWN",
                    "date_of_birth": None,
                    "date_of_issue": None,
                    "date_of_expiry": None,
                    "sex": None,
                    "document_type": "PASSPORT"
                },
                "confidence": 0.50,
                "detected_lines": []
            }

class MockOCRService(BaseOCRService):
    """Fallback OCR service for deterministic demo runs or lightweight tests."""
    def extract_text(self, image_path: str) -> Dict[str, Any]:
        return {
            "raw_text": "PASSPORT REPUBLIC OF UTOPIA\nSURNAME: KAUL\nGIVEN NAMES: ARIHANT\nNATIONALITY: UTOPIAN\nDOB: 01/01/2000\nDOC NO: X1234567\nEXPIRY: 01/01/2030\nP<UTOKAUL<<ARIHANT<<<<<<<<<<<<<<<<<<<<<<\nX1234567<8UTO0001011M3001012<<<<<<<<<<<<<<02",
            "fields": {
                "full_name": "ARIHANT KAUL",
                "document_number": "X1234567",
                "nationality": "UTOPIA",
                "country": "UTOPIA",
                "date_of_birth": "01/01/2000",
                "date_of_issue": "01/01/2020",
                "date_of_expiry": "01/01/2030",
                "sex": "M",
                "document_type": "PASSPORT"
            },
            "confidence": 0.96,
            "detected_lines": [
                "PASSPORT REPUBLIC OF UTOPIA",
                "SURNAME: KAUL",
                "GIVEN NAMES: ARIHANT",
                "DOB: 01/01/2000",
                "DOC NO: X1234567",
                "EXPIRY: 01/01/2030",
                "P<UTOKAUL<<ARIHANT<<<<<<<<<<<<<<<<<<<<<<",
                "X1234567<8UTO0001011M3001012<<<<<<<<<<<<<<02"
            ]
        }

def get_ocr_service() -> BaseOCRService:
    if settings.OCR_ENGINE == "mock":
        return MockOCRService()
    return TesseractOCRService()
