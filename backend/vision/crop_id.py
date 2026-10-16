"""Name the crop in a photo with CLIP, zero-shot, to give a useful answer when the disease model is unsure.

Only used AFTER the classifier abstains. It never diagnoses anything; it only lets Dehqan say
"this looks like wheat ears, which I cannot diagnose yet" instead of a bare "I'm not sure".

The prompts' text embeddings are computed once by `export_crop_prompts.py` and committed (vision/crop_prompts.npz,
about 16 KB), so the server needs no PyTorch and no extra model files on the Hub.
"""

from pathlib import Path

import numpy as np

# label -> prompt. Labels are what the farmer is told; "other" soaks up plants we have no prompt for.
CROP_PROMPTS = {
    "wheat ears": "a photo of wheat ears (grain heads) in a field",
    "wheat leaves": "a close-up photo of wheat leaves",
    "cotton": "a photo of a cotton plant with leaves or bolls",
    "rice": "a photo of rice plants in a paddy field",
    "maize": "a photo of maize (corn) plants or a corn cob",
    "sugarcane": "a photo of sugarcane plants",
    "vegetable or fruit plant": "a photo of a vegetable or fruit plant",
    "other": "a photo of some other plant or tree",
}
PROMPTS_FILE = Path(__file__).with_name("crop_prompts.npz")

# Crops the disease classifier really knows (see app/pipeline.py). Wheat and cotton are not among them.
COVERED_CROPS = {"vegetable or fruit plant", "maize"}
MIN_PROB = 0.6   # below this the recogniser is not sure either, and we say nothing about the crop


def identify_crop(emb: np.ndarray, text: np.ndarray, scale: float, labels: list[str]) -> tuple[str, float]:
    """(label, probability) of the best-matching crop prompt for one CLIP image embedding."""
    emb = emb / np.linalg.norm(emb, axis=-1, keepdims=True)
    logits = scale * emb @ text.T
    e = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs = (e / e.sum(axis=-1, keepdims=True))[0]
    i = int(probs.argmax())
    return labels[i], float(probs[i])


def load_prompts(path: Path = PROMPTS_FILE) -> tuple[np.ndarray, float, list[str]] | None:
    """None if the file is missing: the server then just skips the crop hint."""
    if not path.exists():
        return None
    d = np.load(path, allow_pickle=False)
    return d["text"], float(d["scale"]), [str(x) for x in d["labels"]]
