"""Export the three models to ONNX so the server can run WITHOUT PyTorch (which alone needs ~290 MB of RAM).

Usage (from backend/, needs the trained weights in data/models/ and the CLIP files):
    uv run python -m vision.export_onnx

Writes data/models/onnx/:
  classifier.onnx      disease classifier (27 classes), input 1x3x224x224 -> logits
  severity.onnx        lesion segmenter, input 1x3x384x384 -> 3-class logits
  clip_vision.onnx     CLIP image tower + projection, input 1x3x224x224 -> 512-d embedding (fp32)
  clip_vision_int8.onnx the same, weights quantised to int8 (~4x smaller; this is what the server uses)
  clip_text.npy        unit-length text embeddings of our prompts, computed once here instead of on every request
  meta.json            class names, CLIP logit scale, number of leaf prompts

The "is it a leaf?" score is then softmax(scale * image_emb @ text_emb.T)[:n_leaf].sum(), identical to what the
PyTorch CLIP model computes.
"""

import json

import numpy as np
import torch
from torch import nn

from app.fetch_models import MODELS_DIR
from vision.classes import SHARED_CLASSES
from vision.crop_gate import LOCAL_CLIP_DIR, LEAF_PROMPTS, PROMPTS
from vision.train_baseline import make_model
from vision.train_severity import SIZE as SEG_SIZE

from torchvision import models as tv_models
from torchvision.models.segmentation import lraspp_mobilenet_v3_large

OUT = MODELS_DIR / "onnx"
OPSET = 17


class SegLogits(nn.Module):
    """LR-ASPP returns a dict; ONNX wants a plain tensor."""

    def __init__(self, net: nn.Module):
        super().__init__()
        self.net = net

    def forward(self, x):
        return self.net(x)["out"]


class ClipImageEmbed(nn.Module):
    def __init__(self, clip):
        super().__init__()
        self.vision, self.proj = clip.vision_model, clip.visual_projection

    def forward(self, pixel_values):
        return self.proj(self.vision(pixel_values=pixel_values).pooler_output)


def export(model: nn.Module, example: torch.Tensor, path, output="output") -> None:
    model.eval()
    torch.onnx.export(
        model, example, str(path), input_names=["input"], output_names=[output],
        opset_version=OPSET, dynamo=False,
    )
    print(f"wrote {path.name}: {path.stat().st_size / 1e6:.1f} MB", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    ckpt = torch.load(MODELS_DIR / "field_tuned.pt", weights_only=True)
    clf = make_model(len(ckpt["classes"]))
    clf.load_state_dict(ckpt["state_dict"])
    export(clf, torch.randn(1, 3, 224, 224), OUT / "classifier.onnx", "logits")

    seg = lraspp_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=3)
    seg.load_state_dict(torch.load(MODELS_DIR / "severity.pt", weights_only=True))
    export(SegLogits(seg), torch.randn(1, 3, SEG_SIZE, SEG_SIZE), OUT / "severity.onnx", "logits")

    from transformers import CLIPModel, CLIPTokenizer

    clip = CLIPModel.from_pretrained(str(LOCAL_CLIP_DIR)).eval()
    export(ClipImageEmbed(clip), torch.randn(1, 3, 224, 224), OUT / "clip_vision.onnx", "embedding")

    tok = CLIPTokenizer.from_pretrained(str(LOCAL_CLIP_DIR))
    inputs = tok(PROMPTS, padding=True, return_tensors="pt")
    with torch.no_grad():
        text = clip.text_projection(clip.text_model(**inputs).pooler_output)
        text = text / text.norm(dim=-1, keepdim=True)
    np.save(OUT / "clip_text.npy", text.numpy().astype(np.float32))
    (OUT / "meta.json").write_text(json.dumps({
        "classes": ckpt["classes"],
        "clip_logit_scale": float(clip.logit_scale.exp()),
        "n_leaf_prompts": len(LEAF_PROMPTS),
        "n_prompts": len(PROMPTS),
        "shared_classes_match": ckpt["classes"] == SHARED_CLASSES,
    }, indent=2))

    from onnxruntime.quantization import QuantType, quantize_dynamic

    q = OUT / "clip_vision_int8.onnx"
    quantize_dynamic(str(OUT / "clip_vision.onnx"), str(q), weight_type=QuantType.QInt8)
    print(f"wrote {q.name}: {q.stat().st_size / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
