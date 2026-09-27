import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, date

from app.services.mrz_service import MRZService

class SyntheticDocumentGenerator:
    """
    Generates high-fidelity synthetic travel documents for demonstration and testing.
    All data is strictly fictional: 'DEMO TRAVEL DOCUMENT / REPUBLIC OF UTOPIA'.
    Supports genuine document generation and controlled synthetic tampering:
    - altered text
    - replaced portrait photo
    - MRZ checksum tampering
    - expired validity
    - multi-signal forensic anomalies
    """

    WIDTH = 1000
    HEIGHT = 650

    _FONT_CANDIDATES = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    @classmethod
    def _load_font(cls, size: int) -> ImageFont.FreeTypeFont:
        """
        PIL's font-less draw.text() falls back to a fixed ~10px bitmap font
        that doesn't scale -- fine for a screen mockup, but it's exactly the
        kind of small, low-fidelity glyph rendering that produces marginal,
        easily-misread characters under Tesseract (observed: a single '5'
        misread as '6' in a document number, entirely a rendering artifact
        rather than anything-wrong with the OCR pass itself). Use a real
        scalable font at a deliberately readable size everywhere text needs
        to survive OCR, the same way the MRZ line already does.
        """
        for candidate in cls._FONT_CANDIDATES:
            if os.path.exists(candidate):
                try:
                    return ImageFont.truetype(candidate, size)
                except Exception:
                    continue
        return ImageFont.load_default(size=size)

    @classmethod
    def _paste_photo(cls, img: Image.Image, photo_path: str, x: int, y: int, w: int, h: int):
        """
        Pastes a real face photo into the given box, center-cropped to fill it.

        Used instead of _draw_avatar when a genuine face-verification mismatch
        needs to be demonstrable: a real trained face-embedding model weighs
        facial structure far more than the hand-drawn vector avatar's color
        scheme, so two flat cartoon avatars are correctly recognized as "the
        same face" regardless of how their proportions are varied. A real (here,
        AI-generated, non-real-person) photo gives the model genuine structure
        to discriminate on.

        The paste is alpha-feathered at the border rather than a hard
        rectangular replace: a plain `img.paste(photo, (x, y))` leaves a sharp
        tonal/texture discontinuity at the photo's edge -- structurally the
        same signature as a real crop-and-replace forgery, which is exactly
        what a tamper-detection CNN trained on real forgery examples (SIDTD)
        is designed to catch. A "genuine" demo specimen's own compositing
        method shouldn't itself look like the attack the model is built to
        detect. The feather blends the photo into the surrounding page rather
        than butting a hard-edged rectangle against it, like a photo actually
        printed/laminated onto the document base material would.
        """
        photo = Image.open(photo_path).convert("RGB")
        pw, ph = photo.size
        target_ratio = w / h
        src_ratio = pw / ph
        if src_ratio > target_ratio:
            new_w = int(ph * target_ratio)
            left = (pw - new_w) // 2
            photo = photo.crop((left, 0, left + new_w, ph))
        else:
            new_h = int(pw / target_ratio)
            top = (ph - new_h) // 2
            photo = photo.crop((0, top, pw, top + new_h))
        photo = photo.resize((w, h), Image.LANCZOS)

        feather = max(2, min(w, h) // 20)
        mask = Image.new("L", (w, h), 255)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rectangle((0, 0, w - 1, h - 1), outline=0, width=feather)
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
        img.paste(photo, (x, y), mask=mask)

    @classmethod
    def _draw_avatar(cls, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, variant: int = 1):
        """
        Draws a clean biometric avatar portrait with face contours.

        variant controls both coloring AND facial geometry (face proportions,
        eye spacing/position, hair coverage) -- a real face-embedding model
        weighs structure far more than color, so two avatars that only differ
        in palette are correctly recognized as "the same face" by a properly
        trained model (this was validated against the LFW benchmark). To
        simulate a genuine face mismatch (e.g. photo-replacement fraud), the
        variants must look like structurally different people, not just a
        different color scheme.
        """
        # Background
        bg_color = (210, 225, 240) if variant == 1 else (240, 220, 210)
        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=(150, 160, 180), width=2)

        cx, cy = x + w // 2, y + h // 2

        # Shoulders
        shoulder_color = (40, 60, 90) if variant == 1 else (90, 40, 50)
        draw.ellipse([cx - int(w * 0.45), y + int(h * 0.65), cx + int(w * 0.45), y + int(h * 1.35)], fill=shoulder_color)

        # Neck
        neck_color = (235, 195, 165) if variant == 1 else (200, 155, 120)
        draw.rectangle([cx - int(w * 0.12), cy + int(h * 0.10), cx + int(w * 0.12), cy + int(h * 0.35)], fill=neck_color)

        # Head / Face -- variant 2 is narrower/longer, a structurally different shape
        face_w = int(w * (0.32 if variant == 1 else 0.27))
        face_h = int(h * (0.40 if variant == 1 else 0.46))
        draw.ellipse([cx - face_w, cy - int(face_h * 0.8), cx + face_w, cy + int(face_h * 0.6)], fill=neck_color, outline=(180, 140, 120), width=2)

        # Hair -- variant 2 covers more of the head and sits lower (different hairline)
        hair_color = (30, 25, 20) if variant == 1 else (90, 60, 30)
        hair_bottom = -0.1 if variant == 1 else 0.15
        draw.chord([cx - face_w - 2, cy - int(face_h * 0.95), cx + face_w + 2, cy - int(face_h * hair_bottom)], 180, 360, fill=hair_color)

        # Eyes -- variant 2 has wider-set eyes at a different vertical position
        eye_y = cy - int(face_h * (0.15 if variant == 1 else 0.05))
        eye_inner = 0.25 if variant == 1 else 0.40
        eye_outer = 0.55 if variant == 1 else 0.75
        draw.ellipse([cx - int(face_w * eye_outer), eye_y - 4, cx - int(face_w * eye_inner), eye_y + 6], fill=(30, 30, 30))
        draw.ellipse([cx + int(face_w * eye_inner), eye_y - 4, cx + int(face_w * eye_outer), eye_y + 6], fill=(30, 30, 30))

        # Nose & Mouth
        draw.line([cx, eye_y + 6, cx, eye_y + 22], fill=(180, 130, 100), width=2)
        draw.arc([cx - 15, eye_y + 24, cx + 15, eye_y + 36], 0, 180, fill=(160, 70, 70), width=3)

    @classmethod
    def generate_live_face_image(cls, out_path: str, variant: int = 1, face_photo_path: Optional[str] = None):
        """Generates a matching or mismatched live webcam frame with avatar."""
        img = Image.new("RGB", (400, 400), color=(25, 30, 42))
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 50, 50, 300, 300)
        else:
            draw = ImageDraw.Draw(img)
            cls._draw_avatar(draw, 50, 50, 300, 300, variant=variant)

        # Subtle vignette / lighting gradient
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img.save(out_path, "JPEG", quality=92)
        return out_path

    @classmethod
    def generate_document(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "KAUL",
        given_names: str = "ARIHANT",
        country_code: str = "UTO",
        country_name: str = "REPUBLIC OF UTOPIA",
        doc_number: str = "X1234567",
        nationality: str = "UTOPIAN",
        dob_yymmdd: str = "000101", # 01 Jan 2000
        expiry_yymmdd: str = "300101", # 01 Jan 2030
        sex: str = "M",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic document image with specified properties.
        Modes: 'genuine', 'altered_text', 'mrz_tampered', 'photo_replaced', 'expired', 'multiple_anomalies'.
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        # 1. Subtle security guilloche pattern / microprint background
        for y in range(0, h - 140, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h - 140)], fill=(240, 246, 254), width=1)

        # 2. Header banner (Navy Security Operations style)
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246)) # Cyan/blue accent line

        # Title text
        draw.text((25, 16), "DEMO TRAVEL DOCUMENT", fill=(255, 255, 255))
        draw.text((25, 42), f"{country_name} • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 220, 25), "TYPE: P  CODE: " + country_code, fill=(203, 213, 225))

        # 3. Avatar Portrait (Left side: 40, 100 to 280, 420)
        avatar_variant = 2 if mode in ["photo_replaced", "multiple_anomalies"] else 1
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=avatar_variant)

        # 4. Identity Fields
        left_text = 320
        fields = [
            ("SURNAME / NOM", surname),
            ("GIVEN NAMES / PRENOMS", given_names),
            ("NATIONALITY / NATIONALITE", nationality),
            ("COUNTRY OF ISSUE / PAYS", country_name),
            ("DOCUMENT NO / NO DU PASSEPORT", doc_number),
            ("DATE OF BIRTH / DATE DE NAISSANCE", f"{dob_yymmdd[4:6]}/{dob_yymmdd[2:4]}/20{dob_yymmdd[:2]}"),
            ("SEX / SEXE", sex),
            ("DATE OF EXPIRY / DATE D'EXPIRATION", f"{expiry_yymmdd[4:6]}/{expiry_yymmdd[2:4]}/20{expiry_yymmdd[:2]}")
        ]

        if mode == "expired":
            # Change expiry to 2022
            expiry_yymmdd = "220101"
            fields[7] = ("DATE OF EXPIRY / DATE D'EXPIRATION", "01/01/2022")

        if mode == "altered_text":
            # Tamper visual expiry date to 2035 while MRZ stays 2030
            fields[7] = ("DATE OF EXPIRY / DATE D'EXPIRATION", "01/01/2035")

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        # 5. Security emblem stamp watermark
        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSECURITY", fill=(191, 219, 254))

        if mode in ["stamp_manipulated", "multiple_anomalies"]:
            # Simulated unauthorized pasted secondary stamp
            draw.rectangle([w - 240, 180, w - 60, 240], fill=(254, 242, 242), outline=(220, 38, 38), width=2)
            draw.text((w - 230, 195), "VISA EXEMPTION\n[SIMULATED PATCH]", fill=(185, 28, 28))

        # 6. MRZ Zone (Bottom 150px)
        draw.rectangle([0, h - 145, w, h], fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        
        # Build TD3 lines
        # Line 1: P<[Country 3][Surname]<<[Given Names]...
        clean_surn = surname.replace(" ", "<").upper()
        clean_giv = given_names.replace(" ", "<").upper()
        l1_name = f"{clean_surn}<<{clean_giv}"
        line1 = f"P<{country_code}{l1_name}".ljust(44, '<')[:44]

        # Line 2:
        # [Doc# 9][Doc# CD 1][Nat 3][DOB 6][DOB CD 1][Sex 1][Expiry 6][Expiry CD 1][Optional 14][Comp CD 1]
        doc_raw = doc_number.ljust(9, '<')[:9]
        doc_cd = MRZService.compute_check_digit(doc_raw)
        
        dob_raw = dob_yymmdd.ljust(6, '0')[:6]
        dob_cd = MRZService.compute_check_digit(dob_raw)
        
        exp_raw = expiry_yymmdd.ljust(6, '0')[:6]
        exp_cd = MRZService.compute_check_digit(exp_raw)
        
        optional_raw = "".ljust(15, '<')
        
        comp_payload = doc_raw + doc_cd + dob_raw + dob_cd + exp_raw + exp_cd + optional_raw
        comp_cd = MRZService.compute_check_digit(comp_payload)

        # Inject tampering if requested
        if mode in ["mrz_tampered", "multiple_anomalies"]:
            # Intentionally corrupt check digits
            exp_cd = "9" if exp_cd != "9" else "8"
            comp_cd = "4" if comp_cd != "4" else "3"

        line2 = f"{doc_raw}{doc_cd}{country_code}{dob_raw}{dob_cd}{sex}{exp_raw}{exp_cd}{optional_raw}{comp_cd}"

        # Draw OCR-B / Monospace font in MRZ zone
        font_mrz = None
        for font_candidate in ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]:
            if os.path.exists(font_candidate):
                try:
                    font_mrz = ImageFont.truetype(font_candidate, 22)
                    break
                except Exception:
                    pass
        if font_mrz is None:
            font_mrz = ImageFont.load_default(size=22)

        draw.text((45, h - 120), line1, fill=(15, 23, 42), font=font_mrz)
        draw.text((45, h - 65), line2, fill=(15, 23, 42), font=font_mrz)

        # Save base image
        img.save(out_path, "JPEG", quality=95)

        # 7. Apply forensic tampering if mode requires photo replacement or compression anomaly
        if mode in ["photo_replaced", "multiple_anomalies"]:
            cv_img = cv2.imread(out_path)
            # Add subtle splicing seam around photo box
            cv2.rectangle(cv_img, (38, 98), (282, 422), (180, 160, 140), 1)
            # Add localized compression noise
            patch = cv_img[100:420, 40:280]
            noisy_patch = cv2.convertScaleAbs(patch, alpha=1.05, beta=10)
            cv_img[100:420, 40:280] = noisy_patch
            cv2.imwrite(out_path, cv_img, [cv2.IMWRITE_JPEG_QUALITY, 75])

        if mode == "altered_text":
            cv_img = cv2.imread(out_path)
            # Add recompression boundary around date field
            cv2.rectangle(cv_img, (left_text - 5, cur_y - 50), (left_text + 200, cur_y - 20), (220, 220, 220), 1)
            cv2.imwrite(out_path, cv_img, [cv2.IMWRITE_JPEG_QUALITY, 80])

        if mode == "brightness_manipulated":
            cv_img = cv2.imread(out_path)
            # Apply non-uniform brightness manipulation hotspot over text zone
            cv_img[100:320, 320:800] = cv2.convertScaleAbs(cv_img[100:320, 320:800], alpha=1.35, beta=35)
            cv2.imwrite(out_path, cv_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

        return {
            "image_path": out_path,
            "mode": mode,
            "line1": line1,
            "line2": line2,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "country": country_name
        }

    @staticmethod
    def _format_yymmdd_display(yymmdd: str) -> str:
        """
        Formats a YYMMDD string as DD/MM/YYYY for on-image field rendering,
        using the same century heuristic as
        DocumentRulesEngine.parse_yymmdd/parse_ddmmyyyy (00-45 -> 20xx,
        46-99 -> 19xx). generate_document's own passport DOB field instead
        always prepends "20" regardless of century -- a pre-existing quirk
        left as-is there; not propagated here, since the PAN/DL specimens
        below need their printed dates to round-trip correctly through a
        real OCR pass.
        """
        yy = int(yymmdd[:2])
        mm = yymmdd[2:4]
        dd = yymmdd[4:6]
        year = 2000 + yy if yy <= 45 else 1900 + yy
        return f"{dd}/{mm}/{year}"

    @classmethod
    def generate_pan_card(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "VERMA",
        given_names: str = "ANANYA",
        father_name: str = "RAJESH VERMA",
        doc_number: str = "ABCPV1234F",
        dob_yymmdd: str = "920615",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic Indian PAN (Permanent Account Number) card
        specimen. A PAN card has no ICAO MRZ -- the "INCOME TAX DEPARTMENT"
        / "PERMANENT ACCOUNT NUMBER" boilerplate drawn below is itself what
        TesseractOCRService._detect_document_type keys off (see
        ocr_service.py's PAN_MARKERS) to route OCR to the PAN field parser
        instead of the passport one.

        Modes: 'genuine' only for now -- there is no PAN-specific visual
        tamper scenario wired up yet. RULE 1b's format/entity-type check
        (rules_engine.py) is exercised directly by hand-authored field
        dicts in test_rules.py rather than by a corrupted specimen here.
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        # Subtle security guilloche pattern, matching the passport specimen's own
        for y in range(0, h, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h)], fill=(240, 246, 254), width=1)

        # Header banner
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246))
        draw.text((25, 16), "INCOME TAX DEPARTMENT", fill=(255, 255, 255))
        draw.text((25, 42), "GOVT. OF INDIA • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 340, 25), "PERMANENT ACCOUNT NUMBER CARD", fill=(203, 213, 225))

        # Photo
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=1)

        full_name = f"{given_names} {surname}".upper()
        fields = [
            ("PERMANENT ACCOUNT NUMBER", doc_number),
            ("NAME", full_name),
            ("FATHER'S NAME", father_name.upper()),
            ("DATE OF BIRTH", cls._format_yymmdd_display(dob_yymmdd)),
        ]

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        left_text = 320
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        # Security emblem stamp watermark, matching the passport specimen's own
        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSPECIMEN", fill=(191, 219, 254))

        img.save(out_path, "JPEG", quality=95)

        return {
            "image_path": out_path,
            "mode": mode,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
        }

    @classmethod
    def generate_driving_license(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "REDDY",
        given_names: str = "KIRAN",
        state_code: str = "KA",
        state_name: str = "KARNATAKA",
        doc_number: str = "KA0320110098765",
        dob_yymmdd: str = "880210",
        issue_yymmdd: str = "110320",
        expiry_yymmdd: str = "310320",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic Indian Driving Licence specimen. Like PAN, a DL
        has no ICAO MRZ -- "DRIVING LICENCE" / "TRANSPORT DEPARTMENT" is
        what routes OCR to the DL field parser (see ocr_service.py's
        DL_MARKERS). Unlike Aadhaar/PAN, a DL has a genuine printed expiry
        ("VALID TILL"), which is what lets DocumentRulesEngine's expiration
        check (previously MRZ-only) apply to it.

        Modes: 'genuine' (expiry as given) or 'expired' (VALID TILL is
        overridden to a fixed past date, mirroring how generate_document's
        own 'expired' mode overrides the passport's expiry field).
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        for y in range(0, h, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h)], fill=(240, 246, 254), width=1)

        # Header banner
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246))
        draw.text((25, 16), "TRANSPORT DEPARTMENT", fill=(255, 255, 255))
        draw.text((25, 42), f"GOVT. OF {state_name} • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 220, 25), "DRIVING LICENCE", fill=(203, 213, 225))

        # Photo
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=1)

        full_name = f"{given_names} {surname}".upper()
        valid_till_display = "01/01/2020" if mode == "expired" else cls._format_yymmdd_display(expiry_yymmdd)
        fields = [
            ("DL NO", doc_number),
            ("NAME", full_name),
            ("DATE OF BIRTH", cls._format_yymmdd_display(dob_yymmdd)),
            ("VALID FROM", cls._format_yymmdd_display(issue_yymmdd)),
            ("VALID TILL", valid_till_display),
        ]

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        left_text = 320
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSPECIMEN", fill=(191, 219, 254))

        img.save(out_path, "JPEG", quality=95)

        return {
            "image_path": out_path,
            "mode": mode,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
            "state": state_name,
        }

    @classmethod
    def generate_voter_id_card(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "NAIR",
        given_names: str = "ANJALI",
        relation_name: str = "SURESH NAIR",
        doc_number: str = "MLD1234567",
        dob_yymmdd: str = "970422",
        sex: str = "FEMALE",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic Indian Voter ID (EPIC) specimen. Like PAN/DL, a
        Voter ID has no ICAO MRZ -- "ELECTION COMMISSION OF INDIA" /
        "ELECTORS PHOTO IDENTITY CARD" boilerplate drawn below is what
        routes OCR to the Voter ID field parser (see ocr_service.py's
        VOTER_ID_MARKERS).

        Modes: 'genuine' only for now -- like PAN, there is no Voter-ID-
        specific visual tamper scenario wired up yet. RULE 1c's
        format-mismatch check (rules_engine.py) is exercised directly by
        hand-authored field dicts in test_rules.py rather than by a
        corrupted specimen here.
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        for y in range(0, h, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h)], fill=(240, 246, 254), width=1)

        # Header banner
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246))
        draw.text((25, 16), "ELECTION COMMISSION OF INDIA", fill=(255, 255, 255))
        draw.text((25, 42), "GOVT. OF INDIA • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 300, 25), "ELECTORS PHOTO IDENTITY CARD", fill=(203, 213, 225))

        # Photo
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=1)

        full_name = f"{given_names} {surname}".upper()
        fields = [
            ("EPIC NO", doc_number),
            ("ELECTOR'S NAME", full_name),
            ("FATHER'S NAME", relation_name.upper()),
            ("SEX", sex.upper()),
            ("DATE OF BIRTH", cls._format_yymmdd_display(dob_yymmdd)),
        ]

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        left_text = 320
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        # Security emblem stamp watermark, matching the passport specimen's own
        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSPECIMEN", fill=(191, 219, 254))

        img.save(out_path, "JPEG", quality=95)

        return {
            "image_path": out_path,
            "mode": mode,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
        }

    @classmethod
    def generate_visa(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "MENDEZ",
        given_names: str = "CARLOS",
        nationality: str = "ATLANTIAN",
        doc_number: str = "UV1234567",
        dob_yymmdd: str = "850314",
        visa_type: str = "BUSINESS",
        entry_validation: str = "MULTIPLE ENTRY",
        issue_yymmdd: str = "260101",
        stay_duration_yymmdd: str = "300630",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic Visa specimen, issued by this project's own
        fictional "Republic of Utopia" (matching the passport specimen's
        own fictional issuer) rather than any one real country's visa
        design -- there is no single real template to validate a generic
        visa against the way Aadhaar/PAN/DL/EPIC each have one real
        national issuer. "ENTRY VISA" / "BUREAU OF IMMIGRATION" boilerplate
        drawn below is what routes OCR to the visa field parser (see
        ocr_service.py's VISA_MARKERS) -- deliberately not a bare "VISA"
        substring, since generate_document's own 'stamp_manipulated' mode
        draws unrelated "VISA EXEMPTION" stamp text onto a PASSPORT
        specimen.

        'Stay Duration' is a printed validity date (the date until which
        the holder may remain), not a duration-in-days count -- see
        parse_visa_fields' own docstring for why. Visa Number is
        extract-only: no checksum is fabricated for it.

        Modes: 'genuine' (stay_duration_yymmdd as given) or 'expired'
        (the printed Stay Duration is overridden to a fixed past date,
        mirroring generate_driving_license's own 'expired' mode).
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        for y in range(0, h, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h)], fill=(240, 246, 254), width=1)

        # Header banner
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246))
        draw.text((25, 16), "ENTRY VISA", fill=(255, 255, 255))
        draw.text((25, 42), "BUREAU OF IMMIGRATION • REPUBLIC OF UTOPIA • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 220, 25), "TRAVEL VISA", fill=(203, 213, 225))

        # Photo
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=1)

        full_name = f"{given_names} {surname}".upper()
        stay_display = "01/01/2020" if mode == "expired" else cls._format_yymmdd_display(stay_duration_yymmdd)
        fields = [
            ("VISA NUMBER", doc_number),
            ("FULL NAME", full_name),
            ("NATIONALITY", nationality.upper()),
            ("DATE OF BIRTH", cls._format_yymmdd_display(dob_yymmdd)),
            ("VISA TYPE", visa_type.upper()),
            ("ENTRY VALIDATION", entry_validation.upper()),
            ("DATE OF ISSUE", cls._format_yymmdd_display(issue_yymmdd)),
            ("STAY DURATION", stay_display),
        ]

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        left_text = 320
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        # Security emblem stamp watermark, matching the passport specimen's own
        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSPECIMEN", fill=(191, 219, 254))

        img.save(out_path, "JPEG", quality=95)

        return {
            "image_path": out_path,
            "mode": mode,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
        }

    @classmethod
    def generate_permit(
        cls,
        out_path: str,
        mode: str = "genuine",
        surname: str = "ADEYEMI",
        given_names: str = "TOLA",
        nationality: str = "ATLANTIAN",
        doc_number: str = "RP7734210",
        permit_type: str = "RESIDENCE PERMIT",
        issuing_authority: str = "REPUBLIC OF UTOPIA IMMIGRATION SERVICE",
        dob_yymmdd: str = "910304",
        issue_yymmdd: str = "240101",
        expiry_yymmdd: str = "290101",
        face_photo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a synthetic residence/work/entry/transit Permit specimen --
        like Visa, issued by this project's own fictional "Republic of
        Utopia" rather than any one real country's format, since there is
        no single real template to validate a generic permit against.
        "RESIDENCE PERMIT" / "WORK PERMIT" / etc boilerplate drawn below is
        what routes OCR to the permit field parser (see ocr_service.py's
        PERMIT_MARKERS) -- deliberately a two-word phrase (never a bare
        "PERMIT" substring), the same reasoning as VISA_MARKERS not being a
        bare "VISA" substring.

        Modes: 'genuine' (expiry_yymmdd as given) or 'expired' (the printed
        expiry is overridden to a fixed past date, mirroring
        generate_driving_license/generate_visa's own 'expired' mode).
        """
        w, h = cls.WIDTH, cls.HEIGHT
        img = Image.new("RGB", (w, h), color=(248, 250, 252))
        draw = ImageDraw.Draw(img)

        for y in range(0, h, 12):
            color = (230, 238, 248) if (y // 12) % 2 == 0 else (238, 244, 252)
            draw.line([(0, y), (w, y)], fill=color, width=1)
        for x in range(0, w, 24):
            draw.line([(x, 0), (x, h)], fill=(240, 246, 254), width=1)

        # Header banner
        draw.rectangle([0, 0, w, 70], fill=(15, 23, 42))
        draw.rectangle([0, 70, w, 74], fill=(59, 130, 246))
        draw.text((25, 16), permit_type.upper(), fill=(255, 255, 255))
        draw.text((25, 42), f"{issuing_authority.upper()} • FICTIONAL TEST SPECIMEN", fill=(148, 163, 184))
        draw.text((w - 220, 25), "PERMIT", fill=(203, 213, 225))

        # Photo
        if face_photo_path:
            cls._paste_photo(img, face_photo_path, 40, 100, 240, 320)
            draw.rectangle([40, 100, 40 + 240, 100 + 320], outline=(150, 160, 180), width=2)
        else:
            cls._draw_avatar(draw, 40, 100, 240, 320, variant=1)

        full_name = f"{given_names} {surname}".upper()
        expiry_display = "01/01/2020" if mode == "expired" else cls._format_yymmdd_display(expiry_yymmdd)
        fields = [
            ("PERMIT NUMBER", doc_number),
            ("FULL NAME", full_name),
            ("NATIONALITY", nationality.upper()),
            ("DATE OF BIRTH", cls._format_yymmdd_display(dob_yymmdd)),
            ("PERMIT TYPE", permit_type.upper()),
            ("ISSUING AUTHORITY", issuing_authority.upper()),
            ("DATE OF ISSUE", cls._format_yymmdd_display(issue_yymmdd)),
            ("DATE OF EXPIRY", expiry_display),
        ]

        label_font = cls._load_font(12)
        value_font = cls._load_font(18)
        left_text = 320
        cur_y = 95
        for label, val in fields:
            draw.text((left_text, cur_y), label, fill=(100, 116, 139), font=label_font)
            draw.text((left_text, cur_y + 18), str(val), fill=(15, 23, 42), font=value_font)
            cur_y += 48

        # Security emblem stamp watermark, matching the passport specimen's own
        draw.ellipse([w - 180, 250, w - 40, 390], outline=(219, 234, 254), width=4)
        draw.text((w - 165, 310), "SIMULATED\nSPECIMEN", fill=(191, 219, 254))

        img.save(out_path, "JPEG", quality=95)

        return {
            "image_path": out_path,
            "mode": mode,
            "doc_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
        }
