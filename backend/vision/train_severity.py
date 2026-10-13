"""Severity grading: a classical colour baseline vs a small learned segmentation model.

Usage (from backend/):
    uv run python -m vision.train_severity
    uv run python -m vision.train_severity --epochs 1 --limit 12     # smoke test

Data: PDSNet (240 field photos: apple cedar rust, soybean bacterial blight, wheat stripe rust) with
pixel masks (0 background, 1 healthy leaf, 2 spots). Split 2/3 train, 1/3 test within each crop.
Ground truth severity = spots / (spots + healthy leaf) from the mask.

Compared on the SAME held-out photos:
  naive baseline  - always predict the training-set mean severity
  colour baseline - HSV thresholds, no learning (severity.estimate_severity_color)
  learned model   - LR-ASPP MobileNetV3 segmentation net, ImageNet backbone, fine-tuned here
Metrics: severity MAE in percentage points, Pearson r, grade accuracy (mild/moderate/severe), and
lesion IoU for the learned model. PDSNet is CC-BY-NC-4.0 (non-commercial).
Writes evals/severity.json.
"""

import argparse
import json
import time

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from torchvision.models.segmentation import lraspp_mobilenet_v3_large

from vision.download_data import DATA_DIR
from vision.severity import (GRADES, estimate_severity_color, grade, grouped_split,
                             severity_from_mask)
from vision.train_baseline import EVALS_DIR

PARQUET = DATA_DIR / "raw" / "pdsnet.parquet"
SIZE = 384
NORM = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def load_rows(limit: int | None):
    from datasets import load_dataset

    ds = load_dataset("parquet", data_files=str(PARQUET), split="train")
    rows = [(r["image"].convert("RGB"), np.array(r["mask"]), r["crop"]) for r in ds]
    return rows[:limit] if limit else rows


def resize_pair(image: Image.Image, mask: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    img = image.resize((SIZE, SIZE), Image.BILINEAR)
    m = np.array(Image.fromarray(mask).resize((SIZE, SIZE), Image.NEAREST))
    return img, m


class SegDataset(Dataset):
    def __init__(self, pairs, train: bool):
        self.pairs, self.train = pairs, train

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        img, mask = self.pairs[i]
        x = transforms.functional.to_tensor(img)
        y = torch.from_numpy(mask.astype(np.int64))
        if self.train and torch.rand(1) < 0.5:
            x, y = x.flip(-1), y.flip(-1)
        if self.train and torch.rand(1) < 0.5:
            x, y = x.flip(-2), y.flip(-2)
        return NORM(x), y


def pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def summarise(true_sev: list[float], pred_sev: list[float]) -> dict:
    t, p = np.array(true_sev), np.array(pred_sev)
    r = pearson(true_sev, pred_sev)
    return {
        "severity_mae_points": round(float(np.abs(t - p).mean() * 100), 2),
        "pearson_r": None if r is None else round(r, 3),
        "grade_accuracy": round(float(np.mean([grade(a) == grade(b) for a, b in zip(t, p)])), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="use only the first N photos (smoke test)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed)

    rows = load_rows(args.limit)
    crops = [r[2] for r in rows]
    train_idx, test_idx = grouped_split(crops, 1 / 3, args.seed)
    pairs = [resize_pair(img, m) for img, m, _ in rows]
    train_pairs = [pairs[i] for i in train_idx]
    test_pairs = [pairs[i] for i in test_idx]
    print(f"train={len(train_pairs)} test={len(test_pairs)}", flush=True)

    # Ground truth severity of each test photo, from its resized mask.
    keep = [i for i, (_, m) in enumerate(test_pairs) if severity_from_mask(m) is not None]
    test_pairs = [test_pairs[i] for i in keep]
    test_crops = [crops[test_idx[i]] for i in keep]
    true_sev = [severity_from_mask(m) for _, m in test_pairs]

    train_sev = [s for _, m in train_pairs if (s := severity_from_mask(m)) is not None]
    mean_sev = float(np.mean(train_sev))
    naive = summarise(true_sev, [mean_sev] * len(true_sev))
    majority_grade = max(GRADES, key=lambda g: sum(grade(s) == g for s in train_sev))
    naive["grade_accuracy"] = round(float(np.mean([grade(s) == majority_grade for s in true_sev])), 4)

    colour_pred = [estimate_severity_color(img) for img, _ in test_pairs]
    colour_found = [i for i, s in enumerate(colour_pred) if s is not None]
    colour = summarise([true_sev[i] for i in colour_found], [colour_pred[i] for i in colour_found])
    colour["n_no_leaf_found"] = len(colour_pred) - len(colour_found)
    print("naive :", naive, flush=True)
    print("colour:", colour, flush=True)

    model = lraspp_mobilenet_v3_large(
        weights=None, weights_backbone=models.MobileNet_V3_Large_Weights.DEFAULT, num_classes=3
    )
    weights = torch.tensor([0.5, 1.0, 2.0])  # spots are rare, so upweight them
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loader = DataLoader(SegDataset(train_pairs, True), batch_size=args.batch_size, shuffle=True)
    start = time.time()
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for x, y in loader:
            opt.zero_grad()
            loss = loss_fn(model(x)["out"], y)
            loss.backward()
            opt.step()
            total += loss.item() * len(y)
        print(f"epoch {epoch + 1}/{args.epochs} loss={total / len(train_pairs):.4f} ({time.time() - start:.0f}s)",
              flush=True)

    model.eval()
    pred_masks = []
    with torch.no_grad():
        for x, _ in DataLoader(SegDataset(test_pairs, False), batch_size=8):
            pred_masks += model(x)["out"].argmax(1).numpy().astype(np.uint8).tolist()
    pred_masks = [np.array(m) for m in pred_masks]
    learned_sev_all = [severity_from_mask(m) for m in pred_masks]
    found = [i for i, s in enumerate(learned_sev_all) if s is not None]
    learned = summarise([true_sev[i] for i in found], [learned_sev_all[i] for i in found])
    learned["n_no_leaf_found"] = len(learned_sev_all) - len(found)
    inter = sum(int(((p == 2) & (g == 2)).sum()) for p, (_, g) in zip(pred_masks, test_pairs))
    union = sum(int(((p == 2) | (g == 2)).sum()) for p, (_, g) in zip(pred_masks, test_pairs))
    learned["lesion_iou"] = round(inter / union, 4) if union else None
    print("learned:", learned, flush=True)

    by_crop = {}
    for crop in sorted(set(test_crops)):
        ii = [i for i in found if test_crops[i] == crop]
        by_crop[crop] = {"n": len(ii), **summarise([true_sev[i] for i in ii], [learned_sev_all[i] for i in ii])}
    results = {
        "data": "PDSNet field photos (apple cedar rust, soybean bacterial blight, wheat stripe rust)",
        "grades": "mild <10%, moderate 10-30%, severe >=30% (our cut-offs)",
        "config": vars(args) | {"n_train": len(train_pairs), "n_test": len(test_pairs), "image_size": SIZE},
        "naive_mean_baseline": naive,
        "colour_threshold_baseline": colour,
        "learned_segmentation": learned,
        "learned_by_crop": by_crop,
    }
    print(json.dumps(by_crop, indent=2), flush=True)
    if not args.limit:  # smoke tests must not overwrite the real result
        EVALS_DIR.mkdir(exist_ok=True)
        (EVALS_DIR / "severity.json").write_text(json.dumps(results, indent=2))
        (DATA_DIR / "models").mkdir(exist_ok=True)
        torch.save(model.state_dict(), DATA_DIR / "models" / "severity.pt")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
