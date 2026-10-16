"""How well does the zero-shot crop recogniser (vision/crop_id.py) name the crop? Writes evals/crop_id.json.

Usage (from backend/):  uv run --group train python -m vision.eval_crop_id

Five test sets of photos whose crop we know, 60 images each (wheat leaves: JIC; wheat ears: Ma et al. crops;
cotton: both cotton sets; maize: Anhui corn fields; vegetable/fruit: PlantDoc field photos, corn excluded).
Each photo ends in one of three outcomes: correct, wrong, or "unsure" (top probability below MIN_PROB, so Dehqan
says nothing about the crop). Wheat leaves and wheat ears both count as "wheat". The baseline is always answering
the most common label of the five sets (20% by construction). The wheat-ear set is small crops cut from detection
boxes, so it is only a rough guide to real whole-photo ears.
"""

import json
import random

import numpy as np
import torch
from PIL import Image

from vision.crop_gate import MODEL_ID
from vision.crop_id import MIN_PROB, identify_crop, load_prompts
from vision.download_data import DATA_DIR, IMAGE_EXTS
from vision.download_field_crops import FIELD_DIR
from vision.train_baseline import EVALS_DIR

N = 60
FAMILY = {"wheat ears": "wheat", "wheat leaves": "wheat"}


def files(root, pred=lambda p: True):
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS and pred(p))


def sets() -> dict[str, list]:
    rng = random.Random(0)
    pick = lambda fs: rng.sample(fs, min(N, len(fs)))
    return {
        "wheat": pick(files(DATA_DIR / "wheat_jic" / "photos")),
        "wheat (ears)": pick(files(DATA_DIR / "wheat_ears")),
        "cotton": pick(files(FIELD_DIR / "cotton_bd")) [: N // 2] + pick(files(FIELD_DIR / "cotton_alt"))[: N // 2],
        "maize": pick(files(FIELD_DIR / "corn_anhui")),
        "vegetable or fruit plant": pick(files(DATA_DIR / "plantdoc", lambda p: "corn" not in str(p).lower() and "maize" not in str(p).lower())),
    }


def main() -> None:
    from transformers import CLIPModel, CLIPProcessor

    text, scale, labels = load_prompts()
    clip, proc = CLIPModel.from_pretrained(MODEL_ID).eval(), CLIPProcessor.from_pretrained(MODEL_ID)
    results, total_ok, total = {}, 0, 0
    for truth, paths in sets().items():
        want = truth.split(" (")[0]
        ok = wrong = unsure = 0
        confusions: dict[str, int] = {}
        for p in paths:
            with torch.no_grad():
                emb = clip.get_image_features(**proc(images=Image.open(p).convert("RGB"), return_tensors="pt"))
            emb = emb if isinstance(emb, torch.Tensor) else emb.pooler_output
            label, prob = identify_crop(emb.numpy(), text, scale, labels)
            if prob < MIN_PROB:
                unsure += 1
            elif FAMILY.get(label, label) == want:
                ok += 1
            else:
                wrong += 1
                confusions[label] = confusions.get(label, 0) + 1
        n = len(paths)
        results[truth] = {"n": n, "correct": round(ok / n, 3), "wrong": round(wrong / n, 3), "unsure": round(unsure / n, 3), "wrong_labels": confusions}
        total_ok += ok
        total += n
        print(truth, results[truth], flush=True)
    out = {"min_probability": MIN_PROB, "images_per_set": N, "overall_correct": round(total_ok / total, 3), "chance_baseline": 0.2, "by_true_crop": results}
    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "crop_id.json").write_text(json.dumps(out, indent=2))
    print("overall correct", out["overall_correct"])


if __name__ == "__main__":
    main()
