"""
Regression guard for FaceVerificationService.verify()'s handling of multiple
detected faces. The live-capture side explicitly detects and flags this
(status "MULTIPLE_FACES"); the document side had no equivalent check -- if
the detector found more than one plausible face region in the document
image (background pattern, hologram, a splice with two portraits), the code
silently used doc_faces[0] (whatever order the detector happened to return)
with no signal raised at all, unlike the symmetric live-face path.

Uses a lightweight PIL-generated image and a monkeypatched detector so this
doesn't need to load the real MTCNN/InceptionResnetV1 models.
"""
import os

import numpy as np
from PIL import Image

from app.services.face_service import FaceVerificationService


class _FakeDetector:
    """Reports two plausible face boxes on the FIRST call (the document
    side's detect_face call, which happens first in verify()) and exactly
    one box on every call after that (the live-capture side) -- isolates
    testing the document-side multiplicity gap specifically, independent of
    the live-side check that already exists."""

    def __init__(self):
        self.call_count = 0

    def detect_face(self, img_bgr, max_w_ratio=1.0, max_h_ratio=1.0, fallback_rect=None):
        self.call_count += 1
        if self.call_count == 1:
            return [(5, 5, 20, 20), (40, 40, 20, 20)]
        return [(5, 5, 20, 20)]


def _make_image(path, size=(100, 100)):
    Image.new("RGB", size, "white").save(path)


def test_multiple_document_faces_are_flagged_not_silently_picked(tmp_path):
    doc_path = str(tmp_path / "doc.jpg")
    live_path = str(tmp_path / "live.jpg")
    _make_image(doc_path)
    _make_image(live_path)

    service = FaceVerificationService()
    service.detector = _FakeDetector()

    result = service.verify(doc_path, live_path, "test-case-multi-doc-face")

    assert result["status"] == "MULTIPLE_FACES"
    assert any(
        c["category"] == "FACE" and "Multiple" in c["label"] and "document" in c["explanation"].lower()
        for c in result["checks"]
    )


class _FakeDetectorWithFrequencyArtifact:
    """A single plausible face on every call (no multi-face/no-face branch
    involved), a high similarity (a clean MATCH), and check_quality
    reporting a detected frequency artifact -- isolates testing the new
    FFT-based signal's wiring into verify() specifically, independent of
    the real MTCNN/InceptionResnetV1/FFT computation."""

    def detect_face(self, img_bgr, max_w_ratio=1.0, max_h_ratio=1.0, fallback_rect=None):
        return [(5, 5, 20, 20)]

    def check_quality(self, face_bgr):
        return {
            "resolution": "20x20", "mean_brightness": 120.0, "laplacian_sharpness": 200.0,
            "is_blurry": False, "is_dark": False, "is_overexposed": False,
            "moire_energy_concentration": 0.6, "frequency_artifact_detected": True,
            "liveness_score": 0.60
        }

    def extract_embedding(self, face_bgr):
        return np.ones(512, dtype=np.float32) / np.sqrt(512)

    @staticmethod
    def compare_faces(emb1, emb2):
        return 0.99


def test_frequency_artifact_signal_is_low_severity_and_does_not_block_a_match(tmp_path):
    """
    The new FFT-based moire/halftone signal (FaceDetectorAndVerifier.
    analyze_frequency_artifacts, wired through check_quality) must be
    LOW-severity and non-blocking: present in `signals` for officer review,
    but it must never downgrade a genuine MATCH to REVIEW_REQUIRED or
    otherwise change the similarity-based decision -- see face_service.py's
    own comment at this signal's point of construction for why.
    """
    doc_path = str(tmp_path / "doc.jpg")
    live_path = str(tmp_path / "live.jpg")
    _make_image(doc_path)
    _make_image(live_path)

    service = FaceVerificationService()
    service.detector = _FakeDetectorWithFrequencyArtifact()

    result = service.verify(doc_path, live_path, "test-case-freq-artifact")

    assert result["status"] == "MATCH"
    assert result["similarity"] == 0.99
    freq_checks = [c for c in result["checks"] if c["label"] == "Possible Screen/Print Recapture Pattern"]
    assert len(freq_checks) == 1
    assert freq_checks[0]["status"] == "FAIL"
    assert freq_checks[0]["severity"] == "LOW"
    assert freq_checks[0]["category"] == "FACE"
    assert "not a certified" in freq_checks[0]["explanation"].lower()


def test_no_frequency_artifact_signal_when_not_detected(tmp_path):
    """Symmetric negative case: check_quality reporting no artifact must not
    emit the signal at all."""
    doc_path = str(tmp_path / "doc.jpg")
    live_path = str(tmp_path / "live.jpg")
    _make_image(doc_path)
    _make_image(live_path)

    class _CleanFakeDetector(_FakeDetectorWithFrequencyArtifact):
        def check_quality(self, face_bgr):
            q = super().check_quality(face_bgr)
            q["frequency_artifact_detected"] = False
            q["moire_energy_concentration"] = 0.05
            return q

    service = FaceVerificationService()
    service.detector = _CleanFakeDetector()

    result = service.verify(doc_path, live_path, "test-case-no-freq-artifact")

    assert not any(c["label"] == "Possible Screen/Print Recapture Pattern" for c in result["checks"])
    moire_check = next(c for c in result["checks"] if c["id"] == "FACE_QUALITY_MOIRE")
    assert moire_check["status"] == "PASS"
