import cv2
import numpy as np
from PIL import Image
from app.services.tamper_service import TamperDetectionService
from app.ml.tamper_model import TamperForensics


def _canvas_with_real_qr_code(payload: str = "https://example.com/test-payload-1234567890") -> np.ndarray:
    """A genuine, decodable QR code (via OpenCV's own encoder) pasted onto a
    blank canvas -- not a synthetic noise stand-in, so detection/exclusion
    logic is exercised against the real thing."""
    qr = cv2.QRCodeEncoder_create().encode(payload)
    qr_big = cv2.resize(qr, (150, 150), interpolation=cv2.INTER_NEAREST)
    canvas = np.full((400, 400, 3), 255, dtype=np.uint8)
    canvas[100:250, 100:250] = cv2.cvtColor(qr_big, cv2.COLOR_GRAY2BGR)
    return canvas


def test_genuine_qr_code_is_not_flagged_as_a_splicing_anomaly():
    """
    Reproduces a real false positive found by running an actual e-Aadhaar
    screenshot through the live app: `detect_splicing_boundaries` looks for
    bounded rectangular regions of unusually high internal variance to catch
    pasted photo/text patches. A QR code -- present by design on real
    government ID formats like Aadhaar -- IS exactly that shape (a small,
    high-contrast block of dense black/white noise), so a genuine,
    untampered card's own QR code was flagged as a "High-frequency boundary
    discontinuity" with 95% confidence.
    """
    canvas = _canvas_with_real_qr_code()
    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert anomalies == []


def test_qr_exclusion_does_not_blind_detection_of_a_real_splice_elsewhere():
    """The QR-code exclusion must be scoped to the QR's own region -- an
    actual pasted patch elsewhere on the same document must still be
    caught."""
    canvas = _canvas_with_real_qr_code()
    rng = np.random.default_rng(42)
    noise_patch = rng.integers(0, 255, size=(60, 80, 3), dtype=np.uint8)
    canvas[300:360, 20:100] = noise_patch

    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert len(anomalies) == 1
    x, y, cw, ch = anomalies[0]["region"]
    assert x < 100 or y >= 300  # matches the noise patch, not the QR region


def _canvas_with_wide_thin_header_banner() -> np.ndarray:
    """
    A single continuous, thin, textured horizontal strip -- e.g. a printed
    decorative banner/rule carrying a logo mark and wordmark, the kind of
    element real ID-card header layouts (Aadhaar's government emblem +
    'आधार' wordmark row, in particular) actually have. Real, not synthetic
    noise standing in for something else: same shape class (extreme
    width:height ratio) as what was actually flagged -- 95% confidence --
    on a genuine, unaltered Aadhaar card (case BM-2026-41713, region
    361x19px, ~19:1 aspect ratio) after the QR-code-shaped false positive
    above was already excluded.
    """
    rng = np.random.default_rng(7)
    canvas = np.full((300, 512, 3), 255, dtype=np.uint8)
    canvas[10:29, 20:470] = rng.integers(50, 200, size=(19, 450, 3), dtype=np.uint8)
    return canvas


def test_wide_thin_header_banner_is_not_flagged_as_a_splicing_anomaly():
    """
    Reproduces a real false positive found by running an actual, genuine
    e-Aadhaar card (never a synthetic specimen) through the live app: the
    QR-code exclusion above only scopes out QR-shaped (roughly square)
    regions. A different genuine design element -- a wide, thin banner
    row containing the government emblem and the 'आधार' wordmark -- is
    NOT QR-shaped (its bounding box is ~19:1 wide:tall, nothing like a
    QR code's near-1:1 box), so it sailed straight past that exclusion
    and was flagged as a "High-frequency boundary discontinuity" at 95%
    confidence, pushing the case to 83% overall tamper risk / HIGH.

    A real pasted/spliced patch (a photo replacement, a stamp, an altered
    text block) is essentially never this extremely elongated -- this is
    the geometric signature of a printed banner/rule, not a forgery.
    """
    canvas = _canvas_with_wide_thin_header_banner()
    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert anomalies == []


def test_extreme_aspect_ratio_guard_does_not_blind_detection_of_a_real_splice_elsewhere():
    """The wide-thin-banner exclusion must be scoped to genuinely elongated
    shapes -- an actual pasted patch of ordinary (non-extreme) proportions
    elsewhere on the same document must still be caught."""
    canvas = _canvas_with_wide_thin_header_banner()
    rng = np.random.default_rng(42)
    noise_patch = rng.integers(0, 255, size=(60, 80, 3), dtype=np.uint8)
    canvas[150:210, 200:280] = noise_patch

    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert len(anomalies) == 1
    x, y, cw, ch = anomalies[0]["region"]
    assert x >= 150 and y >= 100  # matches the noise patch, not the banner


def test_stamp_shaped_patch_is_classified_as_stamp_forgery():
    """
    A pasted/altered stamp patch is a genuinely different shape class from
    other spliced patches -- calibrated against this project's own
    synthetic 'stamp_manipulated' specimen (synthetic_generator.py), which
    draws an exact 180x60px (3.0:1) patch. A patch this shape should be
    reported as the distinct 'stamp_forgery' type, not lumped into the
    generic 'edge_discontinuity' catch-all every other spliced-patch shape
    still gets.
    """
    rng = np.random.default_rng(11)
    canvas = np.full((400, 400, 3), 255, dtype=np.uint8)
    stamp_patch = rng.integers(0, 255, size=(60, 180, 3), dtype=np.uint8)
    canvas[150:210, 100:280] = stamp_patch

    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert len(anomalies) == 1
    assert anomalies[0]["type"] == "stamp_forgery"
    assert "stamp" in anomalies[0]["explanation"].lower()


def test_non_stamp_shaped_patch_stays_generic_edge_discontinuity():
    """A patch shaped nothing like a stamp (here, close to the ~1.3:1 this
    project's own photo-replacement patch uses) must still be caught, but
    keep the generic 'edge_discontinuity' type -- the stamp classification
    must not swallow every other kind of spliced patch."""
    rng = np.random.default_rng(23)
    canvas = np.full((400, 400, 3), 255, dtype=np.uint8)
    photo_shaped_patch = rng.integers(0, 255, size=(120, 90, 3), dtype=np.uint8)
    canvas[100:220, 100:190] = photo_shaped_patch

    anomalies = TamperForensics.detect_splicing_boundaries(canvas)
    assert len(anomalies) == 1
    assert anomalies[0]["type"] == "edge_discontinuity"


def test_high_confidence_cnn_alone_reaches_high_risk_tier():
    """
    Reproduces a real calibration gap: the tamper CNN was trained tonight to
    87.8% validation accuracy specifically so it can flag forgeries the
    hand-tuned heuristics miss (e.g. clean ELA, no detectable splice edges).
    But the aggregation formula capped its contribution at
    `cnn_tamper_prob * 0.4`, so even a maximally confident CNN detection
    (prob ~1.0) could never independently push tamper_risk into the HIGH
    tier (>= 0.70) -- it could only ever nudge the score toward MEDIUM,
    silently discarding the model's own confidence.
    """
    score = TamperDetectionService._aggregate_tamper_score(
        mean_ela=0.05,  # clean by the ELA heuristic
        cnn_tamper_prob=0.98,  # CNN is highly confident this is tampered
        signals=[],  # no heuristic signals fired
    )
    assert score >= 0.70


def test_low_confidence_cnn_does_not_reach_high_risk_tier():
    """A weak/uncertain CNN signal (near coin-flip) should not, by itself,
    escalate a document with no other anomalies to HIGH."""
    score = TamperDetectionService._aggregate_tamper_score(
        mean_ela=0.05,
        cnn_tamper_prob=0.55,
        signals=[],
    )
    assert score < 0.70


def test_signal_score_contribution_scales_with_its_own_confidence():
    """
    Two forensic signals at low confidence (e.g. 0.5) should contribute less
    to the aggregate score than two signals at high confidence (e.g. 0.95) --
    the old formula added a flat 0.25 per signal regardless of its own
    confidence, treating a barely-there anomaly the same as a near-certain one.
    """
    low_conf_signals = [
        {"type": "a", "confidence": 0.50},
        {"type": "b", "confidence": 0.50},
    ]
    high_conf_signals = [
        {"type": "a", "confidence": 0.95},
        {"type": "b", "confidence": 0.95},
    ]
    low_score = TamperDetectionService._aggregate_tamper_score(0.05, None, low_conf_signals)
    high_score = TamperDetectionService._aggregate_tamper_score(0.05, None, high_conf_signals)
    assert high_score > low_score


# --- EXIF metadata signal (Signal E) -----------------------------------
#
# Unit-tested against plain exif/exif_ifd dicts via _evaluate_exif_signals,
# the same way _aggregate_tamper_score above is tested against plain
# numbers/dicts rather than real files -- this pins down each business
# rule (missing metadata, an editor signature, a suspicious date gap)
# precisely and independently of Pillow's own EXIF-writing quirks.
# Pillow can only reliably WRITE top-level IFD0 tags (e.g. Software) in a
# round-trippable way; nested Exif-sub-IFD tags like DateTimeOriginal are
# unreliable to write back out for a test fixture, so the date-gap rule is
# covered here at the dict level instead of via a real saved file.

def test_missing_exif_is_flagged_but_only_at_low_confidence():
    """
    Absence of EXIF is a real but weak/noisy tell -- innocent pipelines
    (WhatsApp/Telegram recompression, a screenshot of an already-issued
    digital ID) strip it just as thoroughly as tampering does. It must
    still surface as a signal (so a fully metadata-stripped image isn't
    silently ignored), but at low confidence so it can't dominate the
    aggregate score on its own.
    """
    signals = TamperDetectionService._evaluate_exif_signals({}, {})
    assert len(signals) == 1
    assert signals[0]["type"] == "exif_metadata_missing"
    assert signals[0]["confidence"] < 0.5


def test_genuine_camera_exif_is_not_flagged():
    """A plausible camera capture profile -- Make/Model present, no editor
    Software tag, capture and modify timestamps matching -- must not raise
    any EXIF signal."""
    exif = {271: "Google", 272: "Pixel 8", 306: "2026:01:15 10:00:00"}
    exif_ifd = {36867: "2026:01:15 10:00:00"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, exif_ifd)
    assert signals == []


def test_editing_software_tag_is_flagged_at_high_confidence():
    """An EXIF Software tag naming a known photo editor has no legitimate
    documentary-capture explanation -- a camera/scanner never writes
    'Adobe Photoshop' as its own Software tag."""
    exif = {305: "Adobe Photoshop 25.0 (Windows)"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, {})
    assert len(signals) == 1
    assert signals[0]["type"] == "exif_editing_software"
    assert signals[0]["confidence"] >= 0.7


def test_editing_software_check_is_case_insensitive_and_substring_based():
    """Editor signatures appear as free-form version strings (e.g. 'GIMP
    2.10.34') -- the check must match on substring, not exact equality."""
    exif = {305: "gimp 2.10.34"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, {})
    assert any(s["type"] == "exif_editing_software" for s in signals)


def test_modification_date_shortly_after_capture_is_not_flagged():
    """A few seconds/minutes between DateTimeOriginal and DateTime is
    normal encoder/save latency on a genuine single capture-to-storage
    write -- must not trigger the date-inconsistency signal."""
    exif = {306: "2026:01:15 10:00:04"}
    exif_ifd = {36867: "2026:01:15 10:00:00"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, exif_ifd)
    assert not any(s["type"] == "exif_date_inconsistency" for s in signals)


def test_modification_date_long_after_capture_is_flagged():
    """A modification timestamp a full day after the original capture
    timestamp is the EXIF fingerprint of a post-capture re-save/edit."""
    exif = {306: "2026:01:20 10:00:00"}  # 5 days after capture
    exif_ifd = {36867: "2026:01:15 10:00:00"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, exif_ifd)
    matches = [s for s in signals if s["type"] == "exif_date_inconsistency"]
    assert len(matches) == 1
    assert matches[0]["confidence"] >= 0.6


def test_malformed_exif_dates_do_not_crash_or_flag():
    """Not every device writes EXIF dates in the standard format -- an
    unparseable date must be treated as no signal, not an exception."""
    exif = {306: "not-a-date"}
    exif_ifd = {36867: "also-not-a-date"}
    signals = TamperDetectionService._evaluate_exif_signals(exif, exif_ifd)
    assert not any(s["type"] == "exif_date_inconsistency" for s in signals)


def _save_jpeg_with_exif(path, exif_dict=None):
    img = Image.new("RGB", (200, 120), color=(230, 230, 230))
    if exif_dict:
        exif = Image.Exif()
        for tag, value in exif_dict.items():
            exif[tag] = value
        img.save(path, "JPEG", exif=exif.tobytes())
    else:
        img.save(path, "JPEG")


def test_genuine_specimen_file_is_not_flagged(tmp_path):
    """End-to-end through analyze_exif_metadata (real file I/O, not just
    the pure dict logic above): a specimen carrying a plausible camera
    profile must not be flagged."""
    path = str(tmp_path / "genuine.jpg")
    _save_jpeg_with_exif(path, {271: "Google", 272: "Pixel 8", 305: "HDR+ 1.0"})
    service = TamperDetectionService()
    result = service.analyze_exif_metadata(path)
    assert result["signals"] == []


def test_stripped_exif_specimen_file_is_flagged(tmp_path):
    """A specimen saved with no EXIF block at all -- e.g. a screenshot or
    a messaging-app recompression -- must raise the missing-metadata
    signal."""
    path = str(tmp_path / "stripped.jpg")
    _save_jpeg_with_exif(path, exif_dict=None)
    service = TamperDetectionService()
    result = service.analyze_exif_metadata(path)
    assert any(s["type"] == "exif_metadata_missing" for s in result["signals"])


# --- analyze()'s unified checks list: CNN per-region evidence -------------
#
# The priority addition from the risk-reasons schema work: each sampled
# region (portrait/center/mrz) becomes its own PASS/FAIL check with its own
# region box and measured probability, rather than a single opaque max()
# folded silently into the aggregate score.

class _FixedProbabilityModel:
    """Stands in for LightweightForensicCNN -- returns a fixed
    [authentic, tampered] logit pair for every patch, so the per-region
    probability is deterministic and known in advance, independent of the
    real (untrained-by-default) model's actual weights."""

    def __init__(self, tampered_logit: float):
        self.tampered_logit = tampered_logit

    def eval(self):
        return self

    def to(self, device):
        return self

    def __call__(self, patch_t):
        import torch
        batch = patch_t.shape[0]
        return torch.tensor([[0.0, self.tampered_logit]] * batch)


def _real_document_shaped_image(path, size=(400, 260)):
    rng__ = __import__("numpy").random.default_rng(3)
    arr = rng__.integers(120, 200, size=(size[1], size[0], 3), dtype="uint8")
    Image.fromarray(arr).save(path, "JPEG", quality=92)


def test_analyze_emits_a_pass_check_per_cnn_region_when_confident_clean(tmp_path):
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = True
    service.model = _FixedProbabilityModel(tampered_logit=-5.0)  # softmax -> ~0% tampered

    result = service.analyze(doc_path, "test-case-cnn-clean")

    cnn_checks = [c for c in result["checks"] if c["id"].startswith("TAMPER_CNN_")]
    assert len(cnn_checks) == 3
    assert {c["id"] for c in cnn_checks} == {
        "TAMPER_CNN_PORTRAIT_REGION", "TAMPER_CNN_CENTER_REGION", "TAMPER_CNN_MRZ_REGION",
    }
    for c in cnn_checks:
        assert c["status"] == "PASS"
        assert c["evidence"]["region"] is not None
        assert len(c["evidence"]["region"]) == 4
        assert c["evidence"]["region_source"] == "document"
        assert c["evidence"]["measured_value"] < c["evidence"]["threshold_value"]


def test_analyze_emits_a_fail_check_per_cnn_region_when_confident_tampered(tmp_path):
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = True
    service.model = _FixedProbabilityModel(tampered_logit=5.0)  # softmax -> ~100% tampered

    result = service.analyze(doc_path, "test-case-cnn-tampered")

    cnn_checks = [c for c in result["checks"] if c["id"].startswith("TAMPER_CNN_")]
    assert len(cnn_checks) == 3
    for c in cnn_checks:
        assert c["status"] == "FAIL"
        assert c["severity"] in ("MEDIUM", "HIGH", "CRITICAL")
        assert c["evidence"]["measured_value"] > c["evidence"]["threshold_value"]
        assert c["score_impact"] > 0.0


def test_analyze_emits_no_cnn_checks_when_no_trained_checkpoint_is_loaded(tmp_path):
    """cnn_ready=False (no checkpoint on disk, see __init__) must not
    fabricate CNN region checks at all. Forced explicitly rather than
    relying on whether a real checkpoint happens to be present in this
    environment -- this repo does commit a trained tamper_cnn.pth."""
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = False

    result = service.analyze(doc_path, "test-case-no-cnn")

    assert not any(c["id"].startswith("TAMPER_CNN_") for c in result["checks"])


def test_analyze_skips_the_mrz_cnn_region_for_a_non_mrz_document_type(tmp_path):
    """
    Reproduces a real bug: before analyze() took a document_type param, the
    CNN's third sampled region unconditionally treated the bottom 25% of
    EVERY document as "the MRZ zone" and labeled its finding "Forensic CNN
    — Mrz Region" regardless of document type -- wrong for the 6 document
    types (Aadhaar, PAN, Driving Licence, Voter ID, Visa, Permit) that carry
    no ICAO MRZ by design. Only 2 CNN regions (portrait, center) should run
    for those document types.
    """
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = True
    service.model = _FixedProbabilityModel(tampered_logit=-5.0)

    result = service.analyze(doc_path, "test-case-non-mrz-doc", document_type="AADHAAR")

    cnn_checks = [c for c in result["checks"] if c["id"].startswith("TAMPER_CNN_")]
    assert len(cnn_checks) == 2
    assert {c["id"] for c in cnn_checks} == {"TAMPER_CNN_PORTRAIT_REGION", "TAMPER_CNN_CENTER_REGION"}
    assert not any(c["id"] == "TAMPER_CNN_MRZ_REGION" for c in cnn_checks)


def test_analyze_still_samples_the_mrz_cnn_region_for_a_passport(tmp_path):
    """Passport is the one document type that genuinely carries an MRZ --
    confirms the fix didn't just remove the region unconditionally."""
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = True
    service.model = _FixedProbabilityModel(tampered_logit=-5.0)

    result = service.analyze(doc_path, "test-case-passport", document_type="PASSPORT")

    assert any(c["id"] == "TAMPER_CNN_MRZ_REGION" for c in result["checks"])


def test_analyze_defaults_to_mrz_aware_behavior_when_document_type_is_not_passed(tmp_path):
    """Backward compatibility for any caller not yet updated to pass
    document_type -- must behave exactly as before (MRZ region sampled),
    not silently start skipping it for every caller that omits the arg."""
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    service.cnn_ready = True
    service.model = _FixedProbabilityModel(tampered_logit=-5.0)

    result = service.analyze(doc_path, "test-case-no-doc-type")

    assert any(c["id"] == "TAMPER_CNN_MRZ_REGION" for c in result["checks"])


def test_text_compression_check_is_not_applicable_for_a_non_mrz_document_type(tmp_path):
    """The 'Text/MRZ Compression Consistency' check must show NOT_APPLICABLE
    for a document type with no MRZ, not run the pixel comparison against a
    region that isn't actually an MRZ and risk a wrongly-labeled PASS/FAIL."""
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    result = service.analyze(doc_path, "test-case-non-mrz-text", document_type="DRIVING_LICENSE")

    check = next(c for c in result["checks"] if c["id"] == "TAMPER_TEXT_COMPRESSION_ANOMALY")
    assert check["status"] == "NOT_APPLICABLE"


def test_analyze_emits_pass_checks_for_every_category_on_a_clean_document(tmp_path):
    """A clean document must show a populated evidentiary trail (ELA,
    edge/splice scan, portrait boundary, text compression, EXIF), not
    silence -- see the "show why it's clean" principle behind this schema."""
    doc_path = str(tmp_path / "doc.jpg")
    _real_document_shaped_image(doc_path)

    service = TamperDetectionService()
    result = service.analyze(doc_path, "test-case-clean-checks")

    check_ids = {c["id"] for c in result["checks"]}
    assert "TAMPER_ELA" in check_ids
    assert "TAMPER_EDGE_DISCONTINUITY" in check_ids
    assert "TAMPER_PHOTO_BOUNDARY_ANOMALY" in check_ids
    assert "TAMPER_TEXT_COMPRESSION_ANOMALY" in check_ids
    # A bare PIL-saved JPEG genuinely carries no EXIF block, so the "missing
    # metadata" check legitimately fires here rather than PASSing -- either
    # way, some EXIF-category check must be present, not silence.
    assert "TAMPER_EXIF_METADATA" in check_ids or "TAMPER_EXIF_METADATA_MISSING" in check_ids
    assert all(c["status"] in ("PASS", "FAIL") for c in result["checks"])


def test_editor_software_specimen_file_is_flagged(tmp_path):
    """A specimen whose EXIF Software tag names a photo editor must raise
    the editing-software signal."""
    path = str(tmp_path / "edited.jpg")
    _save_jpeg_with_exif(path, {305: "Adobe Photoshop 25.0 (Windows)"})
    service = TamperDetectionService()
    result = service.analyze_exif_metadata(path)
    assert any(s["type"] == "exif_editing_software" for s in result["signals"])
