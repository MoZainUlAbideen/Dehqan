"""Download the lab (PlantVillage) and field (PlantDoc) datasets into data/.

Usage (from backend/):
    uv run python -m vision.download_data            # both
    uv run python -m vision.download_data plantvillage
    uv run python -m vision.download_data plantdoc

Both end up as plain image folders: data/<name>/<class_name>/<image>.jpg
"""

import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Parquet copies download as a few big files (the folder-of-jpgs copies get rate-limited by the Hub).
PLANTVILLAGE_REPO = "BrandonFors/Plant-Diseases-PlantVillage-Dataset"  # lab images, 38 classes
PLANTDOC_REPO = "Project-AgML/plant_doc_classification"  # field images, 28 classes


def count_images(root: Path) -> dict[str, int]:
    """Count images per class folder under root. Returns {class_name: n_images}."""
    counts: dict[str, int] = {}
    for class_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        n = sum(1 for f in class_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
        if n:
            counts[class_dir.name] = n
    return counts


def export_split(ds, out: Path, prefix: str) -> None:
    """Write a HF dataset with image+label columns into out/<class>/<prefix>_<i>.jpg."""
    names = ds.features["label"].names
    for i, row in enumerate(ds):
        class_dir = out / names[row["label"]]
        class_dir.mkdir(parents=True, exist_ok=True)
        path = class_dir / f"{prefix}_{i:05d}.jpg"
        if not path.exists():
            row["image"].convert("RGB").save(path, quality=92)


def download_plantvillage() -> Path:
    from datasets import load_dataset

    out = DATA_DIR / "plantvillage"
    for split in ("train", "test"):
        export_split(load_dataset(PLANTVILLAGE_REPO, split=split), out, split)
    return out


def download_plantdoc() -> Path:
    from datasets import load_dataset

    out = DATA_DIR / "plantdoc"
    export_split(load_dataset(PLANTDOC_REPO, split="train"), out, "doc")
    return out


def summarize(name: str, root: Path) -> None:
    counts = count_images(root)
    print(f"\n{name}: {sum(counts.values())} images, {len(counts)} classes  ({root})")
    for cls, n in counts.items():
        print(f"  {n:6d}  {cls}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "plantvillage"):
        summarize("PlantVillage (lab)", download_plantvillage())
    if which in ("all", "plantdoc"):
        summarize("PlantDoc (field)", download_plantdoc())
