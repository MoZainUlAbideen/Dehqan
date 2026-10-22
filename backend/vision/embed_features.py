"""Turn every photo of the field-tuned experiment into a CLIP image embedding and save them (data/features/clip_b32.npz).

Same data and the same split as train_field_tuned.py (PlantVillage 150/class + 70% of PlantDoc to train, the other
30% of PlantDoc held out), so a classifier trained on these embeddings is scored on exactly the same 768 field photos.
Run (from backend/):  uv run --group train python -m vision.embed_features
"""

import os

import numpy as np
import torch
from PIL import Image

from vision.crop_gate import MODEL_ID
from vision.download_data import DATA_DIR
from vision.samples import plantdoc_samples, plantvillage_samples, stratified_split

MODEL = os.environ.get("EMBED_MODEL", MODEL_ID)   # e.g. openai/clip-vit-base-patch16
OUT = DATA_DIR / "features" / os.environ.get("EMBED_OUT", "clip_b32.npz")


def embed(clip, proc, paths, flip=False, batch=32):
    out = []
    for i in range(0, len(paths), batch):
        imgs = [Image.open(p).convert("RGB") for p in paths[i:i + batch]]
        if flip:
            imgs = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in imgs]
        with torch.no_grad():
            e = clip.get_image_features(**proc(images=imgs, return_tensors="pt"))
        e = e if isinstance(e, torch.Tensor) else e.pooler_output
        out.append((e / e.norm(dim=-1, keepdim=True)).numpy())
        print(f"  {i + len(imgs)}/{len(paths)}", flush=True)
    return np.concatenate(out)


def main() -> None:
    from transformers import CLIPModel, CLIPProcessor

    clip, proc = CLIPModel.from_pretrained(MODEL).eval(), CLIPProcessor.from_pretrained(MODEL)
    lab_train = plantvillage_samples(DATA_DIR / "plantvillage", "train", 150, 0)
    lab_test = plantvillage_samples(DATA_DIR / "plantvillage", "test", 60, 0)
    field_train, field_test = stratified_split(plantdoc_samples(DATA_DIR / "plantdoc"), 0.3, 0)
    data = {}
    for name, s in [("lab_train", lab_train), ("field_train", field_train), ("field_test", field_test), ("lab_test", lab_test)]:
        print(name, len(s), flush=True)
        paths = [p for p, _ in s]
        data[f"{name}_x"] = embed(clip, proc, paths)
        data[f"{name}_y"] = np.array([y for _, y in s])
        if name in ("lab_train", "field_train"):   # flipped copies = free extra training data
            data[f"{name}_xflip"] = embed(clip, proc, paths, flip=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez(OUT, **data)
    print("DONE", OUT)


if __name__ == "__main__":
    main()
