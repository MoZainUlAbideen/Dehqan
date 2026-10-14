"""One place that decides which weather source to use, so the API and the question router behave the same.

Open-Meteo is the primary source (hourly for 5 days, with wind gusts and rain probability). If it fails (for example its
daily limit for our hosting IP is used up), MET Norway is used instead, with rules that only ask for the data it has.
The answer always says which source it came from.
"""

import logging
from dataclasses import dataclass
from typing import Callable

import httpx

from app.spray_window import BACKUP_RULES, Rules, Window, find_windows
from data_sources.met_no import fetch_met_no
from data_sources.open_meteo import Hour, fetch_forecast

log = logging.getLogger("dehqan.weather")

PRIMARY_NAME = "open-meteo"
BACKUP_NAME = "met.no (backup)"
BACKUP_NOTE = (
    "A backup weather source is being used because the main one is unavailable: it covers only about 2 days and has no "
    "wind-gust or rain-probability data, so spray windows rest on wind speed and forecast rain amount alone, and a window is only offered if it stays dry for 9 hours after."
)


@dataclass(frozen=True)
class Forecast:
    hours: list[Hour]
    source: str
    rules: Rules

    @property
    def backup(self) -> bool:
        return self.source != PRIMARY_NAME


def get_forecast(
    lat: float, lon: float,
    primary: Callable[[float, float], list[Hour]] = fetch_forecast,
    backup: Callable[[float, float], list[Hour]] = fetch_met_no,
) -> Forecast:
    """Primary forecast, or the backup if the primary fails. Raises only if BOTH fail (the backup's error)."""
    try:
        return Forecast(primary(lat, lon), PRIMARY_NAME, Rules())
    except (httpx.HTTPError, ValueError) as e:
        log.warning("primary weather source failed (%s: %s); trying the backup", type(e).__name__, str(e)[:120])
    return Forecast(backup(lat, lon), BACKUP_NAME, BACKUP_RULES)


def spray_windows(lat: float, lon: float, primary=fetch_forecast, backup=fetch_met_no) -> tuple[Forecast, list[Window]]:
    fc = get_forecast(lat, lon, primary, backup)
    return fc, find_windows(fc.hours, fc.rules)
