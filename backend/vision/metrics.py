"""Plain-Python classification metrics (no sklearn needed)."""

from collections import Counter


def accuracy(y_true: list[int], y_pred: list[int]) -> float:
    return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)


def macro_f1(y_true: list[int], y_pred: list[int]) -> float:
    """Average F1 over the classes that appear in y_true (so rare classes count equally)."""
    f1s = []
    for c in set(y_true):
        tp = sum(t == c and p == c for t, p in zip(y_true, y_pred))
        fp = sum(t != c and p == c for t, p in zip(y_true, y_pred))
        fn = sum(t == c and p != c for t, p in zip(y_true, y_pred))
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return sum(f1s) / len(f1s)


def per_class_recall(y_true: list[int], y_pred: list[int], names: list[str]) -> dict[str, float]:
    """Share of each class's images that were labelled correctly (only classes present in y_true)."""
    out = {}
    for c, name in enumerate(names):
        idxs = [i for i, t in enumerate(y_true) if t == c]
        if idxs:
            out[name] = round(sum(y_pred[i] == c for i in idxs) / len(idxs), 4)
    return out


def auroc(pos_scores: list[float], neg_scores: list[float]) -> float:
    """Chance that a random positive scores higher than a random negative (ties count half).
    1.0 = perfect separation, 0.5 = no better than a coin flip."""
    wins = sum((p > n) + 0.5 * (p == n) for p in pos_scores for n in neg_scores)
    return wins / (len(pos_scores) * len(neg_scores))


def tpr_at_max_fpr(pos_scores: list[float], neg_scores: list[float], max_fpr: float) -> float:
    """Best true-positive rate over thresholds whose false-positive rate is <= max_fpr."""
    best = 0.0
    for t in sorted(set(pos_scores + neg_scores)):
        fpr = sum(n >= t for n in neg_scores) / len(neg_scores)
        if fpr <= max_fpr:
            best = max(best, sum(p >= t for p in pos_scores) / len(pos_scores))
    return best


def majority_baseline_accuracy(train_labels: list[int], y_true: list[int]) -> float:
    """Accuracy of a dumb model that always predicts the most common training class."""
    most_common = Counter(train_labels).most_common(1)[0][0]
    return accuracy(y_true, [most_common] * len(y_true))
