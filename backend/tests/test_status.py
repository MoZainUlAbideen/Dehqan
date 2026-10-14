import httpx
from fastapi.testclient import TestClient

from app import status
from app.main import create_app


def client_for(open_meteo, stac):
    def handler(request: httpx.Request) -> httpx.Response:
        return open_meteo(request) if "open-meteo" in request.url.host else stac(request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def ok(request):
    return httpx.Response(200, json={})


def test_everything_reachable_reports_ok_with_timings():
    status._cache = None
    r = status.check(True, client=client_for(ok, ok), now=0.0)
    assert r["ok"] is True and r["models_loaded"] is True and r["cached"] is False
    assert r["services"]["open_meteo_weather"]["ok"] and r["services"]["sentinel2_catalogue"]["ok"]
    assert len(r["services"]["price_data"]["data_as_of"]) == 7


def test_a_rate_limited_weather_service_is_named_but_a_working_backup_keeps_weather_ok():
    status._cache = None
    limited = lambda request: httpx.Response(429, json={"error": True, "reason": "Daily API request limit exceeded"})
    r = status.check(True, client=client_for(limited, ok), now=0.0)
    w = r["services"]["open_meteo_weather"]
    assert w["ok"] is False and w["http_status"] == 429 and "limit exceeded" in w["error"]
    assert r["services"]["met_no_weather_backup"]["ok"] is True
    assert r["ok"] is True and r["weather_source_in_use"] == "met.no (backup)"      # the app still has weather


def test_with_both_weather_sources_down_the_report_says_weather_is_unavailable():
    status._cache = None
    down = lambda request: httpx.Response(503, json={"reason": "down"})

    def handler(request):
        return ok(request) if "earth-search" in request.url.host else down(request)

    r = status.check(True, client=httpx.Client(transport=httpx.MockTransport(handler)), now=0.0)
    assert r["ok"] is False and r["weather_source_in_use"] is None


def test_a_network_error_is_reported_with_its_type():
    status._cache = None

    def down(request):
        raise httpx.ConnectTimeout("timed out")

    r = status.check(False, client=client_for(ok, down), now=0.0)
    s = r["services"]["sentinel2_catalogue"]
    assert s["ok"] is False and s["http_status"] is None and "ConnectTimeout" in s["error"] and r["models_loaded"] is False


def test_results_are_cached_for_a_minute_so_the_endpoint_cannot_hammer_the_services():
    status._cache = None
    calls = []

    def counting(request):
        calls.append(1)
        return httpx.Response(200, json={})

    c = client_for(counting, counting)
    status.check(True, client=c, now=0.0)
    n = len(calls)
    again = status.check(True, client=c, now=30.0)
    assert len(calls) == n and again["cached"] is True
    status.check(True, client=c, now=61.0)
    assert len(calls) == 2 * n


def test_status_endpoint_returns_the_report(monkeypatch):
    monkeypatch.setattr(status, "check", lambda models_loaded, **k: {"ok": True, "services": {}, "models_loaded": models_loaded, "cached": False})
    body = TestClient(create_app(load_models=False)).get("/status").json()
    assert body["ok"] is True and body["models_loaded"] is False
