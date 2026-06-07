"""GPVE FastAPI app — serves the JSON API and (in production) the compiled React build.

One container: `/api/*` is the backend; everything else falls through to the SPA's
index.html so client-side routes (Discover/Collections/Insights) work on refresh. In dev the
React app runs on Vite (:5173) and calls the API cross-origin (CORS is open below)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.clients.cache import build_reputation_cache
from app.clients.db import create_pool
from app.clients.gemini import GeminiClient
from app.clients.tavily import TavilyClient
from app.config import settings
from app.pipeline.reputation import WebReputation
from app.routers import catalog, recommend

_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.pool = await create_pool(settings.database_url)
    app.state.gemini = GeminiClient(
        settings.gemini_api_key, settings.gemini_model,
        settings.embedding_model, settings.embedding_dim,
    )
    app.state.reputation = WebReputation(
        TavilyClient(settings.tavily_api_key),
        build_reputation_cache(
            settings.redis_url,
            settings.enrichment_cache_path.with_name("web_reputation_cache.json"),
        ),
    )
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="GPVE — Vibe Discovery Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(recommend.router, prefix="/api", tags=["recommend"])
app.include_router(catalog.router, prefix="/api", tags=["catalog"])


# --- Serve the SPA build if present (no-op in API-only dev) -------------------
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")  # client-side routing fallback
