# Single-container image (ADR-2/3): build the React SPA, then serve it + the API from FastAPI.
# Cloud Run-ready (listens on $PORT). The DB (Cloud SQL/Postgres) and API keys are provided at
# runtime via env vars; the catalog must already be ingested into that DB.

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build              # -> /app/frontend/dist

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# main.py resolves the SPA at <repo>/frontend/dist == /app/frontend/dist
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# Catalog artifacts (CSV + enrichment/embeddings caches) at /app/data, where config.py expects
# them. Only used by the seed/re-load Cloud Run Job; the serving path reads from Postgres.
COPY data/ /app/data/

EXPOSE 8080
# Shell form so ${PORT} (Cloud Run) expands; defaults to 8080 locally.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
