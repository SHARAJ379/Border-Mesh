"""
Evaluates the CURRENTLY COMMITTED tamper_cnn.pth checkpoint (trained on our
own synthetic splice generator + CASIA v2.0 only -- see scripts/train_tamper_cnn.py,
SIDTD_DIR unset for the committed checkpoint) on SIDTD: real, digitally
tampered ID *documents* (crop-and-replace / inpainting on MIDV-2020-style
templates), via scripts/generate_tamper_training_data.load_sidtd_patches.

This is a second, independent held-out/out-of-distribution evaluation,
distinct from CASIA: CASIA is real photo splices but not documents; SIDTD is
real document forgeries the checkpoint has never been trained on either
(see KNOWN_LIMITATIONS.md -- a SIDTD-blended retrain was tried and reverted
after it false-positived on the project's own genuine specimens; the
committed checkpoint itself was never changed and has never been evaluated
against SIDTD before now).

Get the data first (needs the extracted `templates/` directory):
    curl -o data/SIDTD/templates.zip http://datasets.cvc.uab.es/SIDTD/templates.zip
    unzip data/SIDTD/templates.zip -d data/SIDTD

Run with:
    .venv-train/Scripts/python.exe scripts/evaluate_tamper_on_sidtd.py [sidtd_templates_root] [--split]

Pass --split test to evaluate only the document TYPES held out of training by
scripts/train_tamper_cnn.py (split="train" there, same seed and
holdout_fraction) -- entire template designs the checkpoint never saw in any
form. Omitting --split evaluates every document type, which includes types
used in training for any checkpoint trained with SIDTD_DIR set.
"""
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from app.ml.tamper_model import LightweightForensicCNN
from generate_tamper_training_data import load_sidtd_patches

WEIGHTS_PATH = PROJECT_ROOT / "backend" / "app" / "ml" / "weights" / "tamper_cnn.pth"


def find_sidtd_root(explicit: str = None) -> Path:
    if explicit:
        return Path(explicit)
    candidate = PROJECT_ROOT / "data" / "SIDTD" / "templates"
    if (candidate / "Images" / "reals").is_dir():
        return candidate
    for sub in (PROJECT_ROOT / "data" / "SIDTD").rglob("reals"):
        if sub.parent.name == "Images":
            return sub.parent.parent
    return candidate


def main():
    raw_args = sys.argv[1:]
    split = "test" if "--split" in raw_args else None
    positional = [a for a in raw_args if not a.startswith("--")]
    root_arg = positional[0] if positional else None
    sidtd_root = find_sidtd_root(root_arg)
    print(f"SIDTD templates root: {sidtd_root}  (split={split!r})")
    if not (sidtd_root / "Images" / "reals").is_dir():
        print(f"ERROR: {sidtd_root}/Images/reals not found. Extract templates.zip and/or pass the correct root as an argument.")
        sys.exit(1)

    if not WEIGHTS_PATH.exists():
        print(f"ERROR: no trained checkpoint at {WEIGHTS_PATH}. Run scripts/train_tamper_cnn.py first.")
        sys.exit(1)

    device = torch.device("cpu")  # matches TamperDetectionService's own inference device
    model = LightweightForensicCNN().to(device)
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=device))
    model.eval()

    print(f"Loading SIDTD patches (4 patches/real, 4 patches/fake-field + 2 elsewhere/fake, split={split!r})...")
    patches, labels = load_sidtd_patches(str(sidtd_root), split=split, holdout_fraction=0.2)
    print(f"  {len(patches)} patches: {int((labels == 0).sum())} authentic, {int((labels == 1).sum())} tampered")

    x = torch.from_numpy(patches).permute(0, 3, 1, 2).float() / 255.0
    y = labels

    preds = []
    probs_tampered = []
    batch_size = 256
    with torch.no_grad():
        for i in range(0, len(x), batch_size):
            batch = x[i:i + batch_size].to(device)
            out = model(batch)
            probs = torch.softmax(out, dim=1).numpy()
            probs_tampered.extend(probs[:, 1].tolist())
            preds.extend(probs.argmax(axis=1).tolist())

    preds = np.array(preds)
    probs_tampered = np.array(probs_tampered)

    tp = int(((preds == 1) & (y == 1)).sum())
    fp = int(((preds == 1) & (y == 0)).sum())
    tn = int(((preds == 0) & (y == 0)).sum())
    fn = int(((preds == 0) & (y == 1)).sum())

    accuracy = (tp + tn) / len(y)
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")
    far = fp / (fp + tn) if (fp + tn) else float("nan")  # authentic misclassified as tampered
    frr = fn / (fn + tp) if (fn + tp) else float("nan")  # tampered misclassified as authentic

    print(f"\n=== tamper_cnn.pth on SIDTD (out-of-distribution: real document forgeries, never trained on) ===")
    print(f"n = {len(y)}  (authentic={int((y==0).sum())}, tampered={int((y==1).sum())})")
    print(f"Accuracy:  {accuracy:.3%}")
    print(f"Precision: {precision:.3%}  (of patches flagged tampered, how many really were)")
    print(f"Recall:    {recall:.3%}  (of truly tampered patches, how many were caught)")
    print(f"F1:        {f1:.3%}")
    print(f"Confusion: TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    print(f"False-accept rate (authentic misclassified as tampered): {far:.3%}")
    print(f"False-reject rate (tampered misclassified as authentic): {frr:.3%}")
    print(f"Mean predicted tampered-probability -- authentic patches: {probs_tampered[y==0].mean():.3f}")
    print(f"Mean predicted tampered-probability -- tampered patches:  {probs_tampered[y==1].mean():.3f}")


if __name__ == "__main__":
    main()
