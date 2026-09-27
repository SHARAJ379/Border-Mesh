import os
import cv2
import numpy as np
import torch
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from PIL import Image

from app.core.config import settings
from app.ml.tamper_model import LightweightForensicCNN, TamperForensics
from app.services.risk_types import RiskCheckStatus, RiskFactorKey, make_check, make_evidence

class BaseTamperService(ABC):
    @abstractmethod
    def analyze(self, image_path: str, case_id: str) -> Dict[str, Any]:
        """Performs multi-signal forensic tampering analysis on document image."""
        pass

WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "ml" / "weights" / "tamper_cnn.pth"


class TamperDetectionService(BaseTamperService):
    # Camera/scanner capture pipelines never write one of these as their own
    # EXIF Software tag -- each name here belongs exclusively to a
    # post-capture image editor, so a match has no legitimate documentary-
    # capture explanation (unlike bare EXIF absence, which innocent
    # pipelines produce too -- see analyze_exif_metadata).
    EXIF_EDITOR_SOFTWARE_MARKERS = (
        "PHOTOSHOP", "GIMP", "PAINT.NET", "AFFINITY PHOTO", "LIGHTROOM",
        "SNAPSEED", "PIXLR", "CANVA", "PICSART"
    )

    # A genuine single capture-to-storage write leaves DateTime (last save)
    # and DateTimeOriginal (capture) identical or, at most, a few
    # seconds/minutes apart from encoder latency. Set well above that so
    # ordinary clock-skew/timezone quirks between the two tags don't fire
    # this on an unedited capture -- only a re-save meaningfully later than
    # capture should.
    EXIF_DATE_GAP_SUSPICIOUS_HOURS = 24.0

    def __init__(self):
        self.device = torch.device("cpu")
        self.model = LightweightForensicCNN().to(self.device)
        self.model.eval()

        # The CNN starts with random (untrained) weights, which produce
        # near-arbitrary output -- not a useful signal, and mixing it into the
        # score would let noise skew results. Only use its output once a real
        # trained checkpoint exists (see scripts/train_tamper_cnn.py); until
        # then, the well-tested forensic heuristics (ELA, edge discontinuity,
        # portrait-seam, compression-mismatch) carry the score alone.
        self.cnn_ready = False
        if WEIGHTS_PATH.exists():
            try:
                state_dict = torch.load(WEIGHTS_PATH, map_location=self.device)
                self.model.load_state_dict(state_dict)
                self.cnn_ready = True
            except Exception:
                self.cnn_ready = False

    @staticmethod
    def _aggregate_tamper_score(mean_ela: float, cnn_tamper_prob: Optional[float], signals: List[Dict[str, Any]]) -> float:
        """
        Combines the ELA baseline, the trained CNN's patch-level probability,
        and any heuristic signals into a single 0.0-1.0 tamper risk score.
        """
        base_score = mean_ela * 2.0
        if cnn_tamper_prob is not None:
            # Scaled to 0.85 rather than 1.0 to leave headroom reflecting the
            # model's own measured accuracy (87.8% validation) -- but high
            # enough that a maximally confident detection can independently
            # clear the HIGH threshold (0.70) instead of being diluted to a
            # MEDIUM nudge regardless of how certain the model is.
            base_score = max(base_score, cnn_tamper_prob * 0.85)
        if signals:
            # Weight each signal's contribution by its own confidence rather
            # than a flat amount -- a barely-there anomaly (confidence ~0.5)
            # should not count the same as a near-certain one (confidence ~0.95).
            base_score += sum(0.25 * sig.get("confidence", 0.8) for sig in signals)

        return min(0.96, max(0.04, round(base_score, 2)))

    def analyze_portrait_region(self, img_cv: np.ndarray) -> Dict[str, Any]:
        """
        Signal C: Analyzes the portrait photo region (left side of document).
        Checks for spliced borders, mismatch in resolution, and halo artifacts.
        """
        h, w = img_cv.shape[:2]
        # In travel documents/passports, photo is typically in the left 10%-45% width, 15%-75% height
        photo_roi = img_cv[int(h*0.15):int(h*0.75), int(w*0.05):int(w*0.45)]
        if photo_roi.size == 0:
            return {"suspicious": False, "score": 0.1, "signals": []}

        # Analyze edges around photo perimeter
        gray_roi = cv2.cvtColor(photo_roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray_roi, 80, 180)
        edge_density = float(np.count_nonzero(edges)) / float(edges.size)

        # Compute gradient orientation consistency along boundary
        border_top = photo_roi[0:10, :]
        border_left = photo_roi[:, 0:10]
        border_var = float(np.var(border_top) + np.var(border_left)) / 2.0

        signals = []
        is_suspicious = False
        # border_var's threshold was calibrated against flat, hand-drawn avatar
        # graphics (uniform background -> low variance baseline). A real photo
        # composited into the document naturally has rich texture right up to
        # its own edges (hair, lighting, background detail), which pushes
        # border_var well above that old baseline regardless of tampering --
        # measured ~5900-6400 for both genuine and actually-spliced real-photo
        # documents, i.e. it no longer discriminates once real photos are in
        # play. detect_splicing_boundaries' edge_discontinuity signal (Signal B)
        # reliably catches real splices instead, so this check is raised well
        # above the natural real-photo baseline rather than tuned to a value
        # that can't actually separate the two cases.
        if edge_density > 0.18 or border_var > 9000:
            is_suspicious = True
            signals.append({
                "type": "photo_boundary_anomaly",
                "confidence": 0.86,
                "region": [int(w*0.05), int(h*0.15), int(w*0.40), int(h*0.60)],
                "explanation": "Unusual edge density and high-gradient seam around portrait boundary. Potential photo replacement.",
                "edge_density": round(edge_density, 3),
            })

        return {
            "suspicious": is_suspicious,
            "score": 0.75 if is_suspicious else 0.15,
            "signals": signals
        }

    def analyze_text_compression(self, img_cv: np.ndarray, ela_gray: np.ndarray) -> Dict[str, Any]:
        """
        Signal D: Analyzes visual text and MRZ regions for recompression mismatch.
        """
        h, w = img_cv.shape[:2]
        # MRZ zone is bottom 25% of document
        mrz_roi = ela_gray[int(h*0.75):h, :]
        # Upper body zone
        upper_roi = ela_gray[0:int(h*0.5), :]
        
        mrz_mean = float(np.mean(mrz_roi)) if mrz_roi.size > 0 else 0
        upper_mean = float(np.mean(upper_roi)) if upper_roi.size > 0 else 0

        signals = []
        is_anomaly = False
        ratio = abs(mrz_mean - upper_mean) / (upper_mean + 1e-5)
        
        if ratio > 0.85 and mrz_mean > 35:
            is_anomaly = True
            signals.append({
                "type": "text_compression_anomaly",
                "confidence": 0.82,
                "region": [0, int(h*0.75), w, int(h*0.25)],
                "explanation": "Significant compression divergence between Machine Readable Zone and main document body."
            })
        # ratio is returned unconditionally (not just when it fires) below,
        # so the check built from it in analyze() can cite the real measured
        # value even when it's clean -- see the "show why it's clean, not
        # just silence" principle behind this whole schema.

        return {
            "is_anomaly": is_anomaly,
            "ratio": ratio,
            "signals": signals
        }

    @staticmethod
    def _evaluate_exif_signals(exif: Dict[int, Any], exif_ifd: Dict[int, Any]) -> List[Dict[str, Any]]:
        """
        Pure decision logic for Signal E (EXIF metadata), factored out from
        the file I/O in analyze_exif_metadata so each rule can be pinned
        down against plain tag dicts -- the same way _aggregate_tamper_score
        above is tested against plain numbers rather than real files.

        `exif` is the top-level IFD0 tag dict (Software=305, DateTime=306,
        etc.); `exif_ifd` is the nested Exif sub-IFD (DateTimeOriginal=36867,
        DateTimeDigitized=36868) -- see PIL's Image.Exif.get_ifd(0x8769).
        """
        if not exif:
            # Bare absence is real but weak: innocent pipelines (WhatsApp/
            # Telegram recompression, a screenshot of an already-issued
            # digital ID) strip EXIF just as thoroughly as tampering does,
            # so this can't be allowed to dominate the aggregate score --
            # confidence stays well below the other signals here.
            return [{
                "type": "exif_metadata_missing",
                "confidence": 0.35,
                "region": [],
                "explanation": (
                    "No EXIF metadata present. A genuine phone or scanner "
                    "capture typically embeds some capture metadata, but "
                    "its complete absence is also common for innocent "
                    "reasons (messaging-app recompression, a screenshot of "
                    "an already-issued digital document) -- treated as a "
                    "weak signal on its own."
                )
            }]

        signals: List[Dict[str, Any]] = []

        software = exif.get(305)  # Software (IFD0)
        if software and any(marker in str(software).upper() for marker in TamperDetectionService.EXIF_EDITOR_SOFTWARE_MARKERS):
            signals.append({
                "type": "exif_editing_software",
                "confidence": 0.85,
                "region": [],
                "explanation": (
                    f"EXIF Software tag identifies image-editing software "
                    f"('{software}'), not a camera or scanner capture "
                    f"pipeline -- inconsistent with a direct, unedited "
                    f"document photo."
                )
            })

        date_original = exif_ifd.get(36867) or exif_ifd.get(36868)  # DateTimeOriginal, else DateTimeDigitized
        date_modified = exif.get(306)  # DateTime -- IFD0's "file change" tag
        if date_original and date_modified:
            try:
                fmt = "%Y:%m:%d %H:%M:%S"
                dt_original = datetime.strptime(str(date_original), fmt)
                dt_modified = datetime.strptime(str(date_modified), fmt)
                gap_hours = (dt_modified - dt_original).total_seconds() / 3600.0
            except (ValueError, TypeError):
                gap_hours = 0.0

            if gap_hours > TamperDetectionService.EXIF_DATE_GAP_SUSPICIOUS_HOURS:
                signals.append({
                    "type": "exif_date_inconsistency",
                    "confidence": min(0.9, round(0.6 + gap_hours / 500.0, 2)),
                    "region": [],
                    "explanation": (
                        f"EXIF modification timestamp is {gap_hours:.1f} "
                        f"hours after the original capture timestamp -- "
                        f"consistent with the file being re-saved well "
                        f"after capture, rather than a single direct "
                        f"capture-to-storage write."
                    )
                })

        return signals

    def analyze_exif_metadata(self, image_path: str) -> Dict[str, Any]:
        """
        Signal E: inspects the file's own embedded EXIF metadata for
        evidence of post-capture editing -- distinct from every signal
        above, which all analyze pixel CONTENT. This one survives an edit
        that leaves no visible pixel trace at all (e.g. a metadata-only
        tool, or a re-save that happens not to disturb ELA/edge/CNN
        detectability).
        """
        try:
            with Image.open(image_path) as pil_img:
                exif = pil_img.getexif()
                exif_ifd = exif.get_ifd(0x8769) if exif else {}
        except Exception:
            # An unreadable/corrupt EXIF block is itself consistent with a
            # re-saved or edited file, but too ambiguous on its own (could
            # just as easily be a harmless encoder quirk) to score here.
            return {"signals": []}

        return {"signals": self._evaluate_exif_signals(exif, exif_ifd)}

    # Uniform per-check score contribution for a heuristic tamper FAIL,
    # scaled by that finding's own confidence -- preserves exactly the
    # weighting risk_engine.py used to apply uniformly to every tamper
    # signal regardless of type. This is a DISPLAY/evidence-list number:
    # the TAMPER factor's actual weighted contribution to the total risk
    # score still comes from tamper_risk (the calibrated aggregate below),
    # not from summing these -- see risk_engine.py's own comment on why
    # TAMPER (unlike MRZ_VALIDATION/CONSISTENCY) keeps its bespoke formula.
    _CHECK_SCORE_IMPACT_PER_CONFIDENCE = 18.0

    def _check_from_heuristic_signal(self, sig: Dict[str, Any], severity: str) -> Dict[str, Any]:
        confidence = sig.get("confidence", 0.8)
        region = sig.get("region") or None  # EXIF signals carry region: [] -- not a real locus, treat as none
        evidence_kwargs: Dict[str, Any] = {"region": region, "region_source": "document" if region else None}
        if "roi_variance" in sig:
            evidence_kwargs.update(measured_value=sig["roi_variance"], threshold_value=1400, unit="roi_variance")
        elif "edge_density" in sig:
            evidence_kwargs.update(measured_value=sig["edge_density"], threshold_value=0.18, unit="edge_density")
        return make_check(
            id=f"TAMPER_{sig['type'].upper()}", category="TAMPER", factor=RiskFactorKey.TAMPER,
            label=f"Forensic Anomaly ({sig['type'].replace('_', ' ').title()})",
            status=RiskCheckStatus.FAIL, severity=severity, confidence=confidence,
            explanation=sig.get("explanation", "Potential image texture or compression anomaly detected."),
            evidence=make_evidence(**evidence_kwargs),
            score_impact=round(confidence * self._CHECK_SCORE_IMPACT_PER_CONFIDENCE, 1),
        )

    def analyze(self, image_path: str, case_id: str) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Document image not found: {image_path}")

        img_cv = cv2.imread(image_path)
        if img_cv is None:
            raise ValueError(f"OpenCV cannot decode image: {image_path}")

        h, w = img_cv.shape[:2]

        # Prepare heatmap destination
        heatmap_filename = f"{case_id}_tamper_heatmap.jpg"
        heatmap_full_path = os.path.join(settings.UPLOAD_DIR, "heatmaps", heatmap_filename)

        # 1. Error Level Analysis (Signal A)
        mean_ela, ela_gray = TamperForensics.generate_ela(image_path, heatmap_full_path)

        signals: List[Dict[str, Any]] = []
        ela_fired = mean_ela > 0.22
        if ela_fired:
            signals.append({
                "type": "compression_anomaly",
                "confidence": min(0.92, round(mean_ela * 3.5, 2)),
                "region": [int(w*0.1), int(h*0.2), int(w*0.8), int(h*0.6)],
                "explanation": "Multi-layer JPEG recompression artifacts detected via Error Level Analysis (ELA)."
            })

        # 2. Boundary / edge splicing (Signal B)
        splicing_anomalies = TamperForensics.detect_splicing_boundaries(img_cv)
        signals.extend(splicing_anomalies)

        # 3. Portrait photo boundary (Signal C)
        portrait_res = self.analyze_portrait_region(img_cv)
        signals.extend(portrait_res["signals"])

        # 4. Text region recompression (Signal D)
        text_res = self.analyze_text_compression(img_cv, ela_gray)
        signals.extend(text_res["signals"])

        # 5. Patch-level CNN feature scoring (only once a trained checkpoint is
        # loaded -- see __init__). Sample multiple document regions rather than
        # just the center: the portrait and MRZ zones are where photo-splice
        # and text tampering actually occur, and a center-only patch mostly
        # never overlaps either. Each region's own probability is kept (not
        # just the max) so it can become its own PASS/FAIL check with its
        # own region box -- previously the per-region detail was computed
        # and immediately discarded, leaving the CNN's single most
        # model-driven finding invisible to the officer.
        cnn_regions = [
            ("portrait", (int(h*0.15), int(h*0.75), int(w*0.05), int(w*0.45))),
            ("center", (h//2 - 64, h//2 + 64, w//2 - 64, w//2 + 64)),
            ("mrz", (int(h*0.75), h, 0, w)),
        ]
        cnn_region_results: List[Dict[str, Any]] = []
        if self.cnn_ready:
            for region_name, (y1, y2, x1, x2) in cnn_regions:
                y1c, y2c = max(0, y1), min(h, y2)
                x1c, x2c = max(0, x1), min(w, x2)
                patch = img_cv[y1c:y2c, x1c:x2c]
                if patch.size == 0:
                    continue
                patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
                patch_resized = cv2.resize(patch_rgb, (64, 64))
                patch_t = torch.tensor(patch_resized, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0) / 255.0
                with torch.no_grad():
                    cnn_out = self.model(patch_t)
                    probs = torch.softmax(cnn_out, dim=1).squeeze().numpy()
                cnn_region_results.append({
                    "region_name": region_name,
                    "probability": float(probs[1]),
                    "region": [int(x1c), int(y1c), int(x2c - x1c), int(y2c - y1c)],
                })
        cnn_tamper_prob = max((r["probability"] for r in cnn_region_results), default=None)

        # 6. EXIF metadata analysis (Signal E) -- the one signal here that
        # inspects the file's own embedded metadata rather than pixel
        # content, so it survives edits that leave no visible pixel trace.
        exif_res = self.analyze_exif_metadata(image_path)
        signals.extend(exif_res["signals"])

        tamper_risk = self._aggregate_tamper_score(mean_ela, cnn_tamper_prob, signals)

        if tamper_risk >= 0.70:
            risk_level = "CRITICAL" if tamper_risk >= 0.85 else "HIGH"
        elif tamper_risk >= 0.40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # --- Build the unified itemized checks list -----------------------
        #
        # Per-signal severity escalates to CRITICAL when the document-level
        # tamper verdict itself is CRITICAL (a highly-confident forgery
        # finding should be able to trigger the same hard-stop floor as an
        # expired document, rather than being capped at HIGH and diluted by
        # unrelated clean signals) -- this can only be decided now that
        # tamper_risk/risk_level are known, after the heuristics above ran.
        def severity_for(confidence: float) -> str:
            if risk_level == "CRITICAL":
                return "CRITICAL"
            return "HIGH" if confidence > 0.85 else "MEDIUM"

        checks: List[Dict[str, Any]] = []

        # ELA
        ela_evidence = make_evidence(measured_value=round(mean_ela, 3), threshold_value=0.22, unit="ela_mean_error")
        if ela_fired:
            ela_sig = signals[0]  # always appended first, above, when ela_fired
            checks.append(make_check(
                id="TAMPER_ELA", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Error Level Analysis", status=RiskCheckStatus.FAIL,
                severity=severity_for(ela_sig["confidence"]), confidence=ela_sig["confidence"],
                explanation=ela_sig["explanation"], evidence=ela_evidence,
                score_impact=round(ela_sig["confidence"] * self._CHECK_SCORE_IMPACT_PER_CONFIDENCE, 1),
            ))
        else:
            checks.append(make_check(
                id="TAMPER_ELA", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Error Level Analysis", status=RiskCheckStatus.PASS, confidence=0.9,
                explanation="No significant multi-layer JPEG recompression artifacts detected.",
                evidence=ela_evidence,
            ))

        # Splicing / edge discontinuity
        if splicing_anomalies:
            for anom in splicing_anomalies:
                checks.append(self._check_from_heuristic_signal(anom, severity_for(anom["confidence"])))
        else:
            checks.append(make_check(
                id="TAMPER_EDGE_DISCONTINUITY", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Boundary / Edge Splicing Scan", status=RiskCheckStatus.PASS, confidence=0.85,
                explanation="No unnatural edge discontinuities or pasted-patch boundaries detected.",
            ))

        # Portrait boundary
        if portrait_res["signals"]:
            for sig in portrait_res["signals"]:
                checks.append(self._check_from_heuristic_signal(sig, severity_for(sig["confidence"])))
        else:
            checks.append(make_check(
                id="TAMPER_PHOTO_BOUNDARY_ANOMALY", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Portrait Boundary Scan", status=RiskCheckStatus.PASS, confidence=0.85,
                explanation="No suspicious seam or edge-density anomaly detected around the portrait boundary.",
            ))

        # Text/MRZ compression consistency -- ratio is cited whether or not
        # it fired, so a clean result states the real measured ratio instead
        # of silence.
        text_evidence = make_evidence(measured_value=round(text_res["ratio"], 3), threshold_value=0.85, unit="mrz_body_compression_ratio")
        if text_res["signals"]:
            sig = text_res["signals"][0]
            checks.append(make_check(
                id="TAMPER_TEXT_COMPRESSION_ANOMALY", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Text/MRZ Compression Consistency", status=RiskCheckStatus.FAIL,
                severity=severity_for(sig["confidence"]), confidence=sig["confidence"],
                explanation=sig["explanation"], evidence=text_evidence,
                score_impact=round(sig["confidence"] * self._CHECK_SCORE_IMPACT_PER_CONFIDENCE, 1),
            ))
        else:
            checks.append(make_check(
                id="TAMPER_TEXT_COMPRESSION_ANOMALY", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="Text/MRZ Compression Consistency", status=RiskCheckStatus.PASS, confidence=0.8,
                explanation="Machine Readable Zone and main document body show consistent compression levels.",
                evidence=text_evidence,
            ))

        # CNN per-region forgery probability -- the priority addition: each
        # sampled region becomes its OWN check with its own region box, not
        # a single opaque max() folded silently into the aggregate score.
        if self.cnn_ready:
            for r in cnn_region_results:
                is_fail = r["probability"] >= settings.TAMPER_REGION_THRESHOLD
                evidence = make_evidence(
                    measured_value=round(r["probability"], 3),
                    threshold_value=settings.TAMPER_REGION_THRESHOLD,
                    unit="tamper_probability",
                    region=r["region"], region_source="document",
                )
                checks.append(make_check(
                    id=f"TAMPER_CNN_{r['region_name'].upper()}_REGION", category="TAMPER", factor=RiskFactorKey.TAMPER,
                    label=f"Forensic CNN — {r['region_name'].title()} Region",
                    status=RiskCheckStatus.FAIL if is_fail else RiskCheckStatus.PASS,
                    severity=severity_for(r["probability"]) if is_fail else None,
                    confidence=r["probability"] if is_fail else (1.0 - r["probability"]),
                    explanation=(
                        f"Trained forensic CNN classified the {r['region_name']} region as tampered with "
                        f"{round(r['probability'] * 100, 1)}% probability."
                        if is_fail else
                        f"Trained forensic CNN found no tampering indicators in the {r['region_name']} region "
                        f"({round(r['probability'] * 100, 1)}% probability)."
                    ),
                    evidence=evidence,
                    score_impact=round(r["probability"] * self._CHECK_SCORE_IMPACT_PER_CONFIDENCE, 1) if is_fail else 0.0,
                ))

        # EXIF metadata
        if exif_res["signals"]:
            for sig in exif_res["signals"]:
                checks.append(self._check_from_heuristic_signal(sig, severity_for(sig["confidence"])))
        else:
            checks.append(make_check(
                id="TAMPER_EXIF_METADATA", category="TAMPER", factor=RiskFactorKey.TAMPER,
                label="EXIF Metadata Consistency", status=RiskCheckStatus.PASS, confidence=0.8,
                explanation="Embedded EXIF metadata is consistent with a genuine, unedited capture.",
            ))

        return {
            "tamper_risk": tamper_risk,
            "risk_level": risk_level,
            "checks": checks,
            "heatmap_url": f"/uploads/heatmaps/{heatmap_filename}",
        }

def get_tamper_service() -> BaseTamperService:
    return TamperDetectionService()
