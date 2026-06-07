"""Unit tests for the pure row-building in ingest.load (no database needed)."""
from datetime import date

from ingest.clean import CleanedGame
from ingest.load import build_row, build_rows, _parse_date, _COLUMNS


def _game(**kw) -> CleanedGame:
    base = dict(
        title="Hades", normalized_title="hades", ratio=4.4, gamers=51530,
        completion_pct=1.0, time_min_hours=20.0, time_max_hours=40.0, time_midpoint=30.0,
        rating=4.4, added_date=date(2021, 8, 13), true_achievement=3000, game_score=1000,
        source_titles=["Hades"],
    )
    base.update(kw)
    return CleanedGame(**base)


def test_parse_date():
    assert _parse_date("2013-09-17") == date(2013, 9, 17)
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("Yesterday") is None       # not ISO -> None, never raises


def test_build_row_has_one_value_per_column():
    row = build_row(_game(), {"matched": True}, [0.0] * 768)
    assert len(row) == len(_COLUMNS)


def test_build_row_status_and_mapping():
    enrichment = {
        "title": "Hades", "matched": True, "rawg_id": 7, "genres": ["Action"],
        "tags": ["Atmospheric"], "description": "desc", "cover_image": "http://img",
        "released": "2020-09-17", "metacritic": 93,
    }
    row = dict(zip(_COLUMNS, build_row(_game(), enrichment, [0.1] * 768)))
    assert row["enrichment_status"] == "ok"
    assert row["rawg_id"] == 7
    assert row["summary"] == "desc" and row["cover_url"] == "http://img"
    assert row["released"] == date(2020, 9, 17)
    assert row["themes"] == []                      # RAWG has no distinct theme field
    assert row["enriched_text"].startswith("Title: Hades")
    assert row["embedding"] == [0.1] * 768


def test_status_miss_when_enriched_but_unmatched():
    row = dict(zip(_COLUMNS, build_row(_game(), {"matched": False}, None)))
    assert row["enrichment_status"] == "miss"
    assert row["embedding"] is None


def test_status_pending_when_no_enrichment():
    row = dict(zip(_COLUMNS, build_row(_game(), None, None)))
    assert row["enrichment_status"] == "pending"
    assert row["enriched_text"] is None
    assert row["genres"] == [] and row["tags"] == []   # null-safe defaults


def test_build_rows_joins_by_normalized_title():
    games = [_game(normalized_title="hades"), _game(title="Limbo", normalized_title="limbo")]
    rows = build_rows(games, {"hades": {"matched": True}}, {"limbo": [0.2] * 768})
    by_title = {r[0]: r for r in rows}
    assert dict(zip(_COLUMNS, by_title["Hades"]))["enrichment_status"] == "ok"
    assert dict(zip(_COLUMNS, by_title["Limbo"]))["embedding"] == [0.2] * 768
