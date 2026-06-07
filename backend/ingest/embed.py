"""Embed the enriched catalog with Gemini (the vector side of vibe retrieval).

For each enriched game we compose a compact semantic "document" (title + genres + tags +
trimmed description) and embed it with ``gemini-embedding-001`` at 768 dimensions (Matryoshka
truncation, to match the ``vector(768)`` schema). Vectors are L2-normalized so cosine and
inner-product behave identically downstream.

Design (mirrors ingest/enrich.py):
  - Reads data/enrichment_cache.json, writes data/embeddings_cache.json keyed by
    normalized_title -> 768-float vector. Re-runs are incremental; ``--force`` refreshes.
  - The catalog is embedded with task_type RETRIEVAL_DOCUMENT; the live user vibe is embedded
    with RETRIEVAL_QUERY (in the request pipeline) — the asymmetric task types Gemini
    recommends for retrieval.
  - ``--dry-run`` builds and inspects the embedding texts WITHOUT calling Gemini (useful when
    the key has no credits yet): it prints samples + length stats so composition is reviewable.

Run:  python -m ingest.embed             # embed all enriched games -> embeddings_cache.json
      python -m ingest.embed --dry-run   # compose + inspect texts, no API calls
      python -m ingest.embed --limit 5   # smoke test;  --force ignores the cache
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

# Catalog documents and the live query use Gemini's asymmetric retrieval task types.
_DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
_QUERY_TASK = "RETRIEVAL_QUERY"
# gemini-embedding-001 accepts up to ~2048 input tokens; we trim descriptions well under that
# (most of the vibe signal is in title/genres/tags, and shorter text keeps cost down).
_DESC_CHAR_CAP = 1200
# Small batches + a pause keep us under the per-minute request/token quota (the embedding
# tier rate-limits hard); the embedder also backs off and retries on a rate-limit 429.
_BATCH_SIZE = 20
_BATCH_DELAY_SEC = 1.5


# ---------------------------------------------------------------------------
# Embedding-text composition (pure, deterministic, unit-tested)
# ---------------------------------------------------------------------------

def build_embedding_text(game: dict) -> str:
    """Compose the semantic document embedded for one game. Deterministic: the same enriched
    record always yields the same text (and therefore the same vector).

    Genres and tags lead because they're the densest vibe signal (EDA: the CSV had none of
    this); the description adds nuance but is trimmed so it can't dominate or blow the token
    budget."""
    parts: list[str] = [f"Title: {game.get('title', '').strip()}"]
    genres = game.get("genres") or []
    tags = game.get("tags") or []
    if genres:
        parts.append("Genres: " + ", ".join(genres))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    desc = (game.get("description") or "").strip()
    if desc:
        if len(desc) > _DESC_CHAR_CAP:
            desc = desc[:_DESC_CHAR_CAP].rsplit(" ", 1)[0] + "…"
        parts.append(desc)
    return "\n".join(parts)


def _normalize(vector: list[float]) -> list[float]:
    """L2-normalize. MRL-truncated dims (<3072) aren't unit-norm, so we normalize ourselves."""
    a = np.asarray(vector, dtype=np.float32)
    n = float(np.linalg.norm(a))
    return (a / n).tolist() if n > 0 else a.tolist()


# ---------------------------------------------------------------------------
# Gemini embedder (batched, polite, retrying)
# ---------------------------------------------------------------------------

class GeminiEmbedder:
    def __init__(self, api_key: str, model: str, dim: int, *, max_retries: int = 6,
                 base_backoff: float = 10.0):
        from google import genai  # imported lazily so --dry-run needs no SDK/key
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dim = dim
        self._max_retries = max_retries
        self._base_backoff = base_backoff

    def embed(self, texts: list[str], task_type: str = _DOCUMENT_TASK) -> list[list[float]]:
        """Embed a batch of texts; returns L2-normalized 768-dim vectors in input order.

        Retries rate-limit 429s with exponential backoff (windows are per-minute), but fails
        fast on a *billing* 429 — no amount of waiting fixes depleted credits."""
        from google.genai import types
        cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self._dim)
        for attempt in range(self._max_retries):
            try:
                resp = self._client.models.embed_content(model=self._model, contents=texts, config=cfg)
                return [_normalize(e.values) for e in resp.embeddings]
            except Exception as e:
                msg = str(e).lower()
                if any(w in msg for w in ("credit", "billing", "prepay")):
                    raise SystemExit(f"Gemini billing/credits problem (not rate-limit): {str(e)[:200]}")
                if attempt == self._max_retries - 1:
                    raise
                wait = self._base_backoff * (2 ** attempt)  # 10s, 20s, 40s, 80s, 160s
                print(f"  rate-limited; backing off {wait:.0f}s (attempt {attempt + 1}/{self._max_retries})…",
                      flush=True)
                time.sleep(wait)
        return []  # unreachable


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _load_enrichment(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("games", {})


def _load_embeddings(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("embeddings", {})


def embed_all(
    enriched: dict[str, dict],
    embedder: GeminiEmbedder,
    *,
    existing: dict[str, list[float]] | None = None,
    force: bool = False,
    batch_size: int = _BATCH_SIZE,
    save=None,
) -> dict[str, list[float]]:
    """Embed every enriched game not already in ``existing``. Returns norm_title -> vector.

    ``save(out)`` is called after each batch (for incremental persistence), and we pause
    between batches to stay under the rate limit."""
    # Copy the existing cache (don't mutate the caller's); --force ignores it and re-embeds all.
    out = {} if force else dict(existing or {})
    todo = [(k, v) for k, v in enriched.items() if k not in out]
    for i in range(0, len(todo), batch_size):
        chunk = todo[i : i + batch_size]
        vectors = embedder.embed([build_embedding_text(g) for _, g in chunk])
        for (key, _), vec in zip(chunk, vectors):
            out[key] = vec
        if save is not None:
            save(out)
        print(f"  embedded {min(i + batch_size, len(todo))}/{len(todo)} new "
              f"({len(out)} total)", flush=True)
        if i + batch_size < len(todo):
            time.sleep(_BATCH_DELAY_SEC)
    return out


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser(description="Embed the enriched catalog with Gemini.")
    ap.add_argument("--enrichment", type=Path, default=settings.enrichment_cache_path)
    ap.add_argument("--out", type=Path,
                    default=settings.enrichment_cache_path.with_name("embeddings_cache.json"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Compose + inspect texts; no API calls.")
    args = ap.parse_args()

    enriched = _load_enrichment(args.enrichment)
    if args.limit:
        enriched = dict(list(enriched.items())[: args.limit])

    if args.dry_run:
        lengths = [len(build_embedding_text(g)) for g in enriched.values()]
        print(f"[dry-run] {len(enriched)} games. Embedding-text length (chars): "
              f"min={min(lengths)} mean={sum(lengths)//len(lengths)} max={max(lengths)}")
        for g in list(enriched.values())[:3]:
            print("\n" + "=" * 70 + f"\n{build_embedding_text(g)}")
        print("\n[dry-run] No embeddings written. Add GEMINI credits, then re-run without --dry-run.")
        return

    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is empty — set it in backend/.env (see .env.example).")

    def _write(embeddings: dict[str, list[float]]) -> None:
        payload = {"version": 1, "model": settings.embedding_model, "dim": settings.embedding_dim,
                   "count": len(embeddings), "embeddings": embeddings}
        args.out.write_text(json.dumps(payload), encoding="utf-8")

    embedder = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model, settings.embedding_dim)
    existing = _load_embeddings(args.out)
    embeddings = embed_all(enriched, embedder, existing=existing, force=args.force, save=_write)
    _write(embeddings)
    print(f"Embedded {len(embeddings)}/{len(enriched)} games "
          f"({settings.embedding_model}, {settings.embedding_dim}-dim) -> {args.out}")


if __name__ == "__main__":
    main()
