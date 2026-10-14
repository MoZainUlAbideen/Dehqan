import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.spray_window import Rules, find_windows
from data_sources import open_meteo
from data_sources.open_meteo import Hour, fetch_forecast, parse_hourly

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_peshawar.json"
START = datetime(2026, 10, 14, 0, 0)


def make_hours(overrides: dict | None = None) -> list[Hour]:
    """48 calm, dry, mild hours; `overrides` maps hour-index -> dict of field changes."""
    overrides = overrides or {}
    base = dict(temperature_c=25.0, rain_probability_pct=0.0, rain_mm=0.0, wind_kmh=5.0, gust_kmh=10.0)
    out = []
    for i in range(48):
        out.append(Hour(time=START + timedelta(hours=i), **{**base, **overrides.get(i, {})}))
    return out


def test_calm_dry_days_give_a_window_each_day_within_working_hours():
    wins = find_windows(make_hours())
    assert len(wins) == 2
    # day 1: hours 5..18 are in range, but 17,18 lack 3 following dry hours? they are dry, so ok -> 5..18
    assert wins[0].start == "2026-10-14T05:00:00" and wins[0].end == "2026-10-14T18:00:00"
    assert wins[0].hours == 14


def test_wind_breaks_a_window_in_two():
    hours = make_hours({10: dict(wind_kmh=30.0, gust_kmh=40.0)})
    wins = find_windows(hours)
    day1 = [w for w in wins if w.start.startswith("2026-10-14")]
    assert [(w.start[11:13], w.end[11:13]) for w in day1] == [("05", "09"), ("11", "18")]


def test_rain_soon_after_removes_the_hours_before_it_too():
    # rain at 12:00 -> hours 9,10,11 are not rainfast (3h dry needed), so the first window ends at 08:00
    hours = make_hours({12: dict(rain_mm=1.2, rain_probability_pct=80.0)})
    wins = find_windows(hours)
    first = wins[0]
    assert first.start.endswith("05:00:00") and first.end.endswith("08:00:00")


def test_unknown_values_are_never_safe():
    hours = make_hours({i: dict(rain_probability_pct=None) for i in range(48)})
    assert find_windows(hours) == []
    assert find_windows(make_hours({i: dict(wind_kmh=None) for i in range(48)})) == []


def test_too_hot_and_outside_working_hours_are_excluded():
    assert find_windows(make_hours({i: dict(temperature_c=40.0) for i in range(48)})) == []
    wins = find_windows(make_hours())
    assert all(5 <= int(w.start[11:13]) and int(w.end[11:13]) < 19 for w in wins)


def test_last_hours_of_forecast_cannot_be_confirmed_rainfast():
    hours = make_hours()[:20]  # forecast ends at 19:00 index 19; hours 17+ lack 3 following hours
    wins = find_windows(hours)
    assert wins[-1].end.endswith("16:00:00")


def test_short_windows_are_dropped():
    hours = make_hours({i: dict(wind_kmh=30.0) for i in range(48) if i not in (7,)})
    assert find_windows(hours, Rules(min_window_hours=2)) == []


def test_real_peshawar_response_parses_and_every_window_hour_obeys_the_rules():
    payload = json.loads(FIXTURE.read_text())
    hours = parse_hourly(payload)
    assert len(hours) == 120 and hours[0].time == datetime(2026, 10, 14, 0, 0)
    rules = Rules()
    by_time = {h.time: h for h in hours}
    for w in find_windows(hours, rules):
        t = datetime.fromisoformat(w.start)
        end = datetime.fromisoformat(w.end)
        while t <= end:
            h = by_time[t]
            assert h.wind_kmh <= rules.max_wind_kmh and h.gust_kmh <= rules.max_gust_kmh
            assert h.rain_mm == 0 and h.rain_probability_pct <= rules.max_rain_prob_pct
            assert rules.earliest_hour <= t.hour < rules.latest_hour
            t += timedelta(hours=1)


def test_parse_hourly_rejects_wrong_shape():
    with pytest.raises(ValueError):
        parse_hourly({"nope": 1})


def test_fetch_forecast_uses_client_and_caches(monkeypatch):
    open_meteo._cache.clear()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["latitude"])
        return httpx.Response(200, json=json.loads(FIXTURE.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    a = fetch_forecast(34.01, 71.52, client=client)
    b = fetch_forecast(34.02, 71.53, client=client)  # same 0.1-degree cell -> cached
    assert len(calls) == 1 and a is b and len(a) == 120
    open_meteo._cache.clear()


def test_fetch_forecast_raises_on_http_error():
    open_meteo._cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_forecast(10.0, 10.0, client=client, sleep=lambda s: None)


# ---------- retries and honest logging when the weather service misbehaves ----------
def test_a_brief_rate_limit_is_retried_and_then_succeeds():
    open_meteo._cache.clear()
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, json={"error": True, "reason": "Too many requests"})
        return httpx.Response(200, json=json.loads(FIXTURE.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pauses = []
    hours = fetch_forecast(34.0, 71.5, client=client, sleep=pauses.append)
    assert len(hours) == 120 and len(calls) == 3 and len(pauses) == 2 and pauses[1] > pauses[0]
    open_meteo._cache.clear()


def test_it_gives_up_after_the_retries_and_the_log_says_why(caplog):
    open_meteo._cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"reason": "Too many requests from this IP"})))
    with caplog.at_level("WARNING", logger="dehqan.open_meteo"), pytest.raises(httpx.HTTPStatusError):
        fetch_forecast(11.0, 11.0, client=client, sleep=lambda s: None)
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "HTTP 429" in messages and "Too many requests from this IP" in messages and "attempt 3/3" in messages


def test_a_client_error_is_not_retried():
    open_meteo._cache.clear()
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"reason": "bad coordinates"})

    with pytest.raises(httpx.HTTPStatusError):
        fetch_forecast(12.0, 12.0, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    assert len(calls) == 1


def test_a_response_of_the_wrong_shape_is_reported_as_a_value_error_after_retry_free_failure():
    open_meteo._cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": True, "reason": "oops"})))
    with pytest.raises(ValueError):
        fetch_forecast(13.0, 13.0, client=client, sleep=lambda s: None)
