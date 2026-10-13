"""Evaluate the CLIP "is this a crop photo?" gate against a simple baseline.

Usage (from backend/, after download_data, download_field_crops, download_negatives, train_field_tuned):
    uv run python -m vision.eval_crop_gate

Positives: 100 random leaf photos from each of 5 sources (lab + field, several crops).
Negatives: everyday-object photos (data/negatives/). NOT included: soil, weeds, fruit, hands.
Baseline : reject a photo when the disease classifier's top softmax probability is low.
           (A tempting shortcut that needs no extra model; we check whether it works.)
Writes evals/crop_gate.json.
"""

import json
import random
from pathlib import Path

import torch

from vision.classes import SHARED_CLASSES
from vision.crop_gate import DEFAULT_THRESHOLD, CropGate
from vision.download_data import DATA_DIR, IMAGE_EXTS
from vision.download_field_crops import FIELD_DIR
from vision.download_negatives import NEGATIVES_DIR
from vision.metrics import auroc, tpr_at_max_fpr
from vision.train_baseline import EVALS_DIR, make_model, predict_logits

N_POS_PER_SOURCE = 100
POSITIVE_SOURCES = {
    "plantvillage_lab": DATA_DIR / "plantvillage",
    "plantdoc_field": DATA_DIR / "plantdoc",
    "cotton_bd": FIELD_DIR / "cotton_bd",
    "cotton_alt": FIELD_DIR / "cotton_alt",
    "corn_anhui": FIELD_DIR / "corn_anhui",
}


def list_images(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def main() -> None:
    rng = random.Random(0)
    pos: dict[str, list[Path]] = {
        name: rng.sample(imgs, min(N_POS_PER_SOURCE, len(imgs)))
        for name, root in POSITIVE_SOURCES.items()
        if (imgs := list_images(root))
    }
    neg: dict[str, list[Path]] = {d.name: list_images(d) for d in sorted(NEGATIVES_DIR.iterdir()) if d.is_dir()}
    print({k: len(v) for k, v in pos.items()}, {k: len(v) for k, v in neg.items()}, flush=True)

    gate = CropGate()
    clip_pos = {k: gate.scores(v) for k, v in pos.items()}
    clip_neg = {k: gate.scores(v) for k, v in neg.items()}

    ckpt = torch.load(DATA_DIR / "models" / "field_tuned.pt", weights_only=True)
    clf = make_model(len(SHARED_CLASSES))
    clf.load_state_dict(ckpt["state_dict"])

    def clf_conf(paths: list[Path]) -> list[float]:
        return predict_logits(clf, [(p, 0) for p in paths]).softmax(1).max(1).values.tolist()

    base_pos = {k: clf_conf(v) for k, v in pos.items()}
    base_neg = {k: clf_conf(v) for k, v in neg.items()}

    flat = lambda d: [s for v in d.values() for s in v]
    cp, cn, bp, bn = flat(clip_pos), flat(clip_neg), flat(base_pos), flat(base_neg)
    t = DEFAULT_THRESHOLD
    results = {
        "n_positive": len(cp),
        "n_negative": len(cn),
        "clip_gate": {
            "threshold": t,
            "true_positive_rate": round(sum(s >= t for s in cp) / len(cp), 4),
            "false_positive_rate": round(sum(s >= t for s in cn) / len(cn), 4),
            "auroc": round(auroc(cp, cn), 4),
            "tpr_at_5pct_fpr": round(tpr_at_max_fpr(cp, cn, 0.05), 4),
            "tpr_by_positive_source": {k: round(sum(s >= t for s in v) / len(v), 4) for k, v in clip_pos.items()},
            "fpr_by_negative_source": {k: round(sum(s >= t for s in v) / len(v), 4) for k, v in clip_neg.items()},
        },
        "baseline_classifier_confidence": {
            "auroc": round(auroc(bp, bn), 4),
            "tpr_at_5pct_fpr": round(tpr_at_max_fpr(bp, bn, 0.05), 4),
        },
    }
    print(json.dumps(results, indent=2), flush=True)
    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "crop_gate.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
