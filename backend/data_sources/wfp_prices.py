"""WFP food prices for Pakistan (monthly retail prices in 5 markets), from the Humanitarian Data Exchange.

Source : https://data.humdata.org/dataset/wfp-food-prices-for-pakistan   (World Food Programme)
License: CC BY-IGO. Credit WFP when showing the data.

IMPORTANT: these are RETAIL prices collected for food-security monitoring, not what a farmer is paid at the
mandi. They move with farm-gate prices but are not the same thing. The market advice says so.

We commit a small filtered snapshot (data/wfp_pakistan_prices.csv) so the API needs no live download.
Refresh it with:   uv run python -m data_sources.wfp_prices refresh
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "wfp_pakistan_prices.csv"
HDX_API = "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-pakistan"
RESOURCE_NAME = "Pakistan - Food Prices"

# Commodities a farming household might sell or watch. WFP has no cotton or maize price for Pakistan.
KEEP = [
    "Wheat", "Wheat flour", "Rice (coarse)", "Rice (basmati, broken)", "Sugar",
    "Lentils (masur)", "Lentils (moong)", "Beans(mash)",
]
FIELDS = ["date", "market", "commodity", "unit", "price"]

Series = list[tuple[str, float]]  # [("2024-03", 123.0), ...] sorted by month


def build_snapshot(src_csv: Path, dest: Path = DATA_FILE) -> int:
    """Filter the full WFP CSV down to KEEP commodities, retail PKR prices. Returns rows written."""
    with open(src_csv, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if not r["date"].startswith("#")]
    keep = [r for r in rows if r["commodity"] in KEEP and r["pricetype"] == "Retail" and r["currency"] == "PKR"]
    keep.sort(key=lambda r: (r["commodity"], r["market"], r["date"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in keep:
            w.writerow([r["date"][:7], r["market"], r["commodity"], r["unit"], r["price"]])
    return len(keep)


def load_series(path: Path = DATA_FILE) -> dict[tuple[str, str], Series]:
    """{(commodity, market): [(month, price), ...]} sorted by month. One price per month (last one wins)."""
    by: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            by[(r["commodity"], r["market"])][r["date"]] = float(r["price"])
    return {k: sorted(v.items()) for k, v in by.items()}


def next_month(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y + (m == 12):04d}-{1 if m == 12 else m + 1:02d}"


def gap_free_tail(series: Series) -> Series:
    """The longest run of consecutive months that ends at the series' last month."""
    out: Series = []
    for month, price in reversed(series):
        if out and next_month(month) != out[0][0]:
            break
        out.insert(0, (month, price))
    return out


def unit_of(commodity: str, path: Path = DATA_FILE) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["commodity"] == commodity:
                return r["unit"]
    raise KeyError(commodity)


def refresh() -> None:
    """Download the latest CSV from HDX and rebuild the committed snapshot."""
    import httpx

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        meta = client.get(HDX_API).raise_for_status().json()["result"]
        url = next(r["url"] for r in meta["resources"] if r["name"] == RESOURCE_NAME)
        raw = client.get(url).raise_for_status().text
    tmp = DATA_FILE.with_suffix(".full.csv")
    tmp.write_text(raw, encoding="utf-8")
    try:
        print(f"snapshot rows: {build_snapshot(tmp)}  (source updated {meta['metadata_modified'][:10]})")
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["refresh"]:
        refresh()
    else:
        print(__doc__)
