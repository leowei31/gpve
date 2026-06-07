"""One-shot seeder for a fresh, managed database (e.g. Cloud SQL).

Locally the schema auto-runs from docker-compose's init scripts, so ``python -m ingest.load``
is enough. A managed Postgres starts empty, so this first applies ``sql/*.sql`` (extension +
table + indexes + the match_games function), then loads the catalog from the committed caches.

It reuses ``ingest.load`` for the join/insert, so there's a single source of truth for how a
row is built. Designed to run two ways with identical behaviour:
  • locally, against Cloud SQL through the Auth Proxy (``DATABASE_URL`` -> 127.0.0.1), or
  • as a Cloud Run Job on the same app image (``DATABASE_URL`` -> the instance private IP),
    which is also the re-load path when the catalog/embeddings are refreshed.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.config import settings
from ingest.clean import clean_csv
from ingest.load import build_rows, load

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


async def apply_schema(database_url: str) -> list[str]:
    """Run every sql/*.sql in name order (01_schema before 02_match_games). Idempotent."""
    import asyncpg

    conn = await asyncpg.connect(database_url)
    applied: list[str] = []
    try:
        for path in sorted(_SQL_DIR.glob("*.sql")):
            await conn.execute(path.read_text(encoding="utf-8"))
            applied.append(path.name)
    finally:
        await conn.close()
    return applied


def _load_caches() -> tuple[list, dict, dict]:
    enrichment_path = settings.enrichment_cache_path
    embeddings_path = enrichment_path.with_name("embeddings_cache.json")

    games, _report = clean_csv(settings.csv_path)
    enrichment = json.loads(enrichment_path.read_text(encoding="utf-8")).get("games", {})
    embeddings = (
        json.loads(embeddings_path.read_text(encoding="utf-8")).get("embeddings", {})
        if embeddings_path.exists() else {}
    )
    if not embeddings:
        print("WARNING: no embeddings cache found — seeding with NULL embeddings. "
              "Run `python -m ingest.embed` first for vibe search to work.")
    return games, enrichment, embeddings


def main() -> None:
    games, enrichment, embeddings = _load_caches()
    rows = build_rows(games, enrichment, embeddings)

    applied = asyncio.run(apply_schema(settings.database_url))
    print(f"Applied schema: {', '.join(applied)}")

    summary = asyncio.run(load(settings.database_url, rows))
    print(f"Seeded {summary['total']} games "
          f"({summary['enriched_ok']} enriched-ok, {summary['with_embedding']} with embeddings).")


if __name__ == "__main__":
    main()
