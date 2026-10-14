"""Download model files from a Hugging Face Hub *model repo* if they are not on disk yet.

Used at image build time and at server start on hosts without a data/models/ folder (e.g. Render):
    DEHQAN_MODEL_REPO=<your-username>/<model-repo>

The repo must contain the ONNX files below inside an `onnx/` folder (produce them with vision.export_onnx).
"""

from pathlib import Path
from typing import Callable

from vision.download_data import DATA_DIR

MODELS_DIR = DATA_DIR / "models"
ONNX_FILES = [
    "onnx/classifier.onnx",
    "onnx/severity.onnx",
    "onnx/clip_vision_int8.onnx",
    "onnx/clip_text.npy",
    "onnx/meta.json",
]

Downloader = Callable[[str, str, Path], None]


def _hub_download(repo_id: str, filename: str, dest_dir: Path) -> None:
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=repo_id, filename=filename, local_dir=dest_dir)


def ensure_models(
    repo_id: str,
    models_dir: Path = MODELS_DIR,
    download: Downloader = _hub_download,
    files: list[str] = ONNX_FILES,
) -> list[str]:
    """Download each missing file. Returns the names that were downloaded.

    Raises FileNotFoundError if a download did not produce the file, so a bad repo fails loudly at startup
    instead of serving a half-working API.
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for name in files:
        if (models_dir / name).exists():
            continue
        download(repo_id, name, models_dir)
        if not (models_dir / name).exists():
            raise FileNotFoundError(f"{repo_id} did not provide {name}")
        fetched.append(name)
    return fetched
