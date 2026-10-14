"""ONNX Runtime model components: the same three models as models_torch.py, with no PyTorch.

Why: PyTorch alone needs ~290 MB of RAM and the CLIP text tower is wasted work on every request. Here the CLIP
text embeddings were computed once (vision/export_onnx.py) and only the int8 image tower runs per photo.
Preprocessing is re-implemented with PIL + numpy to match the PyTorch/transformers pipeline; the parity check
(vision/check_onnx_parity.py) measures how closely the outputs agree.
"""

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from app.components import Components
from app.fetch_models import MODELS_DIR
from app.pipeline import Prediction
from vision.severity import severity_from_mask

ONNX_DIR = MODELS_DIR / "onnx"
REQUIRED = ["classifier.onnx", "severity.onnx", "clip_vision_int8.onnx", "clip_text.npy", "meta.json"]

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
CLASSIFIER_SIZE = 224
SEG_SIZE = 384
CLIP_SIZE = 224


def missing_files(onnx_dir: Path = ONNX_DIR) -> list[str]:
    return [f for f in REQUIRED if not (onnx_dir / f).exists()]


def _to_input(img: Image.Image, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """PIL RGB image -> normalised float32 array of shape 1x3xHxW."""
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return ((arr - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)


def prep_classifier(img: Image.Image) -> np.ndarray:
    """Same as torchvision Resize((224, 224)) + ToTensor + ImageNet normalise."""
    return _to_input(img.convert("RGB").resize((CLASSIFIER_SIZE, CLASSIFIER_SIZE), Image.BILINEAR), IMAGENET_MEAN, IMAGENET_STD)


def prep_segmenter(img: Image.Image) -> np.ndarray:
    return _to_input(img.convert("RGB").resize((SEG_SIZE, SEG_SIZE), Image.BILINEAR), IMAGENET_MEAN, IMAGENET_STD)


def prep_clip(img: Image.Image) -> np.ndarray:
    """Same as CLIPProcessor: shortest side to 224 (bicubic), centre-crop 224, CLIP normalisation."""
    img = img.convert("RGB")
    w, h = img.size
    short, long_ = (w, h) if w <= h else (h, w)
    new_long = int(CLIP_SIZE * long_ / short)
    size = (CLIP_SIZE, new_long) if w <= h else (new_long, CLIP_SIZE)  # (width, height)
    img = img.resize(size, Image.BICUBIC)
    w, h = img.size
    left, top = (w - CLIP_SIZE) // 2, (h - CLIP_SIZE) // 2
    img = img.crop((left, top, left + CLIP_SIZE, top + CLIP_SIZE))
    return _to_input(img, CLIP_MEAN, CLIP_STD)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def leaf_score_from_embedding(emb: np.ndarray, text: np.ndarray, scale: float, n_leaf: int) -> float:
    """CLIP: softmax over prompts of scale * cosine similarity; the leaf score is the mass on the leaf prompts."""
    emb = emb / np.linalg.norm(emb, axis=-1, keepdims=True)
    probs = softmax(scale * emb @ text.T)[0]
    return float(probs[:n_leaf].sum())


def _session(path: Path) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1       # small hosts have ~1 CPU; extra threads only cost memory
    opts.enable_cpu_mem_arena = False   # do not keep a growing pool of freed activation memory
    opts.enable_mem_pattern = False
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def load_components(onnx_dir: Path = ONNX_DIR) -> Components:
    missing = missing_files(onnx_dir)
    if missing:
        raise FileNotFoundError(f"missing ONNX files in {onnx_dir}: {missing}")

    meta = json.loads((onnx_dir / "meta.json").read_text())
    classes: list[str] = meta["classes"]
    text = np.load(onnx_dir / "clip_text.npy")
    clip, clf, seg = (_session(onnx_dir / n) for n in ("clip_vision_int8.onnx", "classifier.onnx", "severity.onnx"))

    def gate(img: Image.Image) -> float:
        emb = clip.run(None, {"input": prep_clip(img)})[0]
        return leaf_score_from_embedding(emb, text, meta["clip_logit_scale"], meta["n_leaf_prompts"])

    def classify(img: Image.Image) -> Prediction:
        probs = softmax(clf.run(None, {"input": prep_classifier(img)})[0])[0]
        i = int(probs.argmax())
        return Prediction(label=classes[i], confidence=float(probs[i]))

    def severity(img: Image.Image) -> float | None:
        logits = seg.run(None, {"input": prep_segmenter(img)})[0]
        return severity_from_mask(logits.argmax(1)[0].astype(np.uint8))

    return Components(gate, classify, severity)
