import time
from datetime import date

import httpx
import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.warp import transform as warp_transform

from data_sources import sentinel
from data_sources.sentinel import (Scene, assess, bucket_of, build_timeline, compare_with_last_year, downsample,
                                   ndvi_stats, pick_scenes, read_ndvi, search_scenes)

nan = np.nan


def scene(day, cloud=5.0, name="s"):
    return Scene(day=day, cloud=cloud, red=f"{name}-red", nir=f"{name}-nir", scl=f"{name}-scl", scale=0.0001)


# ---------- pure maths ----------
def test_stats_ignore_nan_and_report_none_when_nothing_is_clear():
    a = np.array([[0.2, 0.4], [0.6, nan]])
    s = ndvi_stats(a)
    assert s["mean"] == pytest.approx(0.4) and s["median"] == pytest.approx(0.4) and s["valid_fraction"] == 0.75
    empty = ndvi_stats(np.full((3, 3), nan))
    assert empty["median"] is None and empty["valid_fraction"] == 0.0


def test_downsample_block_averages_and_marks_unclear_cells_none():
    a = np.array([[0.2, 0.4, nan, nan], [0.6, 0.8, nan, nan], [0.1, 0.1, 0.5, 0.5], [0.1, 0.1, 0.5, 0.5]])
    assert downsample(a, max_cells=2) == [[0.5, None], [0.1, 0.5]]
    assert len(downsample(np.zeros((5, 5)), max_cells=2)) == 2  # 5 cells, blocks of 3 -> 2 rows


def test_assess_bare_even_patchy_mixed_and_unknown():
    bare = np.full((10, 10), 0.1)
    assert assess(bare)["pattern"] == "bare"
    even = np.full((10, 10), 0.7) + np.linspace(-0.02, 0.02, 100).reshape(10, 10)
    assert assess(even)["pattern"] == "even"
    patchy = np.full((10, 10), 0.75)
    patchy[:3, :] = 0.3                                   # 30% of the patch is far less green
    r = assess(patchy)
    assert r["pattern"] == "patchy" and r["lagging_fraction"] == pytest.approx(0.3) and "30%" in r["message"]
    mixed = np.where(np.arange(100).reshape(10, 10) % 2 == 0, 0.6, 0.75)  # spread 0.15: between even and patchy
    assert assess(mixed)["pattern"] == "mixed"
    assert assess(np.full((4, 4), nan))["pattern"] == "unknown"


def test_the_message_never_names_a_cause():
    for arr in (np.full((5, 5), 0.1), np.full((5, 5), 0.7)):
        msg = assess(arr)["message"].lower()
        assert not any(w in msg for w in ("disease", "rust", "drought", "pest", "fungus"))


def test_compare_with_last_year():
    assert compare_with_last_year(0.5, 0.625)["change_pct"] == -20.0
    assert compare_with_last_year(0.5, 0.1) is None     # last year was bare: no meaningful comparison
    assert compare_with_last_year(None, 0.6) is None


# ---------- choosing scenes ----------
def test_pick_scenes_keeps_the_two_least_cloudy_per_period_oldest_first():
    scenes = [scene("2026-03-01", 40, "a"), scene("2026-03-02", 5, "b"), scene("2026-03-03", 1, "c"), scene("2026-03-04", 20, "d"), scene("2026-04-20", 3, "e")]
    picked = pick_scenes(scenes)
    in_march = [s for s in picked if s.day.startswith("2026-03")]
    assert len(in_march) == 2 and {s.red for s in in_march} == {"b-red", "c-red"} and picked[-1].day == "2026-04-20"
    assert [s.day for s in picked] == sorted(s.day for s in picked)


def test_search_scenes_parses_assets_and_skips_incomplete_items():
    def handler(request: httpx.Request) -> httpx.Response:
        asset = lambda h: {"href": h, "raster:bands": [{"scale": 0.0001}]}
        good = {"properties": {"datetime": "2026-03-05T06:00:00Z", "eo:cloud_cover": 3.5}, "assets": {"red": asset("r"), "nir": asset("n"), "scl": asset("s")}}
        bad = {"properties": {"datetime": "2026-03-06T06:00:00Z", "eo:cloud_cover": 1}, "assets": {"red": asset("r")}}
        return httpx.Response(200, json={"features": [good, bad]})

    out = search_scenes(34.0, 71.5, date(2026, 3, 1), date(2026, 3, 31), client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert [(s.day, s.cloud, s.red, s.scale) for s in out] == [("2026-03-05", 3.5, "r", 0.0001)]


# ---------- the timeline ----------
def fake_search(scenes):
    return lambda lat, lon, start, end: scenes


def test_timeline_drops_cloudy_scenes_counts_failures_and_keeps_the_clearest_per_period():
    scenes = [scene("2026-03-01", 2, "edge"), scene("2026-03-02", 4, "good"), scene("2026-04-20", 1, "cloudy"), scene("2026-06-01", 1, "broken")]

    def read(s, lat, lon, half_m):
        if s.red.startswith("broken"):
            raise OSError("network")
        if s.red.startswith("edge"):
            return np.full((6, 6), nan)                      # edge of the swath: no data
        if s.red.startswith("cloudy"):
            a = np.full((6, 6), 0.6); a[:4, :] = nan         # only a third clear: below the 60% rule
            return a
        return np.full((6, 6), 0.65)

    r = build_timeline(34.0, 71.5, search=fake_search(scenes), read=read, today=date(2026, 7, 1))
    assert r["scenes_failed"] == 1
    assert [p["date"] for p in r["points"]] == ["2026-03-02"]  # the empty edge scene lost; cloudy and broken dropped
    assert r["points"][0]["median"] == 0.65 and len(r["points"][0]["grid"]) == 6


def test_timeline_gives_up_waiting_after_the_time_budget_and_says_so():
    scenes = [scene("2026-03-02", 2, "fast"), scene("2026-05-10", 2, "slow")]

    def read(s, lat, lon, half_m):
        if s.red.startswith("slow"):
            time.sleep(1.5)
        return np.full((4, 4), 0.5)

    t0 = time.monotonic()
    r = build_timeline(34.0, 71.5, search=fake_search(scenes), read=read, today=date(2026, 7, 1), budget_s=0.3)
    assert time.monotonic() - t0 < 1.2 and r["scenes_timed_out"] == 1 and [p["date"] for p in r["points"]] == ["2026-03-02"]


# ---------- reading real GeoTIFFs (small synthetic ones) ----------
def make_scene(tmp_path, red_dn=500, nir_dn=3000, cloud_block=True):
    """100x100 px at 10 m in UTM 42N. The scene-classification layer is 50x50 at 20 m with a cloud block that,
    for a pin at pixel (row 50, col 60), sits in the TOP-LEFT quarter of a 200 m window."""
    x0, y0 = 700000.0, 3800000.0
    tr10 = Affine(10, 0, x0, 0, -10, y0)
    tr20 = Affine(20, 0, x0, 0, -20, y0)

    def write(name, data, transform):
        path = tmp_path / name
        with rasterio.open(path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1, dtype=data.dtype, crs="EPSG:32642", transform=transform) as ds:
            ds.write(data, 1)
        return str(path)

    red = write("red.tif", np.full((100, 100), red_dn, dtype="uint16"), tr10)
    nir = write("nir.tif", np.full((100, 100), nir_dn, dtype="uint16"), tr10)
    scl_data = np.full((50, 50), 4, dtype="uint8")
    if cloud_block:
        scl_data[20:25, 25:30] = 9   # 20 m pixels rows 20-24, cols 25-29 = 10 m pixels rows 40-49, cols 50-59
    scl = write("scl.tif", scl_data, tr20)
    lon, lat = warp_transform("EPSG:32642", "EPSG:4326", [x0 + 60.5 * 10], [y0 - 50.5 * 10])
    return Scene("2026-03-05", 1.0, red, nir, scl, 0.0001), lat[0], lon[0]


def test_read_ndvi_masks_exactly_the_cloudy_block_and_computes_ndvi():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        s, lat, lon = make_scene(Path(d))
        nd = read_ndvi(s, lat, lon, half_m=100)
    assert nd.shape == (20, 20)
    cloudy = np.zeros((20, 20), dtype=bool)
    cloudy[0:10, 0:10] = True                                   # top-left quarter, as built
    assert np.isnan(nd[cloudy]).all(), "the cloud block must be masked where it really is"
    assert not np.isnan(nd[~cloudy]).any(), "everything else must stay clear"
    assert np.allclose(nd[~cloudy], (0.3 - 0.05) / (0.3 + 0.05), atol=1e-4)


def test_a_misaligned_mask_would_be_caught():
    """Regression for a real bug: the scene-classification window was computed from the window's own transform, so
    the mask was read from the wrong place. A clear scene must stay fully clear, and a cloudy one must not."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        s, lat, lon = make_scene(Path(d), cloud_block=False)
        assert np.isnan(read_ndvi(s, lat, lon, half_m=100)).sum() == 0


def test_catalogue_offset_is_not_applied():
    """The catalogue lists a -0.1 offset, but the files carry none: red DN of 500 is reflectance 0.05, not -0.05.
    Applying the offset would push NDVI above 1 (physically impossible); without it NDVI is 0.71."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        s, lat, lon = make_scene(Path(d), red_dn=500, nir_dn=3000, cloud_block=False)
        nd = read_ndvi(s, lat, lon, half_m=100)
    assert 0.70 < np.nanmedian(nd) < 0.72
    assert (nd <= 1).all() and (nd >= -1).all()


def test_a_second_candidate_is_only_read_when_the_first_is_unusable():
    reads = []

    def read(s, lat, lon, half_m):
        reads.append(s.red)
        return np.full((4, 4), nan) if s.red.startswith("edge") else np.full((4, 4), 0.6)

    # period A: first candidate is fine, so the second is never touched. Period B: first is empty, so the second is read.
    scenes = [scene("2026-03-02", 1, "okA"), scene("2026-03-03", 9, "spareA"), scene("2026-05-10", 1, "edgeB"), scene("2026-05-11", 9, "okB")]
    r = build_timeline(34.0, 71.5, search=fake_search(scenes), read=read, today=date(2026, 7, 1))
    assert "spareA-red" not in reads and "okB-red" in reads
    assert [p["date"] for p in r["points"]] == ["2026-03-02", "2026-05-11"]
