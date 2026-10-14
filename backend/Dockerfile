# Dehqan API for Render (free web service). Build context = backend/.
#
# Runs on ONNX Runtime, not PyTorch: ~220 MB of RAM with all three models loaded, versus ~909 MB with PyTorch.
# Render's free tier allows 512 MB. NOT built locally (the Docker engine was not running on the dev PC), so the
# first Render build is the first real test of this file: read its build log.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/app/.venv/bin:$PATH \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# Runtime dependencies only: the "train" group (PyTorch, transformers, datasets, onnx) and the "dev" group
# (pytest) are left out. Dependencies come first so code edits do not re-download them.
COPY --chown=user pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group train --no-install-project

COPY --chown=user app ./app
COPY --chown=user data_sources ./data_sources
COPY --chown=user forecast ./forecast
COPY --chown=user vision ./vision

# Bake the model files into the image: Render's free disk is wiped on every wake-up, so downloading at start
# would repeat on every cold start. Needs the Hugging Face model repo to be public.
ARG MODEL_REPO=MoZainUlAbideen/Dehqan
ENV DEHQAN_MODEL_REPO=${MODEL_REPO}
RUN python -c "from app.fetch_models import ensure_models; print('fetched', ensure_models('${MODEL_REPO}'))"

# Any website may call this read-only demo API from a browser (no logins or cookies; per-IP rate limit applies).
# Override DEHQAN_CORS_ORIGINS in Render's environment settings to restrict it to your website's URL.
ENV DEHQAN_CORS_ORIGINS=*

# Render supplies $PORT (default 10000).
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
