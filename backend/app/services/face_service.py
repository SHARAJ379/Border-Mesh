import os
import cv2
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.core.config import settings
from app.ml.face_verifier import FaceDetectorAndVerifier
from app.services.risk_types import RiskCheckStatus, RiskFactorKey, make_check, make_evidence

class BaseFaceService(ABC):
    @abstractmethod
    def verify(self, document_image_path: str, live_image_path: str, case_id: str) -> Dict[str, Any]:
        """Compares document portrait to live face capture."""
        pass

class FaceVerificationService(BaseFaceService):
    # Calibrated against the LFW face-verification benchmark (500 genuine +
    # 500 impostor pairs) -- see scripts/calibrate_face_threshold.py. At 0.72:
    # 98.0% accuracy, 0.60% false-accept rate, 3.40% false-reject rate.
    # Returned in every result below so the UI displays this real number
    # instead of a value someone has to remember to keep in sync by hand.
    #
    # A FG-NET-only fine-tuned embedder was briefly wired in and recalibrated
    # (threshold 0.70) but reverted: it regressed same-age LFW verification
    # hard -- false-accept rate 0.60% -> 10.20%, a ~17x increase -- because it
    # was trained on only 82 cross-age identities with no same-age diversity.
    # That checkpoint is preserved for reference at
    # backend/app/ml/weights/face_embedder_finetuned.fgnet_only_SANITY_CHECK.pth.bak
    # (renamed so face_verifier.py's auto-load no longer picks it up). Do not
    # re-wire it in; wait for the intended combined FG-NET+YLFW fine-tune
    # (scripts/finetune_face_embedder.py) and recalibrate against that instead.
    MATCH_THRESHOLD = 0.72

    def __init__(self):
        self.detector = FaceDetectorAndVerifier()

    def crop_and_save(self, img_bgr: np.ndarray, bbox: tuple, out_path: str) -> str:
        x, y, w, h = bbox
        # Add slight padding
        pad_x, pad_y = int(w * 0.15), int(h * 0.15)
        ih, iw = img_bgr.shape[:2]
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(iw, x + w + pad_x)
        y2 = min(ih, y + h + pad_y)
        crop = img_bgr[y1:y2, x1:x2]
        cv2.imwrite(out_path, crop)
        return out_path

    def _detect_document_portrait(self, doc_img: np.ndarray) -> list:
        """
        Detects the inset portrait in a document image laid out like this
        project's own synthetic specimens (portrait in the left ~40-55% of
        the frame). Tries the left-ROI first -- a passport-style inset
        portrait is a modest fraction of the full frame, and bounding the
        detection there means a false-positive on document artwork/text on
        the right isn't mistaken for the portrait -- then falls back to the
        whole document image if that misses.
        """
        dh, dw = doc_img.shape[:2]
        doc_left_roi = doc_img[:, 0:int(dw * 0.55)]
        faces = self.detector.detect_face(
            doc_left_roi, max_w_ratio=0.55, max_h_ratio=0.75,
            fallback_rect=(0.05, 0.12, 0.45, 0.55)
        )
        if not faces:
            faces = self.detector.detect_face(
                doc_img, max_w_ratio=0.4, max_h_ratio=0.75,
                fallback_rect=(0.05, 0.15, 0.35, 0.55)
            )
        return faces

    def verify(self, document_image_path: str, live_image_path: str, case_id: str) -> Dict[str, Any]:
        if not os.path.exists(document_image_path):
            raise FileNotFoundError(f"Document image not found: {document_image_path}")
        if not os.path.exists(live_image_path):
            raise FileNotFoundError(f"Live capture image not found: {live_image_path}")

        doc_img = cv2.imread(document_image_path)
        live_img = cv2.imread(live_image_path)

        if doc_img is None or live_img is None:
            raise ValueError("Unable to load document or live image for face verification.")

        doc_faces = self._detect_document_portrait(doc_img)

        # Detect face in live image (subject typically fills most of a selfie frame)
        live_faces = self.detector.detect_face(
            live_img, fallback_rect=(0.15, 0.15, 0.70, 0.70)
        )

        crops_dir = os.path.join(settings.UPLOAD_DIR, "crops")
        doc_crop_path = os.path.join(crops_dir, f"{case_id}_doc_face.jpg")
        live_crop_path = os.path.join(crops_dir, f"{case_id}_live_face.jpg")

        doc_face_url = None
        live_face_url = None

        if not doc_faces:
            # Fallback: extract expected passport photo rectangle
            dh, dw = doc_img.shape[:2]
            px, py, pw, ph = int(dw * 0.05), int(dh * 0.15), int(dw * 0.35), int(dh * 0.55)
            self.crop_and_save(doc_img, (px, py, pw, ph), doc_crop_path)
            doc_face_url = f"/uploads/crops/{case_id}_doc_face.jpg"
            
            return {
                "similarity": 0.0,
                "status": "NO_FACE_DETECTED",
                "document_face_url": doc_face_url,
                "live_face_url": None,
                "quality_checks": {"issue": "Could not detect clear face in document photo"},
                "anti_spoofing_score": 0.5,
                "match_threshold": self.MATCH_THRESHOLD,
                "checks": [make_check(
                    id="FACE_DOCUMENT_PORTRAIT_DETECTION", category="FACE", factor=RiskFactorKey.FACE,
                    label="Document Portrait Undetected", status=RiskCheckStatus.FAIL, severity="HIGH",
                    confidence=0.90,
                    explanation="Automated face detector could not isolate a clear frontal portrait in document image.",
                    score_impact=20.0,
                )]
            }

        if len(doc_faces) > 1:
            # Symmetric with the live-capture multiplicity check below --
            # previously only the live side flagged this; a document image
            # with more than one plausible face region (background pattern,
            # hologram, a splice with two portraits) silently used
            # doc_faces[0] (whatever order the detector happened to return)
            # with no signal at all.
            self.crop_and_save(doc_img, doc_faces[0], doc_crop_path)
            return {
                "similarity": 0.0,
                "status": "MULTIPLE_FACES",
                "document_face_url": f"/uploads/crops/{case_id}_doc_face.jpg",
                "live_face_url": None,
                "quality_checks": {"multiple_faces_detected": len(doc_faces)},
                "anti_spoofing_score": 0.4,
                "match_threshold": self.MATCH_THRESHOLD,
                "checks": [make_check(
                    id="FACE_DOCUMENT_FACE_COUNT", category="FACE", factor=RiskFactorKey.FACE,
                    label="Multiple Faces in Document Image", status=RiskCheckStatus.FAIL, severity="MEDIUM",
                    confidence=0.85,
                    explanation="More than one plausible face region detected in the document image. Manual review required.",
                    evidence=make_evidence(measured_value=len(doc_faces), threshold_value=1, unit="face_count"),
                    score_impact=15.0,
                )]
            }

        if not live_faces:
            # Document face was found
            self.crop_and_save(doc_img, doc_faces[0], doc_crop_path)
            return {
                "similarity": 0.0,
                "status": "NO_FACE_DETECTED",
                "document_face_url": f"/uploads/crops/{case_id}_doc_face.jpg",
                "live_face_url": None,
                "quality_checks": {"issue": "No face found in live capture"},
                "anti_spoofing_score": 0.5,
                "match_threshold": self.MATCH_THRESHOLD,
                "checks": [make_check(
                    id="FACE_LIVE_CAPTURE_DETECTION", category="FACE", factor=RiskFactorKey.FACE,
                    label="Live Subject Face Not Detected", status=RiskCheckStatus.FAIL, severity="HIGH",
                    confidence=0.90,
                    explanation="No face identified in the live webcam/capture frame. Re-take photo.",
                    score_impact=20.0,
                )]
            }

        if len(live_faces) > 1:
            return {
                "similarity": 0.0,
                "status": "MULTIPLE_FACES",
                "document_face_url": None,
                "live_face_url": None,
                "quality_checks": {"multiple_faces_detected": len(live_faces)},
                "anti_spoofing_score": 0.4,
                "match_threshold": self.MATCH_THRESHOLD,
                "checks": [make_check(
                    id="FACE_LIVE_CAPTURE_FACE_COUNT", category="FACE", factor=RiskFactorKey.FACE,
                    label="Multiple Faces in Live Capture", status=RiskCheckStatus.FAIL, severity="MEDIUM",
                    confidence=0.95,
                    explanation="More than one person detected in live capture frame. Individual screening required.",
                    evidence=make_evidence(measured_value=len(live_faces), threshold_value=1, unit="face_count"),
                    score_impact=15.0,
                )]
            }

        # Crop both faces
        self.crop_and_save(doc_img, doc_faces[0], doc_crop_path)
        self.crop_and_save(live_img, live_faces[0], live_crop_path)
        doc_face_url = f"/uploads/crops/{case_id}_doc_face.jpg"
        live_face_url = f"/uploads/crops/{case_id}_live_face.jpg"

        # Quality check on live face
        lx, ly, lw, lh = live_faces[0]
        live_crop_bgr = live_img[ly:ly+lh, lx:lx+lw]
        quality = self.detector.check_quality(live_crop_bgr)

        # Extract embeddings and compute similarity
        dx, dy, dw_f, dh_f = doc_faces[0]
        doc_crop_bgr = doc_img[dy:dy+dh_f, dx:dx+dw_f]
        
        emb_doc = self.detector.extract_embedding(doc_crop_bgr)
        emb_live = self.detector.extract_embedding(live_crop_bgr)
        similarity = self.detector.compare_faces(emb_doc, emb_live)

        is_match = similarity >= self.MATCH_THRESHOLD
        status = "MATCH" if is_match else "REVIEW_REQUIRED"

        checks = []
        match_evidence = make_evidence(measured_value=round(similarity, 3), threshold_value=self.MATCH_THRESHOLD, unit="cosine_similarity")
        if is_match:
            checks.append(make_check(
                id="FACE_BIOMETRIC_MATCH", category="FACE", factor=RiskFactorKey.FACE,
                label="Biometric Face Match", status=RiskCheckStatus.PASS, confidence=round(similarity, 2),
                explanation=f"Live face biometric similarity score ({round(similarity*100, 1)}%) meets or exceeds "
                            f"verification threshold ({self.MATCH_THRESHOLD*100:.0f}%).",
                evidence=match_evidence,
            ))
        else:
            checks.append(make_check(
                id="FACE_BIOMETRIC_MATCH", category="FACE", factor=RiskFactorKey.FACE,
                label="Biometric Face Mismatch", status=RiskCheckStatus.FAIL, severity="HIGH",
                confidence=round(1.0 - similarity, 2),
                explanation=f"Live face biometric similarity score ({round(similarity*100, 1)}%) is below "
                            f"verification threshold ({self.MATCH_THRESHOLD*100:.0f}%). Manual identity review required.",
                evidence=match_evidence, score_impact=25.0,
            ))

        # Quality metrics -- three independent checks (brightness, sharpness,
        # moire) rather than one collapsed "quality" signal, each citing its
        # own measured value against its own threshold: exactly the kind of
        # detail that makes a rejection defensible instead of arbitrary.
        brightness = quality.get("mean_brightness")
        if brightness is not None:
            is_dark, is_overexposed = quality.get("is_dark"), quality.get("is_overexposed")
            checks.append(make_check(
                id="FACE_QUALITY_BRIGHTNESS", category="FACE", factor=RiskFactorKey.FACE,
                label="Live Capture Brightness", status=RiskCheckStatus.FAIL if (is_dark or is_overexposed) else RiskCheckStatus.PASS,
                severity="LOW" if (is_dark or is_overexposed) else None, confidence=0.85,
                explanation=(
                    f"Live capture is {'underexposed' if is_dark else 'overexposed'} "
                    f"(mean brightness {brightness})."
                    if (is_dark or is_overexposed) else
                    f"Live capture brightness ({brightness}) is within the acceptable range."
                ),
                evidence=make_evidence(measured_value=brightness, threshold_value="45–220", unit="mean_brightness_0_255"),
                score_impact=2.5 if (is_dark or is_overexposed) else 0.0,
            ))

        sharpness = quality.get("laplacian_sharpness")
        if sharpness is not None:
            is_blurry = quality.get("is_blurry")
            checks.append(make_check(
                id="FACE_QUALITY_SHARPNESS", category="FACE", factor=RiskFactorKey.FACE,
                label="Live Capture Sharpness", status=RiskCheckStatus.FAIL if is_blurry else RiskCheckStatus.PASS,
                severity="LOW" if is_blurry else None, confidence=0.85,
                explanation=(
                    f"Live facial capture exhibits motion blur (sharpness {sharpness})."
                    if is_blurry else
                    f"Live facial capture is adequately sharp (sharpness {sharpness})."
                ),
                evidence=make_evidence(measured_value=sharpness, threshold_value=35.0, unit="laplacian_variance"),
                score_impact=2.5 if is_blurry else 0.0,
            ))

        # FFT-based moire/halftone signal (FaceDetectorAndVerifier.analyze_
        # frequency_artifacts, see its own docstring). LOW severity and
        # non-blocking BY DESIGN: it never changes `is_match`/`status`
        # above, and LOW severity means it can never trigger risk_engine's
        # CRITICAL-signal floor. This is a coarse HEURISTIC INDICATOR only --
        # not a certified Presentation Attack Detection (PAD) verdict --
        # validated solely against a self-generated synthetic proxy (real
        # face crops with a synthetic moire/halftone pattern overlaid),
        # never against a real spoof capture (see
        # scripts/check_frequency_liveness_signal.py's own disclosure).
        # Officer discretion, not an automated block.
        moire = quality.get("moire_energy_concentration")
        if moire is not None:
            artifact_detected = quality.get("frequency_artifact_detected")
            checks.append(make_check(
                id="FACE_QUALITY_MOIRE", category="FACE", factor=RiskFactorKey.FACE,
                label="Possible Screen/Print Recapture Pattern" if artifact_detected else "Liveness Frequency-Pattern Scan",
                status=RiskCheckStatus.FAIL if artifact_detected else RiskCheckStatus.PASS,
                severity="LOW" if artifact_detected else None, confidence=0.5,
                explanation=(
                    "Frequency-domain analysis of the live capture detected a "
                    "periodic pattern (moire/halftone-like) more consistent with "
                    "photographing a screen or a printed photo than a direct live "
                    "capture. This is a HEURISTIC INDICATOR, not a certified "
                    "Presentation Attack Detection (PAD) result -- it has only "
                    "been validated against a synthetic proxy, not real spoof "
                    "captures (see scripts/check_frequency_liveness_signal.py). "
                    "Non-blocking: does not affect the match decision above. "
                    "Officer discretion advised."
                    if artifact_detected else
                    "No periodic screen-replay/halftone pattern detected in the live capture's frequency "
                    "spectrum. Heuristic indicator only, not a certified PAD result."
                ),
                evidence=make_evidence(measured_value=moire, threshold_value=0.25, unit="energy_concentration"),
                score_impact=5.0 if artifact_detected else 0.0,
            ))

        return {
            "similarity": round(similarity, 3),
            "status": status,
            "document_face_url": doc_face_url,
            "live_face_url": live_face_url,
            "quality_checks": quality,
            "anti_spoofing_score": quality.get("liveness_score", 0.95),
            "match_threshold": self.MATCH_THRESHOLD,
            "checks": checks,
            # The live capture's own embedding -- feeds the cross-case
            # duplicate-identity gallery (identity_gallery_service.py). Only
            # ever the LIVE embedding, never the document photo's: the
            # question that answers is "has this real, physically-present
            # person been screened before under a different claimed
            # identity," not anything about the printed document photo.
            "live_embedding": emb_live.tolist() if emb_live is not None else None
        }

    def compare_document_portraits(self, path_a: str, path_b: str, comparison_id: str) -> Dict[str, Any]:
        """
        Compares the inset portrait photo between two DOCUMENT images of the
        same layout -- e.g. two submissions claiming to be the same identity
        (see change_detection_service.py). Unlike verify(), whose second
        argument is a live capture and gets the whole-frame, selfie-tuned
        detector, both images here get the document-style left-inset
        detection, since both are full document renders, not selfies.
        """
        if not os.path.exists(path_a):
            raise FileNotFoundError(f"Document image not found: {path_a}")
        if not os.path.exists(path_b):
            raise FileNotFoundError(f"Document image not found: {path_b}")

        img_a = cv2.imread(path_a)
        img_b = cv2.imread(path_b)
        if img_a is None or img_b is None:
            raise ValueError("Unable to load one or both document images for portrait comparison.")

        faces_a = self._detect_document_portrait(img_a)
        faces_b = self._detect_document_portrait(img_b)

        crops_dir = os.path.join(settings.UPLOAD_DIR, "crops")
        crop_a_path = os.path.join(crops_dir, f"{comparison_id}_v1_portrait.jpg")
        crop_b_path = os.path.join(crops_dir, f"{comparison_id}_v2_portrait.jpg")

        if not faces_a or not faces_b:
            if faces_a:
                self.crop_and_save(img_a, faces_a[0], crop_a_path)
            if faces_b:
                self.crop_and_save(img_b, faces_b[0], crop_b_path)
            missing = "first" if not faces_a else "second"
            return {
                "similarity": 0.0,
                "status": "NO_FACE_DETECTED",
                "v1_portrait_url": f"/uploads/crops/{comparison_id}_v1_portrait.jpg" if faces_a else None,
                "v2_portrait_url": f"/uploads/crops/{comparison_id}_v2_portrait.jpg" if faces_b else None,
                "match_threshold": self.MATCH_THRESHOLD,
                "issue": f"Could not detect a clear portrait in the {missing} document image."
            }

        self.crop_and_save(img_a, faces_a[0], crop_a_path)
        self.crop_and_save(img_b, faces_b[0], crop_b_path)

        ax, ay, aw, ah = faces_a[0]
        bx, by, bw, bh = faces_b[0]
        emb_a = self.detector.extract_embedding(img_a[ay:ay + ah, ax:ax + aw])
        emb_b = self.detector.extract_embedding(img_b[by:by + bh, bx:bx + bw])
        similarity = self.detector.compare_faces(emb_a, emb_b)
        is_match = similarity >= self.MATCH_THRESHOLD

        return {
            "similarity": round(similarity, 3),
            "status": "SAME_PORTRAIT" if is_match else "PORTRAIT_CHANGED",
            "v1_portrait_url": f"/uploads/crops/{comparison_id}_v1_portrait.jpg",
            "v2_portrait_url": f"/uploads/crops/{comparison_id}_v2_portrait.jpg",
            "match_threshold": self.MATCH_THRESHOLD,
        }

def get_face_service() -> BaseFaceService:
    return FaceVerificationService()
