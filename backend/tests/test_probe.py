import numpy as np

from vision.classes import SHARED_CLASSES
from vision.probe import PROBE_FILE, load_probe, probe_predict


def tiny(w2_scale=1.0):
    return {"w1": np.eye(3, dtype=np.float32), "b1": np.zeros(3, np.float32), "w2": np.eye(3, dtype=np.float32) * w2_scale,
            "b2": np.zeros(3, np.float32), "scale": 1.0, "classes": ["a", "b", "c"]}


def test_probabilities_sum_to_one_and_pick_the_strongest_direction():
    p = probe_predict(tiny(w2_scale=5.0), np.array([[0.1, 0.9, 0.2]]))
    assert abs(p.sum() - 1) < 1e-6 and p.argmax() == 1


def test_embedding_length_does_not_change_the_answer():
    a = probe_predict(tiny(), np.array([[1.0, 2.0, 0.5]]))
    b = probe_predict(tiny(), np.array([[10.0, 20.0, 5.0]]))
    assert np.allclose(a, b)


def test_gelu_matches_the_exact_formula():
    from math import erf, sqrt
    p = tiny()
    p["w2"] = np.array([[1.0, 0, 0], [0, 0, 0], [0, 0, 0]], np.float32)   # class a's logit is gelu(x0 after unit-length scaling)
    x = np.array([[3.0, 4.0, 0.0]])
    h = 3 / 5
    expected_logit = 0.5 * h * (1 + erf(h / sqrt(2)))
    z = np.array([expected_logit, 0.0, 0.0])
    want = np.exp(z) / np.exp(z).sum()
    assert np.allclose(probe_predict(p, x), want, atol=1e-6)


def test_the_committed_probe_matches_the_classifier_classes():
    p = load_probe(PROBE_FILE)
    assert p["classes"] == SHARED_CLASSES and p["w2"].shape[0] == len(SHARED_CLASSES) and p["w1"].shape[1] == 512
