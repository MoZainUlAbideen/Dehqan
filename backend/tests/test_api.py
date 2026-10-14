import io
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from app.main import MAX_UPLOAD_BYTES, create_app
from app.pipeline import Prediction
from data_sources.open_meteo import parse_hourly

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_peshawar.json"
HOURS = parse_hourly(json.loads(FIXTURE.read_text()))


def png_bytes(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 160, 40)).save(buf, format="PNG")
    return buf.getvalue()


def fake_components(gate=0.9, label="Tomato___Late_blight", conf=0.95, sev=0.2, seen=None):
    def classifier(img):
        if seen is not None:
            seen.append(img.size)
        return Prediction(label, conf)

    return SimpleNamespace(gate=lambda img: gate, classifier=classifier, severity=lambda img: sev)


def client(components=None, **kw):
    return TestClient(create_app(components=components, load_models=False, **kw))


def post_image(c, data=None, content_type="image/png", name="leaf.png"):
    return c.post("/diagnose", files={"file": (name, data if data is not None else png_bytes(), content_type)})


def test_health_reports_whether_models_are_loaded():
    assert client().get("/health").json() == {"status": "ok", "models_loaded": False}
    assert client(fake_components()).get("/health").json()["models_loaded"] is True


def test_about_exposes_threshold_and_notes():
    body = client().get("/about").json()
    assert body["abstain_threshold"] == 0.9 and "rules of thumb" in body["spray_window_note"]


def test_diagnose_happy_path():
    r = post_image(client(fake_components()))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "diagnosis" and body["label"] == "Tomato___Late_blight"
    assert body["severity_grade"] == "moderate" and body["limitations"]


def test_diagnose_not_a_crop_and_uncertain_are_normal_200_answers():
    assert post_image(client(fake_components(gate=0.1))).json()["status"] == "not_a_crop"
    assert post_image(client(fake_components(conf=0.3))).json()["status"] == "uncertain"


def test_diagnose_503_when_models_not_loaded():
    assert post_image(client()).status_code == 503


def test_diagnose_rejects_wrong_type_corrupt_and_oversized():
    c = client(fake_components())
    assert post_image(c, b"hello", "text/plain", "x.txt").status_code == 415
    assert post_image(c, b"not really a png", "image/png").status_code == 400
    assert post_image(c, b"\x00" * (MAX_UPLOAD_BYTES + 10), "image/png").status_code == 413


def test_diagnose_downscales_big_photos_before_the_models_see_them():
    seen: list = []
    c = client(fake_components(seen=seen))
    assert post_image(c, png_bytes((3000, 2000))).status_code == 200
    assert max(seen[0]) <= 1024


def test_diagnose_is_rate_limited_per_client():
    c = client(fake_components(), diagnose_per_min=2)
    assert [post_image(c).status_code for _ in range(3)] == [200, 200, 429]


def test_spray_window_returns_windows_from_forecast():
    c = client(forecast_fn=lambda lat, lon: HOURS)
    r = c.post("/spray-window", json={"lat": 34.01, "lon": 71.52})
    body = r.json()
    assert r.status_code == 200 and body["forecast_hours"] == 120 and body["windows"]
    assert body["forecast_start"] == "2026-10-14T00:00:00"
    assert "rules of thumb" in body["note"]


def test_spray_window_rejects_coordinates_outside_pakistan():
    c = client(forecast_fn=lambda lat, lon: HOURS)
    assert c.post("/spray-window", json={"lat": 51.5, "lon": -0.1}).status_code == 422
    assert c.post("/spray-window", json={"lat": "x", "lon": 71}).status_code == 422


def test_spray_window_502_when_weather_service_fails():
    def boom(lat, lon):
        raise httpx.ConnectError("down")

    assert client(forecast_fn=boom).post("/spray-window", json={"lat": 34.0, "lon": 71.5}).status_code == 502


# ---------- market agent endpoints (use the committed WFP price snapshot) ----------
def test_market_options_lists_commodities_with_their_markets_and_source():
    body = client().get("/market/options").json()
    names = {c["name"]: c for c in body["commodities"]}
    assert "Wheat" in names and "Peshawar" in names["Wheat"]["markets"]
    assert names["Wheat"]["unit"].startswith("PKR per")
    assert "WFP" in body["source"] or "World Food Programme" in body["source"]
    assert len(body["data_as_of"]) == 7  # YYYY-MM


def test_market_analysis_has_history_forecast_range_honest_method_and_caveats():
    r = client().get("/market", params={"commodity": "Wheat", "market": "Peshawar"})
    assert r.status_code == 200
    b = r.json()
    assert len(b["history"]) == 36 and len(b["forecast"]) == 3
    assert all(f["low"] <= f["high"] for f in b["forecast"])
    assert b["signal"] in {"hold", "sell", "none"}
    assert "beats_naive" in b["method"] and b["method"]["name"]
    assert any("retail" in c for c in b["caveats"])
    assert b["track_record"]["months_checked"] == 12 and b["source"]


def test_market_unknown_or_too_gappy_series_is_a_clear_404():
    c = client()
    assert c.get("/market", params={"commodity": "Cotton", "market": "Lahore"}).status_code == 404
    assert c.get("/market", params={"commodity": "Wheat flour", "market": "Peshawar"}).status_code == 404  # data has big holes


def test_market_requires_both_parameters():
    assert client().get("/market", params={"commodity": "Wheat"}).status_code == 422


# ---------- satellite field report endpoint (fake report function: no network) ----------
FAKE_REPORT = {"center": {"lat": 34.0, "lon": 71.5}, "size_m": 300, "points": [], "latest": None, "message": "ok", "caveats": ["c"], "source": "s"}


def test_field_ndvi_passes_pin_and_size_to_the_report_function_and_returns_it():
    seen = {}

    def fake(lat, lon, size_m):
        seen.update(lat=lat, lon=lon, size_m=size_m)
        return FAKE_REPORT

    r = client(field_fn=fake).post("/field-ndvi", json={"lat": 34.0, "lon": 71.5, "size_m": 500})
    assert r.status_code == 200 and r.json()["message"] == "ok" and seen == {"lat": 34.0, "lon": 71.5, "size_m": 500}


def test_field_ndvi_defaults_the_size_and_validates_inputs():
    c = client(field_fn=lambda lat, lon, size_m: {"size_m": size_m})
    assert c.post("/field-ndvi", json={"lat": 34.0, "lon": 71.5}).json()["size_m"] == 300
    assert c.post("/field-ndvi", json={"lat": 51.5, "lon": -0.1}).status_code == 422          # not Pakistan
    assert c.post("/field-ndvi", json={"lat": 34.0, "lon": 71.5, "size_m": 50}).status_code == 422
    assert c.post("/field-ndvi", json={"lat": 34.0, "lon": 71.5, "size_m": 5000}).status_code == 422


def test_field_ndvi_502_when_the_satellite_service_fails():
    def boom(lat, lon, size_m):
        raise httpx.ConnectError("down")

    assert client(field_fn=boom).post("/field-ndvi", json={"lat": 34.0, "lon": 71.5}).status_code == 502


def test_field_ndvi_is_rate_limited(monkeypatch):
    monkeypatch.setenv("DEHQAN_FIELD_PER_MIN", "2")
    c = client(field_fn=lambda lat, lon, size_m: FAKE_REPORT)
    codes = [c.post("/field-ndvi", json={"lat": 34.0, "lon": 71.5}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------- the /ask supervisor router ----------
def test_ask_routes_a_price_question_to_the_market_agent_with_real_data():
    r = client().post("/ask", json={"text": "wheat price in Lahore"})
    assert r.status_code == 200
    b = r.json()
    assert b["route"] == "market" and b["understood"]["commodity"] == "Wheat" and b["results"]["market"]["market"] == "Lahore"
    assert "retail prices" in b["answer_en"] and b["answer_ur"]


def test_ask_routes_a_spray_question_through_the_injected_forecast():
    c = client(forecast_fn=lambda lat, lon: HOURS)
    b = c.post("/ask", json={"text": "kal spray kab karun, Peshawar mein"}).json()
    assert b["route"] == "weather" and b["results"]["weather"]["windows"] and "Peshawar" in b["answer_en"]


def test_ask_refuses_pesticide_questions_and_never_calls_a_data_service():
    def boom(*a, **k):
        raise AssertionError("no data service may run for a pesticide question")

    c = client(forecast_fn=boom, field_fn=boom)
    b = c.post("/ask", json={"text": "which pesticide and what dose for rust?"}).json()
    assert b["route"] == "treatment" and b["results"]["treatment"] == {"refused": True}
    assert "extension office" in b["answer_en"]


def test_ask_answers_in_the_language_asked_and_says_what_is_missing():
    b = client().post("/ask", json={"text": "کیا آج سپرے کرنا ٹھیک ہے"}).json()
    assert b["language"] == "ur" and b["needs"] == "location" and b["answer"] == b["answer_ur"]


def test_ask_validates_input_and_needs_both_coordinates_or_none():
    c = client()
    assert c.post("/ask", json={"text": ""}).status_code == 422
    assert c.post("/ask", json={"text": "x" * 501}).status_code == 422
    assert c.post("/ask", json={"text": "weather", "lat": 31.5}).status_code == 422
    assert c.post("/ask", json={"text": "weather", "lat": 51.5, "lon": -0.1}).status_code == 422


def test_ask_502_when_a_data_service_fails_and_is_rate_limited(monkeypatch):
    def boom(lat, lon):
        raise httpx.ConnectError("down")

    assert client(forecast_fn=boom).post("/ask", json={"text": "spray weather in Lahore"}).status_code == 502
    monkeypatch.setenv("DEHQAN_ASK_PER_MIN", "2")
    c = client()
    assert [c.post("/ask", json={"text": "hello"}).status_code for _ in range(3)] == [200, 200, 429]
