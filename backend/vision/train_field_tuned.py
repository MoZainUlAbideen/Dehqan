"""Field-tuned model: how much of the lab-to-field gap does a little field data close?

Usage (from backend/, after `uv run python -m vision.train_baseline`):
    uv run python -m vision.train_field_tuned
    uv run python -m vision.train_field_tuned --epochs 1 --lab-per-class 5   # smoke test

Split PlantDoc (field) 70/30 per class. Train on PlantVillage (lab) + the 70%. Test on the held-out 30%.
The baseline from train_baseline (lab only) is scored on the SAME held-out 30%, so the comparison is fair.
Then check how abstention changes accuracy for the field-tuned model.
Writes evals/field_tuned.json.

Caveat: PlantDoc is scraped from the web and may contain near-duplicate photos on both sides of the split,
so the field-tuned number can be optimistic.
"""

import argparse
import json

import torch

from vision.classes import SHARED_CLASSES
from vision.download_data import DATA_DIR
from vision.eval_abstention import analyse
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy
from vision.samples import plantdoc_samples, plantvillage_samples, stratified_split
from vision.train_baseline import EVALS_DIR, fit, make_model, predict_logits


def score(model, samples, train_labels) -> tuple[dict, list[float], list[bool]]:
    probs = predict_logits(model, samples).softmax(1)
    conf, pred = probs.max(1)
    y_true = [y for _, y in samples]
    y_pred = pred.tolist()
    res = {
        "n_images": len(samples),
        "accuracy": round(accuracy(y_true, y_pred), 4),
        "macro_f1": round(macro_f1(y_true, y_pred), 4),
        "majority_baseline_accuracy": round(majority_baseline_accuracy(train_labels, y_true), 4),
    }
    return res, conf.tolist(), [p == t for p, t in zip(y_pred, y_true)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab-per-class", type=int, default=150)
    ap.add_argument("--lab-test-per-class", type=int, default=60)
    ap.add_argument("--field-test-fraction", type=float, default=0.3)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed)

    lab_train = plantvillage_samples(DATA_DIR / "plantvillage", "train", args.lab_per_class, args.seed)
    lab_test = plantvillage_samples(DATA_DIR / "plantvillage", "test", args.lab_test_per_class, args.seed)
    field_train, field_test = stratified_split(
        plantdoc_samples(DATA_DIR / "plantdoc"), args.field_test_fraction, args.seed
    )
    if args.lab_per_class < 20:  # smoke test: shrink the field side too
        field_train, field_test = field_train[:40], field_test[:40]
    train = lab_train + field_train
    train_labels = [y for _, y in train]
    print(f"lab_train={len(lab_train)} field_train={len(field_train)} field_test={len(field_test)} "
          f"lab_test={len(lab_test)}", flush=True)

    # Old lab-only baseline on the same held-out field images.
    ckpt = torch.load(DATA_DIR / "models" / "baseline.pt", weights_only=True)
    base = make_model(len(SHARED_CLASSES))
    base.load_state_dict(ckpt["state_dict"])
    base_field, base_conf, base_ok = score(base, field_test, [y for _, y in lab_train])
    print(f"lab-only baseline on held-out field: {base_field}", flush=True)

    model = make_model(len(SHARED_CLASSES))
    fit(model, train, args.epochs, args.batch_size)

    tuned_field, conf, ok = score(model, field_test, train_labels)
    tuned_lab, _, _ = score(model, lab_test, train_labels)
    print(f"field-tuned on held-out field: {tuned_field}", flush=True)
    print(f"field-tuned on lab test:       {tuned_lab}", flush=True)

    results = {
        "model": "mobilenet_v3_small (ImageNet-pretrained, fully fine-tuned)",
        "train_data": "PlantVillage (lab) + 70% of PlantDoc (field); tested on held-out 30% of PlantDoc",
        "config": vars(args) | {"n_train": len(train)},
        "held_out_field_lab_only_baseline": base_field,
        "held_out_field_field_tuned": tuned_field,
        "lab_test_field_tuned": tuned_lab,
        "abstention_lab_only_baseline": analyse(base_conf, base_ok),
        "abstention_field_tuned": analyse(conf, ok),
    }
    if args.lab_per_class >= 20:  # smoke tests must not overwrite the real result
        EVALS_DIR.mkdir(exist_ok=True)
        (EVALS_DIR / "field_tuned.json").write_text(json.dumps(results, indent=2))
        torch.save({"state_dict": model.state_dict(), "classes": SHARED_CLASSES},
                   DATA_DIR / "models" / "field_tuned.pt")
    ft = results["abstention_field_tuned"]
    print("best coverage at 90% accuracy:", ft["best_coverage_at_90pct_accuracy"], flush=True)
    print("best coverage at 95% accuracy:", ft["best_coverage_at_95pct_accuracy"], flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
