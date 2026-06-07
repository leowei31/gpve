"""Stage 6 — grounded per-game rationale (REQ-009).

One deterministic Gemini call (temperature 0, JSON schema) writes a short "why this fits your
vibe" for all final games at once. Every game's genres/tags/summary and its live web snippets
are passed in, and the model is instructed to ground claims in them and not invent facts — so
the rationale reflects the same evidence the ranking used. The LLM writes *language only*; it
does not change the ranking.

The exact prompt is reproduced in the README (prompt-engineering section)."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.clients.gemini import GeminiClient
from app.pipeline.retrieve import Candidate


class _Rationale(BaseModel):
    title: str
    rationale: str = Field(description="1-2 sentences on why this game fits the vibe, grounded in the facts given.")


class _RationaleSet(BaseModel):
    items: list[_Rationale]


_RATIONALE_PROMPT = """A player described the vibe they're after:
"{vibe}"

For each game below, write 1–2 sentences explaining why it fits that vibe. Ground every claim \
in the provided genres, tags, summary, and web reputation — do NOT invent facts, review scores, \
or details not present, and do NOT mention any game not in the list. Speak to the player \
directly and naturally. Return one entry per game, echoing its exact title.

Games (JSON):
{games}"""


def _brief(c: Candidate) -> dict:
    web = " ".join(s.get("content", "") for s in c.web_snippets).strip()
    return {
        "title": c.title,
        "genres": c.genres,
        "tags": c.tags[:12],
        "summary": (c.summary or "")[:400],
        "web_reputation": web[:400],
    }


def build_rationale_prompt(vibe: str, candidates: list[Candidate]) -> str:
    briefs = [_brief(c) for c in candidates]
    return _RATIONALE_PROMPT.format(vibe=vibe.strip(), games=json.dumps(briefs, ensure_ascii=False, indent=2))


def apply_rationales(client: GeminiClient, vibe: str, candidates: list[Candidate]) -> None:
    """Generate and attach a rationale to each candidate (in place). Best-effort: a failure
    leaves rationale as None rather than sinking the whole recommendation."""
    if not candidates:
        return
    try:
        result = client.generate_json(build_rationale_prompt(vibe, candidates), _RationaleSet)
        by_title = {item.title: item.rationale for item in result.items}
    except Exception:
        by_title = {}
    for c in candidates:
        c.rationale = by_title.get(c.title)
