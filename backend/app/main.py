"""Dehqan API.

Run locally (from backend/):  uv run uvicorn app.main:app --reload
Docs UI:                      http://127.0.0.1:8000/docs

Settings (environment variables):
  DEHQAN_LOAD_MODELS=0        start without loading models (/diagnose then answers 503)
  DEHQAN_MODEL_REPO=user/repo download missing weights from this Hugging Face model repo at start
  DEHQAN_CORS_ORIGINS=a,b     allowed browser origins (default: http://localhost:3000)
  DEHQAN_DIAGNOSE_PER_MIN=10  rate limit per IP for /diagnose
"""

import io
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Callable

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator

from app.pipeline import ABSTAIN_THRESHOLD, ABSTAIN_THRESHOLD_NOTE, diagnose
from app.ratelimit import RateLimiter
from app.spray_window import NOTE as SPRAY_NOTE
from app.spray_window import find_windows
from data_sources.open_meteo import Hour, fetch_forecast
from app.field_service import field_report
from forecast import service as market_service
from router.core import Agents
from router.core import ask as router_ask
from vision.severity import grade

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE_PX = 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Rough bounding box of Pakistan; rejects obviously wrong coordinates.
LAT_RANGE, LON_RANGE = (23.0, 37.5), (60.5, 77.9)


class FieldRequest(BaseModel):
    lat: float = Field(ge=LAT_RANGE[0], le=LAT_RANGE[1])
    lon: float = Field(ge=LON_RANGE[0], le=LON_RANGE[1])
    size_m: int = Field(default=300, ge=100, le=1000)


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    lat: float | None = Field(default=None, ge=LAT_RANGE[0], le=LAT_RANGE[1])
    lon: float | None = Field(default=None, ge=LON_RANGE[0], le=LON_RANGE[1])

    @model_validator(mode="after")
    def both_or_neither(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("send both lat and lon, or neither")
        return self


class SprayRequest(BaseModel):
    lat: float = Field(ge=LAT_RANGE[0], le=LAT_RANGE[1])
    lon: float = Field(ge=LON_RANGE[0], le=LON_RANGE[1])


def read_image(data: bytes, content_type: str | None) -> Image.Image:
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"unsupported file type {content_type!r}; send a JPEG, PNG or WebP photo")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"photo is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(400, "could not read the photo; is it a valid image?") from e
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))  # bound the compute per request
    return img


def create_app(
    components=None,
    forecast_fn: Callable[[float, float], list[Hour]] = fetch_forecast,
    field_fn: Callable[..., dict] = field_report,
    diagnose_per_min: int | None = None,
    load_models: bool | None = None,
) -> FastAPI:
    if load_models is None:
        load_models = components is None and os.environ.get("DEHQAN_LOAD_MODELS", "1") != "0"
    limit = diagnose_per_min or int(os.environ.get("DEHQAN_DIAGNOSE_PER_MIN", "10"))
    limiter = RateLimiter(limit, 60.0)
    ask_limiter = RateLimiter(int(os.environ.get("DEHQAN_ASK_PER_MIN", "20")), 60.0)
    field_limiter = RateLimiter(int(os.environ.get("DEHQAN_FIELD_PER_MIN", "4")), 60.0)  # satellite reads are heavy

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_models:
            from app.fetch_models import ensure_models
            from app.models import load_components

            repo = os.environ.get("DEHQAN_MODEL_REPO")
            if repo:
                ensure_models(repo)

            app.state.components = load_components()
        yield

    app = FastAPI(title="Dehqan API", version="0.1.0", lifespan=lifespan)
    app.state.components = components
    origins = os.environ.get("DEHQAN_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/health")
    def health():
        return {"status": "ok", "models_loaded": app.state.components is not None}

    @app.get("/about")
    def about():
        return {
            "abstain_threshold": ABSTAIN_THRESHOLD,
            "abstain_threshold_note": ABSTAIN_THRESHOLD_NOTE,
            "spray_window_note": SPRAY_NOTE,
        }

    @app.post("/diagnose")
    async def diagnose_endpoint(request: Request, file: UploadFile = File(...)):
        if app.state.components is None:
            raise HTTPException(503, "models are not loaded on this server")
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "too many requests; please wait a minute")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        img = read_image(data, file.content_type)
        c = app.state.components
        return asdict(diagnose(img, c.gate, c.classifier, c.severity, grade))

    @app.post("/spray-window")
    def spray_window(req: SprayRequest):
        try:
            hours = forecast_fn(req.lat, req.lon)
        except (httpx.HTTPError, ValueError) as e:
            raise HTTPException(502, "weather service unavailable; try again later") from e
        windows = find_windows(hours)
        return {
            "forecast_start": hours[0].time.isoformat() if hours else None,
            "forecast_hours": len(hours),
            "windows": [asdict(w) for w in windows],
            "note": SPRAY_NOTE,
            "message": "No safe spray window in the next 5 days." if not windows else f"{len(windows)} safe spray window(s) found.",
        }

    agents = Agents(
        spray=lambda lat, lon: [asdict(w) for w in find_windows(forecast_fn(lat, lon))],
        market_options=market_service.options,
        market=market_service.analysis,
        field=lambda lat, lon: field_fn(lat, lon, 300),
    )

    @app.post("/ask")
    def ask(req: AskRequest, request: Request):
        """Supervisor router: reads a question (English, Roman Urdu or Urdu) and sends it to the right specialist."""
        client = request.client.host if request.client else "unknown"
        if not ask_limiter.allow(client):
            raise HTTPException(429, "too many questions; please wait a minute")
        try:
            return router_ask(req.text, agents, req.lat, req.lon)
        except (httpx.HTTPError, OSError) as e:
            raise HTTPException(502, "a data service is unavailable; try again later") from e

    @app.post("/field-ndvi")
    def field_ndvi(req: FieldRequest, request: Request):
        client = request.client.host if request.client else "unknown"
        if not field_limiter.allow(client):
            raise HTTPException(429, "too many satellite requests; please wait a minute")
        try:
            return field_fn(req.lat, req.lon, req.size_m)
        except (httpx.HTTPError, OSError) as e:
            raise HTTPException(502, "satellite data service unavailable; try again later") from e

    @app.get("/market/options")
    def market_options():
        return market_service.options()

    @app.get("/market")
    def market(commodity: str, market: str):
        try:
            return market_service.analysis(commodity, market)
        except KeyError:
            raise HTTPException(404, "no reliable price history for that commodity and market") from None

    return app


app = create_app()
