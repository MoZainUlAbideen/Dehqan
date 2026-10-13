"""Coverage-vs-accuracy of the cotton model when it is allowed to abstain.

Usage (from backend/, after `uv run python -m vision.train_cotton`):
    uv run python -m vision.eval_abstention

Same two test sets as train_cotton (same seed, so the same split):
- same_source  : held-out Bangladesh images, 7-way
- cross_source : the other cotton dataset, 2 shared classes, model restricted to those 2
Baseline for abstention = "answer everything", i.e. overall accuracy at 100% coverage.
Writes evals/abstention_cotton.json.
"""

import json

import torch

from vision.abstention import best_coverage_at_accuracy, coverage_accuracy_curve
from vision.download_data import DATA_DIR
from vision.download_field_crops import FIELD_DIR
from vision.samples import folder_samples, stratified_split
from vision.train_baseline import EVALS_DIR, make_model, predict_logits
from vision.train_cotton import BD_CLASSES, SHARED_IDX, cross_source_samples

TARGETS = (0.90, 0.95)


def analyse(confidences: list[float], correct: list[bool]) -> dict:
    result = {
        "n_images": len(confidences),
        "answer_everything_accuracy": round(sum(correct) / len(correct), 4),
        "curve": [
            {"threshold": round(p.threshold, 2), "coverage": round(p.coverage, 4),
             "selective_accuracy": None if p.selective_accuracy is None else round(p.selective_accuracy, 4)}
            for p in coverage_accuracy_curve(confidences, correct)
        ],
    }
    for target in TARGETS:
        p = best_coverage_at_accuracy(confidences, correct, target)
        result[f"best_coverage_at_{int(target * 100)}pct_accuracy"] = (
            None if p is None else {"threshold": round(p.threshold, 4), "coverage": round(p.coverage, 4)}
        )
    return result


def main() -> None:
    ckpt = torch.load(DATA_DIR / "models" / "cotton.pt", weights_only=True)
    model = make_model(len(BD_CLASSES))
    model.load_state_dict(ckpt["state_dict"])

    _, test = stratified_split(folder_samples(FIELD_DIR / "cotton_bd", BD_CLASSES), 0.2, 0)
    probs = predict_logits(model, test).softmax(1)
    conf, pred = probs.max(1)
    same = analyse(conf.tolist(), [p == y for p, (_, y) in zip(pred.tolist(), test)])

    cross = cross_source_samples()
    probs2 = predict_logits(model, cross)[:, SHARED_IDX].softmax(1)  # choose between the 2 shared classes
    conf2, pred2 = probs2.max(1)
    pred2_idx = [SHARED_IDX[i] for i in pred2.tolist()]
    cross_res = analyse(conf2.tolist(), [p == y for p, (_, y) in zip(pred2_idx, cross)])

    results = {"same_source_7way": same, "cross_source_2way": cross_res}
    for name, r in results.items():
        print(f"\n{name}: n={r['n_images']}, answer-everything accuracy={r['answer_everything_accuracy']}")
        for row in r["curve"][::2]:
            print(f"  threshold {row['threshold']:.2f}: coverage {row['coverage']:.2f}, selective acc {row['selective_accuracy']}")
        for t in TARGETS:
            print(f"  best coverage at >={int(t * 100)}% accuracy: {r[f'best_coverage_at_{int(t * 100)}pct_accuracy']}")

    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "abstention_cotton.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
