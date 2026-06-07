"""Shared Gemini client for the request pipeline (query embedding + structured/text generation).

Distinct from ingest/embed.py (which embeds the *catalog* at build time): this is the
runtime client used per request to embed the user's vibe (RETRIEVAL_QUERY), parse the vibe
into structured intent (JSON), and write grounded rationales. All language calls default to
temperature 0 with thinking disabled, for the determinism story (see README)."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import numpy as np
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


def _normalize(values: list[float]) -> list[float]:
    a = np.asarray(values, dtype=np.float32)
    n = float(np.linalg.norm(a))
    return (a / n).tolist() if n > 0 else a.tolist()


def _is_transient(e: Exception) -> bool:
    """5xx is transient (e.g. 503 'high demand'); a 429 is transient *unless* it's billing."""
    if isinstance(e, genai_errors.ServerError):
        return True
    if isinstance(e, genai_errors.ClientError) and getattr(e, "code", None) == 429:
        return not any(w in str(e).lower() for w in ("credit", "billing", "prepay"))
    return False


def _retry(fn: Callable[[], R], *, tries: int = 5, base: float = 2.0) -> R:
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            if attempt == tries - 1 or not _is_transient(e):
                raise
            time.sleep(base * (2 ** attempt))  # 2s, 4s, 8s, 16s
    raise RuntimeError("unreachable")


class GeminiClient:
    def __init__(self, api_key: str, model: str, embedding_model: str, embedding_dim: int):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model
        self._dim = embedding_dim

    def embed_query(self, text: str) -> list[float]:
        """Embed the user's vibe with RETRIEVAL_QUERY (asymmetric to the catalog's
        RETRIEVAL_DOCUMENT) and L2-normalize to match the stored vectors."""
        r = _retry(lambda: self._client.models.embed_content(
            model=self._embedding_model,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=self._dim),
        ))
        return _normalize(r.embeddings[0].values)

    def generate_json(self, prompt: str, schema: type[T], *, temperature: float = 0.0) -> T:
        """Structured output: returns a validated instance of ``schema`` (a Pydantic model)."""
        resp = _retry(lambda: self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        ))
        if getattr(resp, "parsed", None) is not None:
            return resp.parsed  # SDK already validated into the schema
        return schema.model_validate_json(resp.text)  # fallback

    def generate_text(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        resp = _retry(lambda: self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        ))
        return (resp.text or "").strip()
