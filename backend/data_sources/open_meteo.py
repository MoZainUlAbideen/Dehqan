"""Open-Meteo hourly forecast client (free, no API key).

Docs: https://open-meteo.com/en/docs
Times come back as local-time strings for the requested timezone (we ask for Asia/Karachi).
Missing values (null) are kept as None: the spray-window logic treats "unknown" as NOT safe.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

log = logging.getLogger("dehqan.open_meteo")
RETRY_STATUSES = {429, 500, 502, 503, 504}
API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m"
CACHE_SECONDS = 30 * 60

_cache: dict[tuple[float, float, int], tuple[float, list["Hour"]]] = {}


@dataclass(frozen=True)
class Hour:
    time: datetime               # local time (Asia/Karachi)
    temperature_c: float | None
    rain_probability_pct: float | None
    rain_mm: float | None
    wind_kmh: float | None
    gust_kmh: float | None


def parse_hourly(payload: dict) -> list[Hour]:
    """Turn an Open-Meteo JSON response into a list of Hour. Raises ValueError if the shape is wrong."""
    try:
        h = payload["hourly"]
        times = h["time"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected Open-Meteo response: missing {e}") from e
    return [
        Hour(
            time=datetime.fromisoformat(t),
            temperature_c=h["temperature_2m"][i],
            rain_probability_pct=h["precipitation_probability"][i],
            rain_mm=h["precipitation"][i],
            wind_kmh=h["wind_speed_10m"][i],
            gust_kmh=h["wind_gusts_10m"][i],
        )
        for i, t in enumerate(times)
    ]


def _why(e: Exception) -> str:
    """One line saying what went wrong, for the log."""
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}: {e.response.text[:140]!r}"
    return f"{type(e).__name__}: {str(e)[:140]}"


def fetch_forecast(lat: float, lon: float, days: int = 5, client: httpx.Client | None = None, retries: int = 2, sleep=time.sleep) -> list[Hour]:
    """Hourly forecast for the next `days` days. Cached 30 min per ~11 km grid cell to be polite to the API.

    Retries briefly on network errors and on 429/5xx (a shared hosting IP can be rate-limited for a moment) and logs the
    exact reason each time, so a failure shows up in the host's log instead of as a bare "unavailable"."""
    key = (round(lat, 1), round(lon, 1), days)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    params = {
        "latitude": lat, "longitude": lon, "hourly": HOURLY_FIELDS,
        "timezone": "Asia/Karachi", "forecast_days": days,
    }
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        for attempt in range(retries + 1):
            try:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                hours = parse_hourly(resp.json())
                break
            except (httpx.HTTPError, ValueError) as e:
                retryable = isinstance(e, httpx.TransportError) or (isinstance(e, httpx.HTTPStatusError) and e.response.status_code in RETRY_STATUSES)
                log.warning("open-meteo attempt %d/%d failed: %s", attempt + 1, retries + 1, _why(e))
                if attempt < retries and retryable:
                    sleep(0.6 * (attempt + 1))
                    continue
                raise
    finally:
        if own:
            client.close()
    _cache[key] = (time.monotonic(), hours)
    return hours
