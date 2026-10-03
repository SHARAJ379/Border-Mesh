"""
Fourth face-embedder fine-tuning attempt. Same ArcFace objective as attempt 3
(scripts/finetune_face_embedder_arcface.py), which avoided attempt 2's total
collapse but still regressed accuracy -- the working hypothesis afterward was
that FG-NET + CALFW's thin per-identity depth (~3.2 images/identity across
4,106 identities) was the dominant problem, not the loss function. This
attempt tests that hypothesis directly: same objective, much richer data.

Adds two real, properly-licensed datasets with far deeper per-identity
coverage:
  - CelebA (flwrlabs/celeba on HuggingFace): ~19 images/identity average,
    official "celeba-dataset-release-agreement" research license.
  - WebFace4M (gaunernst/webface4m-wds-gz on HuggingFace): the official
    reduced subset of WebFace42M (InsightFace's SOTA training corpus),
    non-commercial-research license. Only a 6-shard SAMPLE is used here
    (~211k of the ~4.2M images in the full subset, which is itself ~1/10 of
    the full 42M-image WebFace42M) -- downloading and training the full
    corpus is a multi-day, multi-GPU undertaking, not something this script
    claims to do.

Explicitly NOT used, with reasons (see KNOWN_LIMITATIONS.md section 5 and
the chat discussion that led here):
  - LFW: this is the evaluation benchmark every accuracy number in this
    project is measured against. Training on it would contaminate the test
    set, not improve real generalization.
  - WIDER FACE: face-detection-only, zero identity labels -- structurally
    unusable for verification fine-tuning (confirmed, not assumed).
  - FairFace: single image per sample, no identity grouping -- same
    structural problem (confirmed, not assumed).
  - MS-Celeb-1M: withdrawn by Microsoft in 2019 after non-consensual
    scraping was exposed; documented use by surveillance vendors in
    human-rights-abuse contexts. Not used regardless of mirror
    availability.

Approach: IDENTICAL to finetune_face_embedder_arcface.py -- freeze all
early conv blocks, unfreeze only block8 + last_linear + last_bn, ArcFace
additive angular margin loss (s=30, m=0.5) instead of plain softmax. All
four sources merged into ONE identity label space, one DataLoader -- same
reasoning as the prior scripts' module docstrings (avoids catastrophic
forgetting from sequential fit() calls).

Get the data first (if not already present):
    .venv-train/Scripts/python.exe -c "
    from huggingface_hub import hf_hub_download
    import os
    os.makedirs('data/CelebA', exist_ok=True)
    for i in range(6):
        hf_hub_download(repo_id='flwrlabs/celeba', repo_type='dataset',
                         filename=f'img_align+identity+attr/train-{i:05d}-of-00019.parquet',
                         local_dir='data/CelebA')
    os.makedirs('data/WebFace4M', exist_ok=True)
    for i in range(6):
        hf_hub_download(repo_id='gaunernst/webface4m-wds-gz', repo_type='dataset',
                         filename=f'webface4m-{i:04d}.tar.gz', local_dir='data/WebFace4M')
    "

Run with (.venv-train, GPU):
    .venv-train/Scripts/python.exe scripts/finetune_face_embedder_bigdata.py

Output:
    backend/app/ml/weights/face_embedder_finetuned_bigdata.pth (state_dict)
    -- deliberately NOT the auto-loaded filename. Per the project's own
    policy, a candidate must first pass scripts/evaluate_lfw_same_age.py's
    same-age regression check (>=95%) before promotion.
"""
import csv
import io
import math
import os
import random
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from facenet_pytorch import MTCNN, InceptionResnetV1

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FGNET_IMAGES_DIR = PROJECT_ROOT / "data" / "FGNET" / "images"
CALFW_ALIGNED_DIR = PROJECT_ROOT / "data" / "CALFW" / "aligned"
CALFW_METADATA_CSV = CALFW_ALIGNED_DIR / "metadata.csv"
CELEBA_DIR = PROJECT_ROOT / "data" / "CelebA" / "img_align+identity+attr"
WEBFACE4M_DIR = PROJECT_ROOT / "data" / "WebFace4M"

CROP_CACHE_DIR = PROJECT_ROOT / "data" / ".face_crop_cache"
# Attempt 5: same script as attempt 4, scaled up (6->19 CelebA shards,
# 6->24 WebFace4M shards, ~1.0M images vs attempt 4's 221,516) -- kept as
# its own weights file (not overwriting attempt 4's checkpoint) so both
# remain on disk for comparison/reproducibility.
WEIGHTS_PATH = PROJECT_ROOT / "backend" / "app" / "ml" / "weights" / "face_embedder_finetuned_bigdata_v2.pth"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EMBED_SIZE = (160, 160)
EPOCHS = 5  # fewer than attempt 4's 8 -- ~4.6x more data/epoch, and attempt 4 had already plateaued by epoch 5-6
BATCH_SIZE = 64
LR = 1e-4
VAL_FRACTION = 0.10  # lower than attempts 2/3's 0.15 -- much larger pool now, 10% is still plenty for a stable validation read
SEED = 42
MIN_IMAGES_PER_IDENTITY = 2
NUM_WORKERS = 4  # full config -- two attempts at reduced scale (12 shards/1 worker, and
# the original 24 shards/4 workers) both got OOM-killed at an almost identical ~3.6GB-free
# ceiling, which pointed at persistent baseline load from other running apps (Discord,
# Chrome, WSL, Edge webview) rather than this script's own tunables. Reverted to full scale
# on the expectation that headroom has been freed on the host side; if this still OOMs,
# the fix is host memory, not these numbers.
MAX_WEBFACE4M_SHARDS = 24  # full set downloaded

ARCFACE_S = 30.0
ARCFACE_M = 0.50

random.seed(SEED)
torch.manual_seed(SEED)

FGNET_FNAME_RE = re.compile(r"^(\d{3})[Aa](\d{2})", re.IGNORECASE)


def parse_fgnet_identity(fname: str):
    m = FGNET_FNAME_RE.match(fname)
    return m.group(1) if m else None


def build_fgnet_samples(mtcnn: MTCNN):
    if not FGNET_IMAGES_DIR.is_dir():
        print(f"WARNING: {FGNET_IMAGES_DIR} not found -- skipping FG-NET.")
        return []
    cache_dir = CROP_CACHE_DIR / "fgnet"
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in os.listdir(FGNET_IMAGES_DIR) if f.upper().endswith(".JPG"))
    print(f"FG-NET: found {len(files)} images")
    samples = []
    for i, fname in enumerate(files):
        identity = parse_fgnet_identity(fname)
        if identity is None:
            continue
        cache_path = cache_dir / (fname + ".npy")
        if not cache_path.exists():
            img_bgr = cv2.imread(str(FGNET_IMAGES_DIR / fname))
            if img_bgr is None:
                continue
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            box, _ = mtcnn.detect(rgb)
            if box is not None and len(box) > 0:
                x1, y1, x2, y2 = [int(max(0, v)) for v in box[0]]
                crop = rgb[y1:y2, x1:x2]
            else:
                crop = rgb
            if crop.size == 0:
                crop = rgb
            crop = cv2.resize(crop, EMBED_SIZE)
            np.save(cache_path, crop)
        samples.append((str(cache_path), f"FGNET:{identity}"))
    print(f"  FG-NET: {len(samples)} usable samples")
    return samples


def build_calfw_samples():
    if not CALFW_METADATA_CSV.exists():
        print(f"WARNING: {CALFW_METADATA_CSV} not found -- skipping CALFW.")
        return []
    cache_dir = CROP_CACHE_DIR / "calfw"
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(CALFW_METADATA_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    samples = []
    for row in rows:
        rel_path = row["file_name"]
        identity = row["identity"]
        src_path = CALFW_ALIGNED_DIR / rel_path
        cache_path = cache_dir / (rel_path.replace("/", "__") + ".npy")
        if not cache_path.exists():
            img_bgr = cv2.imread(str(src_path))
            if img_bgr is None:
                continue
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            crop = cv2.resize(rgb, EMBED_SIZE)
            np.save(cache_path, crop)
        samples.append((str(cache_path), f"CALFW:{identity}"))
    print(f"  CALFW: {len(samples)} usable samples")
    return samples


def build_celeba_samples():
    """CelebA parquet shards: `image` is a {bytes, path} struct (JPEG bytes),
    `celeb_id` an int -- schema confirmed directly against a downloaded
    shard, not assumed. Decoded and cached to .npy once, same convention as
    FG-NET/CALFW above, so later epochs don't re-decode JPEG from parquet."""
    import pyarrow.parquet as pq

    if not CELEBA_DIR.is_dir():
        print(f"WARNING: {CELEBA_DIR} not found -- skipping CelebA.")
        return []
    shard_files = sorted(CELEBA_DIR.glob("train-*.parquet"))
    if not shard_files:
        print(f"WARNING: no CelebA train shards found in {CELEBA_DIR} -- skipping.")
        return []

    cache_dir = CROP_CACHE_DIR / "celeba"
    cache_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    for shard_path in shard_files:
        pf = pq.ParquetFile(shard_path)
        shard_idx = shard_path.stem
        row_i = 0
        for batch in pf.iter_batches(columns=["image", "celeb_id"], batch_size=512):
            for img_struct, celeb_id in zip(batch["image"].to_pylist(), batch["celeb_id"].to_pylist()):
                cache_path = cache_dir / f"{shard_idx}_{row_i}.npy"
                if not cache_path.exists():
                    buf = np.frombuffer(img_struct["bytes"], dtype=np.uint8)
                    img_bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                    if img_bgr is None:
                        row_i += 1
                        continue
                    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                    crop = cv2.resize(rgb, EMBED_SIZE)
                    np.save(cache_path, crop)
                samples.append((str(cache_path), f"CELEBA:{celeb_id}"))
                row_i += 1
        print(f"  CelebA {shard_idx}: {row_i} rows processed, {len(samples)} cumulative samples")
    return samples


def build_webface4m_samples():
    """WebFace4M tar.gz shards: paired `{key}.jpg` + `{key}.cls` members
    (cls = plain-text integer identity) -- confirmed directly against a
    downloaded shard's actual tarfile contents, not assumed. Images are
    already 112x112 aligned crops; just resized up to EMBED_SIZE and
    cached to .npy, same convention as the other three sources.

    Single SEQUENTIAL pass via tf.extractfile(member) on members in their
    physical tar order (for member in tf), not a sorted-name dict lookup --
    an earlier version built a {name: member} dict and called extractfile()
    by name in sorted order, which (measured directly: 2,524 of ~211k files
    cached after several minutes, versus this version's full single shard
    in well under a minute) forces the gzip stream to repeatedly seek
    backward and re-decompress from the start for out-of-physical-order
    lookups -- gzip is not efficiently random-access. The jpg/cls pair for
    a given key are adjacent in physical order (confirmed when the shard
    was first inspected), so a straight forward iteration naturally pairs
    them with a 1-item lookback buffer, no seeking at all.
    """
    if not WEBFACE4M_DIR.is_dir():
        print(f"WARNING: {WEBFACE4M_DIR} not found -- skipping WebFace4M.")
        return []
    shard_files = sorted(WEBFACE4M_DIR.glob("webface4m-*.tar.gz"))[:MAX_WEBFACE4M_SHARDS]
    if not shard_files:
        print(f"WARNING: no WebFace4M shards found in {WEBFACE4M_DIR} -- skipping.")
        return []

    cache_dir = CROP_CACHE_DIR / "webface4m"
    cache_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    for shard_path in shard_files:
        pending: dict[str, bytes] = {}  # key -> whichever half (jpg or cls bytes/cls id) arrived first
        with tarfile.open(shard_path, "r:gz") as tf:
            for member in tf:  # physical order, single forward pass, no re-seeking
                if not member.isfile():
                    continue
                key, _, ext = member.name.rpartition(".")
                if ext not in ("jpg", "cls"):
                    continue
                cache_path = cache_dir / f"{key.replace('/', '__')}.npy"
                if ext == "cls":
                    cls_id = tf.extractfile(member).read().decode("utf-8").strip()
                    other = pending.pop(key, None)
                    if cache_path.exists():
                        samples.append((str(cache_path), f"WEBFACE:{cls_id}"))
                    elif other is not None:  # jpg bytes arrived first
                        _save_webface_crop(other, cache_path)
                        samples.append((str(cache_path), f"WEBFACE:{cls_id}"))
                    else:
                        pending[key] = cls_id  # cls arrived first; wait for jpg
                else:  # jpg
                    jpg_bytes = tf.extractfile(member).read()
                    other = pending.pop(key, None)
                    if cache_path.exists():
                        if isinstance(other, str):
                            samples.append((str(cache_path), f"WEBFACE:{other}"))
                        # else: cls not seen yet for an already-cached crop -- dropped (rare, next run recaches)
                    elif isinstance(other, str):  # cls id arrived first
                        _save_webface_crop(jpg_bytes, cache_path)
                        samples.append((str(cache_path), f"WEBFACE:{other}"))
                    else:
                        pending[key] = jpg_bytes  # jpg arrived first; wait for cls
        print(f"  WebFace4M {shard_path.name}: {len(samples)} cumulative samples")
    return samples


def _save_webface_crop(jpg_bytes: bytes, cache_path: Path) -> None:
    buf = np.frombuffer(jpg_bytes, dtype=np.uint8)
    img_bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    crop = cv2.resize(rgb, EMBED_SIZE)
    np.save(cache_path, crop)


class FaceIdentityDataset(Dataset):
    def __init__(self, samples, label_map):
        self.samples = samples
        self.label_map = label_map

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, identity = self.samples[idx]
        crop = np.load(path)
        tensor = torch.from_numpy(crop).permute(2, 0, 1).float()
        tensor = (tensor - 127.5) / 128.0
        return tensor, self.label_map[identity]


class ArcMarginProduct(nn.Module):
    def __init__(self, in_features: int, out_features: int, s: float = ARCFACE_S, m: float = ARCFACE_M):
        super().__init__()
        self.s = s
        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        sine = torch.sqrt((1.0 - cosine.pow(2)).clamp(min=1e-7, max=1.0))
        phi = cosine * self.cos_m - sine * self.sin_m
        phi = torch.where(cosine > 0, phi, cosine)
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)
        logits = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        return logits * self.s


def main():
    print(f"Device: {DEVICE}" + (f" ({torch.cuda.get_device_name(0)})" if DEVICE.type == "cuda" else ""))
    if DEVICE.type != "cuda":
        print("WARNING: no CUDA device visible -- this will be slow. Run under .venv-train.")

    mtcnn = MTCNN(keep_all=False, device=DEVICE, post_process=False)

    print("\n--- Building sample list from all four sources ---")
    fgnet_samples = build_fgnet_samples(mtcnn)
    calfw_samples = build_calfw_samples()
    celeba_samples = build_celeba_samples()
    webface_samples = build_webface4m_samples()

    samples = fgnet_samples + calfw_samples + celeba_samples + webface_samples
    if not samples:
        print("ERROR: no training samples found from any source. Aborting.")
        sys.exit(1)

    by_identity = defaultdict(list)
    for s in samples:
        by_identity[s[1]].append(s)

    dropped = {ident: items for ident, items in by_identity.items() if len(items) < MIN_IMAGES_PER_IDENTITY}
    if dropped:
        print(f"Dropping {len(dropped)} identities with < {MIN_IMAGES_PER_IDENTITY} images "
              f"({sum(len(v) for v in dropped.values())} images total)")
        by_identity = {k: v for k, v in by_identity.items() if k not in dropped}

    identities = sorted(by_identity.keys())
    label_map = {ident: i for i, ident in enumerate(identities)}
    counts = {
        src: sum(1 for i in identities if i.startswith(f"{src}:"))
        for src in ("FGNET", "CALFW", "CELEBA", "WEBFACE")
    }
    total_images = sum(len(v) for v in by_identity.values())
    avg_per_id = total_images / len(identities) if identities else 0
    print(f"\nCombined: {len(identities)} identities {counts}, {total_images} usable images, "
          f"{avg_per_id:.1f} images/identity average "
          f"(attempts 2/3 had ~3.2 images/identity, for comparison)")

    train_samples, val_samples = [], []
    for ident, items in by_identity.items():
        random.shuffle(items)
        n_val = max(1, int(len(items) * VAL_FRACTION)) if len(items) > 5 else 0
        val_samples += items[:n_val]
        train_samples += items[n_val:]

    print(f"Train: {len(train_samples)}  Val: {len(val_samples)}")

    train_ds = FaceIdentityDataset(train_samples, label_map)
    val_ds = FaceIdentityDataset(val_samples, label_map)
    pin_memory = DEVICE.type == "cuda"
    num_workers = NUM_WORKERS if DEVICE.type == "cuda" else 0
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, pin_memory=pin_memory, num_workers=num_workers)
    val_dl = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, pin_memory=pin_memory, num_workers=num_workers)

    embedder = InceptionResnetV1(pretrained="vggface2").to(DEVICE)
    unfreeze = {"block8", "last_linear", "last_bn"}
    for name, param in embedder.named_parameters():
        param.requires_grad = any(name.startswith(u) for u in unfreeze)

    arc_head = ArcMarginProduct(512, len(identities)).to(DEVICE)
    params = [p for p in embedder.parameters() if p.requires_grad] + list(arc_head.parameters())
    optimizer = torch.optim.Adam(params, lr=LR)
    criterion = nn.CrossEntropyLoss()

    print(f"Trainable params: {sum(p.numel() for p in params):,}")
    print(f"ArcFace: s={ARCFACE_S}, m={ARCFACE_M}")

    best_val_acc = 0.0
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, EPOCHS + 1):
        embedder.train()
        arc_head.train()
        total_loss, n = 0.0, 0
        for bi, (x, y) in enumerate(train_dl):
            x, y = x.to(DEVICE), y.to(DEVICE)
            optimizer.zero_grad()
            emb = embedder(x)
            logits = arc_head(emb, y)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * x.size(0)
            n += x.size(0)
            if (bi + 1) % 200 == 0:
                print(f"  epoch {epoch} batch {bi + 1}/{len(train_dl)}  running_loss={total_loss / n:.4f}")

        embedder.eval()
        arc_head.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(DEVICE), y.to(DEVICE)
                emb = embedder(x)
                cosine = F.linear(F.normalize(emb), F.normalize(arc_head.weight))
                preds = cosine.argmax(dim=1)
                correct += (preds == y).sum().item()
                total += x.size(0)
        val_acc = correct / total if total else 0.0
        print(f"Epoch {epoch}/{EPOCHS}  train_loss={total_loss / n:.4f}  val_acc={val_acc:.3%}")

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save(embedder.state_dict(), WEIGHTS_PATH)

    print(f"\nBest combined val identity-classification accuracy: {best_val_acc:.3%}")
    print(f"Saved fine-tuned embedder weights to {WEIGHTS_PATH}")
    print("\nThis is a CANDIDATE checkpoint, NOT yet wired into the app. Before "
          "wiring it into backend/app/ml/face_verifier.py, run:\n"
          f"    .venv-train/Scripts/python.exe scripts/evaluate_lfw_same_age.py --weights {WEIGHTS_PATH}\n"
          "and confirm same-age accuracy does not regress below the 95% bar.")


if __name__ == "__main__":
    main()
