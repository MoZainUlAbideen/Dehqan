"""Sentinel-2 NDVI for a small patch of land around a pin, from the open AWS archive (no account needed).

Data  : Sentinel-2 L2A Cloud-Optimised GeoTIFFs, found through the Earth Search STAC API.
        https://earth-search.aws.element84.com/v1   (Copernicus Sentinel data, free and open)
How   : for each scene we read only a tiny window (a few hundred metres wide) of the red and near-infrared bands,
        so a scene costs a few hundred KB, not the 100 MB tile. Cloud, shadow and water pixels are masked with the
        scene classification layer (SCL).
Units : reflectance = DN x 0.0001. We deliberately do NOT apply the "-0.1 offset" that the catalogue lists for
        processing baseline 04.00 and later: in these files the red band reads well below 1000 (median about 500 over
        wheat), which is impossible if that offset had been added, and applying it gives NDVI above 1. Scanning March
        scenes of the same wheat area for 2019 to 2026 (baselines 02.11 to 05.12), ignoring the offset gives a stable
        NDVI of 0.66 to 0.79 every year. See tests/test_sentinel.py::test_catalogue_offset_is_not_applied.
NDVI  : (NIR - red) / (NIR + red). Dense healthy crop is high (about 0.6 to 0.9), bare soil is low (about 0.05
        to 0.2). NDVI shows how green the ground looks from space. It does NOT say why.
"""

import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
VALID_SCL = (4, 5)  # vegetation, not-vegetated (bare soil). Clouds, shadow, water, snow, no-data are dropped.
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MULTIRANGE="YES")
MIN_VALID_FRACTION = 0.6   # a scene needs at least this share of clear pixels in the window to be used
GRID_MAX = 20              # the picture sent to the browser is at most GRID_MAX x GRID_MAX cells


@dataclass(frozen=True)
class Scene:
    day: str                 # YYYY-MM-DD (acquisition date, UTC)
    cloud: float             # whole-tile cloud cover %, from the catalogue
    red: str
    nir: str
    scl: str
    scale: float


# ---------- finding scenes ----------
def search_scenes(lat: float, lon: float, start: date, end: date, max_cloud: float = 60, client: httpx.Client | None = None) -> list[Scene]:
    """All scenes covering the pin between start and end, newest first."""
    body = {
        "collections": [COLLECTION],
        "bbox": [lon - 0.001, lat - 0.001, lon + 0.001, lat + 0.001],
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": 200,
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        features = client.post(STAC_SEARCH, json=body).raise_for_status().json().get("features", [])
    finally:
        if own:
            client.close()
    scenes = []
    for f in features:
        a = f["assets"]
        if not all(k in a for k in ("red", "nir", "scl")):
            continue
        band = (a["red"].get("raster:bands") or [{}])[0]
        scenes.append(Scene(
            day=f["properties"]["datetime"][:10], cloud=float(f["properties"].get("eo:cloud_cover", 100)),
            red=a["red"]["href"], nir=a["nir"]["href"], scl=a["scl"]["href"],
            scale=float(band.get("scale", 0.0001)),
        ))
    return scenes


def bucket_of(day: str, every_days: int = 14) -> int:
    return date.fromisoformat(day).toordinal() // every_days


def pick_scenes(scenes: list[Scene], every_days: int = 14, per_bucket: int = 2) -> list[Scene]:
    """Up to `per_bucket` scenes per `every_days` period, those with the least tile cloud. Oldest first.

    Two candidates, because the least-cloudy scene can be one whose edge misses the pin (all no-data); the timeline
    keeps whichever candidate turns out clearer on the ground.
    """
    groups: dict[int, list[Scene]] = {}
    for s in scenes:
        groups.setdefault(bucket_of(s.day, every_days), []).append(s)
    picked = [s for g in groups.values() for s in sorted(g, key=lambda x: x.cloud)[:per_bucket]]
    return sorted(picked, key=lambda s: s.day)


# ---------- reading one scene ----------
def _window(ds, lon: float, lat: float, half_m: float) -> Window:
    left, bottom, right, top = transform_bounds("EPSG:4326", ds.crs, lon, lat, lon, lat)
    cx, cy = (left + right) / 2, (bottom + top) / 2
    return from_bounds(cx - half_m, cy - half_m, cx + half_m, cy + half_m, ds.transform).round_offsets().round_lengths()


def read_ndvi(scene: Scene, lat: float, lon: float, half_m: float) -> np.ndarray:
    """NDVI of the window around the pin; NaN where the pixel is cloudy, shadowed, water or has no data."""
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(scene.red) as ds:
            win = _window(ds, lon, lat, half_m)
            inside = win.col_off >= 0 and win.row_off >= 0 and win.col_off + win.width <= ds.width and win.row_off + win.height <= ds.height
            red = ds.read(1, window=win, boundless=not inside, fill_value=0).astype("float32")
            geo_bounds = ds.window_bounds(win)  # ground coordinates of the window, from the WHOLE raster's transform
        with rasterio.open(scene.nir) as ds:
            nir = ds.read(1, window=win, boundless=not inside, fill_value=0).astype("float32")
        with rasterio.open(scene.scl) as ds:  # 20 m layer: resample (nearest) onto the 10 m grid
            scl = ds.read(1, window=ds.window(*geo_bounds), out_shape=red.shape, resampling=Resampling.nearest, boundless=True, fill_value=0)
    r = red * scene.scale   # scale only: see the module docstring about the catalogue's offset
    n = nir * scene.scale
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (n - r) / (n + r)
    ndvi = np.where(np.isin(scl, VALID_SCL) & (red > 0) & (nir > 0), ndvi, np.nan)
    return np.clip(ndvi, -1, 1)


# ---------- turning pixels into numbers (pure, tested) ----------
def ndvi_stats(ndvi: np.ndarray) -> dict:
    """Summary of the clear pixels. All NDVI values are None if nothing is clear."""
    valid = ndvi[~np.isnan(ndvi)]
    frac = float(valid.size / ndvi.size) if ndvi.size else 0.0
    if valid.size == 0:
        return {"valid_fraction": 0.0, "mean": None, "median": None, "p10": None, "p90": None, "spread": None}
    p10, p90 = np.percentile(valid, [10, 90])
    return {
        "valid_fraction": round(frac, 3), "mean": round(float(valid.mean()), 3), "median": round(float(np.median(valid)), 3),
        "p10": round(float(p10), 3), "p90": round(float(p90), 3), "spread": round(float(p90 - p10), 3),
    }


def downsample(ndvi: np.ndarray, max_cells: int = GRID_MAX) -> list[list[float | None]]:
    """Block-average to at most max_cells x max_cells for the picture. Cells with no clear pixel are None."""
    h, w = ndvi.shape
    block = max(1, -(-max(h, w) // max_cells))  # ceiling division
    rows = []
    for i in range(0, h, block):
        row = []
        for j in range(0, w, block):
            cell = ndvi[i : i + block, j : j + block]
            clear = cell[~np.isnan(cell)]
            row.append(round(float(clear.mean()), 2) if clear.size else None)
        rows.append(row)
    return rows


SPARSE = 0.2        # median NDVI below this: bare ground or very thin cover, so there is no crop to judge
EVEN_SPREAD = 0.12  # p90 - p10 below this: the patch looks even
PATCHY_SPREAD = 0.2 # p90 - p10 at or above this: clearly uneven
PATCH_DROP = 0.15   # a pixel this far below the patch median counts as "lagging"


def assess(ndvi: np.ndarray) -> dict:
    """Plain-language reading of ONE date: bare, even, patchy, or mixed. Says what it sees, never the cause."""
    stats = ndvi_stats(ndvi)
    if stats["median"] is None:
        return {"pattern": "unknown", "message": "No clear pixels on this date (cloud, shadow or water).", "lagging_fraction": None}
    valid = ndvi[~np.isnan(ndvi)]
    lagging = float((valid < stats["median"] - PATCH_DROP).mean())
    if stats["median"] < SPARSE:
        return {"pattern": "bare", "message": "Mostly bare ground or very thin cover: there is little crop to judge yet (or it is fallow).", "lagging_fraction": round(lagging, 3)}
    if stats["spread"] < EVEN_SPREAD:
        return {"pattern": "even", "message": "The patch looks even: greenness is similar across it, so there is no sign of a patch problem.", "lagging_fraction": round(lagging, 3)}
    if stats["spread"] >= PATCHY_SPREAD and 0.05 <= lagging <= 0.6:
        return {"pattern": "patchy", "message": f"Uneven: about {round(lagging * 100)}% of the patch is clearly less green than the rest. That points to a problem in part of the field, not the whole field.", "lagging_fraction": round(lagging, 3)}
    return {"pattern": "mixed", "message": "Some variation across the patch, not clearly in one area.", "lagging_fraction": round(lagging, 3)}


def compare_with_last_year(now_median: float | None, last_year_median: float | None) -> dict | None:
    """How the patch's greenness compares with the same time last year. Timing differences are normal."""
    if now_median is None or last_year_median is None or last_year_median < SPARSE:
        return None
    change = (now_median - last_year_median) / last_year_median
    return {"now": now_median, "last_year": last_year_median, "change_pct": round(change * 100, 1)}


# ---------- the whole timeline ----------
def build_timeline(lat: float, lon: float, half_m: float = 150, months: int = 12, today: date | None = None, budget_s: float = 45, workers: int = 6, search=search_scenes, read=read_ndvi) -> dict:
    """Timeline of NDVI around the pin.

    Phase 1 reads the least-cloudy scene of every two-week period. Phase 2 reads a second candidate only for periods
    where phase 1 gave nothing usable (cloud over the pin, or the pin sat in the empty edge of a satellite pass).
    Stops waiting after budget_s seconds in total and returns what it has, so a slow host answers instead of timing out.
    """
    today = today or datetime.now(timezone.utc).date()
    found = search(lat, lon, today - timedelta(days=int(months * 30.5) + 20), today)
    groups: dict[int, list[Scene]] = {}
    for sc in found:
        groups.setdefault(bucket_of(sc.day), []).append(sc)
    for g in groups.values():
        g.sort(key=lambda x: x.cloud)

    t0 = time.monotonic()
    pool = ThreadPoolExecutor(workers)
    failed = timed_out = 0
    usable: dict[int, dict] = {}   # period -> its best point so far

    def run(batch: list[Scene]) -> None:
        nonlocal failed, timed_out
        futures = {pool.submit(read, sc, lat, lon, half_m): sc for sc in batch}
        done, not_done = wait(futures, timeout=max(0.0, budget_s - (time.monotonic() - t0)))
        timed_out += len(not_done)
        for fut in done:
            sc = futures[fut]
            try:
                ndvi = fut.result()
            except Exception:  # one bad scene must not break the timeline
                failed += 1
                continue
            stats = ndvi_stats(ndvi)
            if stats["valid_fraction"] < MIN_VALID_FRACTION:
                continue
            point = {"date": sc.day, "tile_cloud_pct": round(sc.cloud, 1), **stats, "assessment": assess(ndvi), "grid": downsample(ndvi)}
            b = bucket_of(sc.day)
            if b not in usable or (point["valid_fraction"], -point["tile_cloud_pct"]) > (usable[b]["valid_fraction"], -usable[b]["tile_cloud_pct"]):
                usable[b] = point

    run([g[0] for g in groups.values()])
    second = [g[1] for b, g in groups.items() if b not in usable and len(g) > 1]
    if second and time.monotonic() - t0 < budget_s:
        run(second)
    pool.shutdown(wait=False, cancel_futures=True)

    points = sorted(usable.values(), key=lambda p: p["date"])
    return {
        "scenes_found": len(found), "periods": len(groups), "scenes_used": len(points), "scenes_failed": failed,
        "scenes_timed_out": timed_out, "seconds": round(time.monotonic() - t0, 1), "points": points,
    }
