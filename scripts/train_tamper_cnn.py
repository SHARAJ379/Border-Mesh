"""
Trains LightweightForensicCNN (backend/app/ml/tamper_model.py) on a splice-
detection dataset (see generate_tamper_training_data.py) and saves the
checkpoint that TamperDetectionService loads automatically at startup
(backend/app/services/tamper_service.py: WEIGHTS_PATH).

Run with:
    PYTHONPATH=backend venv/bin/python3 scripts/train_tamper_cnn.py

Takes a few minutes on CPU. Until this has been run at least once, the tamper
service safely ignores the CNN entirely and relies on its forensic heuristics
(ELA, edge discontinuity, portrait-seam, compression-mismatch) alone -- see
the `cnn_ready` gate in TamperDetectionService.__init__.

By default this trains on synthetic patches only (self-contained, no
external download). Two optional real datasets can be blended in via env
vars (see CASIA2_DIR / SIDTD_DIR below) -- neither is committed to this
repo, only the small trained checkpoint is:

  - CASIA v2.0: real photos, real human-made splices, but not documents.
  - SIDTD (http://datasets.cvc.uab.es/SIDTD/templates.zip): real ID
    document forgeries -- MIDV-2020 templates digitally tampered
    (crop-and-replace or inpainting) at the same resolution as their
    source, with the tampered field and its pixel bounding box given in
    the accompanying annotations (see load_sidtd_patches). This is
    document-domain data our own synthetic generator's narrow rectangular
    copy-paste signature can't provide on its own.

CAUTION -- SIDTD and this tiny 25k-parameter model: blending SIDTD in
measurably improved validation accuracy (up to ~82%) but, in four separate
training runs, produced a checkpoint that scored a confident (~1.0
probability) FALSE POSITIVE on the portrait region of every fresh genuine
demo specimen -- regardless of domain-sampling weights (tried 1/3-1/3-1/3
and 50/25/25), and independent of whether a real photo or the default
avatar was in the portrait box. SIDTD's own portrait-tampering examples are
narrow (~7 "photo" field-tampering images among ~1200 fakes) and specific
to MIDV-2020's face style; this model appears too small to absorb that
signal without overfitting to spurious correlations that then misfire on
our own generator's differently-styled portraits. The committed
`tamper_cnn.pth` is therefore NOT trained with SIDTD blended in --
CASIA-only, as before. The SIDTD loader and this 3-way domain-tracking
infrastructure are kept because they work correctly and are valuable for a
future attempt (a larger model, more own-domain data to counterbalance, or
per-domain model selection) -- just don't trust a SIDTD-blended checkpoint
without running the sanity check below AND manually inspecting per-region
CNN output (portrait/center/mrz), not just the aggregate score.
"""
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader, random_split, WeightedRandomSampler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.tamper_model import LightweightForensicCNN
from app.utils.synthetic_generator import SyntheticDocumentGenerator
from generate_tamper_training_data import generate_dataset, load_casia_patches, load_sidtd_patches

WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "backend" / "app" / "ml" / "weights" / "tamper_cnn.pth"

# The synthetic document generator falls back through a list of fonts
# (see SyntheticDocumentGenerator._load_font) -- macOS has Helvetica, but the
# production container (backend/Dockerfile) only installs `fonts-dejavu-core`.
# Training on whichever machine happens to run this script means the model
# can learn on Helvetica-rendered text glyphs while production only ever
# shows it DejaVu-rendered ones -- a real train/inference mismatch discovered
# after a genuine document scored differently on macOS vs. in Docker despite
# identical logical content. Force the container's actual font here so the
# checkpoint is calibrated against what it will actually see in production,
# regardless of what machine trains it. TAMPER_TRAIN_FONT can override this
# (e.g. to point at a local copy of DejaVuSans.ttf extracted from the image).
_PRODUCTION_FONT = os.environ.get("TAMPER_TRAIN_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if os.path.exists(_PRODUCTION_FONT):
    SyntheticDocumentGenerator._FONT_CANDIDATES = [_PRODUCTION_FONT]
    print(f"Training with production font: {_PRODUCTION_FONT}")
else:
    print(f"WARNING: production font not found at {_PRODUCTION_FONT} -- "
          f"falling back to this machine's default font candidates, which "
          f"will NOT match the Docker deployment's rendering.")

# Set the CASIA2_DIR env var to a local CASIA v2.0 extraction path (the
# directory containing Au/, Tp/, and "CASIA 2 Groundtruth/") to blend real
# splice data into training. Unset/absent means synthetic data only.
CASIA2_DIR = os.environ.get("CASIA2_DIR")

# Set the SIDTD_DIR env var to a local extraction of SIDTD's templates.zip
# (the directory containing Images/ and Annotations/) to blend in real
# document forgeries: MIDV-2020 ID templates that were printed, physically
# tampered, laminated, and re-photographed. Unlike CASIA (real splices, not
# documents) this is real document-domain data -- see
# generate_tamper_training_data.load_sidtd_patches for how to get it.
SIDTD_DIR = os.environ.get("SIDTD_DIR")

# Fraction of each real dataset withheld from training entirely (CASIA: by
# image; SIDTD: by whole document type) -- see the split="train"/"test" note
# at the CASIA2_DIR/SIDTD_DIR loading calls below for why.
HOLDOUT_FRACTION = 0.2

EPOCHS = 12
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
VAL_FRACTION = 0.2


def to_tensor_dataset(patches: np.ndarray, labels: np.ndarray) -> TensorDataset:
    x = torch.from_numpy(patches).permute(0, 3, 1, 2).float() / 255.0  # N,H,W,C -> N,C,H,W
    y = torch.from_numpy(labels).long()
    return TensorDataset(x, y)


def _domain_val_accuracy(model, val_ds, domain: np.ndarray, which: int) -> Optional[float]:
    """Validation accuracy restricted to one domain (0=our own synthetic
    generator, 1=CASIA, 2=SIDTD). Kept separate from the combined metric
    because a larger domain's sheer volume can swamp it -- a model can look
    accurate overall (or on a "document-domain" umbrella average) while
    silently regressing on the specific domain that matters. Blending in
    SIDTD's real document forgeries measurably raised the combined
    document-domain figure, but SIDTD's real-photograph statistics (camera
    noise, JPEG artifacts from phone capture) ended up outnumbering and
    diluting our own generator's clean-render statistics 2:1 within that
    combined figure -- silently regressing exactly the style our own demo
    scenarios actually produce, invisible unless measured on its own."""
    idxs = [i for i in val_ds.indices if domain[i] == which]
    if not idxs:
        return None
    xb = torch.stack([val_ds.dataset[i][0] for i in idxs])
    yb = torch.stack([val_ds.dataset[i][1] for i in idxs])
    model.eval()
    with torch.no_grad():
        preds = model(xb).argmax(dim=1)
    return (preds == yb).float().mean().item()


def main():
    print("Generating training data (synthetic splice patches)...")
    # n_docs raised from 80 -> 300 (patches_per_doc unchanged): with CASIA
    # blended in, the document domain was only ~1600 patches (a ~320-sample
    # validation slice), too small to measure doc-domain accuracy reliably --
    # bumping document-domain volume stabilizes both training signal and the
    # per-domain validation metric introduced above.
    patches, labels = generate_dataset(n_docs=300, patches_per_doc=8)
    print(f"  {len(patches)} patches: {int((labels==0).sum())} authentic, {int((labels==1).sum())} tampered")
    # DOMAIN 0 = our own synthetic generator -- what the demo scenarios
    # actually produce and the only thing directly, visibly testable right
    # now. DOMAIN 1 = CASIA's natural photographs (real splices, not
    # documents). DOMAIN 2 = SIDTD's real, photographed document forgeries.
    # Tracked separately rather than folding SIDTD into domain 0: SIDTD's
    # sheer volume would otherwise dominate a combined "document domain"
    # figure and hide a regression on our own generator's specific style
    # (see _domain_val_accuracy docstring for how this was actually caught).
    domain = np.zeros(len(patches), dtype=np.int64)

    # split="train" (with HOLDOUT_FRACTION reserved as split="test") keeps a
    # slice of each real dataset OUT of training entirely, so the dedicated
    # evaluate_tamper_on_casia.py/evaluate_tamper_on_sidtd.py scripts can
    # later measure genuinely unseen data -- see _split_files' docstring in
    # generate_tamper_training_data.py for why this matters: the prior CASIA
    # "held-out" evaluation used the exact same full image set (same default
    # seed) as training, so it wasn't actually held out.
    if CASIA2_DIR and Path(CASIA2_DIR).is_dir():
        print(f"\nBlending in real splice data from {CASIA2_DIR} "
              f"(using {1 - HOLDOUT_FRACTION:.0%} of images; {HOLDOUT_FRACTION:.0%} reserved for held-out eval) ...")
        casia_patches, casia_labels = load_casia_patches(CASIA2_DIR, split="train", holdout_fraction=HOLDOUT_FRACTION)
        print(f"  {len(casia_patches)} CASIA patches: "
              f"{int((casia_labels==0).sum())} authentic, {int((casia_labels==1).sum())} tampered")
        patches = np.concatenate([patches, casia_patches], axis=0)
        labels = np.concatenate([labels, casia_labels], axis=0)
        domain = np.concatenate([domain, np.ones(len(casia_patches), dtype=np.int64)])

    if SIDTD_DIR and Path(SIDTD_DIR).is_dir():
        print(f"\nBlending in real document forgeries from {SIDTD_DIR} "
              f"({HOLDOUT_FRACTION:.0%} of document TYPES reserved, entirely unseen, for held-out eval) ...")
        sidtd_patches, sidtd_labels = load_sidtd_patches(SIDTD_DIR, split="train", holdout_fraction=HOLDOUT_FRACTION)
        print(f"  {len(sidtd_patches)} SIDTD patches: "
              f"{int((sidtd_labels==0).sum())} authentic, {int((sidtd_labels==1).sum())} tampered")
        patches = np.concatenate([patches, sidtd_patches], axis=0)
        labels = np.concatenate([labels, sidtd_labels], axis=0)
        domain = np.concatenate([domain, np.full(len(sidtd_patches), 2, dtype=np.int64)])

    print(f"\nCombined total: {len(patches)} patches "
          f"({int((domain==0).sum())} own-synthetic, {int((domain==1).sum())} CASIA, "
          f"{int((domain==2).sum())} SIDTD)")

    dataset = to_tensor_dataset(patches, labels)
    n_val = int(len(dataset) * VAL_FRACTION)
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val], generator=torch.Generator().manual_seed(42))

    # Each domain has wildly different volume (CASIA and SIDTD both dwarf our
    # own generator's patch count). A plain shuffled loader would let the
    # largest domain dominate every batch -- exactly what caused a genuine
    # specimen to be confidently misflagged as tampered the first time
    # (CASIA drowning out our own documents entirely). Giving all three
    # domains EQUAL per-epoch probability fixed that but overcorrected:
    # CASIA and SIDTD are both real *photographs* (camera noise, JPEG
    # artifacts) while our own generator produces clean, noise-free digital
    # renders -- two photographic domains at 2/3 combined share pulled the
    # tiny 25k-param model's learned features toward photographic statistics
    # that don't transfer to our own render style, producing a maximally
    # confident (~1.0) false positive on every genuine demo specimen despite
    # a deceptively decent held-out validation number (see epoch log this
    # replaced). Our own domain keeps majority share (50%) -- it's what the
    # visible demo scenarios actually run against and the only one directly,
    # visibly testable right now -- while CASIA and SIDTD still each get
    # meaningful, non-trivial exposure (25% apiece) rather than being
    # dropped, so their splice statistics still contribute.
    train_domain = domain[train_ds.indices]
    domain_counts = np.bincount(train_domain, minlength=3)
    domain_share = np.array([0.50, 0.25, 0.25])  # own-synthetic, CASIA, SIDTD
    per_sample_weight = domain_share[train_domain] / domain_counts[train_domain]
    sampler = WeightedRandomSampler(per_sample_weight, num_samples=n_train, replacement=True)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, sampler=sampler)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    model = LightweightForensicCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    print(f"\nTraining for {EPOCHS} epochs on {n_train} patches ({n_val} held out for validation)...")
    best_val_acc = -1.0
    best_state = None
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            out = model(xb)
            loss = criterion(out, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * xb.size(0)
        train_loss = total_loss / n_train

        model.eval()
        correct = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                preds = model(xb).argmax(dim=1)
                correct += (preds == yb).sum().item()
        val_acc = correct / max(1, n_val)
        own_acc = _domain_val_accuracy(model, val_ds, domain, which=0)
        casia_acc = _domain_val_accuracy(model, val_ds, domain, which=1)
        sidtd_acc = _domain_val_accuracy(model, val_ds, domain, which=2)
        fmt = lambda a: f"{a:.3%}" if a is not None else "n/a"

        marker = ""
        # Model selection is driven by accuracy on OUR OWN generator's domain
        # specifically (falling back to the combined metric if that domain
        # has no validation data): it's the only domain that's directly,
        # visibly testable right now (the built-in demo scenarios), and
        # SIDTD/CASIA already showed that a broader "document domain" or
        # combined figure can look better while this specific one regresses.
        selection_metric = own_acc if own_acc is not None else val_acc
        if selection_metric > best_val_acc:
            best_val_acc = selection_metric
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            marker = "  (best so far)"
        print(f"  epoch {epoch:2d}/{EPOCHS}  train_loss={train_loss:.4f}  val_acc={val_acc:.3%}  "
              f"own_synthetic_acc={fmt(own_acc)}  casia_acc={fmt(casia_acc)}  sidtd_acc={fmt(sidtd_acc)}{marker}")

    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, WEIGHTS_PATH)
    print(f"\nBest own-synthetic-domain validation accuracy: {best_val_acc:.3%}")
    print(f"Saved best-epoch checkpoint to {WEIGHTS_PATH}")
    print("Restart the backend (or the docker container) to pick it up --")
    print("TamperDetectionService loads it automatically on startup.")

    _sanity_check_against_fresh_specimens()


def _sanity_check_against_fresh_specimens():
    """
    The held-out validation split is drawn from the SAME pool of patches used
    for training, just excluded from gradient updates -- it can look good
    (a real run scored 79.7% own-synthetic accuracy) while the saved
    checkpoint is still a confident (~1.0 probability) false positive on
    entirely fresh genuine documents, because the model memorized training
    patches rather than generalizing. This runs the checkpoint through the
    actual production code path (TamperDetectionService.analyze, same
    portrait/center/mrz regions, same font) against freshly generated
    documents that were never in the training set at all, as a direct,
    honest check before anyone trusts this checkpoint.
    """
    import tempfile
    from app.services.tamper_service import TamperDetectionService

    print("\nSanity-checking the saved checkpoint against 5 FRESH genuine specimens "
          "(never seen during training)...")
    service = TamperDetectionService()
    risks = []
    for i in range(5):
        out_path = tempfile.mktemp(suffix=".jpg")
        SyntheticDocumentGenerator.generate_document(
            out_path=out_path, mode="genuine", doc_number=f"S{9000000 + i}"
        )
        result = service.analyze(out_path, case_id=f"sanity-{i}")
        risks.append(result["tamper_risk"])
        os.remove(out_path)
    mean_risk = sum(risks) / len(risks)
    print(f"  tamper_risk on fresh genuine specimens: {risks} (mean {mean_risk:.2f})")
    if mean_risk >= 0.60:
        print(f"  WARNING: mean risk {mean_risk:.2f} is uncomfortably close to or above "
              f"the 0.70 HIGH threshold despite a good validation accuracy figure. "
              f"Do NOT deploy this checkpoint without investigating further -- "
              f"the validation split is not a reliable enough proxy on its own.")
    else:
        print(f"  OK: comfortably below the 0.70 HIGH threshold.")


if __name__ == "__main__":
    main()
