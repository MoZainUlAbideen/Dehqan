import numpy as np
import pytest
from PIL import Image

from vision.severity import estimate_severity_color, grade, grouped_split, severity_from_mask


def test_severity_from_mask_is_spots_over_leaf():
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[:5] = 1          # 50 healthy leaf pixels
    mask[:1] = 2          # row 0 becomes spots: 10 spots, 40 healthy
    assert severity_from_mask(mask) == pytest.approx(10 / 50)


def test_severity_from_mask_without_leaf_is_none():
    assert severity_from_mask(np.zeros((4, 4), dtype=np.uint8)) is None


def test_grade_boundaries():
    assert [grade(x) for x in (0.0, 0.099, 0.10, 0.299, 0.30, 0.9)] == [
        "mild", "mild", "moderate", "moderate", "severe", "severe"]


def test_grouped_split_keeps_ratio_per_group_without_overlap():
    groups = ["a"] * 9 + ["b"] * 6
    train, test = grouped_split(groups, 1 / 3, seed=1)
    assert sorted(train + test) == list(range(15)) and not set(train) & set(test)
    assert sum(groups[i] == "a" for i in test) == 3 and sum(groups[i] == "b" for i in test) == 2
    assert grouped_split(groups, 1 / 3, seed=1) == (train, test)


def test_color_estimator_on_synthetic_leaf():
    # 80 green columns, 10 orange columns touching them, black padding after: 10 / (80 + 10) lesion.
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:, :80] = (40, 160, 40)
    arr[:, 80:90] = (230, 120, 20)
    assert estimate_severity_color(Image.fromarray(arr)) == pytest.approx(10 / 90, abs=0.01)


def test_color_estimator_only_counts_lesion_within_reach_of_green():
    # Known limitation: lesion pixels more than ~15 px from any green pixel are ignored,
    # so a 20-column-wide orange patch only counts its first 15 columns.
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:, :80] = (40, 160, 40)
    arr[:, 80:] = (230, 120, 20)
    assert estimate_severity_color(Image.fromarray(arr)) == pytest.approx(15 / 95, abs=0.01)


def test_color_estimator_ignores_brown_far_from_any_leaf_and_black_padding():
    arr = np.zeros((200, 200, 3), dtype=np.uint8)   # black padding everywhere
    arr[:20, :20] = (40, 160, 40)                    # small leaf, top-left corner
    arr[150:, 150:] = (150, 100, 50)                 # brown soil, far from the leaf
    assert estimate_severity_color(Image.fromarray(arr)) == 0.0


def test_color_estimator_returns_none_without_green():
    assert estimate_severity_color(Image.fromarray(np.zeros((20, 20, 3), dtype=np.uint8))) is None
