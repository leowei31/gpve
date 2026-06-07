"""Stage 1 — parse the free-form vibe into structured intent (REQ-003).

A single deterministic Gemini call (temperature 0, JSON schema, thinking off) turns
"something eerie and lonely to play after work" into structured fields the rest of the
pipeline uses: a clean search phrase to embed (Stage 2) and constraints — session length,
social preference, mood/genre hints — that the deterministic metric re-scorer applies
(Stage 3). The LLM only *interprets language*; it never picks games or scores them.

The exact prompt lives here and is reproduced verbatim in the README (prompt-engineering /
determinism section)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.clients.gemini import GeminiClient


class VibeIntent(BaseModel):
    search_query: str = Field(description="Concise phrase (<=15 words) capturing genre + mood, for semantic search.")
    genres: list[str] = Field(default_factory=list, description="Plausible game genres implied by the vibe.")
    mood_tags: list[str] = Field(default_factory=list, description="Atmosphere/feel descriptors, e.g. atmospheric, cozy, intense.")
    session_length: Literal["short", "medium", "long", "any"] = "any"
    social: Literal["solo", "multiplayer", "any"] = "any"


_PARSE_PROMPT = """You convert a player's free-form "vibe" into structured search intent for a \
video-game recommender. Respond ONLY via the provided schema.

Guidelines:
- Infer only what the vibe implies. Never invent or name specific game titles.
- search_query: a concise phrase (<= 15 words) blending genre + mood for semantic matching.
- genres: plausible genres (e.g. RPG, Shooter, Puzzle, Racing, Platformer). Empty if unclear.
- mood_tags: atmosphere/feel words (e.g. atmospheric, cozy, intense, story-rich, relaxing).
- session_length: "short" for quick/after-work/casual, "long" for epic/deep/grindy, "medium",
  or "any" if the vibe says nothing about length.
- social: "solo" for single-player/alone, "multiplayer" for with-friends/competitive/co-op,
  or "any" if unstated.
- Be deterministic and literal — do not embellish.

Vibe: "{vibe}\""""


def build_parse_prompt(vibe: str) -> str:
    return _PARSE_PROMPT.format(vibe=vibe.strip())


def parse_vibe(client: GeminiClient, vibe: str) -> VibeIntent:
    return client.generate_json(build_parse_prompt(vibe), VibeIntent)
