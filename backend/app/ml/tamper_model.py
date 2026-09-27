import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageChops, ImageEnhance
from typing import Dict, Any, List, Tuple
from pathlib import Path

class LightweightForensicCNN(nn.Module):
    """
    Lightweight convolutional neural network for patch-level forensic texture classification.
    Distinguishes authentic document background textures from spliced/tampered patches.
    """
    def __init__(self):
        super(LightweightForensicCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2), # 64 -> 32
            
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2), # 32 -> 16

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        self.classifier = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 2) # [authentic, tampered]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        feat = torch.flatten(feat, 1)
        out = self.classifier(feat)
        return out


class TamperForensics:
    """
    Forensic analysis algorithms:
    - Error Level Analysis (ELA)
    - Local Laplacian texture gradient variance
    - Photo boundary edge splicing analysis
    - Copy-paste / recompression patch detection
    """

    @staticmethod
    def generate_ela(image_path: str, output_path: str, quality: int = 90, scale: int = 15) -> Tuple[float, np.ndarray]:
        """
        Performs Error Level Analysis (ELA) by recompressing at a specific JPEG quality
        and calculating the amplified pixel delta.
        Returns the mean error level and the ELA heatmap image array.
        """
        original = Image.open(image_path).convert("RGB")
        
        # Save temporary recompressed JPEG in memory
        temp_path = f"{output_path}_temp.jpg"
        original.save(temp_path, "JPEG", quality=quality)
        recompressed = Image.open(temp_path).convert("RGB")
        
        # Compute absolute difference
        diff = ImageChops.difference(original, recompressed)
        
        # Remove temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Scale difference to visualize compression artifacts
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema]) if extrema else 1
        scale_val = 255.0 / max(max_diff, 1) if max_diff > 0 else 1.0
        diff_scaled = ImageEnhance.Brightness(diff).enhance(min(scale_val, scale))

        diff_np = np.array(diff_scaled)
        # Convert to a thermal / jet heatmap for high visual security-ops impact
        gray_diff = cv2.cvtColor(diff_np, cv2.COLOR_RGB2GRAY)
        heatmap = cv2.applyColorMap(gray_diff, cv2.COLORMAP_JET)

        # Overlay heatmap transparently onto original document
        orig_cv = cv2.cvtColor(np.array(original), cv2.COLOR_RGB2BGR)
        orig_resized = cv2.resize(orig_cv, (heatmap.shape[1], heatmap.shape[0]))
        blended = cv2.addWeighted(orig_resized, 0.45, heatmap, 0.55, 0)

        cv2.imwrite(output_path, blended)
        
        mean_error = float(np.mean(gray_diff)) / 255.0
        return mean_error, gray_diff

    @staticmethod
    def _detect_qr_boxes(gray: np.ndarray) -> List[tuple]:
        """
        Locates any QR code(s) in the image as (x1, y1, x2, y2) boxes.

        A genuine QR code -- present by design on real government ID
        formats like Aadhaar -- is, by construction, a small high-contrast
        rectangular block of dense black/white noise: exactly the shape
        `detect_splicing_boundaries` below is looking for (a bounded
        rectangle with unusually high internal variance). Detecting it
        explicitly, rather than trying to raise the variance/area
        thresholds until a QR code no longer qualifies, avoids blinding the
        check to an actual small pasted patch of similar size elsewhere on
        the same document.
        """
        try:
            retval, points = cv2.QRCodeDetector().detectMulti(gray)
        except cv2.error:
            return []
        if not retval or points is None:
            return []
        boxes = []
        for quad in points:
            xs, ys = quad[:, 0], quad[:, 1]
            boxes.append((float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())))
        return boxes

    @staticmethod
    def _overlaps_a_qr_box(x: int, y: int, cw: int, ch: int, qr_boxes: List[tuple]) -> bool:
        cand_area = cw * ch
        for qx1, qy1, qx2, qy2 in qr_boxes:
            ix1, iy1 = max(x, qx1), max(y, qy1)
            ix2, iy2 = min(x + cw, qx2), min(y + ch, qy2)
            overlap = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            if cand_area > 0 and overlap / cand_area > 0.5:
                return True
        return False

    @staticmethod
    def detect_splicing_boundaries(img_cv: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects sharp unnatural rectangular or irregular edge discontinuities characteristic
        of pasted text patches or replaced photos.
        """
        h, w = img_cv.shape[:2]
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        qr_boxes = TamperForensics._detect_qr_boxes(gray)

        # High-pass filter using Laplacian
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_abs = np.uint8(np.absolute(lap))

        # Threshold high-frequency edges
        _, thresh = cv2.threshold(lap_abs, 45, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        anomalies = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = cw * ch
            # Look for suspicious patches (e.g. 50x20 to 300x150) with high perimeter-to-area ratio
            if 1500 < area < 70000 and cw > 35 and ch > 18:
                if TamperForensics._overlaps_a_qr_box(x, y, cw, ch, qr_boxes):
                    continue
                # A real pasted/spliced patch (a replaced photo, a pasted
                # stamp, an altered text block) is essentially never this
                # elongated -- this project's own synthetic patches are
                # ~3:1 (stamp) and ~1.3:1 (photo replacement) at their most
                # extreme. An extreme width:height ratio here is instead
                # the geometric signature of a genuine printed design
                # element -- confirmed against a real, unaltered Aadhaar
                # card, where a wide, thin header banner (government
                # emblem + wordmark row, 361x19px, ~19:1) was flagged as a
                # "High-frequency boundary discontinuity" at 95% confidence
                # (case BM-2026-41713). The pre-existing QR-code exclusion
                # above only scopes out QR-shaped (near-square) regions and
                # doesn't cover this different shape class.
                MAX_ASPECT_RATIO = 8.0
                if max(cw, ch) / min(cw, ch) > MAX_ASPECT_RATIO:
                    continue
                roi = gray[y:y+ch, x:x+cw]
                roi_var = float(np.var(roi))

                # Check variance deviation from image background
                if roi_var > 1400:
                    anomaly_type, explanation = TamperForensics._classify_splice_shape(cw, ch, x, y)
                    anomalies.append({
                        "type": anomaly_type,
                        "region": [int(x), int(y), int(cw), int(ch)],
                        "confidence": min(0.95, round(0.65 + (roi_var / 5000), 2)),
                        "explanation": explanation,
                        # The actual measured region variance vs. the 1400
                        # threshold it was judged against -- previously only
                        # encoded opaquely into `confidence` above, now
                        # exposed as citable evidence too (see
                        # tamper_service.py's own check construction).
                        "roi_variance": round(roi_var, 1),
                    })
        return anomalies[:5] # Return top most prominent

    # A pasted stamp/seal patch is a genuinely different shape class from a
    # replaced-photo or altered-text patch: this project's own synthetic
    # stamp specimen (see synthetic_generator.py's 'stamp_manipulated' mode)
    # is a 180x60px rectangle -- exactly 3.0:1 -- while a photo replacement
    # is closer to 1.3:1 (caught primarily by analyze_portrait_region's own
    # Signal C anyway) and an altered text block tends to be wide and short
    # but less extreme than a stamp. This window is centered on that real
    # 3.0:1 ratio with margin on both sides, bounded above by
    # MAX_ASPECT_RATIO (8.0) already excluding genuine thin banner/wordmark
    # design elements before this is ever reached.
    _STAMP_ASPECT_RATIO_MIN = 2.2
    _STAMP_ASPECT_RATIO_MAX = 4.2

    @staticmethod
    def _classify_splice_shape(cw: int, ch: int, x: int, y: int) -> Tuple[str, str]:
        """Returns (anomaly type, explanation) for a detected high-variance
        boundary patch, based purely on its shape -- distinguishes a
        stamp/seal-shaped patch from the generic edge-discontinuity catch-all
        so the tamper report doesn't lump a forged stamp in with every other
        kind of pasted patch under one unlabeled signal."""
        aspect_ratio = max(cw, ch) / min(cw, ch)
        if TamperForensics._STAMP_ASPECT_RATIO_MIN <= aspect_ratio <= TamperForensics._STAMP_ASPECT_RATIO_MAX:
            return (
                "stamp_forgery",
                f"Patch at ({x}, {y}) has the proportions and high-frequency boundary "
                f"signature of a pasted or altered stamp/seal, not a general document "
                f"edit -- aspect ratio {aspect_ratio:.1f}:1."
            )
        return (
            "edge_discontinuity",
            f"High-frequency boundary discontinuity detected at coordinate ({x}, {y})."
        )
