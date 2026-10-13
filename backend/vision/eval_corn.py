"""Corn field test: do our PlantVillage-trained models work on corn photos taken in Chinese fields?

Usage (from backend/, after train_baseline and train_field_tuned):
    uv run python -m vision.eval_corn

corn_anhui has 6 diseases; our models know only 2 of them (Common Rust, Northern Leaf Blight):
  known  - scored for accuracy (does the model name the right disease?)
  unseen - 4 diseases the model was never trained on. Any disease name is wrong, so we measure how
           CONFIDENT the model is anyway (a safe model would be unsure on these).
Models: lab-only baseline vs the field-tuned model (which saw PlantDoc corn, but never this dataset).
Writes evals/corn_field.json.
"""

import json

import torch

from vision.classes import CLASS_TO_INDEX, SHARED_CLASSES
from vision.download_data import DATA_DIR
from vision.download_field_crops import FIELD_DIR
from vision.metrics import accuracy
from vision.samples import folder_samples
from vision.train_baseline import EVALS_DIR, make_model, predict_logits

KNOWN = {
    "Common_Rust": "Corn_(maize)___Common_rust_",
    "Northern-Leaf-Blight": "Corn_(maize)___Northern_Leaf_Blight",
}
UNSEEN = ["Bipolaris_Maydis", "Curvularia_Lunata(wakker)boed_Spot", "Own-Spot", "Sheath-Blight"]
CORN_CLASSES = [c for c in SHARED_CLASSES if c.startswith("Corn_")]


def load(name: str) -> torch.nn.Module:
    ckpt = torch.load(DATA_DIR / "models" / name, weights_only=True)
    model = make_model(len(SHARED_CLASSES))
    model.load_state_dict(ckpt["state_dict"])
    return model


def main() -> None:
    root = FIELD_DIR / "corn_anhui"
    known_names = list(KNOWN)
    known = [(p, CLASS_TO_INDEX[KNOWN[known_names[i]]]) for p, i in folder_samples(root, known_names)]
    unseen = folder_samples(root, UNSEEN)
    y_true = [y for _, y in known]
    corn_idx = [CLASS_TO_INDEX[c] for c in CORN_CLASSES]
    results = {"n_known": len(known), "n_unseen": len(unseen), "models": {}}

    for label, ckpt in (("lab_only_baseline", "baseline.pt"), ("field_tuned", "field_tuned.pt")):
        model = load(ckpt)
        probs_k = predict_logits(model, known).softmax(1)
        pred = probs_k.argmax(1).tolist()
        pred_corn_only = [corn_idx[i] for i in probs_k[:, corn_idx].argmax(1).tolist()]
        conf_u = predict_logits(model, unseen).softmax(1).max(1).values.tolist()
        results["models"][label] = {
            "known_accuracy_all_27_classes": round(accuracy(y_true, pred), 4),
            "known_accuracy_if_told_it_is_corn": round(accuracy(y_true, pred_corn_only), 4),
            "known_always_guess_one_class": round(max(y_true.count(c) for c in set(y_true)) / len(y_true), 4),
            "unseen_mean_confidence": round(sum(conf_u) / len(conf_u), 4),
            "unseen_share_confidence_above_0.9": round(sum(c > 0.9 for c in conf_u) / len(conf_u), 4),
        }
        print(label, results["models"][label], flush=True)

    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "corn_field.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
