"""Download model weights from a Hugging Face Hub *model repo* if they are not on disk yet.

Used at server start on hosts where data/models/ does not exist (Docker, Hugging Face Spaces):
    DEHQAN_MODEL_REPO=<your-username>/dehqan-models

The repo must contain the files listed in MODEL_FILES at its top level. CLIP is not copied: it is loaded
straight from the public openai/clip-vit-base-patch32 repo when no local copy exists.
"""

from pathlib import Path
from typing import Callable

from vision.download_data import DATA_DIR

MODELS_DIR = DATA_DIR / "models"
MODEL_FILES = ["field_tuned.pt", "severity.pt"]

Downloader = Callable[[str, str, Path], None]


def _hub_download(repo_id: str, filename: str, dest_dir: Path) -> None:
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=repo_id, filename=filename, local_dir=dest_dir)


def ensure_models(repo_id: str, models_dir: Path = MODELS_DIR, download: Downloader = _hub_download) -> list[str]:
    """Download each missing file in MODEL_FILES. Returns the names that were downloaded.

    Raises FileNotFoundError if a download did not produce the file, so a bad repo fails loudly at startup
    instead of serving a half-working API.
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for name in MODEL_FILES:
        if (models_dir / name).exists():
            continue
        download(repo_id, name, models_dir)
        if not (models_dir / name).exists():
            raise FileNotFoundError(f"{repo_id} did not provide {name}")
        fetched.append(name)
    return fetched
