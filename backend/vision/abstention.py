"""Abstention: answer only when the model is confident, otherwise say "I'm not sure".

A prediction is *answered* if its confidence (top softmax probability) >= threshold.
- coverage            = share of photos we answer
- selective accuracy  = accuracy on only the answered photos
Raising the threshold lowers coverage and (if confidence means anything) raises selective accuracy.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    coverage: float
    selective_accuracy: float | None  # None when nothing is answered


def operating_point(confidences: list[float], correct: list[bool], threshold: float) -> OperatingPoint:
    answered = [ok for c, ok in zip(confidences, correct) if c >= threshold]
    coverage = len(answered) / len(confidences)
    acc = sum(answered) / len(answered) if answered else None
    return OperatingPoint(threshold, coverage, acc)


def coverage_accuracy_curve(
    confidences: list[float], correct: list[bool], n_points: int = 20
) -> list[OperatingPoint]:
    """Operating points at evenly spaced thresholds from 0 to just under 1."""
    thresholds = [i / n_points for i in range(n_points)] + [0.99]
    return [operating_point(confidences, correct, t) for t in thresholds]


def best_coverage_at_accuracy(
    confidences: list[float], correct: list[bool], target_accuracy: float
) -> OperatingPoint | None:
    """Highest-coverage threshold whose selective accuracy reaches the target (None if none does).

    Candidate thresholds are the observed confidences, so the result is exact for this data.
    """
    best: OperatingPoint | None = None
    for t in sorted(set(confidences)):
        p = operating_point(confidences, correct, t)
        if p.selective_accuracy is not None and p.selective_accuracy >= target_accuracy:
            if best is None or p.coverage > best.coverage:
                best = p
    return best
