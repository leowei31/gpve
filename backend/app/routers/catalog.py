"""Catalog read endpoints: health + browse/insights data for the non-Discover pages."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


def _clean(row) -> dict:
    """asyncpg returns numeric columns as Decimal, which FastAPI serializes as a string;
    coerce to float so the JSON (and the typed frontend) get real numbers."""
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in dict(row).items()}


@router.get("/health")
async def health(request: Request) -> dict:
    async with request.app.state.pool.acquire() as conn:
        total = await conn.fetchval("select count(*) from games")
        with_emb = await conn.fetchval("select count(*) from games where embedding is not null")
    return {"status": "ok", "games": total, "with_embeddings": with_emb}


@router.get("/stats")
async def stats(request: Request) -> dict:
    """Aggregates for the Insights page."""
    async with request.app.state.pool.acquire() as conn:
        total = await conn.fetchval("select count(*) from games")
        avg_rating = await conn.fetchval("select round(avg(rating), 2) from games where rating is not null")
        top_genres = await conn.fetch(
            "select g as name, count(*) as n from games, unnest(genres) g "
            "group by g order by n desc limit 12")
        top_tags = await conn.fetch(
            "select t as name, count(*) as n from games, unnest(tags) t "
            "group by t order by n desc limit 20")
        # Hidden gems: well-rated but low player count (EDA §8) — high rating, low popularity.
        hidden_gems = await conn.fetch(
            "select id, title, rating, gamers, cover_url, genres from games "
            "where rating >= 4.1 and gamers is not null and gamers > 0 "
            "order by rating desc, gamers asc limit 8")
    return {
        "total": total,
        "avg_rating": float(avg_rating) if avg_rating is not None else None,
        "top_genres": [dict(r) for r in top_genres],
        "top_tags": [dict(r) for r in top_tags],
        "hidden_gems": [_clean(r) for r in hidden_gems],
    }


@router.get("/games")
async def list_games(
    request: Request,
    genre: str | None = None,
    search: str | None = None,
    sort: str = Query("rating", pattern="^(rating|popularity|recent)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """Browsable catalog for the Collections page (filter by genre / search, simple sorts)."""
    order = {"rating": "rating desc nulls last",
             "popularity": "gamers desc nulls last",
             "recent": "released desc nulls last"}[sort]
    where, args = ["enrichment_status = 'ok'"], []
    if genre:
        args.append(genre)
        where.append(f"${len(args)} = any(genres)")
    if search:
        args.append(f"%{search}%")
        where.append(f"title ilike ${len(args)}")
    clause = " and ".join(where)
    args.extend([limit, offset])
    sql = (
        "select id, title, cover_url, genres, tags, rating, gamers, time_midpoint, released, summary "
        f"from games where {clause} order by {order}, gamers desc nulls last "
        f"limit ${len(args) - 1} offset ${len(args)}"
    )
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        total = await conn.fetchval(f"select count(*) from games where {clause}", *args[:-2])
    return {"total": total, "games": [_clean(r) for r in rows]}


# Full single-game profile + nearest-neighbour "similar games" (deferred §18.1 → shipped).
# Both keep the routes after /games so the static segments aren't shadowed by the {game_id} path.
_GAME_SQL = """
select id, title, cover_url, genres, tags, rating, gamers, completion_pct,
       time_min_hours, time_max_hours, time_midpoint, released, metacritic,
       summary, true_achievement, game_score
from games where id = $1
"""

# Reuse match_games(query, count, exclude_id): feed a game its own embedding and exclude itself.
# The lateral join yields zero rows when the game is missing or unembedded, so similarity is
# never null. We join back to games for the display columns the catalog cards need.
_SIMILAR_SQL = """
with target as (
  select embedding from games where id = $1 and embedding is not null
)
select g.id, g.title, g.cover_url, g.genres, g.rating, g.released, m.similarity
from target t
cross join lateral match_games(t.embedding, $2, $1) m
join games g on g.id = m.id
order by m.similarity desc
"""


@router.get("/games/{game_id}")
async def get_game(game_id: int, request: Request) -> dict:
    """Full profile for the Game detail page (all display metrics for one title)."""
    async with request.app.state.pool.acquire() as conn:
        row = await conn.fetchrow(_GAME_SQL, game_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _clean(row)


@router.get("/games/{game_id}/similar")
async def similar_games(
    game_id: int,
    request: Request,
    limit: int = Query(6, ge=1, le=24),
) -> dict:
    """Nearest neighbours by vibe embedding — pure vector search, no LLM (instant, free)."""
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch(_SIMILAR_SQL, game_id, limit)
    return {"games": [_clean(r) for r in rows]}
