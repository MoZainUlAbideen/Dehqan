"""Fetch the CLIP model files into data/models/clip/ with a plain streaming download.

Usage (from backend/):
    uv run python -m vision.download_clip

The huggingface_hub client hung at 0 bytes on this machine; a plain HTTP download worked.
"""

from vision.download_data import DATA_DIR
from vision.download_negatives import parallel_download, stream_download

CLIP_DIR = DATA_DIR / "models" / "clip"
BASE = "https://huggingface.co/openai/clip-vit-base-patch32/resolve/main/"
FILES = [
    "config.json", "preprocessor_config.json", "merges.txt", "vocab.json", "tokenizer.json",
    "tokenizer_config.json", "special_tokens_map.json", "pytorch_model.bin",
]

if __name__ == "__main__":
    for name in FILES:
        print(f"fetching {name}", flush=True)
        (parallel_download if name.endswith(".bin") else stream_download)(BASE + name, CLIP_DIR / name)
    print("CLIP READY", flush=True)
