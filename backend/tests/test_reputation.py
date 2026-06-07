"""Unit tests for the deterministic web-reputation synthesis (pure, no network)."""
from app.pipeline.reputation import synthesize_web_score, _NEUTRAL


def _result(title="", content=""):
    return {"title": title, "url": "http://x", "content": content}


def test_no_results_is_neutral():
    score, snippets = synthesize_web_score([])
    assert score == _NEUTRAL and snippets == []


def test_positive_terms_raise_score():
    results = [_result("Review", "An acclaimed masterpiece, beloved and highly rated.")]
    score, _ = synthesize_web_score(results)
    assert score > _NEUTRAL


def test_negative_terms_lower_score():
    results = [_result("Review", "A buggy, disappointing and mediocre experience.")]
    score, _ = synthesize_web_score(results)
    assert score < _NEUTRAL


def test_score_stays_in_unit_interval():
    gushing = [_result("", "acclaimed praised beloved masterpiece classic excellent brilliant "
                            "stellar fantastic must-play underrated gem award best")]
    panned = [_result("", "disappointing mixed mediocre buggy broken panned flawed overrated "
                          "boring worst terrible poor forgettable repetitive clunky")]
    assert 0.0 <= synthesize_web_score(gushing)[0] <= 1.0
    assert 0.0 <= synthesize_web_score(panned)[0] <= 1.0


def test_word_boundary_avoids_false_positives():
    # "best" must not match inside "bestiality"/"bestseller"; "gem" not inside "gemstone".
    score, _ = synthesize_web_score([_result("", "a gemstone bestseller management sim")])
    assert score == _NEUTRAL


def test_snippets_capped_at_three():
    results = [_result(f"t{i}", "content " * 50) for i in range(5)]
    _, snippets = synthesize_web_score(results)
    assert len(snippets) == 3
    assert all(len(s["content"]) <= 300 for s in snippets)
