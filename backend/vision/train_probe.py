"""A small classifier on top of frozen CLIP image embeddings ("linear probe"), scored on the same held-out field photos.

Run (from backend/, after embed_features):  uv run --group train python -m vision.train_probe

Honest-evaluation rules: the 768 held-out PlantDoc photos are touched ONCE, at the end. The settings (weight decay,
field-photo weight) are chosen on a validation slice cut out of the TRAINING field photos only.
Writes evals/field_probe.json and data/models/probe.npz (weights; small).
"""

import json
import os

import numpy as np
import torch

from vision.classes import SHARED_CLASSES
from vision.download_data import DATA_DIR
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy
from vision.train_baseline import EVALS_DIR

FEATURES = DATA_DIR / "features" / os.environ.get("EMBED_OUT", "clip_b32.npz")


def fit_probe(x, y, w, wd, epochs=300, hidden=0, seed=0):
    torch.manual_seed(seed)
    d, k = x.shape[1], len(SHARED_CLASSES)
    net = torch.nn.Linear(d, k) if not hidden else torch.nn.Sequential(torch.nn.Linear(d, hidden), torch.nn.GELU(), torch.nn.Dropout(0.3), torch.nn.Linear(hidden, k))
    opt = torch.optim.AdamW(net.parameters(), lr=3e-3, weight_decay=wd)
    x, y, w = torch.tensor(x), torch.tensor(y), torch.tensor(w, dtype=torch.float32)
    scale = 20.0   # embeddings are unit length: a temperature makes the softmax able to be confident
    for _ in range(epochs):
        net.train()
        opt.zero_grad()
        loss = (torch.nn.functional.cross_entropy(net(x * scale), y, reduction="none") * w).mean()
        loss.backward()
        opt.step()
    net.eval()
    def predict(z):
        return torch.softmax(net(torch.tensor(z) * scale), 1).detach().numpy()

    predict.net = net
    return predict


def main() -> None:
    d = np.load(FEATURES)
    cat = lambda *a: np.concatenate(a)
    lab_x, lab_y = cat(d["lab_train_x"], d["lab_train_xflip"]), cat(d["lab_train_y"], d["lab_train_y"])
    fx, fy = cat(d["field_train_x"], d["field_train_xflip"]), cat(d["field_train_y"], d["field_train_y"])

    # validation slice from the TRAIN field photos (original + flip of the same photo stay together)
    n = len(d["field_train_y"])
    rng = np.random.default_rng(0)
    val_idx = rng.permutation(n)[: n // 5]
    is_val = np.zeros(n, bool); is_val[val_idx] = True
    val_x, val_y = d["field_train_x"][is_val], d["field_train_y"][is_val]
    tr = np.concatenate([~is_val, ~is_val])
    best = None
    fixed = os.environ.get("PROBE_FIXED")   # "hidden,wd,field_w": skip the search and reuse settings chosen earlier on validation
    grid = [(int(fixed.split(",")[0]), float(fixed.split(",")[1]), float(fixed.split(",")[2]))] if fixed else         [(h, wd, fw) for h in (0, 512) for wd in (1e-4, 1e-2, 1e-1) for fw in (1.0, 3.0, 6.0)]
    for hidden, wd, field_w in grid:
        if True:
            if True:
                x = cat(lab_x, fx[tr]); y = cat(lab_y, fy[tr])
                w = cat(np.ones(len(lab_y)), np.full(tr.sum(), field_w))
                acc = accuracy(val_y.tolist(), fit_probe(x, y, w, wd, hidden=hidden)(val_x).argmax(1).tolist())
                print(f"hidden={hidden} wd={wd} field_w={field_w}: val acc {acc:.3f}", flush=True)
                if best is None or acc > best[0]:
                    best = (acc, hidden, wd, field_w)
    _, hidden, wd, field_w = best
    print("chosen on validation:", best, flush=True)

    x, y = cat(lab_x, fx), cat(lab_y, fy)
    w = cat(np.ones(len(lab_y)), np.full(len(fy), field_w))
    predict = fit_probe(x, y, w, wd, hidden=hidden)
    yt = d["field_test_y"].tolist()
    p = predict(d["field_test_x"])
    pred = p.argmax(1).tolist()
    lab_acc = accuracy(d["lab_test_y"].tolist(), predict(d["lab_test_x"]).argmax(1).tolist())
    conf = p.max(1)
    curve = []
    for t in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95):
        keep = conf >= t
        curve.append({"threshold": t, "coverage": round(float(keep.mean()), 4),
                      "selective_accuracy": round(float(np.mean(np.array(pred)[keep] == np.array(yt)[keep])) if keep.any() else 0, 4)})
    if hidden and os.environ.get("PROBE_SAVE"):   # the deployable weights: 2 small matrices
        net = predict.net
        lin1, lin2 = net[0], net[3]
        np.savez(os.environ["PROBE_SAVE"], w1=lin1.weight.detach().numpy(), b1=lin1.bias.detach().numpy(),
                 w2=lin2.weight.detach().numpy(), b2=lin2.bias.detach().numpy(), scale=np.float32(20.0), classes=np.array(SHARED_CLASSES))
    res = {
        "model": "frozen CLIP ViT-B/32 image embeddings + small classifier head",
        "chosen_on_validation": {"hidden": hidden, "weight_decay": wd, "field_weight": field_w, "validation_accuracy": round(best[0], 4)},
        "held_out_field": {"n_images": len(yt), "accuracy": round(accuracy(yt, pred), 4), "macro_f1": round(macro_f1(yt, pred), 4),
                           "majority_baseline_accuracy": round(majority_baseline_accuracy(y.tolist(), yt), 4)},
        "lab_test_accuracy": round(lab_acc, 4),
        "abstention_curve": curve,
        "previous_field_tuned_mobilenet_accuracy": 0.474,
    }
    print(json.dumps(res, indent=2))
    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / os.environ.get("PROBE_EVAL", "field_probe.json")).write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
