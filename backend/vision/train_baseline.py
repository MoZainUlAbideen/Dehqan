"""Baseline: fine-tune MobileNetV3-Small on PlantVillage (lab), test on lab AND PlantDoc (field).

Usage (from backend/):
    uv run python -m vision.train_baseline
    uv run python -m vision.train_baseline --per-class 100 --epochs 2   # quicker

Writes evals/baseline_lab_vs_field.json. The checkpoint goes in data/models/ (gitignored).
"""

import argparse
import json
import time
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from vision.classes import SHARED_CLASSES
from vision.download_data import DATA_DIR
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy
from vision.samples import Sample, plantdoc_samples, plantvillage_samples

EVALS_DIR = DATA_DIR.parent / "evals"
IMG_SIZE = 224
NORM = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
TRAIN_TF = transforms.Compose([
    transforms.RandomResizedCrop(IMG_SIZE, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    NORM,
])
EVAL_TF = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    NORM,
])


class ImageListDataset(Dataset):
    def __init__(self, samples: list[Sample], tf):
        self.samples, self.tf = samples, tf

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        path, label = self.samples[i]
        return self.tf(Image.open(path).convert("RGB")), label


def make_model(n_classes: int) -> nn.Module:
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, n_classes)
    return model


def predict(model: nn.Module, samples: list[Sample], batch_size: int = 64) -> list[int]:
    model.eval()
    loader = DataLoader(ImageListDataset(samples, EVAL_TF), batch_size=batch_size, num_workers=0)
    preds: list[int] = []
    with torch.no_grad():
        for x, _ in loader:
            preds += model(x).argmax(1).tolist()
    return preds


def evaluate(name: str, model: nn.Module, samples: list[Sample], train_labels: list[int]) -> dict:
    y_true = [label for _, label in samples]
    y_pred = predict(model, samples)
    result = {
        "n_images": len(samples),
        "accuracy": round(accuracy(y_true, y_pred), 4),
        "macro_f1": round(macro_f1(y_true, y_pred), 4),
        "majority_baseline_accuracy": round(majority_baseline_accuracy(train_labels, y_true), 4),
    }
    print(f"{name}: {result}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=150, help="train images per class")
    ap.add_argument("--test-per-class", type=int, default=60, help="lab test images per class")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    train = plantvillage_samples(DATA_DIR / "plantvillage", "train", args.per_class, args.seed)
    lab_test = plantvillage_samples(DATA_DIR / "plantvillage", "test", args.test_per_class, args.seed)
    field_test = plantdoc_samples(DATA_DIR / "plantdoc")
    train_labels = [label for _, label in train]
    print(f"train={len(train)} lab_test={len(lab_test)} field_test={len(field_test)} classes={len(SHARED_CLASSES)}")

    model = make_model(len(SHARED_CLASSES))
    loader = DataLoader(
        ImageListDataset(train, TRAIN_TF), batch_size=args.batch_size, shuffle=True, num_workers=0
    )
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    start = time.time()
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for x, y in loader:
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            total += loss.item() * len(y)
        print(f"epoch {epoch + 1}/{args.epochs} loss={total / len(train):.4f} ({time.time() - start:.0f}s)")

    results = {
        "model": "mobilenet_v3_small (ImageNet-pretrained, fully fine-tuned)",
        "train_data": "PlantVillage (lab), shared classes only",
        "config": vars(args) | {"n_train": len(train), "n_classes": len(SHARED_CLASSES)},
        "lab_test": evaluate("lab_test  (PlantVillage held-out)", model, lab_test, train_labels),
        "field_test": evaluate("field_test (PlantDoc)", model, field_test, train_labels),
    }
    results["lab_to_field_accuracy_drop"] = round(
        results["lab_test"]["accuracy"] - results["field_test"]["accuracy"], 4
    )
    print(f"lab -> field accuracy drop: {results['lab_to_field_accuracy_drop']}")

    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "baseline_lab_vs_field.json").write_text(json.dumps(results, indent=2))
    model_dir = DATA_DIR / "models"
    model_dir.mkdir(exist_ok=True)
    torch.save(
        {"state_dict": model.state_dict(), "classes": SHARED_CLASSES}, model_dir / "baseline.pt"
    )


if __name__ == "__main__":
    main()
