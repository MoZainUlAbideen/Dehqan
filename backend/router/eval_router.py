"""Evaluate how well the router understands questions.

Usage (from backend/):
    uv run python -m router.eval_router            # dev set only: look at the mistakes and fix them
    uv run python -m router.eval_router --final    # dev AND the frozen test set; writes evals/router.json

Two question sets (router/eval/dev.json, router/eval/test.json), written by the developer in natural phrasing,
English, Roman Urdu and Urdu script, including out-of-scope questions and awkward ones ("I won't sell, just the
weather"). The dev set is used to find and fix mistakes. The test set is run once, at the end, so its numbers are not
inflated by tuning. Both sets are small and written by the same person who wrote the router: real farmers will
phrase things differently, so treat the numbers as an optimistic upper bound.

Compared with two dumb baselines: "never recognise anything" and "always answer with the most common intent".
Safety check: every question that asks which pesticide / what dose must be routed to the refusal (target 100%).
"""

import json
import sys
from collections import Counter
from pathlib import Path

from router.core import detect_intents
from vision.train_baseline import EVALS_DIR

EVAL_DIR = Path(__file__).parent / "eval"
INTENTS = ["weather", "market", "field", "diagnosis", "treatment"]


def predict(text: str) -> set[str]:
    return {i.name for i in detect_intents(text)}


def scores(items: list[dict], predictor) -> dict:
    tp = fp = fn = exact = 0
    per = {k: Counter() for k in INTENTS}
    wrong = []
    for it in items:
        gold, pred = set(it["expect"]), predictor(it["text"])
        exact += gold == pred
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
        for k in INTENTS:
            per[k]["tp"] += k in gold and k in pred
            per[k]["fp"] += k not in gold and k in pred
            per[k]["fn"] += k in gold and k not in pred
        if gold != pred:
            wrong.append({"text": it["text"], "expected": sorted(gold), "got": sorted(pred)})
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    treat = [it for it in items if "treatment" in it["expect"]]
    safe = sum("treatment" in predictor(it["text"]) for it in treat)
    return {
        "n": len(items),
        "exact_match": round(exact / len(items), 3),
        "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
        "per_intent_recall": {k: round(per[k]["tp"] / (per[k]["tp"] + per[k]["fn"]), 3) for k in INTENTS if per[k]["tp"] + per[k]["fn"]},
        "pesticide_questions": len(treat),
        "pesticide_questions_routed_to_refusal": safe,
        "wrong": wrong,
    }


def run(name: str, most_common: str) -> dict:
    items = json.loads((EVAL_DIR / f"{name}.json").read_text(encoding="utf-8"))
    real = scores(items, predict)
    nothing = scores(items, lambda t: set())
    always = scores(items, lambda t: {most_common})
    return {
        "router": real,
        "baseline_never_recognise_anything": {k: nothing[k] for k in ("exact_match", "precision", "recall", "f1")},
        f"baseline_always_say_{most_common}": {k: always[k] for k in ("exact_match", "precision", "recall", "f1")},
    }


def show(name: str, r: dict) -> None:
    x = r["router"]
    print(f"\n=== {name} set ({x['n']} questions)")
    print(f"exact match {x['exact_match']:.0%} | precision {x['precision']:.0%} recall {x['recall']:.0%} F1 {x['f1']:.0%}")
    print("per-intent recall:", x["per_intent_recall"])
    print(f"pesticide questions sent to the refusal: {x['pesticide_questions_routed_to_refusal']}/{x['pesticide_questions']}")
    for k, v in r.items():
        if k.startswith("baseline"):
            print(f"{k}: exact {v['exact_match']:.0%}, F1 {v['f1']:.0%}")
    for w in x["wrong"]:
        print(f"  MISS  expected {w['expected']} got {w['got']}  <- {w['text']}")


def main() -> None:
    dev_items = json.loads((EVAL_DIR / "dev.json").read_text(encoding="utf-8"))
    most_common = Counter(i for it in dev_items for i in it["expect"]).most_common(1)[0][0]
    dev = run("dev", most_common)
    show("dev", dev)
    if "--final" in sys.argv:
        test = run("test", most_common)
        show("TEST (frozen)", test)
        EVALS_DIR.mkdir(exist_ok=True)
        (EVALS_DIR / "router.json").write_text(json.dumps({"dev": dev, "test": test}, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\nwrote evals/router.json")


if __name__ == "__main__":
    main()
