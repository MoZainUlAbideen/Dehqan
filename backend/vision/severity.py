"""Disease severity = share of the leaf area covered by disease spots.

severity = spot_pixels / (spot_pixels + healthy_leaf_pixels)

Mask classes follow PDSNet: 0 background, 1 healthy leaf, 2 disease spots.
Grades are OUR cut-offs (mild < 10%, moderate 10-30%, severe >= 30%), chosen from the spread of the
PDSNet data. They are not an official agronomic scale.
"""

import random

import numpy as np
from PIL import Image, ImageFilter

GRADES = ["mild", "moderate", "severe"]
MILD_BELOW = 0.10
SEVERE_FROM = 0.30


def severity_from_mask(mask: np.ndarray) -> float | None:
    """Severity from a 0/1/2 mask, or None if the mask contains no leaf at all."""
    spots = int((mask == 2).sum())
    leaf = int((mask >= 1).sum())
    return spots / leaf if leaf else None


def grade(severity: float) -> str:
    if severity < MILD_BELOW:
        return "mild"
    return "moderate" if severity < SEVERE_FROM else "severe"


def grouped_split(groups: list[str], test_fraction: float, seed: int = 0) -> tuple[list[int], list[int]]:
    """Indices (train, test) where every group (e.g. crop) is split with the same ratio."""
    rng = random.Random(seed)
    train: list[int] = []
    test: list[int] = []
    for g in sorted(set(groups)):
        idxs = [i for i, x in enumerate(groups) if x == g]
        rng.shuffle(idxs)
        n_test = max(1, round(len(idxs) * test_fraction))
        test += idxs[:n_test]
        train += idxs[n_test:]
    return sorted(train), sorted(test)


def estimate_severity_color(image: Image.Image) -> float | None:
    """Classical baseline: no learning, just colour thresholds in HSV.

    Green pixels = healthy leaf. Yellow/orange/brown pixels = lesion, but only counted when they sit
    near green pixels (so brown soil far from any leaf is ignored). Returns None if no green is found.
    """
    hsv = np.array(image.convert("RGB").convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1] / 255, hsv[..., 2] / 255
    usable = (s > 0.25) & (v > 0.20)  # skips black padding, grey and washed-out pixels
    green = usable & (h >= 43) & (h <= 120)  # PIL hue 0-255 ~ 0-360 degrees: 60-170 degrees
    lesion_color = usable & (h >= 5) & (h < 43)  # roughly 7-60 degrees: orange, yellow, brown
    near_leaf = np.array(
        Image.fromarray((green * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(31))
    ) > 0
    lesion = lesion_color & near_leaf
    n_green, n_lesion = int(green.sum()), int(lesion.sum())
    total = n_green + n_lesion
    return n_lesion / total if total else None
