"""Stage 4 — live web reputation, deterministically synthesized (REQ-004 + REQ-006).

For the provisional top candidates we run a *live* Tavily search ("<title> video game review
reception") and turn the results into a web_score in [0, 1] using a fixed sentiment lexicon —
**no LLM in the scoring path**, so the same web text always yields the same score (the
determinism story). Results are cached by normalized_title (with a TTL) so repeat vibes are
reproducible and we don't re-hit Tavily. The raw snippets are kept on each candidate to
*ground* the Stage-6 rationale in real, modern coverage.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.clients.cache import ReputationCache
from app.clients.tavily import TavilyClient
from app.pipeline.retrieve import Candidate

# Reputation lexicon. We count *distinct terms present* (not raw frequency) for stability.
_POSITIVE = {
    "acclaimed", "praised", "beloved", "masterpiece", "classic", "excellent", "brilliant",
    "stellar", "fantastic", "must-play", "underrated", "gem", "award", "best", "favorite",
    "highly rated", "recommended", "great game", "addictive", "charming",
}
_NEGATIVE = {
    "disappointing", "mixed", "mediocre", "buggy", "broken", "panned", "flawed", "overrated",
    "boring", "worst", "terrible", "poor", "forgettable", "repetitive", "clunky",
}
_NEUTRAL = 0.5            # no signal / no results
_STEP = 0.08             # per-net-term shift around neutral


def _present(term: str, text: str) -> bool:
    if " " in term or "-" in term:        # phrases: substring is fine
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def synthesize_web_score(results: list[dict]) -> tuple[float, list[dict]]:
    """Deterministic [0,1] reputation from search results + up to 3 grounding snippets."""
    if not results:
        return _NEUTRAL, []
    text = " ".join(f"{r.get('title', '')} {r.get('content', '')}" for r in results).lower()
    pos = sum(1 for t in _POSITIVE if _present(t, text))
    neg = sum(1 for t in _NEGATIVE if _present(t, text))
    score = max(0.0, min(1.0, _NEUTRAL + _STEP * (pos - neg)))
    snippets = [
        {"title": r.get("title"), "url": r.get("url"), "content": (r.get("content") or "")[:300]}
        for r in results[:3]
    ]
    return score, snippets


class WebReputation:
    """Live Tavily lookups behind a pluggable, TTL'd, title-keyed cache.

    The cache backend (local JSON file or Memorystore/Redis) is injected — see
    ``app.clients.cache`` — so dev and prod share this exact code path (ADR-1/ADR-11).
    """

    def __init__(self, tavily: TavilyClient, cache: ReputationCache, ttl_days: int = 7):
        self._tavily = tavily
        self._cache = cache
        self._ttl_days = ttl_days

    def _fresh(self, entry: dict) -> bool:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(entry["fetched_at"])
            return age.days < self._ttl_days
        except Exception:
            return False

    def _results_for(self, title: str, normalized_title: str) -> list[dict]:
        entry = self._cache.get(normalized_title)
        if entry and self._fresh(entry):
            return entry["results"]
        results = self._tavily.search(f"{title} video game review reception")
        self._cache.set(normalized_title, {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        })
        return results

    def apply(self, candidates: list[Candidate]) -> None:
        """Set web_score + web_snippets in place for each candidate."""
        for c in candidates:
            results = self._results_for(c.title, c.normalized_title)
            c.web_score, c.web_snippets = synthesize_web_score(results)
