# Dehqan API for Hugging Face Spaces (Docker SDK). Build context = the folder made by deploy/make_space.ps1,
# i.e. the contents of backend/ at the top level.
#
# NOT built or run locally: the Docker engine was not running and the CPU-PyTorch layer is a multi-GB
# download. Treat the first Space build as the first real test and read its build log.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv

# Hugging Face Spaces runs containers as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/app/.venv/bin:$PATH \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# Dependencies first, so code edits do not re-download PyTorch. Linux resolves the CPU-only torch wheels.
COPY --chown=user pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=user . .

# Spaces expects the app on port 7860. Weights are fetched from DEHQAN_MODEL_REPO at startup.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
