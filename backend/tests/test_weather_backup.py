import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.spray_window import BACKUP_RULES, Rules, find_windows
from app.weather import BACKUP_NAME, PRIMARY_NAME, get_forecast
from data_sources import met_no
from data_sources.met_no import USER_AGENT, fetch_met_no, parse_met_no
from data_sources.open_meteo import Hour
from router.core import Agents, ask

FIXTURES = Path(__file__).parent / "fixtures"
REAL = json.loads((FIXTURES / "met_no_lahore.json").read_text())      # a real MET Norway response
PRIMARY_HOURS = [Hour(datetime(2026, 10, 15, h), 25.0, 0.0, 0.0, 5.0, 10.0) for h in range(24)]


def entry(t: datetime, temp=25.0, wind=2.0, rain=0.0, one_hour=True):
    data = {"instant": {"details": {"air_temperature": temp, "wind_speed": wind}}}
    if one_hour:
        data["next_1_hours"] = {"details": {"precipitation_amount": rain}}
    return {"time": t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "data": data}


# ---------- reading MET Norway ----------
def test_real_response_gives_about_two_and_a_half_days_of_hourly_data_in_pakistan_time():
    hours = parse_met_no(REAL)
    assert 60 <= len(hours) <= 70
    assert all(b.time - a.time == timedelta(hours=1) for a, b in zip(hours, hours[1:]))
    first_utc = datetime.fromisoformat(REAL["properties"]["timeseries"][0]["time"].replace("Z", "+00:00"))
    assert hours[0].time == (first_utc + timedelta(hours=5)).replace(tzinfo=None)         # UTC+5
    assert all(h.gust_kmh is None and h.rain_probability_pct is None for h in hours)         # never invented
    assert all(h.wind_kmh is not None and h.rain_mm is not None and 0 <= h.temperature_c <= 55 for h in hours)


def test_wind_is_converted_from_metres_per_second_to_kmh_and_rain_comes_from_the_next_hour():
    t = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)
    h = parse_met_no({"properties": {"timeseries": [entry(t, temp=31.5, wind=5.0, rain=1.2)]}})[0]
    assert h.wind_kmh == 18.0 and h.rain_mm == 1.2 and h.temperature_c == 31.5


def test_parsing_stops_when_the_data_changes_to_six_hour_steps_or_loses_the_one_hour_rain_amount():
    t = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)
    series = [entry(t + timedelta(hours=i)) for i in range(4)] + [entry(t + timedelta(hours=10))]   # a 6-hour jump
    assert len(parse_met_no({"properties": {"timeseries": series}})) == 4
    series = [entry(t + timedelta(hours=i)) for i in range(3)] + [entry(t + timedelta(hours=3), one_hour=False)]
    assert len(parse_met_no({"properties": {"timeseries": series}})) == 3


def test_a_response_of_the_wrong_shape_is_a_value_error():
    for bad in ({}, {"properties": {}}, {"properties": {"timeseries": []}}):
        with pytest.raises(ValueError):
            parse_met_no(bad)


def test_the_request_identifies_the_app_as_met_no_requires_and_is_cached():
    met_no._cache.clear()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, json=REAL)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    a = fetch_met_no(31.52, 74.36, client=client)
    b = fetch_met_no(31.521, 74.361, client=client)
    assert seen == [USER_AGENT] and a is b and "github.com" in USER_AGENT
    met_no._cache.clear()


# ---------- the rules adapt, and the strict default does not loosen ----------
def test_backup_rules_find_windows_where_the_strict_rules_correctly_find_none():
    hours = parse_met_no(REAL)
    assert find_windows(hours, Rules()) == []                          # no gust / probability data: never "safe" by default
    windows = find_windows(hours, BACKUP_RULES)
    by_time = {h.time: h for h in hours}
    for w in windows:                                                    # every hour of every window really obeys the backup rules
        t, end = datetime.fromisoformat(w.start), datetime.fromisoformat(w.end)
        while t <= end:
            h = by_time[t]
            assert h.rain_mm == 0 and h.wind_kmh <= BACKUP_RULES.max_wind_kmh and 5 <= t.hour < 19
            t += timedelta(hours=1)


def test_the_backup_asks_for_a_longer_dry_spell_than_the_primary():
    assert BACKUP_RULES.rainfast_hours == 9 > Rules().rainfast_hours
    # rain 5 hours after a window is acceptable for the primary rules but not for the backup rules
    hours = [Hour(datetime(2026, 10, 15, h), 25.0, None, 0.5 if h == 12 else 0.0, 5.0, None) for h in range(24)]
    morning = lambda rules: [w for w in find_windows(hours, rules) if int(w.start[11:13]) < 12]   # windows that start before the shower
    assert morning(Rules(needs_gust=False, needs_rain_probability=False))     # 3 dry hours after the window is enough
    assert not morning(BACKUP_RULES)                                           # the backup needs 9, so no morning window


def test_backup_rules_still_refuse_forecast_rain_and_strong_wind():
    rainy = [Hour(datetime(2026, 10, 15, h), 25.0, None, 0.4, 5.0, None) for h in range(24)]
    windy = [Hour(datetime(2026, 10, 15, h), 25.0, None, 0.0, 30.0, None) for h in range(24)]
    calm = [Hour(datetime(2026, 10, 15, h), 25.0, None, 0.0, 5.0, None) for h in range(24)]
    assert find_windows(rainy, BACKUP_RULES) == [] and find_windows(windy, BACKUP_RULES) == []
    assert find_windows(calm, BACKUP_RULES)


# ---------- choosing the source ----------
def boom(lat, lon):
    raise httpx.HTTPStatusError("429", request=httpx.Request("GET", "http://x"), response=httpx.Response(429))


def test_the_primary_source_is_used_when_it_works_and_the_backup_is_not_even_called():
    def backup(lat, lon):
        raise AssertionError("the backup must not be called")

    fc = get_forecast(31.5, 74.3, primary=lambda lat, lon: PRIMARY_HOURS, backup=backup)
    assert fc.source == PRIMARY_NAME and fc.backup is False and fc.rules == Rules()


def test_a_rate_limited_primary_falls_back_to_the_backup_with_the_adapted_rules():
    fc = get_forecast(31.5, 74.3, primary=boom, backup=lambda lat, lon: parse_met_no(REAL))
    assert fc.source == BACKUP_NAME and fc.backup is True and fc.rules == BACKUP_RULES


def test_a_bad_primary_response_also_falls_back():
    def garbled(lat, lon):
        raise ValueError("unexpected response")

    assert get_forecast(31.5, 74.3, primary=garbled, backup=lambda lat, lon: parse_met_no(REAL)).backup


def test_if_both_sources_fail_the_error_surfaces():
    with pytest.raises(httpx.ConnectError):
        get_forecast(31.5, 74.3, primary=boom, backup=lambda lat, lon: (_ for _ in ()).throw(httpx.ConnectError("down")))


# ---------- through the API ----------
def test_spray_window_endpoint_says_it_used_the_backup_and_why_it_is_limited():
    app = create_app(load_models=False, forecast_fn=boom, backup_forecast_fn=lambda lat, lon: parse_met_no(REAL))
    r = TestClient(app).post("/spray-window", json={"lat": 31.52, "lon": 74.36})
    body = r.json()
    assert r.status_code == 200 and body["source"] == BACKUP_NAME and body["backup"] is True
    assert "backup weather source" in body["note"] and body["forecast_hours"] < 100


def test_spray_window_endpoint_reports_the_primary_normally_and_502_if_both_fail():
    ok = TestClient(create_app(load_models=False, forecast_fn=lambda lat, lon: PRIMARY_HOURS)).post("/spray-window", json={"lat": 34.0, "lon": 71.5}).json()
    assert ok["source"] == PRIMARY_NAME and ok["backup"] is False and "backup weather source" not in ok["note"]
    dead = create_app(load_models=False, forecast_fn=boom, backup_forecast_fn=lambda lat, lon: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert TestClient(dead).post("/spray-window", json={"lat": 34.0, "lon": 71.5}).status_code == 502


# ---------- the question router tells the farmer too ----------
def agents_with_source(source):
    return Agents(
        spray=lambda lat, lon: ([{"start": "2026-10-15T05:00:00", "end": "2026-10-15T09:00:00", "hours": 5}], source),
        market_options=lambda: {"commodities": []}, market=lambda c, m: {}, field=lambda a, b: {},
    )


def test_a_backup_answer_does_not_claim_five_days_of_coverage():
    backup = ask("is it safe to spray tomorrow in Lahore?", agents_with_source(BACKUP_NAME))
    assert "next 2 days" in backup["answer_en"] and "اگلے دو دنوں" in backup["answer_ur"]
    assert "next 5 days" not in backup["answer_en"] and "پانچ" not in backup["answer_ur"]
    normal = ask("is it safe to spray tomorrow in Lahore?", agents_with_source(PRIMARY_NAME))
    assert "next 5 days" in normal["answer_en"] and "اگلے پانچ دنوں" in normal["answer_ur"]


def test_a_weather_answer_from_the_backup_says_so_in_both_languages():
    r = ask("is it safe to spray tomorrow in Lahore?", agents_with_source(BACKUP_NAME))
    assert "Backup weather source" in r["answer_en"] and "متبادل موسمی ذریعہ" in r["answer_ur"]
    assert r["results"]["weather"]["source"] == BACKUP_NAME
    plain = ask("is it safe to spray tomorrow in Lahore?", agents_with_source(PRIMARY_NAME))
    assert "Backup" not in plain["answer_en"] and "متبادل" not in plain["answer_ur"]
