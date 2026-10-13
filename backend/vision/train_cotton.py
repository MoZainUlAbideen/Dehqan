"""Cotton disease classifier: train on Bangladesh set A, test on held-out A and on a DIFFERENT source B.

Usage (from backend/):
    uv run python -m vision.train_cotton
    uv run python -m vision.train_cotton --epochs 1 --max-per-class 20   # quick smoke test

Set A (cotton_bd) has 7 classes. Set B (cotton_alt) comes from another group and camera setup and shares only
two classes with A: Bacterial Blight and Healthy. So the cross-source test only covers those two classes.
We report it two ways:
  strict       - the model must pick the right class out of all 7 (hard, honest)
  shared_only  - the model may only choose between the 2 shared classes (easier; shows the best case)

Writes evals/cotton_cross_source.json. Checkpoint goes in data/models/ (gitignored).
"""

import argparse
import json
import random

import torch

from vision.download_data import DATA_DIR
from vision.download_field_crops import FIELD_DIR
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy, per_class_recall
from vision.samples import Sample, folder_samples, stratified_split
from vision.train_baseline import EVALS_DIR, fit, make_model, predict_logits

# Set A classes, in a fixed order (label index = position).
BD_CLASSES = [
    "Bacterial Blight", "Curl Virus", "Healthy Leaf", "Herbicide Growth Damage",
    "Leaf Hopper Jassids", "Leaf Redding", "Leaf Variegation",
]
# Set B folder name -> the matching set A class name.
ALT_TO_BD = {"Bacterial_Blight": "Bacterial Blight", "Healthy_Leaf": "Healthy Leaf"}
SHARED_IDX = [BD_CLASSES.index(v) for v in ALT_TO_BD.values()]


def cross_source_samples() -> list[Sample]:
    """Set B images of the two shared classes, labelled with set A's class index."""
    alt_names = list(ALT_TO_BD)
    samples = folder_samples(FIELD_DIR / "cotton_alt", alt_names)
    return [(p, BD_CLASSES.index(ALT_TO_BD[alt_names[i]])) for p, i in samples]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--test-fraction", type=float, default=0.2)
    ap.add_argument("--max-per-class", type=int, default=None, help="cap images per class (smoke tests)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed)

    all_a = folder_samples(FIELD_DIR / "cotton_bd", BD_CLASSES)
    train, test = stratified_split(all_a, args.test_fraction, args.seed)
    cross = cross_source_samples()
    if args.max_per_class:
        rng = random.Random(args.seed)
        cap = lambda s: [x for c in range(len(BD_CLASSES)) for x in rng.sample(
            [t for t in s if t[1] == c], min(args.max_per_class, sum(t[1] == c for t in s)))]
        train, test, cross = cap(train), cap(test), cap(cross)
    train_labels = [y for _, y in train]
    print(f"train={len(train)} test_same_source={len(test)} test_cross_source={len(cross)}", flush=True)

    model = make_model(len(BD_CLASSES))
    fit(model, train, args.epochs, args.batch_size)

    y_test = [y for _, y in test]
    pred_test = predict_logits(model, test).argmax(1).tolist()
    same = {
        "n_images": len(test),
        "accuracy": round(accuracy(y_test, pred_test), 4),
        "macro_f1": round(macro_f1(y_test, pred_test), 4),
        "majority_baseline_accuracy": round(majority_baseline_accuracy(train_labels, y_test), 4),
        "per_class_recall": per_class_recall(y_test, pred_test, BD_CLASSES),
    }

    y_cross = [y for _, y in cross]
    logits = predict_logits(model, cross)
    pred_strict = logits.argmax(1).tolist()
    pred_shared = [SHARED_IDX[i] for i in logits[:, SHARED_IDX].argmax(1).tolist()]
    cross_res = {
        "n_images": len(cross),
        "classes_covered": list(ALT_TO_BD.values()),
        "strict_7way": {
            "accuracy": round(accuracy(y_cross, pred_strict), 4),
            "macro_f1": round(macro_f1(y_cross, pred_strict), 4),
        },
        "shared_only_2way": {
            "accuracy": round(accuracy(y_cross, pred_shared), 4),
            "macro_f1": round(macro_f1(y_cross, pred_shared), 4),
            "chance_accuracy": 0.5,
            "majority_baseline_accuracy": round(
                max(y_cross.count(i) for i in SHARED_IDX) / len(y_cross), 4),
        },
        "per_class_recall_shared_only": per_class_recall(y_cross, pred_shared, BD_CLASSES),
    }

    results = {
        "model": "mobilenet_v3_small (ImageNet-pretrained, fully fine-tuned)",
        "train_data": "cotton_bd (Bangladesh), stratified split",
        "config": vars(args) | {"n_train": len(train)},
        "same_source_test": same,
        "cross_source_test": cross_res,
    }
    print(json.dumps(results, indent=2), flush=True)

    if not args.max_per_class:  # smoke tests must not overwrite the real result
        EVALS_DIR.mkdir(exist_ok=True)
        (EVALS_DIR / "cotton_cross_source.json").write_text(json.dumps(results, indent=2))
        (DATA_DIR / "models").mkdir(exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "classes": BD_CLASSES},
                   DATA_DIR / "models" / "cotton.pt")


if __name__ == "__main__":
    main()
