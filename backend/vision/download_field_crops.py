"""Download real field-photo datasets for Pakistan-relevant crops (cotton, corn) into data/field_crops/.

Usage (from backend/):
    uv run python -m vision.download_field_crops

Sources (all CC-BY-4.0 / CC-BY-NC-4.0, hosted on the HF Hub by the AgML project):
- cotton_bd:   cotton leaves, Bangladesh, 7 classes incl. Curl Virus (CLCuV, a major Pakistan cotton disease)
- cotton_alt:  cotton leaves, a DIFFERENT source/camera setup, 5 classes -> cross-source test set
- corn_anhui:  corn leaves photographed in fields in Anhui, China, 6 classes

None of these are from Pakistan. We say so in the README; they are the closest public field data we found.
Wheat is missing on purpose: the only public wheat-disease set on the Hub has unnamed classes (0-6).
"""

from vision.download_data import DATA_DIR, export_split, summarize

FIELD_SOURCES = {
    "cotton_bd": "Project-AgML/cotton_leaf_disease_classification_bangladesh_2",
    "cotton_alt": "Project-AgML/cotton_leaf_disease_classification",
    "corn_anhui": "Project-AgML/corn_leaf_disease_classification",
}
FIELD_DIR = DATA_DIR / "field_crops"


if __name__ == "__main__":
    from datasets import load_dataset

    for name, repo in FIELD_SOURCES.items():
        out = FIELD_DIR / name
        export_split(load_dataset(repo, split="train"), out, "img")
        summarize(name, out)
