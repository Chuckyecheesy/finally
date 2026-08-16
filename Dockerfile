# syntax=docker/dockerfile:1

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---- Stage 2: FastAPI runtime serving the export ----
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FINALLY_DB_PATH=/app/db/finally.db

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/app ./app
RUN uv sync --locked --no-dev

# app/main.py mounts <backend>/static, which is /app/static here.
COPY --from=frontend /build/out ./static

RUN mkdir -p /app/db
VOLUME ["/app/db"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
