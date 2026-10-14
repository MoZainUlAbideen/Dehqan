"""Field report for a pin: the NDVI timeline plus a plain-language reading and a comparison with last year.

Heavy (it reads satellite imagery), so results are cached in memory for CACHE_SECONDS per rounded location.
"""

import time
from datetime import date, datetime, timedelta, timezone

from data_sources.sentinel import build_timeline, compare_with_last_year

CACHE_SECONDS = 6 * 3600
MONTHS = 14            # 12 months shown, plus enough to find the same time last year
LAST_YEAR_WINDOW = 21  # days either side of "a year ago" in which a scene counts as the same time of year

CAVEATS = [
    "NDVI shows how green the ground looks from space (about 10 m detail). It cannot tell you why.",
    "The picture is a square around your pin; it may include roads, trees or neighbouring fields.",
    "Comparing with last year is rough: sowing dates and rainfall differ every year.",
    "The satellite passes about every 5 days, but clouds hide many dates.",
    "This is not a diagnosis. Use it together with a leaf photo and your local agriculture extension office.",
]
SOURCE = "Copernicus Sentinel-2 L2A imagery (open data), via the Earth Search catalogue on AWS"

_cache: dict[tuple, tuple[float, dict]] = {}


def nearest_last_year(points: list[dict], latest_day: str) -> dict | None:
    """The point closest to one year before latest_day, if within LAST_YEAR_WINDOW days."""
    target = date.fromisoformat(latest_day) - timedelta(days=365)
    best = None
    for p in points:
        gap = abs((date.fromisoformat(p["date"]) - target).days)
        if gap <= LAST_YEAR_WINDOW and (best is None or gap < best[0]):
            best = (gap, p)
    return best[1] if best else None


def field_report(lat: float, lon: float, size_m: int = 300, timeline=build_timeline, now: float | None = None) -> dict:
    key = (round(lat, 3), round(lon, 3), size_m)
    now = time.monotonic() if now is None else now
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]

    tl = timeline(lat, lon, half_m=size_m / 2, months=MONTHS)
    points = tl["points"]
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=366)).isoformat()
    shown = [p for p in points if p["date"] >= cutoff]       # the last 12 months
    latest = shown[-1] if shown else None
    last_year = None
    if latest:
        old = nearest_last_year(points, latest["date"])
        last_year = compare_with_last_year(latest["median"], old["median"]) if old else None
        if last_year and old:
            last_year["last_year_date"] = old["date"]
    report = {
        "center": {"lat": lat, "lon": lon}, "size_m": size_m,
        "scenes_found": tl["scenes_found"], "scenes_used": len(shown), "scenes_failed": tl["scenes_failed"],
        "scenes_timed_out": tl["scenes_timed_out"], "seconds": tl["seconds"],
        "points": shown, "latest": latest, "last_year": last_year,
        "message": ("No clear satellite view of this spot in the last year (cloud, or outside coverage)." if not latest else latest["assessment"]["message"]),
        "caveats": CAVEATS, "source": SOURCE,
    }
    if latest:  # do not cache an empty answer: it may be a temporary failure
        _cache[key] = (now, report)
    return report
