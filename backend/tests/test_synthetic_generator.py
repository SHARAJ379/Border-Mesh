import os
from PIL import Image
from app.utils.synthetic_generator import SyntheticDocumentGenerator
from app.services.ocr_service import TesseractOCRService


def test_pasted_photo_is_feathered_at_the_border(tmp_path):
    """
    A hard-edged `img.paste(photo, (x, y))` leaves a sharp tonal
    discontinuity at the photo's border -- structurally the same signature
    as a real crop-and-replace forgery, which a tamper-detection model
    trained on real forgery examples is specifically built to catch (see
    scripts/train_tamper_cnn.py's SIDTD caution note). The paste must blend
    into the surrounding background at its edge rather than butt a hard
    rectangle against it.
    """
    background_color = (248, 250, 252)
    photo_color = (10, 10, 10)  # deliberately far from the background color

    canvas = Image.new("RGB", (400, 400), color=background_color)
    photo = Image.new("RGB", (300, 300), color=photo_color)
    # A hardcoded "/tmp/..." path doesn't exist on Windows -- tmp_path is
    # pytest's own cross-platform scratch directory fixture.
    photo_path = str(tmp_path / "test_paste_feather_photo.png")
    photo.save(photo_path)

    SyntheticDocumentGenerator._paste_photo(canvas, photo_path, x=50, y=50, w=300, h=300)

    center_pixel = canvas.getpixel((200, 200))
    corner_pixel = canvas.getpixel((50, 50))

    # Center of the pasted box should closely match the photo.
    assert all(abs(c - p) < 15 for c, p in zip(center_pixel, photo_color))
    # The very corner (the hard edge of the old implementation) must be
    # blended -- neither pure photo nor pure background -- proving the
    # feather actually softened the boundary.
    assert corner_pixel != photo_color
    assert corner_pixel != background_color


def test_generate_pan_card_produces_a_correctly_sized_specimen(tmp_path):
    out_path = str(tmp_path / "pan.jpg")
    info = SyntheticDocumentGenerator.generate_pan_card(
        out_path=out_path,
        surname="VERMA",
        given_names="ANANYA",
        father_name="RAJESH VERMA",
        doc_number="ABCPV1234F",
        dob_yymmdd="920615",
    )
    assert os.path.exists(out_path)
    assert info["doc_number"] == "ABCPV1234F"
    img = Image.open(out_path)
    assert img.size == (SyntheticDocumentGenerator.WIDTH, SyntheticDocumentGenerator.HEIGHT)


def test_generate_pan_card_is_recognized_by_the_real_ocr_pipeline(tmp_path):
    """
    The whole point of a Tier B specimen (vs. the hand-authored OCR-text
    fixtures used for the Aadhaar/PAN/DL parsers in test_ocr.py) is that it
    must survive a REAL Tesseract pass, not just look right to a human.
    Docker is the authoritative environment for this test (see README) --
    it depends on a real tesseract binary being reachable, same as the
    existing demo-scenario end-to-end tests in test_api.py.
    """
    out_path = str(tmp_path / "pan.jpg")
    SyntheticDocumentGenerator.generate_pan_card(
        out_path=out_path,
        surname="VERMA",
        given_names="ANANYA",
        father_name="RAJESH VERMA",
        doc_number="ABCPV1234F",
        dob_yymmdd="920615",
    )

    result = TesseractOCRService().extract_text(out_path)
    assert result["fields"]["document_type"] == "PAN"
    assert result["fields"]["document_number"] == "ABCPV1234F"
    assert result["fields"]["full_name"] == "ANANYA VERMA"
    assert result["fields"]["date_of_birth"] == "15/06/1992"


def test_generate_driving_license_produces_a_correctly_sized_specimen(tmp_path):
    out_path = str(tmp_path / "dl.jpg")
    info = SyntheticDocumentGenerator.generate_driving_license(
        out_path=out_path,
        surname="REDDY",
        given_names="KIRAN",
        state_code="KA",
        state_name="KARNATAKA",
        doc_number="KA0320110098765",
        dob_yymmdd="880210",
        issue_yymmdd="110320",
        expiry_yymmdd="310320",
    )
    assert os.path.exists(out_path)
    assert info["doc_number"] == "KA0320110098765"
    img = Image.open(out_path)
    assert img.size == (SyntheticDocumentGenerator.WIDTH, SyntheticDocumentGenerator.HEIGHT)


def test_generate_driving_license_is_recognized_by_the_real_ocr_pipeline(tmp_path):
    out_path = str(tmp_path / "dl.jpg")
    SyntheticDocumentGenerator.generate_driving_license(
        out_path=out_path,
        surname="REDDY",
        given_names="KIRAN",
        state_code="KA",
        state_name="KARNATAKA",
        doc_number="KA0320110098765",
        dob_yymmdd="880210",
        issue_yymmdd="110320",
        expiry_yymmdd="310320",
    )

    result = TesseractOCRService().extract_text(out_path)
    assert result["fields"]["document_type"] == "DRIVING_LICENSE"
    assert result["fields"]["document_number"] == "KA0320110098765"
    assert result["fields"]["full_name"] == "KIRAN REDDY"
    assert result["fields"]["date_of_expiry"] == "20/03/2031"


def test_generate_driving_license_expired_mode_backdates_valid_till(tmp_path):
    """
    mode="expired" must actually change the printed "Valid Till" date to a
    past one -- this is what lets a demo scenario exercise the rules
    engine's newly-generalized (previously MRZ-only) expiration check
    against a Driving Licence.
    """
    out_path = str(tmp_path / "dl_expired.jpg")
    SyntheticDocumentGenerator.generate_driving_license(
        out_path=out_path,
        mode="expired",
        surname="REDDY",
        given_names="KIRAN",
        state_code="KA",
        state_name="KARNATAKA",
        doc_number="KA0320110098765",
        dob_yymmdd="880210",
        issue_yymmdd="110320",
        expiry_yymmdd="310320",  # would be valid, but "expired" mode must override it
    )

    result = TesseractOCRService().extract_text(out_path)
    expiry = result["fields"]["date_of_expiry"]
    assert expiry is not None
    year = int(expiry.split("/")[-1])
    assert year < 2026


def test_generate_voter_id_card_produces_a_correctly_sized_specimen(tmp_path):
    out_path = str(tmp_path / "voter_id.jpg")
    info = SyntheticDocumentGenerator.generate_voter_id_card(
        out_path=out_path,
        surname="NAIR",
        given_names="ANJALI",
        doc_number="MLD1234567",
        dob_yymmdd="970422",
        sex="FEMALE",
    )
    assert os.path.exists(out_path)
    assert info["doc_number"] == "MLD1234567"
    img = Image.open(out_path)
    assert img.size == (SyntheticDocumentGenerator.WIDTH, SyntheticDocumentGenerator.HEIGHT)


def test_generate_voter_id_card_is_recognized_by_the_real_ocr_pipeline(tmp_path):
    """
    Same Tier B bar as the PAN/DL specimens: it must survive a REAL
    Tesseract pass, not just look right to a human.
    """
    out_path = str(tmp_path / "voter_id.jpg")
    SyntheticDocumentGenerator.generate_voter_id_card(
        out_path=out_path,
        surname="NAIR",
        given_names="ANJALI",
        doc_number="MLD1234567",
        dob_yymmdd="970422",
        sex="FEMALE",
    )

    result = TesseractOCRService().extract_text(out_path)
    assert result["fields"]["document_type"] == "VOTER_ID"
    assert result["fields"]["document_number"] == "MLD1234567"
    assert result["fields"]["full_name"] == "ANJALI NAIR"
    assert result["fields"]["date_of_birth"] == "22/04/1997"
    assert result["fields"]["sex"] == "F"


def test_generate_permit_is_recognized_by_the_real_ocr_pipeline(tmp_path):
    """
    Same Tier B bar as the PAN/DL/Voter ID specimens: it must survive a
    REAL Tesseract pass, not just look right to a human.
    """
    out_path = str(tmp_path / "permit.jpg")
    SyntheticDocumentGenerator.generate_permit(
        out_path=out_path,
        surname="ADEYEMI",
        given_names="TOLA",
        nationality="ATLANTIAN",
        doc_number="RP7734210",
        permit_type="RESIDENCE PERMIT",
        issuing_authority="REPUBLIC OF UTOPIA IMMIGRATION SERVICE",
        dob_yymmdd="910304",
        issue_yymmdd="240101",
        expiry_yymmdd="290101",
    )

    result = TesseractOCRService().extract_text(out_path)
    assert result["fields"]["document_type"] == "PERMIT"
    assert result["fields"]["document_number"] == "RP7734210"
    assert result["fields"]["full_name"] == "TOLA ADEYEMI"
    assert result["fields"]["date_of_birth"] == "04/03/1991"
    assert result["fields"]["date_of_expiry"] == "01/01/2029"


def test_generate_permit_expired_mode_backdates_expiry(tmp_path):
    """Mirrors test_generate_driving_license_expired_mode_backdates_valid_till
    -- 'expired' mode must actually change the printed expiry, not just the
    mode label, since the rules engine reads what's printed."""
    out_path = str(tmp_path / "permit_expired.jpg")
    SyntheticDocumentGenerator.generate_permit(
        out_path=out_path,
        mode="expired",
        doc_number="RP7734210",
        expiry_yymmdd="290101",
    )

    result = TesseractOCRService().extract_text(out_path)
    assert result["fields"]["document_type"] == "PERMIT"
    assert result["fields"]["date_of_expiry"] == "01/01/2020"
