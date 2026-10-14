"""Find safe spray windows in an hourly forecast.

An hour is "ok" for spraying when ALL of these hold (and a value we cannot see counts as NOT ok):
  - wind at or below max_wind_kmh and gusts at or below max_gust_kmh   (spray drift)
  - rain probability at or below max_rain_prob_pct and rain_mm == 0    (wash-off)
  - temperature at or below max_temp_c                                  (evaporation / crop stress)
  - local hour within [earliest_hour, latest_hour)                      (daylight, working hours)
A window also needs the following `rainfast_hours` hours to stay dry, because spray needs time to dry in.

IMPORTANT: these thresholds are common agronomy rules of thumb, NOT official advice and NOT from a cited
Pakistani source. The real rain-free period depends on the product label. The result says so, and the
numbers are configurable. Dose and PPE are a separate matter and come from cited sources (rag/guardrail.py).
"""

from dataclasses import dataclass

from data_sources.open_meteo import Hour


@dataclass(frozen=True)
class Rules:
    max_wind_kmh: float = 15.0
    max_gust_kmh: float = 25.0
    max_rain_prob_pct: float = 30.0
    max_temp_c: float = 35.0
    earliest_hour: int = 5
    latest_hour: int = 19          # exclusive
    rainfast_hours: int = 3
    min_window_hours: int = 2


@dataclass(frozen=True)
class Window:
    start: str                      # ISO local time of the first safe hour
    end: str                        # ISO local time of the LAST safe hour (inclusive)
    hours: int
    max_wind_kmh: float
    max_rain_prob_pct: float


def _dry(h: Hour, rules: Rules) -> bool:
    return (
        h.rain_probability_pct is not None and h.rain_probability_pct <= rules.max_rain_prob_pct
        and h.rain_mm is not None and h.rain_mm == 0
    )


def _ok(h: Hour, rules: Rules) -> bool:
    if None in (h.wind_kmh, h.gust_kmh, h.temperature_c):
        return False
    return (
        _dry(h, rules)
        and h.wind_kmh <= rules.max_wind_kmh
        and h.gust_kmh <= rules.max_gust_kmh
        and h.temperature_c <= rules.max_temp_c
        and rules.earliest_hour <= h.time.hour < rules.latest_hour
    )


def find_windows(hours: list[Hour], rules: Rules = Rules()) -> list[Window]:
    """All runs of consecutive safe hours that are long enough. Hours must be consecutive and sorted."""
    safe = []
    for i, h in enumerate(hours):
        after = hours[i + 1 : i + 1 + rules.rainfast_hours]
        # Not enough forecast left to confirm the rain-free period -> cannot call it safe.
        rainfast = len(after) == rules.rainfast_hours and all(_dry(a, rules) for a in after)
        safe.append(_ok(h, rules) and rainfast)

    windows: list[Window] = []
    i = 0
    while i < len(hours):
        if not safe[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(hours) and safe[j + 1]:
            j += 1
        run = hours[i : j + 1]
        if len(run) >= rules.min_window_hours:
            windows.append(Window(
                start=run[0].time.isoformat(), end=run[-1].time.isoformat(), hours=len(run),
                max_wind_kmh=max(h.wind_kmh for h in run),
                max_rain_prob_pct=max(h.rain_probability_pct for h in run),
            ))
        i = j + 1
    return windows


NOTE = (
    "Thresholds are general agronomy rules of thumb, not official advice. "
    "Check the product label for its rain-free period."
)
