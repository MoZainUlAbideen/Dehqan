"""Build (image_path, label_index) lists from the class-folder datasets in data/."""

import random
from pathlib import Path

from vision.classes import CLASS_TO_INDEX, PLANTDOC_TO_PLANTVILLAGE
from vision.download_data import IMAGE_EXTS

Sample = tuple[Path, int]


def plantvillage_samples(
    root: Path, split: str, max_per_class: int | None, seed: int = 0
) -> list[Sample]:
    """PlantVillage images of the shared classes. split is 'train' or 'test' (filename prefix)."""
    rng = random.Random(seed)
    samples: list[Sample] = []
    for cls, idx in CLASS_TO_INDEX.items():
        class_dir = root / cls
        files = sorted(
            f for f in class_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTS and f.name.startswith(f"{split}_")
        )
        rng.shuffle(files)
        samples += [(f, idx) for f in files[:max_per_class]]
    return samples


def folder_samples(root: Path, class_names: list[str]) -> list[Sample]:
    """Images from root/<class_name>/ labelled by the class's position in class_names.
    Classes not in class_names are ignored; missing folders are skipped."""
    samples: list[Sample] = []
    for idx, name in enumerate(class_names):
        class_dir = root / name
        if class_dir.is_dir():
            samples += [(f, idx) for f in sorted(class_dir.iterdir()) if f.suffix.lower() in IMAGE_EXTS]
    return samples


def stratified_split(
    samples: list[Sample], test_fraction: float, seed: int = 0
) -> tuple[list[Sample], list[Sample]]:
    """Split so every class keeps the same train/test ratio. Returns (train, test)."""
    rng = random.Random(seed)
    by_class: dict[int, list[Sample]] = {}
    for s in samples:
        by_class.setdefault(s[1], []).append(s)
    train: list[Sample] = []
    test: list[Sample] = []
    for items in by_class.values():
        items = sorted(items)
        rng.shuffle(items)
        n_test = max(1, round(len(items) * test_fraction))
        test += items[:n_test]
        train += items[n_test:]
    return train, test


def plantdoc_samples(root: Path) -> list[Sample]:
    """All PlantDoc field images of the shared classes, labelled with the shared class index."""
    samples: list[Sample] = []
    for doc_name, pv_name in PLANTDOC_TO_PLANTVILLAGE.items():
        class_dir = root / doc_name
        if not class_dir.is_dir():
            continue
        idx = CLASS_TO_INDEX[pv_name]
        samples += [(f, idx) for f in sorted(class_dir.iterdir()) if f.suffix.lower() in IMAGE_EXTS]
    return samples
