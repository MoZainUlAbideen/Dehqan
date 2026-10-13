"""Zero-shot "is this a crop photo?" gate using CLIP (no training).

CLIP scores how well an image matches each text prompt. We score the image against prompts describing
plant leaves and prompts describing other things; the softmax mass on the leaf prompts is the leaf score.
Photos scoring below the threshold are rejected BEFORE the disease classifier runs, so Dehqan says
"please send a clear photo of a leaf" instead of diagnosing a dog.
"""

from pathlib import Path

LEAF_PROMPTS = [
    "a close-up photo of a healthy plant leaf",
    "a close-up photo of a diseased plant leaf with spots",
    "a photo of a crop plant growing in a field",
]
OTHER_PROMPTS = [
    "a photo of a person",
    "a photo of an animal",
    "a photo of a vehicle",
    "a photo of a building",
    "a photo of food on a plate",
    "a photo of an everyday object indoors",
    "a screenshot or a document with text",
    "a photo of the sky or a landscape",
]
PROMPTS = LEAF_PROMPTS + OTHER_PROMPTS
LOCAL_CLIP_DIR = Path(__file__).resolve().parents[2] / "data" / "models" / "clip"  # see download_clip.py
MODEL_ID = str(LOCAL_CLIP_DIR) if (LOCAL_CLIP_DIR / "pytorch_model.bin").exists() else "openai/clip-vit-base-patch32"
DEFAULT_THRESHOLD = 0.5


def leaf_score(prompt_probs: list[float], n_leaf: int = len(LEAF_PROMPTS)) -> float:
    """Probability mass on the leaf prompts (the first n_leaf entries)."""
    return sum(prompt_probs[:n_leaf])


def is_crop(score: float, threshold: float = DEFAULT_THRESHOLD) -> bool:
    return score >= threshold


class CropGate:
    def __init__(self, model_id: str = MODEL_ID):
        from transformers import CLIPModel, CLIPProcessor

        self.model = CLIPModel.from_pretrained(model_id).eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)

    def scores(self, paths: list[Path], batch_size: int = 32) -> list[float]:
        import torch
        from PIL import Image

        out: list[float] = []
        for i in range(0, len(paths), batch_size):
            images = [Image.open(p).convert("RGB") for p in paths[i : i + batch_size]]
            inputs = self.processor(text=PROMPTS, images=images, return_tensors="pt", padding=True)
            with torch.no_grad():
                probs = self.model(**inputs).logits_per_image.softmax(dim=1)
            out += [leaf_score(row.tolist()) for row in probs]
        return out
