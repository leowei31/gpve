"""RAWG enrichment — the semantic layer the CSV lacks (REQ-005 + the vibe-match foundation).

The 2022 catalog has *zero* columns describing what a game **is** (EDA section 2): no genre,
theme, mood, or summary — only achievement/playtime metrics. You cannot match a vibe like
"eerie isolated sci-fi" against those. So before any embedding or vibe matching, we enrich
each cleaned title with genres, tags, a description, and an official cover image from RAWG
(https://rawg.io/apidocs).

Design choices (DESIGN_RATIONALE):
  - Results are cached to JSON (``data/enrichment_cache.json``), keyed by normalized_title.
    The cache makes embeddings/load reproducible and lets the app run without re-hitting RAWG.
  - Re-runs are incremental: titles already matched in the cache are skipped; misses are
    retried (a miss is often a transient API hiccup, not a permanent gap). ``--force`` refreshes.
  - Matches are scored against our normalized title; low-confidence hits are recorded as
    **misses** with their best candidate for manual review — never silently accepted.
  - Nothing is invented. A game with no good RAWG match stays unenriched and is logged.

Run:  python -m ingest.enrich            # enrich all cleaned games (uses RAWG_API_KEY from .env)
      python -m ingest.enrich --limit 10 # smoke-test the first 10
      python -m ingest.enrich --force    # ignore cache, re-enrich everything
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ingest.clean import clean_csv, strip_platform_tag

RAWG_BASE = "https://api.rawg.io/api"

# Tag slugs that describe a *store/platform feature*, not the game itself. Dropped so the
# embedding text stays semantic. Genre/play-style tags (singleplayer, co-op, atmospheric,
# open-world, story-rich, ...) are deliberately kept — they're exactly the vibe signal.
# RAWG also emits localized duplicates ('Conquistas Steam') and numbered slugs
# ('steam-trading-cards-2'), so _clean_tags requires English and strips the trailing -N.
_TAG_DENYLIST = {
    "captions-available", "commentary-available", "stats", "cloud-saves", "achievements",
    "valve-anti-cheat-enabled", "includes-level-editor", "in-app-purchases",
    "games-with-gold", "xbox-play-anywhere", "cross-platform-multiplayer", "vr-mod",
}
_TAG_DEDUPE_SUFFIX = re.compile(r"-\d+$")
_MAX_TAGS = 20


def _is_noise_slug(slug: str) -> bool:
    """True for store/platform-feature tags. 'steam' is matched as a hyphen-delimited token so
    it catches both 'steam-trading-cards' and the localized 'conquistas-steam' while sparing
    the real 'steampunk'; 'controller' substring catches full/partial/-support variants."""
    stem = _TAG_DEDUPE_SUFFIX.sub("", slug)
    return stem in _TAG_DENYLIST or "steam" in stem.split("-") or "controller" in stem
# Below this match confidence we treat the RAWG hit as unreliable and log it as a miss.
_MATCH_THRESHOLD = 0.5

# A trailing "(YYYY)" in our catalog title is a disambiguator ('DOOM (1993)', 'GRID') that
# confuses RAWG's search. We drop it from the *search query* so the franchise surfaces, but
# keep it as a *scoring* token so the right era still wins via forward-containment.
_YEAR_SUFFIX = re.compile(r"\s*\((?:19|20)\d{2}\)\s*$")

# Manual overrides for the long tail that title-matching provably can't solve — keyed by
# normalized_title -> RAWG game id. Documented & auditable; nothing is silently guessed.
_OVERRIDES: dict[str, int] = {
    # RAWG renamed 'Backbone' (2021, EggNut) to 'Tails Noir' (2023) — zero title overlap,
    # so search can only find the free 'Backbone: Prologue' demo. Pin the real game.
    "backbone": 63845,
}


def _strip_year(title: str) -> str:
    return _YEAR_SUFFIX.sub("", title).strip()


# ---------------------------------------------------------------------------
# Match scoring (how confident are we this RAWG result is the same game?)
# ---------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Edition/marketing words that differ between our catalog and RAWG's canonical name but
# don't change *which game* it is. Dropped for matching only (not for dedup/storage).
_STOPWORDS = {"the", "of", "a", "an", "edition", "definitive", "remastered", "remaster",
              "hd", "goty", "complete", "deluxe", "ultimate"}


def _match_tokens(title: str) -> set[str]:
    """Tokenize for matching: fold diacritics ('Brütal'->'brutal'), lowercase, split on
    punctuation, drop edition/stopwords. Diacritic folding happens *before* punctuation
    stripping so accented letters survive as letters instead of being deleted."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    words = _NON_ALNUM.sub(" ", folded.lower()).split()
    return {w for w in words if w not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a and b) else 0.0


def match_score(query: str, candidate_name: str) -> float:
    """Confidence that ``candidate_name`` (a RAWG result) is the same game as ``query``.

    max(Jaccard, forward-containment), where forward-containment = |overlap| / |candidate|
    asks "is the RAWG canonical name fully accounted for in our title?". This rewards
    subtitle/edition cases ('Spiritfarer: Farewell Edition' -> 'Spiritfarer') without
    over-matching sequels: our 'Doom' against candidate 'Doom Eternal' scores only 0.5
    because 'eternal' is unaccounted for."""
    a, b = _match_tokens(query), _match_tokens(candidate_name)
    inter = a & b
    if not a or not b or not inter:
        return 0.0
    return max(_jaccard(a, b), len(inter) / len(b))


def _select_best(query: str, results: list[dict]) -> dict:
    """Pick the highest-scoring result; break ties by Jaccard so the closest *full-title*
    match wins (e.g. 'Halo Infinite' beats the bare 'Halo' when both contain our tokens)."""
    def key(r: dict) -> tuple[float, float]:
        name = r.get("name", "")
        return (match_score(query, name), _jaccard(_match_tokens(query), _match_tokens(name)))
    return max(results, key=key)


def _clean_tags(raw_tags: list[dict]) -> list[str]:
    """Keep English, semantic tags; drop store/platform-feature noise; cap the count.
    English is required (not just preferred) so localized duplicates don't pollute the text."""
    out: list[str] = []
    for t in raw_tags or []:
        if t.get("language") != "eng":
            continue
        if _is_noise_slug(t.get("slug") or ""):
            continue
        name = (t.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= _MAX_TAGS:
            break
    return out


# ---------------------------------------------------------------------------
# RAWG client (async, polite: bounded concurrency + retry/backoff)
# ---------------------------------------------------------------------------

class RawgClient:
    def __init__(self, api_key: str, *, concurrency: int = 5, max_retries: int = 3):
        self._key = api_key
        self._sem = asyncio.Semaphore(concurrency)
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RawgClient":
        self._client = httpx.AsyncClient(base_url=RAWG_BASE, timeout=20.0)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict) -> dict:
        """GET with the API key injected, retrying transient errors (429/5xx/network)."""
        assert self._client is not None
        params = {**params, "key": self._key}
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            # Hold a concurrency slot only for the request itself; the backoff sleep below sits
            # OUTSIDE this `async with`, so a throttled task frees its slot for others while waiting.
            async with self._sem:
                try:
                    resp = await self._client.get(path, params=params)
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    if e.response.status_code not in (429, 500, 502, 503, 504):
                        raise  # 4xx (bad request/auth) won't fix itself — fail loudly
                except httpx.TransportError as e:
                    last_exc = e
            await asyncio.sleep(delay)
            delay *= 2
        raise RuntimeError(f"RAWG GET {path} failed after {self._max_retries} retries") from last_exc

    async def search(self, query: str, page_size: int = 8) -> list[dict]:
        data = await self._get("/games", {"search": query, "page_size": page_size})
        return data.get("results", [])

    async def detail(self, game_id: int) -> dict:
        return await self._get(f"/games/{game_id}", {})


# ---------------------------------------------------------------------------
# Enriched record
# ---------------------------------------------------------------------------

@dataclass
class EnrichedGame:
    title: str
    normalized_title: str
    matched: bool
    match_score: float
    rawg_id: int | None = None
    rawg_slug: str | None = None
    rawg_name: str | None = None
    released: str | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    cover_image: str | None = None
    metacritic: int | None = None
    rawg_rating: float | None = None
    esrb: str | None = None

    def to_jsonable(self) -> dict:
        return asdict(self)


def _miss(title: str, norm: str, score: float, candidate: str | None) -> dict:
    return {"title": title, "normalized_title": norm, "best_score": round(score, 3),
            "best_candidate": candidate}


def _build(title: str, normalized_title: str, obj: dict, score: float) -> EnrichedGame:
    """Build an EnrichedGame from a RAWG object (detail preferred; list result as fallback).
    Detail objects carry ``description_raw``; list results don't, so description may be None."""
    esrb = obj.get("esrb_rating")
    return EnrichedGame(
        title=title,
        normalized_title=normalized_title,
        matched=True,
        match_score=round(score, 3),
        rawg_id=obj.get("id"),
        rawg_slug=obj.get("slug"),
        rawg_name=obj.get("name"),
        released=obj.get("released"),
        genres=[g["name"] for g in obj.get("genres", []) if g.get("name")],
        tags=_clean_tags(obj.get("tags", [])),
        description=(obj.get("description_raw") or "").strip() or None,
        cover_image=obj.get("background_image"),
        metacritic=obj.get("metacritic"),
        rawg_rating=obj.get("rating"),
        esrb=esrb.get("name") if esrb else None,
    )


async def enrich_one(client: RawgClient, title: str, normalized_title: str) -> tuple[EnrichedGame | None, dict | None]:
    """Resolve one title to a RAWG game and enrich it.

    Order: (1) manual override by id; else (2) search the year-stripped title, pick the
    best-scoring result, then fetch its detail (for description + full tags). Returns
    (EnrichedGame, None) on a confident match, or (None, miss_dict) otherwise."""
    override_id = _OVERRIDES.get(normalized_title)
    if override_id is not None:
        return _build(title, normalized_title, await client.detail(override_id), 1.0), None

    score_query = strip_platform_tag(title)
    results = await client.search(_strip_year(score_query))
    if not results:
        return None, _miss(title, normalized_title, 0.0, None)

    best = _select_best(score_query, results)
    score = match_score(score_query, best.get("name", ""))
    if score < _MATCH_THRESHOLD:
        return None, _miss(title, normalized_title, score, best.get("name"))

    # Prefer the authoritative detail object (adds description, fuller tags); fall back to the
    # list result if the detail call fails so a confident match is never lost over a hiccup.
    try:
        obj = await client.detail(best["id"])
    except Exception:
        obj = best
    return _build(title, normalized_title, obj, score), None


async def enrich_all(
    games: list,
    api_key: str,
    *,
    existing: dict[str, dict] | None = None,
    force: bool = False,
    concurrency: int = 5,
) -> tuple[dict[str, dict], list[dict]]:
    """Enrich the games not already matched in ``existing``. Returns (cache_games, misses)."""
    # Copy so we never mutate the caller's cache; --force starts empty (re-enrich everything).
    existing = {} if force else dict(existing or {})
    todo = [g for g in games if g.normalized_title not in existing]

    misses: list[dict] = []
    async with RawgClient(api_key, concurrency=concurrency) as client:
        tasks = [enrich_one(client, g.title, g.normalized_title) for g in todo]
        for coro in asyncio.as_completed(tasks):
            enriched, miss = await coro
            if enriched is not None:
                existing[enriched.normalized_title] = enriched.to_jsonable()
            elif miss is not None:
                misses.append(miss)
    return existing, misses


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("games", {})


def main() -> None:
    # Import settings lazily so `python -m ingest.enrich --help` works without a full env.
    from app.config import settings

    ap = argparse.ArgumentParser(description="Enrich cleaned games via RAWG (REQ-005).")
    ap.add_argument("--csv", type=Path, default=settings.csv_path)
    ap.add_argument("--cache", type=Path, default=settings.enrichment_cache_path)
    ap.add_argument("--limit", type=int, default=None, help="Only enrich the first N games (smoke test).")
    ap.add_argument("--force", action="store_true", help="Ignore the cache and re-enrich everything.")
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()

    if not settings.rawg_api_key:
        raise SystemExit("RAWG_API_KEY is empty — set it in backend/.env (see .env.example).")

    games, _report = clean_csv(args.csv)
    if args.limit:
        games = games[: args.limit]

    existing = _load_cache(args.cache)
    cache_games, misses = asyncio.run(
        enrich_all(games, settings.rawg_api_key, existing=existing,
                   force=args.force, concurrency=args.concurrency)
    )

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(args.csv),
        "count": len(cache_games),
        "games": cache_games,
    }
    args.cache.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    misses_path = args.cache.with_name("enrichment_misses.json")
    misses_path.write_text(json.dumps(misses, indent=2, ensure_ascii=False), encoding="utf-8")

    total = len(games)
    newly = total - len([g for g in games if g.normalized_title in existing]) if not args.force else total
    matched = sum(1 for g in games if g.normalized_title in cache_games)
    print(f"Processed {total} games -> {matched} enriched ({matched/total:.1%}), "
          f"{len(misses)} miss(es) this run.")
    if misses:
        print("Misses (logged to enrichment_misses.json, nothing invented):")
        for m in misses[:20]:
            print(f"  {m['title']!r:45} best={m['best_candidate']!r} ({m['best_score']})")
    print(f"Cache -> {args.cache}  ({len(cache_games)} total games)")


if __name__ == "__main__":
    main()
