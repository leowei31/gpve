"""Thin Tavily wrapper for live web-reputation lookups (REQ-004)."""
from __future__ import annotations

from tavily import TavilyClient as _Tavily


class TavilyClient:
    def __init__(self, api_key: str):
        self._client = _Tavily(api_key=api_key)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Return Tavily result dicts ({title, url, content, score, ...}); [] on any failure
        (web reputation is an enhancer, never a hard dependency of a recommendation)."""
        try:
            resp = self._client.search(query, max_results=max_results, search_depth="basic")
            return resp.get("results", [])
        except Exception:
            return []
