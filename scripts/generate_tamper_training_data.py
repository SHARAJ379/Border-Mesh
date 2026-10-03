"""
Synthetic training-data generator for the tamper-forensics CNN
(backend/app/ml/tamper_model.py: LightweightForensicCNN).

Produces labeled 64x64 patches:
  - label 0 (authentic): patches from freshly generated, un-tampered documents.
  - label 1 (tampered):  patches containing a synthetic splice -- a rectangular
    region copy-pasted from a DIFFERENT document and re-encoded at a different
    JPEG quality before pasting, which is exactly the kind of copy-paste /
    recompression artifact ELA and edge-discontinuity heuristics are designed
    to catch. This is the standard way to build a labeled dataset for a patch
    splice-detector without any external data: the ground truth is known
    exactly because we created the splice ourselves.

Not run automatically -- this only builds the dataset in memory / on disk.
Actual training happens in scripts/train_tamper_cnn.py, which imports
`generate_dataset` from this module.
"""
import json
import os
import re
import sys
import random
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.utils.synthetic_generator import SyntheticDocumentGenerator

PATCH_SIZE = 64

_SURNAMES = ["KAUL", "SHARMA", "DOE", "PATEL", "KOROL", "MEHTA", "SINGH", "REYES",
             "MULLER", "IVANOV", "NAKAMURA", "OKAFOR", "GARCIA", "KIM", "ANDERSSON"]
_GIVEN = ["ARIHANT", "PRIYA", "JOHN", "ROHAN", "VIKTOR", "ANITA", "RAVI", "MARIA",
          "HANS", "ELENA", "YUKI", "CHIOMA", "CARLOS", "JIWOO", "ERIK"]
_COUNTRIES = [("UTO", "REPUBLIC OF UTOPIA"), ("DEM", "DEMO STATE"),
              ("ATL", "ATLANTIS FEDERATION"), ("NOR", "NORTHLANDIA"), ("VER", "VERITAS UNION")]


def _random_doc_kwargs() -> dict:
    code, country_name = random.choice(_COUNTRIES)
    return {
        "surname": random.choice(_SURNAMES),
        "given_names": random.choice(_GIVEN),
        "country_code": code,
        "country_name": country_name,
        "doc_number": f"{random.choice('ABDPX')}{random.randint(1000000, 9999999)}",
        "dob_yymmdd": f"{random.randint(60,99)}{random.randint(1,12):02d}{random.randint(1,28):02d}",
        "expiry_yymmdd": f"{random.randint(26,35)}{random.randint(1,12):02d}{random.randint(1,28):02d}",
    }


def _generate_genuine_doc(tmp_dir: str) -> np.ndarray:
    """Generates one genuine synthetic document and returns it as a BGR array."""
    out_path = os.path.join(tmp_dir, f"doc_{random.randint(0, 1_000_000)}.jpg")
    SyntheticDocumentGenerator.generate_document(out_path=out_path, mode="genuine", **_random_doc_kwargs())
    img = cv2.imread(out_path)
    os.remove(out_path)
    return img


def _splice(base: np.ndarray, donor: np.ndarray, tmp_dir: str) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Pastes a random rectangular region from `donor` onto `base`, after
    re-encoding the donor patch at a different JPEG quality (simulating a
    realistic copy-paste forgery's recompression artifact). Returns the
    modified image and the (x, y, w, h) region that was spliced.
    """
    h, w = base.shape[:2]
    pw, ph = random.randint(80, 180), random.randint(60, 140)
    x = random.randint(0, max(1, w - pw))
    y = random.randint(0, max(1, h - ph))

    dh, dw = donor.shape[:2]
    dx = random.randint(0, max(1, dw - pw))
    dy = random.randint(0, max(1, dh - ph))
    donor_patch = donor[dy:dy + ph, dx:dx + pw]
    if donor_patch.size == 0:
        return base, (0, 0, 0, 0)

    # Re-encode at a different quality to introduce a genuine recompression
    # mismatch, then decode back -- this is what makes ELA/CNN splice cues real.
    tmp_path = os.path.join(tmp_dir, f"patch_{random.randint(0, 1_000_000)}.jpg")
    cv2.imwrite(tmp_path, donor_patch, [cv2.IMWRITE_JPEG_QUALITY, random.choice([55, 65, 97])])
    reencoded = cv2.imread(tmp_path)
    os.remove(tmp_path)
    if reencoded is None or reencoded.shape[:2] != (ph, pw):
        reencoded = cv2.resize(donor_patch, (pw, ph)) if reencoded is None else cv2.resize(reencoded, (pw, ph))

    spliced = base.copy()
    spliced[y:y + ph, x:x + pw] = reencoded
    return spliced, (x, y, pw, ph)


def _random_patch(img: np.ndarray, region: Tuple[int, int, int, int] = None) -> np.ndarray:
    """Extracts a PATCH_SIZE x PATCH_SIZE patch, either from a given (x,y,w,h)
    region (jittered within it) or from a random location in the image."""
    h, w = img.shape[:2]
    if region is not None:
        x, y, rw, rh = region
        cx = x + random.randint(0, max(1, rw - 1))
        cy = y + random.randint(0, max(1, rh - 1))
    else:
        cx = random.randint(0, max(1, w - 1))
        cy = random.randint(0, max(1, h - 1))

    x1 = max(0, min(w - PATCH_SIZE, cx - PATCH_SIZE // 2))
    y1 = max(0, min(h - PATCH_SIZE, cy - PATCH_SIZE // 2))
    patch = img[y1:y1 + PATCH_SIZE, x1:x1 + PATCH_SIZE]
    if patch.shape[:2] != (PATCH_SIZE, PATCH_SIZE):
        patch = cv2.resize(patch, (PATCH_SIZE, PATCH_SIZE))
    return cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)


def generate_dataset(n_docs: int = 60, patches_per_doc: int = 6, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Builds a labeled patch dataset.

    Returns (patches, labels):
      patches: uint8 array, shape (N, 64, 64, 3), RGB.
      labels:  int64 array, shape (N,), 0=authentic, 1=tampered.
    """
    random.seed(seed)
    np.random.seed(seed)

    patches: List[np.ndarray] = []
    labels: List[int] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = [_generate_genuine_doc(tmp_dir) for _ in range(n_docs)]

        # Authentic patches: random locations across genuine documents.
        for doc in docs:
            for _ in range(patches_per_doc):
                patches.append(_random_patch(doc))
                labels.append(0)

        # Tampered patches: splice a donor region into a base doc, then sample
        # patches from inside the spliced region (label 1) and a few from
        # elsewhere in the same modified doc, which remain genuinely authentic
        # (label 0) -- this teaches the model the difference is localized, not
        # "this whole document is suspicious".
        for i, base in enumerate(docs):
            donor = docs[(i + 1) % len(docs)]
            spliced_img, region = _splice(base, donor, tmp_dir)
            if region == (0, 0, 0, 0):
                continue
            for _ in range(patches_per_doc):
                patches.append(_random_patch(spliced_img, region))
                labels.append(1)
            for _ in range(patches_per_doc // 2):
                # Sample away from the splice region for the "elsewhere" negatives.
                h, w = spliced_img.shape[:2]
                rx, ry = random.randint(0, w - 1), random.randint(0, h - 1)
                rx1, ry1, rw, rh = region
                if rx1 <= rx <= rx1 + rw and ry1 <= ry <= ry1 + rh:
                    continue
                patches.append(_random_patch(spliced_img))
                labels.append(0)

    return np.stack(patches).astype(np.uint8), np.array(labels, dtype=np.int64)


def _patch_centered_at(img: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """Extracts a PATCH_SIZE x PATCH_SIZE RGB patch centered at (cx, cy), clamped to bounds."""
    h, w = img.shape[:2]
    x1 = max(0, min(w - PATCH_SIZE, cx - PATCH_SIZE // 2))
    y1 = max(0, min(h - PATCH_SIZE, cy - PATCH_SIZE // 2))
    patch = img[y1:y1 + PATCH_SIZE, x1:x1 + PATCH_SIZE]
    if patch.shape[:2] != (PATCH_SIZE, PATCH_SIZE):
        patch = cv2.resize(patch, (PATCH_SIZE, PATCH_SIZE))
    return cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)


def _split_files(files: list, split: Optional[str], holdout_fraction: float, seed: int) -> list:
    """
    Deterministically partitions a file list into disjoint train/test subsets
    by filename (not by patch), using a dedicated RNG so the split doesn't
    depend on, or disturb, the global `random`/`np.random` state used
    elsewhere for patch sampling. `split=None` returns every file unchanged
    (the original, pre-split behavior).

    This exists because the project's prior CASIA "held-out" evaluation
    wasn't actually held out: training and evaluation both called
    load_casia_patches() with the same default seed over the *same full
    image set*, so most of the "held-out" eval patches were literally in the
    training set. Training should request split="train" and the final
    evaluation should request split="test" against the same holdout_fraction
    and seed, so the two never overlap.
    """
    if split is None:
        return files
    if split not in ("train", "test"):
        raise ValueError(f"split must be 'train', 'test', or None, got {split!r}")
    ordered = sorted(files)
    rng = random.Random(seed)
    rng.shuffle(ordered)
    n_test = int(len(ordered) * holdout_fraction)
    return ordered[:n_test] if split == "test" else ordered[n_test:]


def load_casia_patches(
    casia_root: str,
    n_authentic: Optional[int] = None,
    n_tampered: Optional[int] = None,
    patches_per_image: int = 2,
    seed: int = 42,
    split: Optional[str] = None,
    holdout_fraction: float = 0.2,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Samples labeled 64x64 patches from the CASIA v2.0 image tampering
    detection dataset (real photographs, real human-made splices -- not
    documents, but a far richer and less predictable splice signature than
    our own synthetic generator's plain rectangular copy-paste). Get it via:

        kaggle datasets download -d divg07/casia-20-image-tampering-detection-dataset -p <dir> --unzip

    Expects the standard CASIA2 layout under `casia_root`:
        Au/                       authentic photos
        Tp/                       tampered photos
        CASIA 2 Groundtruth/      per-tampered-image binary masks, named
                                   "<tp_filename_without_ext>_gt.png"

    Authentic patches are random crops from Au/ images. Tampered patches are
    centered on actual masked (truly-spliced) pixels -- sampled directly from
    the mask's nonzero coordinates rather than its bounding box, since CASIA
    masks are often irregular shapes where the bounding box contains plenty
    of untouched background; centering on the box instead of the mask itself
    would mislabel clean patches as tampered. n_authentic/n_tampered default
    to None, meaning use every available image (the model is tiny -- a few
    tens of thousands of parameters -- so wall-clock time is dominated by
    image I/O, not training compute; there's no accuracy reason to subsample
    a real, labeled dataset). A handful of files in this dataset are known to
    be corrupt/truncated; those are skipped rather than failing the whole run.
    """
    random.seed(seed)
    np.random.seed(seed)

    root = Path(casia_root)
    au_dir, tp_dir, gt_dir = root / "Au", root / "Tp", root / "CASIA 2 Groundtruth"

    au_files = [f for f in au_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".bmp")]
    tp_files = [f for f in tp_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".tif", ".tiff")]
    au_files = _split_files(au_files, split, holdout_fraction, seed)
    tp_files = _split_files(tp_files, split, holdout_fraction, seed)
    random.shuffle(au_files)
    random.shuffle(tp_files)
    if n_authentic is not None:
        au_files = au_files[:n_authentic]
    if n_tampered is not None:
        tp_files = tp_files[:n_tampered]

    patches: List[np.ndarray] = []
    labels: List[int] = []

    for f in au_files:
        img = cv2.imread(str(f))
        if img is None or img.shape[0] < PATCH_SIZE or img.shape[1] < PATCH_SIZE:
            continue
        for _ in range(patches_per_image):
            patches.append(_random_patch(img))
            labels.append(0)

    for f in tp_files:
        gt_path = gt_dir / f"{f.stem}_gt.png"
        if not gt_path.exists():
            continue
        img = cv2.imread(str(f))
        mask = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
        if img is None or mask is None or img.shape[0] < PATCH_SIZE or img.shape[1] < PATCH_SIZE:
            continue
        ys, xs = np.nonzero(mask > 10)
        if len(xs) == 0:
            continue
        # Sample patch centers directly from true mask pixels, jittering the
        # index (not the pixel coordinate) so we still cover the mask's
        # extent rather than always the same spot.
        idxs = np.random.choice(len(xs), size=patches_per_image, replace=True)
        for idx in idxs:
            patches.append(_patch_centered_at(img, int(xs[idx]), int(ys[idx])))
            labels.append(1)

    return np.stack(patches).astype(np.uint8), np.array(labels, dtype=np.int64)


def load_sidtd_patches(
    sidtd_root: str,
    patches_per_real: int = 4,
    patches_per_fake: int = 4,
    elsewhere_per_fake: int = 2,
    seed: int = 42,
    split: Optional[str] = None,
    holdout_fraction: float = 0.2,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Samples labeled 64x64 patches from the SIDTD dataset (Synthetic dataset
    of ID and Travel Documents, CVC/Computer Vision Center, CC BY-SA 3.0):

        http://datasets.cvc.uab.es/SIDTD/templates.zip

    Unlike CASIA (real splices, but not documents) or our own synthetic
    generator (documents, but only a narrow rectangular copy-paste
    signature), SIDTD is real *document* forgeries: MIDV-2020's mock ID
    templates digitally tampered (crop-and-replace or inpainting) at the
    same resolution/coordinate space as their source image -- across 10
    real-looking ID document types. (SIDTD separately offers physically
    printed, laminated, and re-photographed video captures of these same
    forgeries in clips.zip/videos.zip, tens of GB and not used here --
    templates.zip's still images are what this loader reads.) This is
    document-domain data the tamper CNN never had.

    Expects `sidtd_root` to be the extracted `templates/` directory:
        Images/reals/<doctype>_<NN>.jpg           genuine documents
        Images/fakes/<doctype>_<NN>_fake_*.jpg     tampered documents
        Annotations/reals/<doctype>.json           VIA-format field regions
                                                    per genuine image
        Annotations/fakes/<fake_stem>.json         which field was tampered
                                                    and which real image it
                                                    was derived from

    Each fake's annotation names the tampered field (e.g. "expiry_date") and
    its source real image (e.g. "alb_id_00.jpg"); the source's own
    annotation gives that field's pixel bounding box -- letting tampered
    patches be centered on the actual tampered region rather than sampled
    from anywhere in the image (the same lesson CASIA's mask-based sampling
    already taught: a bounding-box-blind sample mislabels clean background
    as tampered). When a field can't be resolved (missing annotation, or a
    two-source Crop_and_Replace whose primary field is "None"), fall back to
    whole-image sampling for that one fake rather than dropping it --
    still real tampered-document data, just without precise localization.
    """
    random.seed(seed)
    np.random.seed(seed)

    root = Path(sidtd_root)
    reals_dir, fakes_dir = root / "Images" / "reals", root / "Images" / "fakes"
    reals_ann_dir, fakes_ann_dir = root / "Annotations" / "reals", root / "Annotations" / "fakes"

    # Split at the DOCUMENT-TYPE level (e.g. "alb_id"), not the individual-
    # file level: all ~100 "reals" of one doctype share the same fixed
    # template design (layout/background), varying only in the overlaid
    # field values -- a file-level split would let the model train on that
    # exact template and then be "tested" on another instance of the same
    # template, which isn't a genuinely unseen case. Holding out whole
    # doctypes means the test set contains template designs the model never
    # saw in any form during training.
    _real_re = re.compile(r'^(.+)_\d+\.jpg$')
    _fake_re = re.compile(r'^(.+)_\d+_fake_.*\.jpg$')
    all_doctypes = sorted({m.group(1) for f in reals_dir.glob("*.jpg") for m in [_real_re.match(f.name)] if m})
    allowed_doctypes = set(_split_files(all_doctypes, split, holdout_fraction, seed))

    doctype_annotations: dict = {}

    def _doctype_annotation(doctype: str) -> Optional[dict]:
        if doctype not in doctype_annotations:
            path = reals_ann_dir / f"{doctype}.json"
            doctype_annotations[doctype] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        return doctype_annotations[doctype]

    def _field_bbox(src_filename: str, field: str) -> Optional[Tuple[int, int, int, int]]:
        m = re.match(r'^(.+)_(\d+)\.jpg$', src_filename)
        if not m:
            return None
        doctype, index = m.group(1), m.group(2)
        annotation = _doctype_annotation(doctype)
        if annotation is None:
            return None
        img_meta = annotation.get("_via_img_metadata", {})
        key = next((k for k in img_meta if k.startswith(f"{index}.jpg")), None)
        if key is None:
            return None
        for region in img_meta[key].get("regions", []):
            if region.get("region_attributes", {}).get("field_name") == field:
                sa = region["shape_attributes"]
                return (sa["x"], sa["y"], sa["width"], sa["height"])
        return None

    patches: List[np.ndarray] = []
    labels: List[int] = []

    for f in sorted(reals_dir.glob("*.jpg")):
        if split is not None:
            m = _real_re.match(f.name)
            if not m or m.group(1) not in allowed_doctypes:
                continue
        img = cv2.imread(str(f))
        if img is None:
            continue
        for _ in range(patches_per_real):
            patches.append(_random_patch(img))
            labels.append(0)

    resolved, unresolved = 0, 0
    for f in sorted(fakes_dir.glob("*.jpg")):
        if split is not None:
            m = _fake_re.match(f.name)
            if not m or m.group(1) not in allowed_doctypes:
                continue
        ann_path = fakes_ann_dir / f"{f.stem}.json"
        if not ann_path.exists():
            continue
        meta = json.loads(ann_path.read_text(encoding="utf-8"))
        img = cv2.imread(str(f))
        if img is None:
            continue

        bbox = None
        src, field = meta.get("src"), meta.get("field")
        if src and src != "None" and field and field != "None":
            bbox = _field_bbox(src, field)

        if bbox is not None:
            resolved += 1
            x, y, w, h = bbox
            for _ in range(patches_per_fake):
                cx = x + random.randint(0, max(1, w - 1))
                cy = y + random.randint(0, max(1, h - 1))
                patches.append(_patch_centered_at(img, cx, cy))
                labels.append(1)
            ih, iw = img.shape[:2]
            added = 0
            for _ in range(elsewhere_per_fake * 5):  # bounded retry, not infinite
                if added >= elsewhere_per_fake:
                    break
                rx, ry = random.randint(0, iw - 1), random.randint(0, ih - 1)
                if x <= rx <= x + w and y <= ry <= y + h:
                    continue
                patches.append(_random_patch(img))
                labels.append(0)
                added += 1
        else:
            unresolved += 1
            for _ in range(patches_per_fake):
                patches.append(_random_patch(img))
                labels.append(1)

    print(f"  SIDTD: {resolved} fakes with a precisely-located tampered field, "
          f"{unresolved} using whole-image weak labeling")

    return np.stack(patches).astype(np.uint8), np.array(labels, dtype=np.int64)


if __name__ == "__main__":
    p, l = generate_dataset()
    print(f"Generated {len(p)} patches: {int((l == 0).sum())} authentic, {int((l == 1).sum())} tampered")
    print(f"Patch shape: {p.shape[1:]}, dtype: {p.dtype}")
