"""Unit tests for embedding-text composition + vector normalization (pure, no API calls)."""
import math

from ingest.embed import build_embedding_text, _normalize, _DESC_CHAR_CAP


def test_build_text_orders_and_labels_sections():
    text = build_embedding_text({
        "title": "Hades",
        "genres": ["Action", "RPG"],
        "tags": ["Atmospheric", "Story Rich"],
        "description": "A rogue-like dungeon crawler.",
    })
    assert text.splitlines()[0] == "Title: Hades"
    assert "Genres: Action, RPG" in text
    assert "Tags: Atmospheric, Story Rich" in text
    assert "rogue-like dungeon crawler" in text


def test_build_text_omits_empty_sections():
    text = build_embedding_text({"title": "Mystery Game", "genres": [], "tags": [], "description": ""})
    assert text == "Title: Mystery Game"
    assert "Genres:" not in text and "Tags:" not in text


def test_long_description_is_trimmed_with_ellipsis():
    text = build_embedding_text({"title": "X", "description": "word " * 1000})
    assert len(text) <= _DESC_CHAR_CAP + len("Title: X\n") + 2
    assert text.endswith("…")


def test_deterministic():
    g = {"title": "A", "genres": ["RPG"], "tags": ["Co-op"], "description": "desc"}
    assert build_embedding_text(g) == build_embedding_text(g)


def test_normalize_unit_length():
    v = _normalize([3.0, 4.0] + [0.0] * 766)
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-5)


def test_normalize_zero_vector_safe():
    v = _normalize([0.0] * 768)
    assert v == [0.0] * 768  # no divide-by-zero blowup
