"""Download NON-crop photos (faces, vehicles, animals, objects) to test the "not a crop" gate.

Usage (from backend/):
    uv run python -m vision.download_negatives

Source: Caltech-101 (101 everyday-object categories). Plant-like categories (sunflower, lotus,
water lily) are dropped so a "leaf-ish" photo is never labelled a negative. Saves a random sample to
data/negatives/caltech101/.

The parquet file is fetched with a plain streaming HTTP download: the huggingface_hub client hung at
0 bytes on this machine while a plain download worked.

Limitation: these are everyday-object photos. Harder negatives a farmer might send (bare soil, weeds,
fruit, a hand holding a leaf) are NOT covered; the README says so.
"""

import random
import urllib.request
from pathlib import Path

from vision.download_data import DATA_DIR

NEGATIVES_DIR = DATA_DIR / "negatives"
PARQUET_URL = "https://huggingface.co/datasets/flwrlabs/caltech101/resolve/main/data/train-00000-of-00001.parquet"
EXCLUDE_LABELS = {"sunflower", "lotus", "water_lilly"}
N_NEGATIVES = 500


def stream_download(url: str, dest: Path) -> None:
    """Download url to dest in 1 MB chunks, printing progress. Skips if dest already exists."""
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as f:
        total, done = int(resp.headers.get("Content-Length", 0)), 0
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            print(f"  downloaded {done / 1e6:.0f}/{total / 1e6:.0f} MB", flush=True)
    tmp.rename(dest)


def parallel_download(url: str, dest: Path, workers: int = 8, chunk_mb: int = 8) -> None:
    """Download a big file with several HTTP Range requests at once (single streams were ~6x slower here).

    Each chunk is written at its own offset and retried with growing pauses (network blips happen).
    Finished chunks are recorded next to the file, so re-running resumes instead of starting over.
    Skips if dest already exists.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor

    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    probe = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(probe, timeout=60) as resp:
        total = int(resp.headers["Content-Range"].split("/")[1])
    tmp = dest.with_suffix(".part")
    log = dest.with_suffix(".chunks")  # one finished chunk start offset per line
    finished = {int(x) for x in log.read_text().split()} if tmp.exists() and log.exists() else set()
    if not (tmp.exists() and tmp.stat().st_size == total):
        finished = set()
        with open(tmp, "wb") as f:
            f.truncate(total)
        log.write_text("")
    size = chunk_mb << 20
    ranges = [(s, min(s + size, total) - 1) for s in range(0, total, size) if s not in finished]
    done = len(finished) * size
    if finished:
        print(f"  resuming: {len(finished)} chunks already done", flush=True)

    def fetch(r: tuple[int, int]) -> None:
        nonlocal done
        for attempt in range(8):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={r[0]}-{r[1]}"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                if len(data) != r[1] - r[0] + 1:
                    raise OSError("short read")
                with open(tmp, "r+b") as f:
                    f.seek(r[0])
                    f.write(data)
                with open(log, "a") as f:
                    f.write(f"{r[0]}\n")
                done += len(data)
                print(f"  downloaded {done / 1e6:.0f}/{total / 1e6:.0f} MB", flush=True)
                return
            except OSError:
                if attempt == 7:
                    raise
                time.sleep(min(2 ** attempt, 30))

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(fetch, ranges))
    log.unlink(missing_ok=True)
    tmp.rename(dest)


def sample_negatives(parquet: Path, seed: int = 0) -> int:
    from datasets import load_dataset

    ds = load_dataset("parquet", data_files=str(parquet), split="train")
    label_feature = ds.features.get("label")
    names = getattr(label_feature, "names", None)
    print(f"columns={list(ds.features)}", flush=True)
    idxs = list(range(len(ds)))
    random.Random(seed).shuffle(idxs)
    out = NEGATIVES_DIR / "caltech101"
    out.mkdir(parents=True, exist_ok=True)
    saved = 0
    for i in idxs:
        row = ds[i]
        if names and names[row["label"]].lower() in EXCLUDE_LABELS:
            continue
        row["image"].convert("RGB").save(out / f"{saved:04d}.jpg", quality=92)
        saved += 1
        if saved >= N_NEGATIVES:
            break
    return saved


if __name__ == "__main__":
    raw = DATA_DIR / "raw" / "caltech101.parquet"
    stream_download(PARQUET_URL, raw)
    print(f"caltech101: saved {sample_negatives(raw)} images", flush=True)
