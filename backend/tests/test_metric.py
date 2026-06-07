"""Unit tests for the deterministic metric re-scorer (pure, no DB/LLM)."""
import math

import pytest

from app.pipeline.parse import VibeIntent
from app.pipeline.retrieve import Candidate
from app.pipeline.metric import (
    quality_score, popularity_score, session_score, social_score, metric_score,
)


def _cand(**kw) -> Candidate:
    base = dict(
        id=1, title="X", normalized_title="x", rating=4.0, gamers=50000, completion_pct=5.0,
        time_midpoint=10.0, genres=[], tags=[], summary=None, cover_url=None, released=None,
        metacritic=None, added_date=None, vibe_similarity=0.7,
    )
    base.update(kw)
    return Candidate(**base)


# --- quality ------------------------------------------------------------------

def test_quality_bounds_and_neutral():
    assert quality_score(2.0) == 0.0
    assert quality_score(4.8) == 1.0
    assert quality_score(None) == 0.5            # unknown is neutral, not imputed
    assert 0.0 < quality_score(3.4) < 1.0
    assert quality_score(5.0) == 1.0             # clamped


# --- popularity ---------------------------------------------------------------

def test_popularity_logscale_and_unknown():
    assert popularity_score(None) == 0.0
    assert popularity_score(0) == 0.0            # 0 players is real but a 0 prior
    assert popularity_score(500_000) == pytest.approx(1.0, abs=1e-6)
    assert popularity_score(100) < popularity_score(100_000)   # monotonic


# --- session ------------------------------------------------------------------

@pytest.mark.parametrize("want, mid, expected", [
    ("any", 999, 1.0),       # no constraint
    ("short", 3, 1.0),       # match
    ("long", 100, 1.0),      # match
    ("short", 15, 0.6),      # adjacent (medium vs short)
    ("short", 100, 0.3),     # far (long vs short)
    ("medium", None, 0.5),   # unknown length
])
def test_session_score(want, mid, expected):
    assert session_score(want, mid) == expected


# --- social -------------------------------------------------------------------

def test_social_score():
    assert social_score("any", []) == 1.0
    assert social_score("multiplayer", ["Co-op", "Online PvP"]) == 1.0
    assert social_score("multiplayer", ["Singleplayer"]) == 0.4
    assert social_score("solo", ["Singleplayer", "Story Rich"]) == 1.0
    assert social_score("solo", ["Multiplayer"]) == 0.4         # multiplayer-only, poor solo fit
    assert social_score("solo", ["Atmospheric"]) == 0.7         # unstated -> mild


# --- blend --------------------------------------------------------------------

def test_metric_score_in_unit_interval():
    intent = VibeIntent(search_query="q", session_length="short", social="solo")
    s = metric_score(_cand(rating=4.5, gamers=80000, time_midpoint=2.0, tags=["Singleplayer"]), intent)
    assert 0.0 <= s <= 1.0


def test_metric_prefers_matching_candidate():
    intent = VibeIntent(search_query="q", session_length="short", social="multiplayer")
    good = _cand(rating=4.5, gamers=200000, time_midpoint=2.0, tags=["Multiplayer", "Co-op"])
    poor = _cand(rating=2.5, gamers=200, time_midpoint=200.0, tags=["Singleplayer"])
    assert metric_score(good, intent) > metric_score(poor, intent)
