"""Stage 2 — vector retrieval (REQ-003).

Embed the parsed search query (RETRIEVAL_QUERY) and pull the top-K nearest catalog vectors
by cosine similarity, returning the full row each candidate needs for downstream scoring and
display. We over-fetch (default 25) so the deterministic re-rank (Stages 3–5) has room to
reorder before we cut to the final 5."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import asyncpg

# Columns needed for re-scoring (rating/gamers/time/tags) and for display (cover/summary).
_RETRIEVE_SQL = """
select id, title, normalized_title, rating, gamers, completion_pct, time_midpoint,
       genres, tags, summary, cover_url, released, metacritic, added_date,
       1 - (embedding <=> $1) as vibe_similarity
from games
where embedding is not null
order by embedding <=> $1
limit $2
"""


@dataclass
class Candidate:
    id: int
    title: str
    normalized_title: str
    rating: float | None
    gamers: int | None
    completion_pct: float | None
    time_midpoint: float | None
    genres: list[str]
    tags: list[str]
    summary: str | None
    cover_url: str | None
    released: date | None
    metacritic: int | None
    added_date: date | None
    vibe_similarity: float
    # filled in by later stages
    metric_score: float = 0.0
    web_score: float = 0.0
    final_score: float = 0.0
    web_snippets: list[dict] = field(default_factory=list)
    rationale: str | None = None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Candidate":
        return cls(
            id=row["id"], title=row["title"], normalized_title=row["normalized_title"],
            rating=_f(row["rating"]), gamers=row["gamers"],
            completion_pct=_f(row["completion_pct"]), time_midpoint=_f(row["time_midpoint"]),
            genres=list(row["genres"] or []), tags=list(row["tags"] or []),
            summary=row["summary"], cover_url=row["cover_url"], released=row["released"],
            metacritic=row["metacritic"], added_date=row["added_date"],
            vibe_similarity=float(row["vibe_similarity"]),
        )


def _f(v) -> float | None:
    return float(v) if v is not None else None


async def retrieve_candidates(conn: asyncpg.Connection, query_vector: list[float], k: int = 25) -> list[Candidate]:
    rows = await conn.fetch(_RETRIEVE_SQL, query_vector, k)
    return [Candidate.from_row(r) for r in rows]
