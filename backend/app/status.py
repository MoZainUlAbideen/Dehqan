"""Dependency health: is each outside service the API relies on actually reachable right now, and if not, why?

GET /status runs one tiny real request against each service and reports the result. It exists because "weather
service unavailable" is useless for debugging: this says WHICH service, with which HTTP status or error. Results are
cached for CACHE_SECONDS so the endpoint cannot be used to hammer the services.
"""

import time
from typing import Callable

import httpx

from forecast import service as market_service

CACHE_SECONDS = 60
OPEN_METEO = "https://api.open-meteo.com/v1/forecast?latitude=31.5&longitude=74.3&hourly=temperature_2m&forecast_days=1"
STAC = "https://earth-search.aws.element84.com/v1/search"
STAC_BODY = {"collections": ["sentinel-2-l2a"], "bbox": [74.3, 31.5, 74.31, 31.51], "limit": 1}

_cache: tuple[float, dict] | None = None


def _timed(call: Callable[[], httpx.Response]) -> dict:
    t0 = time.monotonic()
    try:
        r = call()
        ms = round((time.monotonic() - t0) * 1000)
        if r.status_code == 200:
            return {"ok": True, "http_status": 200, "ms": ms}
        return {"ok": False, "http_status": r.status_code, "ms": ms, "error": r.text[:160].replace("\n", " ")}
    except httpx.HTTPError as e:
        return {"ok": False, "http_status": None, "ms": round((time.monotonic() - t0) * 1000), "error": f"{type(e).__name__}: {str(e)[:120]}"}


def check(models_loaded: bool, client: httpx.Client | None = None, now: float | None = None) -> dict:
    global _cache
    now = time.monotonic() if now is None else now
    if _cache and now - _cache[0] < CACHE_SECONDS:
        return {**_cache[1], "models_loaded": models_loaded, "cached": True}
    own = client is None
    client = client or httpx.Client(timeout=8)
    try:
        services = {
            "open_meteo_weather": _timed(lambda: client.get(OPEN_METEO)),
            "sentinel2_catalogue": _timed(lambda: client.post(STAC, json=STAC_BODY)),
        }
    finally:
        if own:
            client.close()
    try:
        prices = {"ok": True, "data_as_of": market_service.options()["data_as_of"]}
    except Exception as e:  # the snapshot file missing or unreadable
        prices = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    services["price_data"] = prices
    report = {"ok": all(s["ok"] for s in services.values()), "services": services}
    _cache = (now, report)
    return {**report, "models_loaded": models_loaded, "cached": False}
