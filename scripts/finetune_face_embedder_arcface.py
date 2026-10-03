"""
Third face-embedder fine-tuning attempt -- same data as attempt 2
(FG-NET + CALFW, scripts/finetune_face_embedder_calfw.py), a DIFFERENT
training objective.

Why a third attempt, when KNOWN_LIMITATIONS.md says "no known combination
of available real cross-age data has produced a working improvement"?
That line is true for the approach actually tried twice -- plain softmax
cross-entropy over an identity-classification head, used as a proxy for
"did the embedding get better." Both attempts' own validation metric was
closed-set classification accuracy on the training identities, but
production needs open-set verification on identities NEVER seen in
training (LFW pairs, real officers/travellers). Optimizing classification
accuracy on ~82-5000 training identities pulls the embedding toward
decision boundaries FOR THOSE IDENTITIES specifically, which is a known
failure mode distinct from "not enough data" -- and explains why attempt 2
(MORE identities crammed into the SAME shared softmax head) collapsed
further than attempt 1 (52.1% vs 86.7%), the opposite of what more data
diversity should do if the problem were really data volume.

This script changes the objective, not the data: ArcFace (additive angular
margin loss, Deng et al. 2019, arxiv 1801.07698) replaces the plain
classification head. It still uses cross-entropy under the hood, but on
logits computed from the COSINE SIMILARITY between the (L2-normalized)
embedding and each class's (L2-normalized) weight vector, with an angular
margin added to the true class before scaling -- i.e. it directly optimizes
the same cosine-similarity structure face_verifier.py's compare_faces()
uses at inference, instead of an unrelated linear-separability proxy. This
is the standard approach modern face-recognition systems are actually
trained with.

Same frozen/unfrozen layer policy as both prior attempts (freeze everything
except block8 + last_linear + last_bn) and the same data pipeline (copied
from finetune_face_embedder_calfw.py) -- changing one variable (the loss),
not several at once, so if this also fails, the failure is attributable to
something other than "which layers were frozen" or "which data was used."

Get the data first (same as attempt 2 -- already present in this repo if
attempt 2 was run before):
    .venv-train/Scripts/python.exe -c "
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id='marcelohaps/calfw', repo_type='dataset',
                       allow_patterns=['aligned/images/**', 'aligned/metadata.csv'],
                       local_dir='data/CALFW')
    "

Run with (.venv-train, GPU):
    .venv-train/Scripts/python.exe scripts/finetune_face_embedder_arcface.py

Inputs:
    data/FGNET/images/                  -- 1,002 images, 82 identities
    data/CALFW/aligned/images/**         -- CALFW's aligned (already face-cropped, 224x224)
    data/CALFW/aligned/metadata.csv      -- identity label per image

Output:
    backend/app/ml/weights/face_embedder_finetuned_arcface.pth (state_dict)
    -- deliberately NOT named face_embedder_finetuned.pth (the filename
    face_verifier.py auto-loads): this is a CANDIDATE checkpoint. Per the
    project's own policy, a candidate must first pass
    scripts/evaluate_lfw_same_age.py's same-age regression check before
    being renamed/copied to the auto-loaded filename -- this script does
    NOT do that automatically, and does not touch face_verifier.py.
"""
import csv
import math
import os
import random
import re
import sys
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

CROP_CACHE_DIR = PROJECT_ROOT / "data" / ".face_crop_cache"
WEIGHTS_PATH = PROJECT_ROOT / "backend" / "app" / "ml" / "weights" / "face_embedder_finetuned_arcface.pth"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EMBED_SIZE = (160, 160)
EPOCHS = 15
BATCH_SIZE = 32
LR = 1e-4
VAL_FRACTION = 0.15
SEED = 42
MIN_IMAGES_PER_IDENTITY = 2

# ArcFace hyperparameters -- s (logit scale) and m (angular margin in
# radians) are the values from the original paper (Deng et al.), the
# standard starting point for face verification fine-tuning; not tuned
# further here since this is a first attempt at the new objective.
ARCFACE_S = 30.0
ARCFACE_M = 0.50

random.seed(SEED)
torch.manual_seed(SEED)

FGNET_FNAME_RE = re.compile(r"^(\d{3})[Aa](\d{2})", re.IGNORECASE)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_fgnet_identity(fname: str):
    m = FGNET_FNAME_RE.match(fname)
    if not m:
        return None
    return m.group(1)


def build_fgnet_samples(mtcnn: MTCNN):
    """Detect+crop the face in every FG-NET image once, cache to disk so
    re-runs skip the slow MTCNN pass. Returns list of (crop_path, identity)."""
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
        if (i + 1) % 200 == 0:
            print(f"  FG-NET: processed {i + 1}/{len(files)}")

    return samples


def build_calfw_samples():
    if not CALFW_METADATA_CSV.exists():
        print(f"WARNING: {CALFW_METADATA_CSV} not found -- skipping CALFW. "
              f"See this script's module docstring for the download command.")
        return []

    cache_dir = CROP_CACHE_DIR / "calfw"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with open(CALFW_METADATA_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"CALFW: found {len(rows)} labeled images in metadata.csv")

    samples = []
    for i, row in enumerate(rows):
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
        if (i + 1) % 2000 == 0:
            print(f"  CALFW: processed {i + 1}/{len(rows)}")

    return samples


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
        label = self.label_map[identity]
        return tensor, label


class ArcMarginProduct(nn.Module):
    """Additive angular margin head (ArcFace). Replaces the plain
    nn.Linear classification head both prior attempts used. logits =
    s * cos(theta + m) for the true class, s * cos(theta) for others,
    where theta is the angle between the (normalized) embedding and each
    class's (normalized) weight vector -- directly optimizing the cosine
    structure used at inference (det.compare_faces is cosine similarity).
    """

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
        # Easy-margin guard: only apply the margin where cos(theta) > 0
        # (theta < 90deg) -- avoids the non-monotonic region of cos(theta+m)
        # for very poorly-aligned pairs early in training, a standard
        # stabilization used in reference ArcFace implementations.
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

    fgnet_samples = build_fgnet_samples(mtcnn)
    calfw_samples = build_calfw_samples()

    samples = fgnet_samples + calfw_samples
    if not samples:
        print("ERROR: no training samples found from either dataset. Aborting.")
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
    n_fgnet_ids = sum(1 for i in identities if i.startswith("FGNET:"))
    n_calfw_ids = sum(1 for i in identities if i.startswith("CALFW:"))
    total_images = sum(len(v) for v in by_identity.values())
    print(f"\nCombined: {len(identities)} identities ({n_fgnet_ids} FG-NET, {n_calfw_ids} CALFW), "
          f"{total_images} usable images")

    train_samples, val_samples = [], []
    for ident, items in by_identity.items():
        random.shuffle(items)
        n_val = max(1, int(len(items) * VAL_FRACTION)) if len(items) > 3 else 0
        val_samples += items[:n_val]
        train_samples += items[n_val:]

    print(f"Train: {len(train_samples)}  Val: {len(val_samples)}")

    train_ds = FaceIdentityDataset(train_samples, label_map)
    val_ds = FaceIdentityDataset(val_samples, label_map)
    pin_memory = DEVICE.type == "cuda"
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, pin_memory=pin_memory)
    val_dl = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, pin_memory=pin_memory)

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
        for x, y in train_dl:
            x, y = x.to(DEVICE), y.to(DEVICE)
            optimizer.zero_grad()
            emb = embedder(x)  # already L2-normalized (facenet_pytorch's forward)
            logits = arc_head(emb, y)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * x.size(0)
            n += x.size(0)

        embedder.eval()
        arc_head.eval()
        correct = defaultdict(int)
        total = defaultdict(int)
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(DEVICE), y.to(DEVICE)
                emb = embedder(x)
                # At eval time, score against plain cosine similarity to
                # the class weight vectors (no margin) -- margin is a
                # training-time-only regularizer in the reference ArcFace
                # formulation, not part of inference-time scoring.
                cosine = F.linear(F.normalize(emb), F.normalize(arc_head.weight))
                preds = cosine.argmax(dim=1)
                is_fgnet = torch.tensor(
                    [identities[label].startswith("FGNET:") for label in y.cpu().tolist()],
                    device=DEVICE,
                )
                correct["all"] += (preds == y).sum().item()
                total["all"] += x.size(0)
                correct["fgnet"] += (preds == y)[is_fgnet].sum().item()
                total["fgnet"] += int(is_fgnet.sum().item())
                correct["calfw"] += (preds == y)[~is_fgnet].sum().item()
                total["calfw"] += int((~is_fgnet).sum().item())

        val_acc = correct["all"] / total["all"] if total["all"] else 0.0
        fgnet_acc = correct["fgnet"] / total["fgnet"] if total["fgnet"] else None
        calfw_acc = correct["calfw"] / total["calfw"] if total["calfw"] else None
        fmt = lambda a: f"{a:.3%}" if a is not None else "n/a"
        print(f"Epoch {epoch}/{EPOCHS}  train_loss={total_loss / n:.4f}  "
              f"val_acc={val_acc:.3%}  fgnet_acc={fmt(fgnet_acc)}  calfw_acc={fmt(calfw_acc)}")

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save(embedder.state_dict(), WEIGHTS_PATH)

    print(f"\nBest combined val identity-classification accuracy: {best_val_acc:.3%}")
    print(f"Saved fine-tuned embedder weights to {WEIGHTS_PATH}")
    print("\nThis is a CANDIDATE checkpoint, NOT yet wired into the app. Before "
          "wiring it into backend/app/ml/face_verifier.py, run:\n"
          f"    .venv-train/Scripts/python.exe scripts/evaluate_lfw_same_age.py --weights {WEIGHTS_PATH}\n"
          "and confirm same-age accuracy does not regress below the 95% bar before "
          "renaming/copying it to backend/app/ml/weights/face_embedder_finetuned.pth "
          "and re-running scripts/calibrate_face_threshold.py to recalibrate MATCH_THRESHOLD.")


if __name__ == "__main__":
    main()
