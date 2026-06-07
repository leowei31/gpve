"""Unit tests for the CSV cleaner, written against the exact dirty rows in the real CSV.

Run from backend/:  python -m pytest -q
"""
from datetime import date
from pathlib import Path

import pytest

from ingest.clean import (
    clean_csv,
    normalize_title,
    parse_added,
    parse_float,
    parse_int_with_separators,
    parse_ratio,
    parse_time,
)

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "Gamepass_Games_v1.csv"


# --- GAMERS -------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [("84,143", 84143), ("213,257", 213257), ("777", 777), ("0", 0), ("", None), ("-", None)],
)
def test_parse_gamers(raw, expected):
    assert parse_int_with_separators(raw) == expected


# --- RATIO (the Shadowrun "-" rows must not crash) ----------------------
@pytest.mark.parametrize("raw,expected", [("1.87", 1.87), ("12.32", 12.32), ("-", None), ("", None)])
def test_parse_ratio(raw, expected):
    assert parse_ratio(raw) == expected


# --- RATING / COMP % (blanks stay null, real 0.0 preserved) -------------
@pytest.mark.parametrize("raw,expected", [("4.8", 4.8), ("2.0", 2.0), ("0.0", 0.0), ("", None)])
def test_parse_float(raw, expected):
    assert parse_float(raw) == expected


# --- TIME ---------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100-120 hours", (100.0, 120.0, 110.0)),
        ("80-100 hours", (80.0, 100.0, 90.0)),
        ("1000+ hours", (1000.0, None, 1000.0)),   # open upper bound
        ("0.5-1 hour", (0.5, 1.0, 0.75)),          # decimals
        ("0-0.5 hours", (0.0, 0.5, 0.25)),
        ("8-10 hours", (8.0, 10.0, 9.0)),
        ("", (None, None, None)),                  # 34 nulls — never imputed
        (None, (None, None, None)),
    ],
)
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


# --- ADDED (incl. the literal "Yesterday" in the Loot River row) --------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("06 Jan 22", date(2022, 1, 6)),
        ("15 Dec 20", date(2020, 12, 15)),
        ("Yesterday", None),  # relative date string -> null
        ("", None),
        (None, None),
    ],
)
def test_parse_added(raw, expected):
    assert parse_added(raw) == expected


# --- Title normalization / dedup keys -----------------------------------
def test_normalize_collapses_platform_variants():
    assert normalize_title("NBA 2K22 (Xbox One)") == normalize_title("NBA 2K22")
    assert normalize_title("The Evil Within (JP)") == normalize_title("The Evil Within")
    assert normalize_title("Dragon Ball FighterZ (Windows)") == normalize_title("Dragon Ball FighterZ")


def test_normalize_keeps_editions_distinct():
    # An edition collection is a different product from the base game; don't over-merge.
    assert normalize_title("Mass Effect Legendary Edition") != normalize_title("Mass Effect")


# --- End-to-end against the real CSV ------------------------------------
def test_clean_csv_real_file_runs_and_dedupes():
    games, report = clean_csv(CSV_PATH)
    assert report["raw_rows"] > 400
    assert report["duplicates_collapsed"] >= 2          # at least Fable Anniversary + DiRT Rally 2.0
    assert report["deduped_rows"] == len(games)
    assert all(g.title for g in games)                  # no empty titles survive

    by_title = {g.title: g for g in games}
    # Shadowrun rows have RATIO "-" and no rating — must be null, not a crash.
    if "Shadowrun Returns" in by_title:
        sr = by_title["Shadowrun Returns"]
        assert sr.ratio is None and sr.rating is None
    # Loot River's ADDED is the literal "Yesterday".
    if "Loot River" in by_title:
        assert by_title["Loot River"].added_date is None


def test_clean_csv_no_unexpected_exceptions_on_every_row():
    games, _ = clean_csv(CSV_PATH)
    for g in games:  # every numeric field is either None or the right type
        assert g.gamers is None or isinstance(g.gamers, int)
        assert g.ratio is None or isinstance(g.ratio, float)
        assert g.rating is None or isinstance(g.rating, float)
        assert g.time_midpoint is None or isinstance(g.time_midpoint, float)
