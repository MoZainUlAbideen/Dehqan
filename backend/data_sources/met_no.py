"""MET Norway (Norwegian Meteorological Institute) Locationforecast: the BACKUP weather source.

Used only when Open-Meteo refuses us (for example its daily request limit, which a shared hosting IP address can hit).
Free, no key; it asks callers to identify themselves with a User-Agent. https://api.met.no/weatherapi/locationforecast/2.0/documentation

What it does NOT have, and the spray logic must not pretend otherwise:
  - no wind-gust values, and no rain-probability values, for Pakistan (only the rain AMOUNT of each coming hour);
  - one-hour steps only for about the first 64 hours; after that the data is in 6-hour steps, which we do not use.
So a backup forecast covers about 2.5 days, and spray windows from it use BACKUP_RULES (see app/spray_window.py).
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from data_sources.open_meteo import Hour

log = logging.getLogger("dehqan.met_no")
URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
USER_AGENT = "dehqan-app/0.1 (+https://github.com/MoZainUlAbideen/Dehqan)"
PKT = timezone(timedelta(hours=5))  # Pakistan Standard Time: UTC+5, no daylight saving since 2009
CACHE_SECONDS = 30 * 60

_cache: dict[tuple[float, float], tuple[float, list[Hour]]] = {}


def parse_met_no(payload: dict) -> list[Hour]:
    """Hourly steps from the start of the forecast until the data stops being one hour apart.

    Gust and rain probability are None (not provided). Raises ValueError if the response has the wrong shape or no hourly data.
    """
    try:
        series = payload["properties"]["timeseries"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected MET Norway response: missing {e}") from e
    hours: list[Hour] = []
    previous = None
    for entry in series:
        t = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        if previous is not None and t - previous != timedelta(hours=1):
            break                                  # the data switched to 6-hour steps
        data = entry["data"]
        one_hour = data.get("next_1_hours")
        if one_hour is None:                       # no one-hour rain amount: not an hourly step any more
            break
        details = data["instant"]["details"]
        wind = details.get("wind_speed")           # metres per second
        hours.append(Hour(
            time=t.astimezone(PKT).replace(tzinfo=None),
            temperature_c=details.get("air_temperature"),
            rain_probability_pct=None,
            rain_mm=one_hour["details"].get("precipitation_amount"),
            wind_kmh=None if wind is None else round(wind * 3.6, 1),
            gust_kmh=None,
        ))
        previous = t
    if not hours:
        raise ValueError("MET Norway response has no hourly data")
    return hours


def fetch_met_no(lat: float, lon: float, client: httpx.Client | None = None) -> list[Hour]:
    """Hourly forecast (about 64 hours) from MET Norway. Cached 30 minutes per ~1 km cell."""
    key = (round(lat, 2), round(lon, 2))
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.get(URL, params={"lat": round(lat, 4), "lon": round(lon, 4)}, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        hours = parse_met_no(resp.json())
    except (httpx.HTTPError, ValueError) as e:
        log.warning("met.no failed: %s: %s", type(e).__name__, str(e)[:160])
        raise
    finally:
        if own:
            client.close()
    _cache[key] = (time.monotonic(), hours)
    return hours
