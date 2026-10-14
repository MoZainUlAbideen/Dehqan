"""Do the ONNX models behave like the PyTorch models they were exported from? (Development check: needs PyTorch.)

Usage (from backend/, after vision.export_onnx):
    uv run python -m vision.check_onnx_parity

Uses the same 500 leaf photos and 500 non-crop photos as the crop-gate evaluation and reports:
  gate        : score difference torch vs ONNX-int8, and the gate's TPR / FPR / AUROC when run on ONNX
  classifier  : how often the top-1 label agrees, and the largest probability difference
  severity    : mean absolute difference in severity, and how often the mild/moderate/severe grade agrees
Writes evals/onnx_parity.json.
"""

import json
import random

import numpy as np

from app import models_torch, onnx_models
from vision.crop_gate import DEFAULT_THRESHOLD
from vision.eval_crop_gate import N_POS_PER_SOURCE, POSITIVE_SOURCES, list_images
from vision.download_negatives import NEGATIVES_DIR
from vision.metrics import auroc
from vision.severity import grade
from vision.train_baseline import EVALS_DIR

from PIL import Image


def main() -> None:
    rng = random.Random(0)  # same sampling as eval_crop_gate
    pos = [p for root in POSITIVE_SOURCES.values() if (imgs := list_images(root)) for p in rng.sample(imgs, min(N_POS_PER_SOURCE, len(imgs)))]
    neg = [p for d in sorted(NEGATIVES_DIR.iterdir()) if d.is_dir() for p in list_images(d)]
    print(f"{len(pos)} leaf photos, {len(neg)} non-crop photos", flush=True)

    t, o = models_torch.load_components(), onnx_models.load_components()

    def load(p):
        return Image.open(p).convert("RGB")

    gate_t, gate_o = [], []
    for p in pos + neg:
        img = load(p)
        gate_t.append(t.gate(img))
        gate_o.append(o.gate(img))
    gt, go = np.array(gate_t), np.array(gate_o)
    n = len(pos)

    agree, max_dp, sev_diff, grade_agree, n_sev = 0, 0.0, [], 0, 0
    for p in pos:
        img = load(p)
        pt, po = t.classifier(img), o.classifier(img)
        agree += pt.label == po.label
        max_dp = max(max_dp, abs(pt.confidence - po.confidence))
        st, so = t.severity(img), o.severity(img)
        if st is not None and so is not None:
            n_sev += 1
            sev_diff.append(abs(st - so))
            grade_agree += grade(st) == grade(so)

    thr = DEFAULT_THRESHOLD
    res = {
        "n_leaf": n, "n_non_crop": len(neg),
        "gate": {
            "mean_abs_score_diff": round(float(np.abs(gt - go).mean()), 4),
            "max_abs_score_diff": round(float(np.abs(gt - go).max()), 4),
            "decision_agreement_at_0.5": round(float(((gt >= thr) == (go >= thr)).mean()), 4),
            "onnx_int8": {
                "true_positive_rate": round(float((go[:n] >= thr).mean()), 4),
                "false_positive_rate": round(float((go[n:] >= thr).mean()), 4),
                "auroc": round(auroc(go[:n].tolist(), go[n:].tolist()), 4),
            },
            "torch": {
                "true_positive_rate": round(float((gt[:n] >= thr).mean()), 4),
                "false_positive_rate": round(float((gt[n:] >= thr).mean()), 4),
                "auroc": round(auroc(gt[:n].tolist(), gt[n:].tolist()), 4),
            },
        },
        "classifier": {"top1_label_agreement": round(agree / n, 4), "max_abs_confidence_diff": round(max_dp, 5)},
        "severity": {
            "n_compared": n_sev,
            "mean_abs_diff_points": round(float(np.mean(sev_diff)) * 100, 3),
            "max_abs_diff_points": round(float(np.max(sev_diff)) * 100, 3),
            "grade_agreement": round(grade_agree / n_sev, 4),
        },
    }
    print(json.dumps(res, indent=2), flush=True)
    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "onnx_parity.json").write_text(json.dumps(res, indent=2))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
