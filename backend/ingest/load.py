"""Load the cleaned + enriched + embedded catalog into Postgres/pgvector.

Joins the three deterministic artifacts by ``normalized_title``:
  - cleaned metrics  — recomputed from the CSV via ingest.clean (single source of truth)
  - enrichment cache — data/enrichment_cache.json (genres/tags/summary/cover/released/...)
  - embeddings cache — data/embeddings_cache.json (768-dim vectors)

and rebuilds the ``games`` table with a truncate-and-insert. A full rebuild from immutable
caches is idempotent and far simpler than per-row upserts at this scale (~450 rows).

Run:  docker compose up -d            # Postgres + pgvector (first boot runs sql/*.sql)
      python -m ingest.embed          # produce embeddings_cache.json first
      python -m ingest.load           # rebuild the games table
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ingest.clean import CleanedGame, clean_csv
from ingest.embed import build_embedding_text

# Column order shared by the INSERT and build_row (keep them in lockstep).
_COLUMNS = [
    "title", "normalized_title", "ratio", "gamers", "completion_pct",
    "time_min_hours", "time_max_hours", "time_midpoint", "rating", "added_date",
    "true_achievement", "game_score", "rawg_id", "genres", "tags", "themes",
    "summary", "cover_url", "released", "metacritic", "enriched_text", "embedding",
    "enrichment_status", "source_titles",
]
_INSERT = (
    f"insert into games ({', '.join(_COLUMNS)}) "
    f"values ({', '.join(f'${i + 1}' for i in range(len(_COLUMNS)))})"
)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _num(value: float | None) -> Decimal | None:
    """Float -> Decimal via str() so the numeric column stores '4.8', not the binary
    expansion 4.7999...96 that asyncpg would write for a raw float."""
    return Decimal(str(value)) if value is not None else None


def build_row(game: CleanedGame, enrichment: dict | None, vector: list[float] | None) -> tuple:
    """Assemble one games-table row from the three sources. Pure + unit-tested.

    enrichment_status: ok = matched on RAWG, miss = enriched-but-unmatched, pending = no
    enrichment record at all. enriched_text mirrors what embed.py embedded, for traceability."""
    e = enrichment or {}
    status = "ok" if e.get("matched") else ("miss" if e else "pending")
    enriched_text = build_embedding_text(e) if e else None
    return (
        game.title,
        game.normalized_title,
        _num(game.ratio),
        game.gamers,
        _num(game.completion_pct),
        _num(game.time_min_hours),
        _num(game.time_max_hours),
        _num(game.time_midpoint),
        _num(game.rating),
        game.added_date,
        game.true_achievement,
        game.game_score,
        e.get("rawg_id"),
        e.get("genres") or [],
        e.get("tags") or [],
        [],                               # themes: RAWG has no distinct theme field
        e.get("description"),             # -> summary
        e.get("cover_image"),             # -> cover_url
        _parse_date(e.get("released")),
        e.get("metacritic"),
        enriched_text,
        vector,
        status,
        game.source_titles or [],
    )


def build_rows(games: list[CleanedGame], enrichment: dict[str, dict],
               embeddings: dict[str, list[float]]) -> list[tuple]:
    return [
        build_row(g, enrichment.get(g.normalized_title), embeddings.get(g.normalized_title))
        for g in games
    ]


async def load(database_url: str, rows: list[tuple]) -> dict:
    """Truncate + insert all rows in one transaction. Returns a small summary."""
    import asyncpg
    from pgvector.asyncpg import register_vector

    conn = await asyncpg.connect(database_url)
    try:
        await register_vector(conn)  # lets asyncpg encode Python lists as vector(768)
        async with conn.transaction():
            # Full rebuild from the immutable caches. RESTART IDENTITY resets the bigserial id
            # sequence so every reload reproduces the same ids (1..N) — deterministic, not drifting.
            # One transaction means a mid-load failure rolls back, never leaving a half-empty table.
            await conn.execute("truncate games restart identity")
            await conn.executemany(_INSERT, rows)
        total = await conn.fetchval("select count(*) from games")
        with_emb = await conn.fetchval("select count(*) from games where embedding is not null")
        ok = await conn.fetchval("select count(*) from games where enrichment_status = 'ok'")
        return {"total": total, "with_embedding": with_emb, "enriched_ok": ok}
    finally:
        await conn.close()


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser(description="Load the catalog into Postgres/pgvector.")
    ap.add_argument("--enrichment", type=Path, default=settings.enrichment_cache_path)
    ap.add_argument("--embeddings", type=Path,
                    default=settings.enrichment_cache_path.with_name("embeddings_cache.json"))
    args = ap.parse_args()

    games, _report = clean_csv(settings.csv_path)
    enrichment = json.loads(args.enrichment.read_text(encoding="utf-8")).get("games", {})
    embeddings = (
        json.loads(args.embeddings.read_text(encoding="utf-8")).get("embeddings", {})
        if args.embeddings.exists() else {}
    )
    if not embeddings:
        print("WARNING: no embeddings cache found — loading with NULL embeddings. "
              "Run `python -m ingest.embed` first for vibe search to work.")

    rows = build_rows(games, enrichment, embeddings)
    summary = asyncio.run(load(settings.database_url, rows))
    print(f"Loaded {summary['total']} games "
          f"({summary['enriched_ok']} enriched-ok, {summary['with_embedding']} with embeddings).")


if __name__ == "__main__":
    main()
