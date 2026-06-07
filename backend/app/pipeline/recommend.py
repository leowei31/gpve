"""The recommendation orchestrator — runs the six stages and returns the final 5 (REQ-002..009).

  1. parse        vibe -> structured intent (Gemini, deterministic)
  2. retrieve     embed query -> top-K nearest catalog vectors (pgvector)
  3. metric       deterministic re-score (quality / popularity / session / social)
  4. reputation   live Tavily on the provisional leaders, cached, deterministic synthesis
  5. rank         weighted blend (vibe/metrics/web) -> final 5
  6. rationale    grounded per-game "why it fits", from the same evidence

Blocking SDK calls (Gemini, Tavily) are run in threads so the async event loop (asyncpg)
isn't stalled."""
from __future__ import annotations

import asyncio

import asyncpg
from pydantic import BaseModel

from app.clients.gemini import GeminiClient
from app.pipeline.metric import apply_metric_scores
from app.pipeline.parse import VibeIntent, parse_vibe
from app.pipeline.rank import final_score, rank
from app.pipeline.rationale import apply_rationales
from app.pipeline.reputation import WebReputation
from app.pipeline.retrieve import Candidate, retrieve_candidates

_RETRIEVE_K = 25        # over-fetch for the re-rank to reorder
_WEB_N = 10             # only the provisional leaders get a (cost-bearing) live web lookup


class Source(BaseModel):
    title: str | None = None
    url: str | None = None


class Recommendation(BaseModel):
    title: str
    cover_url: str | None
    released: str | None
    genres: list[str]
    tags: list[str]
    rating: float | None
    metacritic: int | None
    vibe_similarity: float
    metric_score: float
    web_score: float
    final_score: float
    rationale: str | None
    sources: list[Source]


class VibeResponse(BaseModel):
    vibe: str
    intent: VibeIntent
    recommendations: list[Recommendation]


def _to_recommendation(c: Candidate) -> Recommendation:
    return Recommendation(
        title=c.title, cover_url=c.cover_url,
        released=c.released.isoformat() if c.released else None,
        genres=c.genres, tags=c.tags, rating=c.rating, metacritic=c.metacritic,
        vibe_similarity=round(c.vibe_similarity, 4), metric_score=round(c.metric_score, 4),
        web_score=round(c.web_score, 4), final_score=round(c.final_score, 4),
        rationale=c.rationale,
        sources=[Source(title=s.get("title"), url=s.get("url")) for s in c.web_snippets],
    )


async def recommend(
    *, pool: asyncpg.Pool, gemini: GeminiClient, reputation: WebReputation, vibe: str,
    w_vibe: float, w_metrics: float, w_web: float, top_k: int = 5,
) -> VibeResponse:
    intent = await asyncio.to_thread(parse_vibe, gemini, vibe)
    query_vector = await asyncio.to_thread(gemini.embed_query, intent.search_query)

    async with pool.acquire() as conn:
        candidates = await retrieve_candidates(conn, query_vector, _RETRIEVE_K)

    apply_metric_scores(candidates, intent)

    # Web reputation is the expensive stage, so only the provisional leaders earn a lookup.
    provisional = sorted(
        candidates, key=lambda c: w_vibe * c.vibe_similarity + w_metrics * c.metric_score,
        reverse=True,
    )[:_WEB_N]
    await asyncio.to_thread(reputation.apply, provisional)

    top = rank(provisional, w_vibe=w_vibe, w_metrics=w_metrics, w_web=w_web, top_k=top_k)
    await asyncio.to_thread(apply_rationales, gemini, vibe, top)

    return VibeResponse(
        vibe=vibe, intent=intent, recommendations=[_to_recommendation(c) for c in top]
    )
