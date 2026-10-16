"""Wheat disease classifier: train on JIC field photos (UK), test on held-out JIC AND on a different source (China).

Usage (from backend/):
    uv run python -m vision.train_wheat
    uv run python -m vision.train_wheat --epochs 1 --max-per-class 20   # quick smoke test

JIC (data/wheat_jic/photos, flat files named like BrownRust123.png): brown rust, healthy, mildew, septoria, yellow rust.
Second source (data/wheat_xiaomai, made by download_wheat_xiaomai): box crops of mildew, brown rust, yellow rust,
healthy, from another group, other cameras, other country. It has no septoria, so we report:
  strict       - the model picks among all 5 classes
  shared_only  - the model may only choose among the 4 shared classes (the best case)

Caveat we cannot remove: the JIC file numbers do not tell us which photos came from the same plant or day, so the
random held-out split can be flattering (near-duplicates). The cross-source number is the one to trust.

Writes evals/wheat_cross_source.json. Checkpoint goes in data/models/ (gitignored).
"""

import argparse
import json
import random

import torch

from vision.download_data import DATA_DIR, IMAGE_EXTS
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy, per_class_recall
from vision.samples import Sample, folder_samples, stratified_split
from vision.train_baseline import EVALS_DIR, fit, make_model, predict_logits

WHEAT_CLASSES = ["brown_rust", "healthy", "mildew", "septoria", "yellow_rust"]
JIC_PREFIX = {"BrownRust": "brown_rust", "Healthy": "healthy", "Mildew": "mildew", "Septoria": "septoria", "YellowRust": "yellow_rust"}
SHARED = ["brown_rust", "healthy", "mildew", "yellow_rust"]
SHARED_IDX = [WHEAT_CLASSES.index(c) for c in SHARED]


def jic_samples() -> list[Sample]:
    root = DATA_DIR / "wheat_jic" / "photos"
    out = []
    for f in sorted(root.iterdir()):
        if f.suffix.lower() in IMAGE_EXTS:
            name = f.stem.rstrip("0123456789")
            out.append((f, WHEAT_CLASSES.index(JIC_PREFIX[name])))
    return out


def cross_samples() -> list[Sample]:
    return folder_samples(DATA_DIR / "wheat_xiaomai", WHEAT_CLASSES)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--test-fraction", type=float, default=0.2)
    ap.add_argument("--max-per-class", type=int, default=None, help="cap images per class (smoke tests)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed)

    train, test = stratified_split(jic_samples(), args.test_fraction, args.seed)
    cross = cross_samples()
    if args.max_per_class:
        rng = random.Random(args.seed)
        cap = lambda s: [x for c in range(len(WHEAT_CLASSES)) for x in rng.sample(
            [t for t in s if t[1] == c], min(args.max_per_class, sum(t[1] == c for t in s)))]
        train, test, cross = cap(train), cap(test), cap(cross)
    train_labels = [y for _, y in train]
    print(f"train={len(train)} test_same_source={len(test)} test_cross_source={len(cross)}", flush=True)

    model = make_model(len(WHEAT_CLASSES))
    fit(model, train, args.epochs, args.batch_size)

    y_test = [y for _, y in test]
    pred_test = predict_logits(model, test).argmax(1).tolist()
    same = {
        "n_images": len(test),
        "accuracy": round(accuracy(y_test, pred_test), 4),
        "macro_f1": round(macro_f1(y_test, pred_test), 4),
        "majority_baseline_accuracy": round(majority_baseline_accuracy(train_labels, y_test), 4),
        "per_class_recall": per_class_recall(y_test, pred_test, WHEAT_CLASSES),
    }

    y_cross = [y for _, y in cross]
    logits = predict_logits(model, cross)
    pred_strict = logits.argmax(1).tolist()
    pred_shared = [SHARED_IDX[i] for i in logits[:, SHARED_IDX].argmax(1).tolist()]
    cross_res = {
        "n_images": len(cross),
        "images_per_class": {c: y_cross.count(WHEAT_CLASSES.index(c)) for c in SHARED},
        "classes_covered": SHARED,
        "strict_5way": {"accuracy": round(accuracy(y_cross, pred_strict), 4), "macro_f1": round(macro_f1(y_cross, pred_strict), 4)},
        "shared_only_4way": {
            "accuracy": round(accuracy(y_cross, pred_shared), 4),
            "macro_f1": round(macro_f1(y_cross, pred_shared), 4),
            "chance_accuracy": 0.25,
            "majority_baseline_accuracy": round(max(y_cross.count(i) for i in SHARED_IDX) / len(y_cross), 4),
        },
        "per_class_recall_shared_only": per_class_recall(y_cross, pred_shared, WHEAT_CLASSES),
    }

    results = {
        "model": "mobilenet_v3_small (ImageNet-pretrained, fully fine-tuned)",
        "train_data": "JIC wheat photos (Long et al. 2023, Zenodo 7573133), stratified split",
        "cross_source_data": "Ma et al. 2024 wheat detection set (Zenodo 15621359), test-split box crops",
        "config": vars(args) | {"n_train": len(train)},
        "same_source_test": same,
        "cross_source_test": cross_res,
    }
    print(json.dumps(results, indent=2), flush=True)

    if not args.max_per_class:
        EVALS_DIR.mkdir(exist_ok=True)
        (EVALS_DIR / "wheat_cross_source.json").write_text(json.dumps(results, indent=2))
        (DATA_DIR / "models").mkdir(exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "classes": WHEAT_CLASSES}, DATA_DIR / "models" / "wheat.pt")


if __name__ == "__main__":
    main()
