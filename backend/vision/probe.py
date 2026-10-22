"""The classifier head that sits on top of CLIP image embeddings (numpy only, so the server needs no PyTorch).

Weights come from vision/train_probe.py (PROBE_SAVE): a 2-layer network, embedding(512, unit length) x scale -> 512 -> GELU -> classes.
"""

from math import erf, sqrt
from pathlib import Path

import numpy as np

PROBE_FILE = Path(__file__).with_name("probe_b32.npz")   # committed (1 MB); made by train_probe.py with PROBE_SAVE
_erf = np.vectorize(erf)


def load_probe(path: Path) -> dict:
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in ("w1", "b1", "w2", "b2")} | {"scale": float(d["scale"]), "classes": [str(c) for c in d["classes"]]}


def probe_predict(p: dict, emb: np.ndarray) -> np.ndarray:
    """Class probabilities for one CLIP image embedding of shape (1, d)."""
    x = emb / np.linalg.norm(emb, axis=-1, keepdims=True) * p["scale"]
    h = x @ p["w1"].T + p["b1"]
    h = 0.5 * h * (1.0 + _erf(h / sqrt(2.0)))   # exact GELU, the same as torch.nn.GELU()
    z = h @ p["w2"].T + p["b2"]
    e = np.exp(z - z.max(axis=-1, keepdims=True))
    return (e / e.sum(axis=-1, keepdims=True))[0]
