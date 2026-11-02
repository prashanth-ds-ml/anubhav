# The API and the built web app in one container, for a Hugging Face Docker Space. Replay needs no keys; for live mode
# add the model keys as Space secrets. Keys never go in the image (.dockerignore keeps .env out).
# Stage 1: build the React app (the build reads the contract files, so they sit one level up)
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY contracts/ /contracts/
RUN npm run build

# Stage 2: the API, serving web/dist at /
FROM python:3.12-slim

ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1 ANUBHAV_PUBLIC=1 PORT=7860
RUN apt-get update && apt-get install -y --no-install-recommends libportaudio2 && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.9.5 \
    && useradd -m -u 1000 anubhav

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src src
COPY configs configs
COPY contracts contracts
COPY demo demo
COPY --from=web /web/dist web/dist
COPY artifacts artifacts
# EXP-004's result files (open weights against Spark 1.3), read by /api/proof
COPY archive/prototype_experiments/artifacts/baseline archive/prototype_experiments/artifacts/baseline
RUN uv sync --frozen --no-dev

# The demo world is built into the image, so the first visitor doesn't wait about a minute for it
RUN .venv/bin/python -m anubhav.data.generate --full && chown -R anubhav:anubhav /app

USER anubhav
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD .venv/bin/python -c "import urllib.request as u; u.urlopen('http://localhost:7860/api/health')"
CMD [".venv/bin/uvicorn", "anubhav.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
