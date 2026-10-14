"""PyTorch model components (CLIP gate, disease classifier, severity segmenter). Used for development and evaluation.
The deployed server uses app/onnx_models.py instead, which needs no PyTorch.

Weights are NOT in git. They live in data/models/ (produced by the training scripts in vision/).
`load_components()` raises FileNotFoundError naming the missing file, so a deploy fails loudly.
"""

import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from torchvision.models.segmentation import lraspp_mobilenet_v3_large

from app.components import Components
from app.pipeline import Prediction
from vision.crop_gate import CropGate
from vision.download_data import DATA_DIR
from vision.severity import severity_from_mask
from vision.train_baseline import EVAL_TF, make_model
from vision.train_severity import NORM as SEG_NORM
from vision.train_severity import SIZE as SEG_SIZE

MODELS_DIR = DATA_DIR / "models"
# CLIP is not required here: with no local copy it is loaded from the public Hub repo (see vision/crop_gate.py).
REQUIRED_FILES = ["field_tuned.pt", "severity.pt"]


def missing_files() -> list[str]:
    return [f for f in REQUIRED_FILES if not (MODELS_DIR / f).exists()]


def load_components() -> Components:
    missing = missing_files()
    if missing:
        raise FileNotFoundError(f"missing model files in {MODELS_DIR}: {missing}")

    gate = CropGate()

    ckpt = torch.load(MODELS_DIR / "field_tuned.pt", weights_only=True)
    classes: list[str] = ckpt["classes"]
    clf = make_model(len(classes))
    clf.load_state_dict(ckpt["state_dict"])
    clf.eval()

    seg = lraspp_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=3)
    seg.load_state_dict(torch.load(MODELS_DIR / "severity.pt", weights_only=True))
    seg.eval()

    def gate_fn(img: Image.Image) -> float:
        return gate.score_images([img])[0]

    def classify_fn(img: Image.Image) -> Prediction:
        with torch.no_grad():
            probs = clf(EVAL_TF(img).unsqueeze(0)).softmax(1)[0]
        conf, idx = probs.max(0)
        return Prediction(label=classes[int(idx)], confidence=float(conf))

    def severity_fn(img: Image.Image) -> float | None:
        x = SEG_NORM(transforms.functional.to_tensor(img.resize((SEG_SIZE, SEG_SIZE), Image.BILINEAR)))
        with torch.no_grad():
            mask = seg(x.unsqueeze(0))["out"].argmax(1)[0].numpy().astype(np.uint8)
        return severity_from_mask(mask)

    return Components(gate_fn, classify_fn, severity_fn)
