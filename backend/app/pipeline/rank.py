"""Stage 5 — deterministic weighted synthesis of the three inputs (REQ-006, ADR-9).

final = w_vibe·vibe_similarity + w_metrics·metric_score + w_web·web_score

All three components are already in [0,1]; the weights (defaults 0.5 / 0.3 / 0.2, from
settings) are the only knob. The ranking is pure arithmetic in code — the LLM never orders
games — so results are explainable and reproducible."""
from __future__ import annotations

from app.pipeline.retrieve import Candidate


def final_score(c: Candidate, *, w_vibe: float, w_metrics: float, w_web: float) -> float:
    return w_vibe * c.vibe_similarity + w_metrics * c.metric_score + w_web * c.web_score


def rank(candidates: list[Candidate], *, w_vibe: float, w_metrics: float, w_web: float,
         top_k: int = 5) -> list[Candidate]:
    """Set final_score in place and return the top_k, highest first (id as a stable tiebreak)."""
    for c in candidates:
        c.final_score = final_score(c, w_vibe=w_vibe, w_metrics=w_metrics, w_web=w_web)
    return sorted(candidates, key=lambda c: (c.final_score, c.id), reverse=True)[:top_k]
