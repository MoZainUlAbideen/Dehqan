"""Fetch PDSNet (field photos with pixel-level lesion masks) into data/raw/pdsnet.parquet.

Usage (from backend/):
    uv run python -m vision.download_pdsnet

240 images (apple cedar rust, soybean bacterial blight, wheat stripe rust), 11 MB, CC-BY-NC-4.0.
Mask classes: 0 background, 1 healthy leaf, 2 disease spots.
"""

from vision.download_data import DATA_DIR
from vision.download_negatives import stream_download

URL = "https://huggingface.co/datasets/Project-AgML/pdsnet_field_plant_disease_segmentation/resolve/main/data/train-00000-of-00001.parquet"
DEST = DATA_DIR / "raw" / "pdsnet.parquet"

if __name__ == "__main__":
    stream_download(URL, DEST)
    print(f"saved {DEST}")
