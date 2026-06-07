"""Unit tests for the RAWG match logic — all pure, no network.

These pin the behaviour that gave us a verified 446/446 match: subtitle/edition tolerance,
diacritic folding, the forward-containment vs Jaccard blend, the tie-break, and the
year-suffix search fix. They guard the matcher against silent regressions.
"""
import pytest

from ingest.enrich import (
    match_score, _select_best, _match_tokens, _strip_year, _clean_tags,
    _MATCH_THRESHOLD,
)


# --- match_score --------------------------------------------------------------

@pytest.mark.parametrize("ours, candidate, expect_pass", [
    ("FIFA 21", "FIFA 21", True),                                              # exact
    ("DEEEER Simulator: Your Average Everyday Deer Game", "DEEEER Simulator", True),  # subtitle
    ("Spiritfarer: Farewell Edition", "Spiritfarer", True),                    # edition word dropped
    ("Brütal Legend", "Brutal Legend", True),                                  # diacritic fold
    ("Dragon Age II", "Dragon Age 2", True),                                   # numeral variant (0.667)
    ("Black Desert", "Black Desert Online", True),                            # suffix variant (0.667)
    ("Kameo: Elements of Power", "Elements: Soul of Fire", False),            # genuinely different game
    ("Hades", "Bastion", False),                                              # unrelated
])
def test_match_score_threshold(ours, candidate, expect_pass):
    assert (match_score(ours, candidate) >= _MATCH_THRESHOLD) is expect_pass


def test_exact_scores_one():
    assert match_score("Hades", "Hades") == 1.0


def test_forward_containment_beats_jaccard_for_subtitles():
    # Pure Jaccard would be 2/7 ≈ 0.29 (a miss); forward-containment lifts it to 1.0.
    assert match_score("DEEEER Simulator: Your Average Everyday Deer Game", "DEEEER Simulator") == 1.0


def test_sequel_is_not_over_matched():
    # 'eternal' is unaccounted for, so a bare-prefix query can't fully claim a sequel.
    assert match_score("Doom", "Doom Eternal") < 1.0


# --- tokenization -------------------------------------------------------------

def test_diacritics_folded():
    assert "brutal" in _match_tokens("Brütal Legend")


def test_stopwords_and_edition_words_dropped():
    toks = _match_tokens("The Witcher 3: Wild Hunt - Game of the Year Edition")
    assert "the" not in toks and "of" not in toks and "edition" not in toks
    assert {"witcher", "3", "wild", "hunt"} <= toks


# --- tie-break ----------------------------------------------------------------

def test_select_best_prefers_full_title_on_tie():
    results = [{"name": "Halo"}, {"name": "Halo Infinite"}, {"name": "Halo Wars"}]
    assert _select_best("Halo Infinite", results)["name"] == "Halo Infinite"


def test_select_best_picks_right_era_for_doom():
    # With the year kept as a scoring token, the 1993 original ('DOOM') beats the reboot.
    results = [{"name": "DOOM (2016)"}, {"name": "DOOM"}, {"name": "DOOM II"}]
    assert _select_best("DOOM (1993)", results)["name"] == "DOOM"


# --- year-suffix --------------------------------------------------------------

@pytest.mark.parametrize("title, expected", [
    ("DOOM (1993)", "DOOM"),
    ("GRID (2019)", "GRID"),
    ("It Takes Two", "It Takes Two"),   # no parenthetical year
    ("NBA 2K22", "NBA 2K22"),           # year-like token, not a (YYYY) suffix
])
def test_strip_year(title, expected):
    assert _strip_year(title) == expected


# --- tag cleaning -------------------------------------------------------------

def test_clean_tags_drops_noise_keeps_semantics_and_caps():
    raw = [
        {"name": "Singleplayer", "slug": "singleplayer", "language": "eng"},
        {"name": "Steam Achievements", "slug": "steam-achievements", "language": "eng"},   # steam- prefix
        {"name": "Steam Trading Cards", "slug": "steam-trading-cards-2", "language": "eng"},  # numbered dup
        {"name": "Full controller support", "slug": "full-controller-support", "language": "eng"},
        {"name": "Conquistas Steam", "slug": "conquistas-steam", "language": "eng"},        # mislabeled eng; -steam token
        {"name": "Steampunk", "slug": "steampunk", "language": "eng"},                      # KEEP (not a steam token)
        {"name": "Atmosphärisch", "slug": "atmospheric", "language": "ger"},                # non-eng dropped
        {"name": "Atmospheric", "slug": "atmospheric", "language": "eng"},
        {"name": "Atmospheric", "slug": "atmospheric", "language": "eng"},                  # dup
    ]
    tags = _clean_tags(raw)
    assert "Singleplayer" in tags and "Atmospheric" in tags
    assert "Steampunk" in tags                       # real tag survives the steam token rule
    assert "Steam Achievements" not in tags          # steam- prefix dropped
    assert "Steam Trading Cards" not in tags         # numbered slug (-2) still dropped
    assert "Full controller support" not in tags     # controller substring dropped
    assert "Conquistas Steam" not in tags            # '-steam' token dropped (even mislabeled eng)
    assert "Atmosphärisch" not in tags               # non-English dropped
    assert tags.count("Atmospheric") == 1            # de-duplicated
