"""Does the probe still work on the embeddings the SERVER makes (int8 ONNX CLIP), not the fp32 PyTorch ones it was trained on?

Run (from backend/):  uv run --group train python -m vision.eval_probe_onnx
Scores the same 768 held-out field photos through app/onnx_models.prep_clip + clip_vision_int8.onnx + the saved probe.
"""

import json
import sys

import numpy as np
import onnxruntime as ort
from PIL import Image

from app.onnx_models import prep_clip
from vision.download_data import DATA_DIR
from vision.metrics import accuracy
from vision.samples import plantdoc_samples, stratified_split
from vision.train_baseline import EVALS_DIR
from vision.probe import load_probe, probe_predict

def main(probe_path=DATA_DIR / "models" / "probe_b32.npz") -> None:
    _, test = stratified_split(plantdoc_samples(DATA_DIR / "plantdoc"), 0.3, 0)
    sess = ort.InferenceSession(str(DATA_DIR / "models" / "onnx" / "clip_vision_int8.onnx"), providers=["CPUExecutionProvider"])
    probe = load_probe(probe_path)
    preds, confs = [], []
    for i, (p, _) in enumerate(test):
        emb = sess.run(None, {"input": prep_clip(Image.open(p).convert("RGB"))})[0]
        probs = probe_predict(probe, emb)
        preds.append(int(probs.argmax())); confs.append(float(probs.max()))
        if i % 100 == 0:
            print(i, flush=True)
    y = [t for _, t in test]
    conf = np.array(confs); ok = np.array(preds) == np.array(y)
    res = {"n_images": len(y), "accuracy_with_int8_onnx_embeddings": round(accuracy(y, preds), 4),
           "at_threshold_0.9": {"coverage": round(float((conf >= 0.9).mean()), 4), "selective_accuracy": round(float(ok[conf >= 0.9].mean()), 4)}}
    print(json.dumps(res, indent=2))
    (EVALS_DIR / "field_probe_onnx.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(*(DATA_DIR / "models" / a for a in sys.argv[1:]))
