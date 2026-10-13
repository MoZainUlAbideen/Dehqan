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
