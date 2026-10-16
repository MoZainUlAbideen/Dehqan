"""Download the JIC wheat disease photos (Zenodo 7573133, CC-BY-4.0, ~1 GB) and unzip them.

999 photos of yellow rust, brown rust, septoria, mildew and healthy wheat leaves, taken in realistic field
conditions (James Hutton / John Innes Centre; Long et al. 2023, Plant Pathology).

Run:  uv run python -m vision.download_wheat
"""

import zipfile

from vision.download_data import DATA_DIR
from vision.download_negatives import parallel_download

URL = "https://zenodo.org/api/records/7573133/files/Long%202023%20Plant%20Path%20999%20photos.zip/content"
OUT = DATA_DIR / "wheat_jic"

if __name__ == "__main__":
    zpath = OUT / "photos.zip"
    parallel_download(URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(OUT / "photos")
    print("done:", OUT / "photos")
