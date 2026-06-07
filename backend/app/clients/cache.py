"""Pluggable cache backends for the web-reputation step (DESIGN_RATIONALE.md ADR-11).

Local/dev uses a JSON file keyed by normalized title; production (Cloud Run) uses Memorystore
(Redis), reachable over the Serverless VPC connector. The request path is identical — only the
presence of ``REDIS_URL`` in the environment decides which backend is built. Both expose the
same tiny get/set-a-dict contract; freshness/TTL logic stays in ``WebReputation``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Protocol


class ReputationCache(Protocol):
    """A dumb key -> JSON-able dict store. TTL semantics live in the caller."""

    def get(self, key: str) -> Optional[dict]: ...
    def set(self, key: str, value: dict) -> None: ...


class FileReputationCache:
    """JSON file holding ``{key: entry}``. Loaded once on init, rewritten on each set.

    This is the original local-dev behaviour, kept byte-for-byte compatible with the existing
    ``data/web_reputation_cache.json`` so cached lookups survive the refactor.
    """

    def __init__(self, path: Path):
        self._path = Path(path)
        self._data: dict[str, dict] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def get(self, key: str) -> Optional[dict]:
        return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        self._data[key] = value
        self._path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")


class RedisReputationCache:
    """Memorystore-backed cache: one key per title, with a native TTL as a freshness backstop.

    Network hiccups degrade gracefully to a miss (we just re-fetch) rather than failing the
    request — caching is an optimisation, never a hard dependency.
    """

    def __init__(self, url: str, ttl_days: int = 7, prefix: str = "gpve:rep:"):
        import redis  # lazy import so the file backend needs no redis dependency installed

        self._client = redis.Redis.from_url(
            url, socket_timeout=2, socket_connect_timeout=2, decode_responses=True
        )
        self._ttl_seconds = ttl_days * 86_400
        self._prefix = prefix

    def get(self, key: str) -> Optional[dict]:
        try:
            raw = self._client.get(self._prefix + key)
        except Exception:
            return None
        return json.loads(raw) if raw else None

    def set(self, key: str, value: dict) -> None:
        try:
            self._client.set(
                self._prefix + key,
                json.dumps(value, ensure_ascii=False),
                ex=self._ttl_seconds,
            )
        except Exception:
            pass  # best-effort; a failed write just means a future cache miss


def build_reputation_cache(redis_url: str, file_path: Path) -> ReputationCache:
    """Pick the backend: Memorystore if REDIS_URL is set, else the local JSON file."""
    if redis_url:
        return RedisReputationCache(redis_url)
    return FileReputationCache(file_path)
