"""Stage 3 — deterministic metric re-scoring (REQ-006, ADR-9: ranking math lives in code).

Vector similarity (Stage 2) already captures *what a game is about* (genres/tags/theme are in
the embedding). This stage adds the orthogonal signals the embedding can't judge — quality,
popularity, and fit to the vibe's session-length / social constraints — into a metric_score
in [0, 1]. Grounded in the EDA:
  - rating is a *soft* quality prior, normalized within the observed 2.0–4.8 range;
  - popularity is log-scaled so blockbusters don't swamp the blend;
  - session fit uses playtime buckets (with partial credit for adjacent buckets);
  - completion_pct and ratio are NOT quality signals (EDA: r≈-0.02 vs rating) and are excluded.
Missing values are neutral, never imputed.
"""
from __future__ import annotations

import math

from app.pipeline.parse import VibeIntent
from app.pipeline.retrieve import Candidate

# Observed catalog bounds / references (EDA section 4 & 6).
_RATING_MIN, _RATING_MAX = 2.0, 4.8
_POP_LOG_REF = math.log10(500_000)  # ~max active players; log-scaled, clamped to [0,1]

# Sub-weights within metric_score (sum to 1.0). Quality leads; the rest are gentle nudges.
_W_QUALITY, _W_POPULARITY, _W_SESSION, _W_SOCIAL = 0.4, 0.2, 0.2, 0.2

_MULTIPLAYER_TAGS = {
    "multiplayer", "co-op", "online co-op", "online pvp", "pvp", "online multiplayer",
    "massively multiplayer", "local multiplayer", "local co-op", "split screen", "mmo",
}
_SOLO_TAGS = {"singleplayer", "single player"}
_SESSION_ORDER = ["short", "medium", "long"]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def quality_score(rating: float | None) -> float:
    """Rating normalized within the observed range; unknown -> neutral 0.5 (never imputed)."""
    if rating is None:
        return 0.5
    return _clamp((rating - _RATING_MIN) / (_RATING_MAX - _RATING_MIN))


def popularity_score(gamers: int | None) -> float:
    """Log-scaled active-player count, a *soft* prior. 0/unknown -> 0.0 (no boost, no penalty
    beyond that)."""
    if not gamers or gamers <= 0:
        return 0.0
    return _clamp(math.log10(gamers) / _POP_LOG_REF)


def _bucket(time_midpoint: float | None) -> str | None:
    if time_midpoint is None:
        return None
    if time_midpoint <= 6:
        return "short"
    if time_midpoint >= 30:
        return "long"
    return "medium"


def session_score(want: str, time_midpoint: float | None) -> float:
    """1.0 when the playtime bucket matches the requested length, partial credit for an
    adjacent bucket, 0.5 when length is unknown, 1.0 when the vibe is length-agnostic."""
    if want == "any":
        return 1.0
    bucket = _bucket(time_midpoint)
    if bucket is None:
        return 0.5
    distance = abs(_SESSION_ORDER.index(bucket) - _SESSION_ORDER.index(want))
    return {0: 1.0, 1: 0.6}.get(distance, 0.3)


def social_score(want: str, tags: list[str]) -> float:
    """Match the vibe's social preference against the game's tags; neutral when agnostic."""
    if want == "any":
        return 1.0
    lower = {t.lower() for t in tags}
    has_multi = bool(lower & _MULTIPLAYER_TAGS)
    has_solo = bool(lower & _SOLO_TAGS)
    if want == "multiplayer":
        return 1.0 if has_multi else 0.4
    # want == "solo"
    if has_solo:
        return 1.0
    return 0.4 if (has_multi and not has_solo) else 0.7  # multiplayer-only is a poor solo fit


def metric_score(candidate: Candidate, intent: VibeIntent) -> float:
    """Blend the sub-signals into a [0,1] metric component (the '2022 metrics' input to the
    final synthesis)."""
    return (
        _W_QUALITY * quality_score(candidate.rating)
        + _W_POPULARITY * popularity_score(candidate.gamers)
        + _W_SESSION * session_score(intent.session_length, candidate.time_midpoint)
        + _W_SOCIAL * social_score(intent.social, candidate.tags)
    )


def apply_metric_scores(candidates: list[Candidate], intent: VibeIntent) -> None:
    """Set candidate.metric_score in place."""
    for c in candidates:
        c.metric_score = metric_score(c, intent)
