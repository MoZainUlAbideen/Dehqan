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
