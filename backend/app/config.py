"""Central configuration. The only thing that changes between local dev and Cloud Run
is the values of these env vars (DESIGN_RATIONALE.md ADR-1)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Data layer
    database_url: str = "postgresql://gpve:gpve@localhost:5432/gpve"

    # Web-reputation cache backend (ADR-11). Empty -> local JSON file (dev); set to a
    # redis:// URL (Memorystore, over the Serverless VPC connector) in production.
    redis_url: str = ""

    # LLM + embeddings (Gemini, via the google-genai SDK).
    # text-embedding-004 / gemini-1.5-flash were retired; these are the current models.
    # gemini-embedding-001 defaults to 3072-dim but supports Matryoshka truncation, so we
    # request 768 to keep the vector(768) schema (see embed.py — vectors are L2-normalized).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # Enrichment + cover art (RAWG)
    rawg_api_key: str = ""

    # Live web reputation (Tavily)
    tavily_api_key: str = ""

    # Ingestion paths (resolved relative to the backend/ dir)
    csv_path: Path = _BACKEND_DIR.parent / "data" / "Gamepass_Games_v1.csv"
    enrichment_cache_path: Path = _BACKEND_DIR.parent / "data" / "enrichment_cache.json"

    # Ranking weights (deterministic blend — ADR-9). Tunable; sum need not be 1.
    w_vibe: float = 0.5
    w_metrics: float = 0.3
    w_web: float = 0.2


settings = Settings()
