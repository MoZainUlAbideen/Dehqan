import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app import onnx_models as om

BACKEND = Path(__file__).resolve().parents[1]


def solid(w, h, color=(120, 60, 200)):
    return Image.new("RGB", (w, h), color)


def test_preprocessing_shapes_dtype_and_normalisation():
    for fn, size in ((om.prep_classifier, 224), (om.prep_segmenter, 384), (om.prep_clip, 224)):
        x = fn(solid(300, 200))
        assert x.shape == (1, 3, size, size) and x.dtype == np.float32
    # A pure-white image normalises to (1 - mean) / std in each channel.
    white = om.prep_classifier(solid(50, 50, (255, 255, 255)))
    expected = (1 - om.IMAGENET_MEAN) / om.IMAGENET_STD
    assert np.allclose(white[0, :, 0, 0], expected, atol=1e-5)


def test_clip_preprocessing_keeps_the_centre_of_non_square_photos():
    # Wide photo: left third red, middle third green, right third blue. After resize + centre crop only green stays.
    img = Image.new("RGB", (900, 300))
    for i, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
        img.paste(Image.new("RGB", (300, 300), color), (300 * i, 0))
    x = om.prep_clip(img)[0]
    raw = x * om.CLIP_STD[:, None, None] + om.CLIP_MEAN[:, None, None]  # undo normalisation -> 0..1
    centre = raw[:, 112, 112]
    assert centre[1] > 0.9 and centre[0] < 0.1 and centre[2] < 0.1
    assert raw[1].mean() > 0.9  # the whole crop is the green third


def test_softmax_sums_to_one_and_is_stable_for_large_values():
    p = om.softmax(np.array([[1000.0, 1001.0, 999.0]]))
    assert np.isclose(p.sum(), 1.0) and np.all(np.isfinite(p))


def test_leaf_score_matches_a_hand_computation():
    text = np.eye(4, dtype=np.float32)[:, :4]          # 4 orthogonal unit "prompts"
    emb = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)  # points exactly at prompt 0
    scale = 2.0
    probs = np.exp(scale * np.array([1, 0, 0, 0.0]))
    probs /= probs.sum()
    assert om.leaf_score_from_embedding(emb, text, scale, n_leaf=1) == pytest.approx(probs[0], abs=1e-6)
    assert om.leaf_score_from_embedding(emb, text, scale, n_leaf=4) == pytest.approx(1.0, abs=1e-6)
    # Embedding length must not matter (it is normalised first).
    assert om.leaf_score_from_embedding(emb * 7, text, scale, 1) == pytest.approx(probs[0], abs=1e-6)


def test_missing_files_are_reported_and_loading_fails_loudly(tmp_path):
    assert set(om.missing_files(tmp_path)) == set(om.REQUIRED)
    with pytest.raises(FileNotFoundError, match="missing ONNX files"):
        om.load_components(tmp_path)


def test_the_server_import_chain_never_imports_pytorch():
    """The deployed image has no PyTorch. If any server module imported it, the container would crash on start."""
    code = """
import sys
for m in ('torch', 'torchvision', 'transformers', 'datasets'):
    sys.modules[m] = None  # any import of these now raises ImportError
import app.main, app.models, app.onnx_models, app.fetch_models
print('ok')
"""
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr
