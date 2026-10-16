"""A second, independent wheat source for the cross-camera test: Ma et al. 2024 "Wheat Dataset" (Zenodo 15621359, CC-BY-4.0).

It is an object-detection set (boxes, not whole-image labels) taken by other people with other cameras, in China.
We read ONLY its test split straight out of the 1.1 GB zip (HTTP Range requests, no full download), cut out every box
of the four classes we share with the JIC set, and save the crops:
    Powdery Mildew -> mildew,  Leaf Rust -> brown_rust,  Stripe Rust -> yellow_rust,  Wheat Leaf -> healthy

Run:  uv run python -m vision.download_wheat_xiaomai
"""

import io
import urllib.request
import zipfile

from PIL import Image

from vision.download_data import DATA_DIR

URL = "https://zenodo.org/api/records/15621359/files/xiaomai.zip/content"
OUT = DATA_DIR / "wheat_xiaomai"
CLASS_IDS = {0: "mildew", 2: "brown_rust", 3: "yellow_rust", 6: "healthy"}   # ids from xiaomai.yaml
MIN_SIDE = 64
MAX_PER_CLASS = 150   # keep the classes balanced enough to read, and the run short


class RangeFile(io.RawIOBase):
    """A read-only file backed by HTTP Range requests, so zipfile can pull single members from a huge remote zip."""

    def __init__(self, url: str):
        self.url = url
        self.n = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD")).headers["Content-Length"])
        self.p = 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.p

    def seek(self, offset, whence=0):
        self.p = offset if whence == 0 else self.p + offset if whence == 1 else self.n + offset
        return self.p

    def readinto(self, b):
        k = min(len(b), self.n - self.p)
        if k <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.p}-{self.p + k - 1}"})
        data = urllib.request.urlopen(req, timeout=60).read()
        b[:len(data)] = data
        self.p += len(data)
        return len(data)


def main() -> None:
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(URL), 1 << 20))
    labels = [n for n in z.namelist() if n.startswith("xiaomai/labels/test/") and n.endswith(".txt")]
    counts = {name: 0 for name in CLASS_IDS.values()}
    for ln in sorted(labels):
        boxes = []
        for row in z.read(ln).decode().splitlines():
            parts = row.split()
            if len(parts) >= 5 and int(parts[0]) in CLASS_IDS and counts[CLASS_IDS[int(parts[0])]] < MAX_PER_CLASS:
                boxes.append((CLASS_IDS[int(parts[0])], *map(float, parts[1:5])))
        if not boxes:
            continue
        stem = ln.rsplit("/", 1)[1][:-4]
        img_name = next((f"xiaomai/images/test/{stem}{e}" for e in (".jpg", ".png", ".jpeg") if f"xiaomai/images/test/{stem}{e}" in z.NameToInfo), None)
        if img_name is None:
            continue
        img = Image.open(io.BytesIO(z.read(img_name))).convert("RGB")
        W, H = img.size
        for i, (name, xc, yc, w, h) in enumerate(boxes):
            x0, y0, x1, y1 = int((xc - w / 2) * W), int((yc - h / 2) * H), int((xc + w / 2) * W), int((yc + h / 2) * H)
            if min(x1 - x0, y1 - y0) < MIN_SIDE or counts[name] >= MAX_PER_CLASS:
                continue
            d = OUT / name
            d.mkdir(parents=True, exist_ok=True)
            img.crop((x0, y0, x1, y1)).save(d / f"{stem}_{i}.jpg", quality=92)
            counts[name] += 1
        print(counts, flush=True)
    print("done", counts)


if __name__ == "__main__":
    main()
