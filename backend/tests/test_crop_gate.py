import pytest

from vision.crop_gate import PROMPTS, LEAF_PROMPTS, is_crop, leaf_score
from vision.metrics import auroc, tpr_at_max_fpr


def test_leaf_score_sums_only_leaf_prompts():
    probs = [0.3, 0.2, 0.1] + [0.4 / (len(PROMPTS) - 3)] * (len(PROMPTS) - 3)
    assert leaf_score(probs) == pytest.approx(0.6)
    assert len(LEAF_PROMPTS) == 3


def test_is_crop_threshold():
    assert is_crop(0.5) and is_crop(0.9) and not is_crop(0.49)
    assert not is_crop(0.7, threshold=0.8)


def test_auroc_perfect_random_and_ties():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auroc([0.1, 0.2], [0.9, 0.8]) == 0.0
    assert auroc([0.5], [0.5]) == 0.5


def test_tpr_at_max_fpr():
    pos, neg = [0.9, 0.8, 0.4], [0.5, 0.3, 0.2, 0.1]
    assert tpr_at_max_fpr(pos, neg, 0.0) == pytest.approx(2 / 3)  # threshold 0.8 keeps 0 false positives
    assert tpr_at_max_fpr(pos, neg, 0.25) == 1.0  # threshold 0.4: only the 0.5 negative gets through
