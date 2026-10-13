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


def majority_baseline_accuracy(train_labels: list[int], y_true: list[int]) -> float:
    """Accuracy of a dumb model that always predicts the most common training class."""
    most_common = Counter(train_labels).most_common(1)[0][0]
    return accuracy(y_true, [most_common] * len(y_true))
